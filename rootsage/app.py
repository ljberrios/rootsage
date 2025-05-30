import sqlite3
import argon2
import pandas as pd
import numpy as np

from html import escape
from flask import request, jsonify, render_template, g, url_for, make_response, redirect, send_from_directory
from rootsage import create_app, db, clf
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from datetime import datetime, timezone


app = create_app("config.DevelopmentConfig")
hasher = argon2.PasswordHasher()
login_manager = LoginManager()

login_manager.init_app(app)


def conn():
    """
    Create a new database connection for each request.
    """

    if "conn" not in g:
        g.conn = sqlite3.connect(app.config["DB_NAME"])
        g.conn.row_factory = sqlite3.Row
        # create tables if needed. this is fine here as it is idempotent
        db.create_tables(g.conn)
    return g.conn


@app.teardown_appcontext
def teardown_db_conn(exception):
    """
    Close the database connection after each request.
    """
    conn = g.pop("conn", None)

    if conn is not None:
        conn.close()


with app.app_context():
    # this is used for the dashboard sensor selector
    active_sensors = {}
    for row in db.get_active_sensors(conn()):
        active_sensors[row["name"]] = row
    default_sensor = active_sensors[next(iter(active_sensors))]

    # load crops from config.json (if any)
    for crop in app.config["CROPS"]:
        db.add_crop(conn(), crop)


def check_is_admin():
    if (current_user.username not in app.config["ADMINS"]):
        return redirect(url_for("dashboard"))


def get_current_nutrient_levels(data):
    return {
        "n": data.N.iat[0],
        "p": data.P.iat[0],
        "k": data.K.iat[0] 
    }


@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for("login"))


@login_manager.user_loader
def load_user(user_id):
    if user_id is not None:
        return db.get_user(conn(), user_id)
    return None


