import logging
import os
import json
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from flask import Flask


def create_app(config):
    """
    Flask application factory.

    :param config: the config class
    :return: the Flask app object
    """

    # Load environment before creating app
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(dotenv_path)
    
    app = Flask(__name__)

    # init config
    app.config.from_object(config)
    app.config.from_prefixed_env(prefix="ROOTSAGE")
    app.config.from_file("config.json", silent=True, load=json.load)

    # init logging
    log_level = app.config["LOG_LEVEL"]
    if "LOGS_DIR" in app.config:
        setup_file_logs(app, log_level)

    # init sessions
    app.secret_key = app.config["SECRET_KEY"]

    app.logger.info("Starting rootsage")
    return app


def setup_file_logs(app, level=logging.INFO):
    """
    Sets up logging using a file handler.

    :param app: the Flask app object
    :param level: the logger's default level
    """

    logs_dir = app.config["LOGS_DIR"]
    os.makedirs(logs_dir, exist_ok=True)

    handler = RotatingFileHandler(
        os.path.join(logs_dir, "app.log"),
        maxBytes=1024 * 1024 * 100,  # 100 MB,
        backupCount=5,
        encoding="utf-8",
    )

    fmt = "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    formatter = logging.Formatter(fmt)
    formatter.datefmt = "%Y-%m-%d %H:%M:%S"
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.setLevel(level)
