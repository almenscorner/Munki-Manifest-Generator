import logging
import sys
import threading

from logging.handlers import RotatingFileHandler


class CustomFormatter(logging.Formatter):
    """Logging colored formatter, adapted from https://stackoverflow.com/a/56944256/3638629"""

    grey = "\x1b[38;5;244m"
    cyan = "\x1b[36m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;9m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    def __init__(self, fmt, error_fmt):
        super().__init__()
        self.fmt = fmt
        self.error_fmt = error_fmt
        self.FORMATS = {
            logging.DEBUG: self.error_fmt,
            logging.INFO: self.fmt,
            logging.WARNING: self.error_fmt,
            logging.ERROR: self.error_fmt,
            logging.CRITICAL: self.error_fmt,
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class CustomLogger(logging.Logger):
    """Custom logger class with multiple destinations"""

    def __init__(self, name, log_file=None):
        super().__init__(name)
        self.lock = threading.Lock()  # create a lock object
        handler = logging.StreamHandler(sys.stdout)
        info_fmt = "%(asctime)s [%(levelname)s] %(message)s"
        error_fmt = "%(asctime)s [%(levelname)s] %(message)s (%(filename)s:%(lineno)d:%(funcName)s)"
        handler.setFormatter(CustomFormatter(fmt=info_fmt, error_fmt=error_fmt))
        handler.setLevel(logging.INFO)
        self.addHandler(handler)
        if log_file:
            file_handler = RotatingFileHandler(
                log_file, mode="a", maxBytes=5 * 1024 * 1024, backupCount=2, encoding=None, delay=0
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(CustomFormatter(fmt=info_fmt, error_fmt=error_fmt))
            self.addHandler(file_handler)
        self.handler = handler

    def handle(self, record):
        with self.lock:  # acquire the lock
            super().handle(record)
            self.handler.flush()


logger = CustomLogger(__name__, log_file="mmg.log")