@app.route("/app/login/", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html")

    data = request.form
    username = data["user"]
    password = data["pass"]

    user = db.get_user_by_name(conn(), username)
    if user is None:
        return """
            <div class="alert alert-danger w-100" role="alert">
                Invalid username or password
            </div>
        """

    try:
        hasher.verify(user.phash, password)

        if hasher.check_needs_rehash(user.phash):
            user.phash = hasher.hash(password)
            db.update_user(conn(), user.phash)

        login_user(user)

        user.last_login = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db.update_user(conn(), user)

        app.logger.info(f"Logged in user '{username}'")

        response = make_response()
        response.headers["HX-Redirect"] = url_for("dashboard")
        return response
    except argon2.exceptions.VerifyMismatchError:
        return """
            <div class="alert alert-danger w-100" role="alert">
                Invalid username or password
            </div>
        """
    

@app.route("/app/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/app/sensors/", methods=["GET", "POST"])
@login_required
def sensors():
    check_is_admin()

    if (request.method == "GET"):
        return render_template("sensors.html", crops=db.get_all_crops(conn()))
    else:
        data = request.form
        name = data["name"]
        desc = data["desc"]
        crop = int(data["crop"])
        status = escape(str(data["status"]))

        sensor = db.get_sensor(conn(), name)
        if sensor is not None:
            return """
                <div class="alert alert-danger w-100" role="alert">
                    Sensor already exists
                </div>
            """
        
        db.add_sensor(conn(), name, desc, crop, status)
        return """
            <div class="alert alert-success w-100" role="alert">
                Sensor registered successfully
            </div>
        """


@app.route("/app/sensors/search/", methods=["POST"])
@login_required
def search_sensors():
    check_is_admin()

    search = request.form["search"]
    if (search is None or search == ""):
        sensors = db.get_all_sensors(conn())
    else:
        sensors = db.search_sensors(conn(), search)
    return render_template("sensors-table.html", sensors=sensors)


@app.route("/app/reports/", methods=["GET", "POST"])
@login_required
def reports():
    if request.method == "GET":
        sensors = [sensor["name"] for sensor in db.get_all_sensors(conn())]
        crops = [crop["name"] for crop in db.get_all_crops(conn())]
        return render_template("reports.html", sensors=sensors, crops=crops)
    else:
        data = request.form
        start_date = data["start_date"]
        end_date = data["end_date"]
        sensor = data["sensor-selector"]
        crop = data["crop-selector"]

        df = db.get_npk_data_df(conn(), start_date, end_date, sensor, crop)
        
        def classify_row(row):
            result = clf.classify(row.to_frame().T)
            return pd.Series({
                "clf_N": result["clf_N"],
                "clf_P": result["clf_P"],
                "clf_K": result["clf_K"]
            })

        df[["clf_N", "clf_P", "clf_K"]] = df.apply(classify_row, axis=1)
        df = df.drop(columns=["label"])
        
        stats = df[["N", "P", "K"]].describe()

        mean_N, mean_P, mean_K = stats.loc["mean", ["N", "P", "K"]]

        stats.loc["N:P ratio"] = [mean_N / mean_P if mean_P else np.nan, np.nan, np.nan]
        stats.loc["N:K ratio"] = [mean_N / mean_K if mean_K else np.nan, np.nan, np.nan]
        stats.loc["P:K ratio"] = [np.nan, mean_P / mean_K if mean_K else np.nan, np.nan]

        with pd.ExcelWriter("report.xlsx") as writer:
            df.to_excel(writer, sheet_name="Data", index=False)
            stats.to_excel(writer, sheet_name="Stats")
        return send_from_directory(
                "../", "report.xlsx", 
                as_attachment=True, 
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


@app.route("/app/users/", methods=["GET", "POST"])
@login_required
def users():
    check_is_admin()

    if (request.method == "GET"):   
        return render_template("users.html")
    else:
        data = request.form
        username = data["user"]
        password = data["pass"]
        confirm = data["confirm-pass"]

        user = db.get_user_by_name(conn(), username)
        if user is not None:
            return """
                <div class="alert alert-danger w-100" role="alert">
                    Username is taken
                </div>
            """
        
        if (password != confirm):
            return """
                <div class="alert alert-danger w-100" role="alert">
                    Passwords do not match
                </div>
            """
        
        db.add_user(conn(), username, hasher.hash(password))
        return """
            <div class="alert alert-success w-100" role="alert">   
                User registered successfully
            </div> 
        """


@app.route("/app/users/search/", methods=["POST"])
@login_required
def search_users():
    check_is_admin()

    search = request.form["search"]
    if (search is None or search == ""):
        users = db.get_all_users(conn())
    else:
        users = db.search_users(conn(), search)

    return render_template("users-table.html", users=users)

@app.route("/app/users/delete/", methods=["DELETE"])
@login_required
def delete_user():
    check_is_admin()

    user_id = request.args["user_id"]

    if (user_id is None):
        return """
            <div class="alert alert-danger w-100" role="alert">
                User ID is null?
            </div>
        """
    
    if (user_id == current_user.id):
        return """
            <div class="alert alert-danger w-100" role="alert">
                Cannot delete yourself
            </div>
        """

    db.delete_user(conn(), user_id)
    return """
        <div class="alert alert-success w-100" role="alert">   
            User deleted successfully
        </div> 
    """


@app.route("/app/dashboard/", methods=["GET"])
@login_required
def dashboard():
    data = db.get_latest_npk_data_df(conn(), default_sensor["name"], n=1)
    nutrient_levels = get_current_nutrient_levels(data)
    classifications = clf.classify(data)
    return render_template(
        "dashboard.html",
        username = current_user.username,
        sensors=active_sensors.keys(),
        current_sensor=default_sensor,
        crop=data.crop_name.iat[0],
        **nutrient_levels,
        **classifications
    )


@app.route("/app/dashboard/update/", methods=["GET"])
@login_required
def update_dashboard():
    current_sensor_name = request.args.get("current_sensor", default_sensor["name"])
    data = db.get_latest_npk_data_df(conn(), current_sensor_name, n=1)
    nutrient_levels = get_current_nutrient_levels(data)
    classifications = clf.classify(data)
    return render_template(
        "dashboard-metrics.html",
        current_sensor=active_sensors[current_sensor_name],
        crop=data.crop_name.iat[0],
        **nutrient_levels,
        **classifications)


def require_api_key(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if request.headers.get('X-API-KEY') != app.config["API_KEY"]:
            return jsonify({"error": "Unauthorized"}), 401
        return view_function(*args, **kwargs)
    return decorated_function


@app.route("/api/crops/", methods=["POST"])
@require_api_key
def add_crop():
    """
    Add a crop to the database.

    :return: success response or error if
             there is any missing data or
             invalid format
    """

    if not request.is_json:
        return jsonify({"error": "Must be a JSON request"}), 400
    
    try:
        data = request.get_json()
        name = escape(str(data["name"]))
    except (KeyError, ValueError):
        return jsonify({"error": "Invalid data format"}), 400
    
    try:
        db.add_crop(conn(), name)
    except sqlite3.IntegrityError:
        return jsonify({"error": "Crop already exists"}), 409
    
    return jsonify({"message": "Crop stored successfully", "data": data}), 201


@app.route("/api/data/", methods=["POST"])
@require_api_key
def add_npk_data():
    """
    Add nutrient data to the database.

    :return: success response or error if
             there is any missing data or
             invalid format

    """

    if not request.is_json:
        return jsonify({"error": "Must be a JSON request"}), 400

    try:
        data = request.get_json()
        n = float(data["n"])
        p = float(data["p"])
        k = float(data["k"])
        sensor_id = int(data["sensor_id"])
    except (KeyError, ValueError):
        return jsonify({"error": "Invalid data format"}), 400

    db.add_npk_data(conn(), n, p, k, sensor_id)

    return jsonify({"message": "Data stored successfully", "data": data}), 201


@app.route("/api/data/", methods=["GET"])
@require_api_key
def get_latest_data():
    """
    Get the latest N rows of sensor data from the database.

    :return: the data
    """

    n = request.args.get("n", default=10, type=int)
    rows = db.get_latest_npk_data(conn(), n)
    data = [dict(row) for row in rows]
    return jsonify(data)


@app.route("/api/sensors/", methods=["POST"])
@require_api_key
def add_sensor():
    """
    Add a sensor to the database.

    :return: success response or error if
             there is any missing data or
             invalid format

    """

    if not request.is_json:
        return jsonify({"error": "Must be a JSON request"}), 400
    
    try:
        data = request.get_json()
        name = escape(str(data["name"]))
        desc = escape(str(data["desc"]))
        crop = int(data["crop"])
        status = int(data["status"])
    except(KeyError, ValueError):
        return jsonify({"error": "Invalid data format"}), 400
    
    try:
        db.add_sensor(conn(), name, desc, crop, status)
    except sqlite3.IntegrityError:
        return jsonify({"error": "Sensor already exists"}), 409

    return jsonify({"message": "Sensor registered successfully", "data": data}), 201


@app.route("/favicon.ico/")
def favicon():
    """
    No favicon provided.
    """
    return "", 200


@app.errorhandler(Exception)
def handle_exception(e):
    """
    Catch-all exception handler for unhandled exceptions.

    :param e: the unhandled exception
    :return: the error response
    """

    app.logger.error(f"Unhandled Exception: {str(e)}", exc_info=True)

    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(debug=True)
