from datetime import datetime
import os
from typing import Union
import logging

addon_path = os.path.dirname(os.path.realpath(__file__))

LOG_FILE_path = os.path.join(addon_path, "log.txt")

# Create a named logger for the add-on
logger = logging.getLogger("SibPush_Delay")
logger.setLevel(logging.DEBUG)
logger.propagate = False

# Add a file handler if it doesn't have one yet
if not logger.handlers:
    file_handler = logging.FileHandler(LOG_FILE_path, encoding="UTF-8")
    formatter = logging.Formatter("%(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def _clear_log_file() -> None:
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and handler.stream is not None:
            handler.acquire()
            try:
                handler.flush()
                handler.stream.seek(0)
                handler.stream.truncate(0)
            finally:
                handler.release()
            return

    with open(LOG_FILE_path, "w", encoding="UTF-8"):
        pass


def logThis(arg: Union[str, object], clear: bool = False):
    """Logs the given message to a log file.

    Args:
        arg (Union[str, object]): The message to log. If this is a function, it will be called and the return value will be logged.
        clear (bool, optional): If True, the log file will be cleared before the message is logged. Defaults to False.
    """
    from .config_parser import config_settings

    if config_settings["debug"]:
        message: str = str(arg() if callable(arg) else arg)

        # Clear the log file if the 'clear' flag is set
        if clear:
            _clear_log_file()

        # Log the message using our named logger
        logger.debug(message)


def initialize_log_file():
    """Initializes the log file by writing the current date and time to it."""
    logThis(
        str(datetime.today())
        + """
# Legend for card details:
#   Type: 0=new, 1=learning, 2=due
#   Queue: same as above, plus: -1=suspended, -2=user buried, -3=sched buried
#   Due is used differently for different queues.
#       new queue: position
#       rev queue: integer day
#       lrn queue: integer timestamp
""",
        True,
    )
