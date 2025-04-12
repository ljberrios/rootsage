import logging


class Config(object):
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True
    DB_NAME = "rootsage/app.db"
    LOGS_DIR = "rootsage/logs/"
    LOG_LEVEL = logging.DEBUG


class TestingConfig(Config):
    TESTING = True
    DB_NAME = ":memory:"
    LOG_LEVEL = logging.WARNING
