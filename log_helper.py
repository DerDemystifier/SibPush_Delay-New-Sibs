from datetime import datetime
import os
from typing import Union


import logging

addon_path = os.path.dirname(os.path.realpath(__file__))

LOG_FILE = os.path.join(addon_path, "log.txt")
# Configure the logging setup
logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG, encoding="UTF-8")


def logThis(arg: Union[str, object], clear: bool = False):
    """Logs the given message to a log file.

    Args:
        arg (Union[str, object]): The message to log. If this is a function, it will be called and the return value will be logged.
        clear (bool, optional): If True, the log file will be cleared before the message is logged. Defaults to False.
    """
    from .config_parser import config_settings

    if config_settings["debug"]:
        message: str = arg() if callable(arg) else arg

        # Clear the log file if the 'clear' flag is set
        if clear:
            with open(LOG_FILE, "w", encoding="UTF-8"):
                pass  # This will clear the file

        # Log the message using Python's logging module
        logging.debug(message)


logThis(
    str(datetime.today())
    + """
# Legend for card details:
#   Type: 0=new, 1=learning, 2=due
#   Queue: same as above, and:
#       -1=suspended, -2=user buried, -3=sched buried
#   Due is used differently for different queues.
#       new queue: position
#       rev queue: integer day
#       lrn queue: integer timestamp
""",
    True,
)
