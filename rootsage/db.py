import sqlite3

from flask import current_app
from pandas import read_sql_query
from flask_login import UserMixin


"""
This schema below is very simple and doesn't account for
other types of measurements and details. Nonetheless it can be used as a
starting point to aid the decision making process of growers. Later on,
more types of measurements can be added, support for crop rotation, and more.
"""


def create_tables(conn):
    """
    Create tables if they don't exist already.

    :param conn: the database connection
    """

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    desc TEXT,
                    crop INTEGER NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (crop) REFERENCES crops (id)
                );               
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS npk_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    n NUMERIC NOT NULL DEFAULT 0,
                    p NUMERIC NOT NULL DEFAULT 0,
                    k NUMERIC NOT NULL DEFAULT 0,
                    sensor_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sensor_id) REFERENCES sensors (id)
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(15) NOT NULL UNIQUE,
                    phash TEXT NOT NULL         
                );
            """)
    except sqlite3.Error:
        current_app.logger.exception("Error initializing database")


def add_crop(conn, name):
    """
    Add a crop to the database.

    :param conn: the database connection
    :param name: the crop's name
    """

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO crops (id) VALUES (?);", (name,))
            current_app.logger.info(f"Inserted crop '{name}'")
    except sqlite3.Error:
        current_app.logger.exception("Error inserting crop")
        raise # catch integrity error


def get_crops(conn):
    """
    Get all crops from the crops table.

    :param conn: the database connection
    """  

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM crops;")
            rows = cursor.fetchall()
            current_app.logger.info(f"Fetched all crops: {len(rows)} row(s)")
            return rows
    except sqlite3.Error:
        current_app.logger.exception("Error fetching crops")


def add_npk_data(conn, n, p, k, sensor_id):
    """
    Add sensor nutrient data to the database.

    :param conn: the database connection
    :param n: nitrogen concentration
    :param p: phosphorus concentration
    :param k: potassium concentration
    :param sensor_id: the id of the sensor that generated the data
    """

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO npk_data (n, p, k, sensor_id) 
                    VALUES (?, ?, ?, ?);
            """, (n, p, k, sensor_id))
            current_app.logger.info(f"Inserted nutrient data of sensor '{sensor_id}'")
    except sqlite3.Error:
        current_app.logger.exception("Error inserting nutrient data")


def get_n_latest(conn, n=10):
    """
    Get the latest N rows from the nutrients data table.

    :param conn: the database connection
    :param n: an integer higher than zero
    """

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM npk_data
                    ORDER BY created_at DESC
                    LIMIT ?;
            """, (n,))
            rows = cursor.fetchall()
            current_app.logger.info(f"Fetched nutrient data: {len(rows)} row(s)")
            return rows
    except sqlite3.Error:
        current_app.logger.exception("Error getting nutrient data")


def get_n_latest_df(conn, sensor_name, n=10):
    """
    Get the latest N rows from the nutrient data table,
    along with the crop associated with the sensor that
    gathered the data. This data is meant to be input to
    trained ML models for classification.

    :param conn: the database connection
    :param n: an integer higher than zero
    """

    try:
        with conn:
            """
            some details here:
             1. the column names for the nutrients need to come in uppercase
             2. the crop IDs need to be decremented by 1

            explanation:
             1. the ML models were simply trained with uppercase column names
                so they won't classify unless that's the case
             2. the ML models can't take strings so the crop names were
                mapped to their respective index during training... since
                IDs start at 1 in the DB we just decrement by 1
            """

            return read_sql_query("""
                SELECT 
                    npk.n as N,
                    npk.p as P,
                    npk.k as K,
                    npk.created_at,
                    s.crop - 1 as label,
                    c.name as crop_name
                FROM npk_data npk
                JOIN sensors s ON npk.sensor_id = s.id
                JOIN crops c ON s.crop = c.id
                WHERE s.name = ?
                ORDER BY npk.created_at DESC
                LIMIT ?;
            """, conn, params=(sensor_name, n))
    except sqlite3.Error:
        current_app.logger.exception("Error getting nutrient data")


def add_sensor(conn, name, desc=None, label=None, is_active=1):
    """
    Add a sensor to the database.

    :param conn: the database connection
    :param name: the sensor's name
    :param desc: the sensor's purpose
    :param crop: the crop
    :param is_active: 1 if the sensor is active, 0 otherwise
    """

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sensors (name, desc, crop, is_active)
                    VALUES (?, ?, ?, ?);
            """, (name, desc, label, is_active))
            current_app.logger.info(f"Inserted sensor '{name}'")
    except sqlite3.Error:
        current_app.logger.exception("Error inserting sensor")
        raise # catch integrity error


def get_sensor(conn, id=None, name=None):
    """
    Get the data for a given sensor.

    :param conn: the database connection
    :param name: the sensor's name
    """

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sensors WHERE id=? OR name=?;", (id, name))
            row = cursor.fetchone()
            if row is not None:
                current_app.logger.info(f"Fetched data for sensor: id={id}, name={name}")
            else:
                current_app.logger.info(f"Could not find sensor data: id={id}, name={name}")
            return row 
    except sqlite3.Error:
        current_app.logger.exception("Error getting sensor data")


def get_active_sensors(conn):
    """
    Get all active sensors from the database.

    :param conn: the database connection
    """

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sensors WHERE is_active=1;")
            rows = cursor.fetchall()
            if len(rows) > 0:
                current_app.logger.info("Fetched data for all active sensors")
            else:
                current_app.logger.info("Could not find any active sensors")
            return rows
    except sqlite3.Error:
        current_app.logger.exception("Error getting sensor data")


class User(UserMixin):
    def __init__(self, user_id, username, phash):
        """
        :param user_id: the user's internal id (optional)
        :param username: the user's username
        :param phash: the password hash
        """
        self.id = str(user_id)
        self.username = username
        self.phash = phash


def add_user(conn, user):
    """
    Add a user to the database.

    :param conn: the database connection
    :param user: the user to add
    """

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
               INSERT INTO users (username, phash)
                    VALUES (?, ?);            
            """, (user.username, user.phash))
            current_app.logger.info(f"Inserted user '{user.username}'")
    except sqlite3.Error:
        current_app.logger.exception("Error adding user")


def get_user(conn, user_id):
    """
    Get a user's data.

    :param conn: the database connection
    :param user_id: the user's internal id
    """

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
            """SELECT id, username, phash 
                    FROM users WHERE id=?;
            """, (user_id,))
            row = cursor.fetchone()
            if row is not None:
                current_app.logger.info(f"Fetched data for user with id '{user_id}'")
                return User(*row)
            else:
                current_app.logger.info(f"Could not find data for user with id '{user_id}'")
                return row
    except sqlite3.Error:
        current_app.logger.exception("Error getting user")


def get_user_by_name(conn, username):
    """
    Get a user's data.

    :param conn: the database connection
    :param username: the user's username
    """

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
            """SELECT id, username, phash 
                    FROM users WHERE username=?;
            """, (username,))
            row = cursor.fetchone()
            if row is not None:
                current_app.logger.info(f"Fetched data for user '{username}'")
                return User(*row)
            else:
                current_app.logger.info(f"Could not find data for user '{username}'")
                return row
    except sqlite3.Error:
        current_app.logger.exception("Error getting user")


def update_user(conn, user):
    """
    Update a user's data.

    :param conn: the database connection
    :param user: the new user data
    """

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET username=?
                    phash=?
                WHERE id=?;
            """, (user.phash, user.username, int(user.id)))
    except sqlite3.Error:
        current_app.logger.exception("Error updating user")


