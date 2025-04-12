import sqlite3
import argon2

from html import escape
from flask import request, jsonify, render_template, g, url_for, make_response, redirect
from rootsage import create_app, db, clf
from flask_login import LoginManager, login_user, login_required, current_user
from functools import wraps


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


# this is used for the dashboard sensor selector
with app.app_context():
    active_sensors = {}
    for row in db.get_active_sensors(conn()):
        active_sensors[row["name"]] = row
    default_sensor = active_sensors[next(iter(active_sensors))]


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

@app.route("/login/", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    else:
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


@app.route("/app/sensors/", methods=["GET"])
@login_required
def get_sensors():
    return render_template("sensors.html")


@app.route("/app/dashboard/", methods=["GET"])
@login_required
def dashboard():
    data = db.get_n_latest_df(conn(), default_sensor["name"], n=1)
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


@app.route("/update_dashboard/", methods=["GET"])
@login_required
def update_dashboard():
    current_sensor_name = request.args.get("current_sensor", default_sensor["name"])
    data = db.get_n_latest_df(conn(), current_sensor_name, n=1)
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
    rows = db.get_n_latest(conn(), n)
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
        is_active = int(data["is_active"])
    except(KeyError, ValueError):
        return jsonify({"error": "Invalid data format"}), 400
    
    try:
        db.add_sensor(conn(), name, desc, crop, is_active)
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
