import queue
import enum
import logging

from osfoffline.utils import Singleton


logger = logging.getLogger(__name__)


class SyncStatus(enum.Enum):
    """Recognized values of sync status, mapped to corresponding system tray icons"""
    NORMAL = ':/tray_icon_color.png'
    PAUSE = ':/tray_icon_pause.png'
    SYNC = ':/tray_icon_sync.png'
    ERROR = ':/tray_icon_stop.png'


class Notification(metaclass=Singleton):

    class Type(enum.Enum):
        INFO = 0,
        WARNING = 1,
        ERROR = 2

    class Event:

        def __init__(self, type, msg):
            self.type = type
            self.msg = msg

    def __init__(self):
        self.queue = queue.Queue()

        # Define event handlers used for notifications
        noop = lambda x: None
        self.cb = noop
        self.status_cb = noop

    def set_callback(self, cb):
        self.cb = cb

    def info(self, msg):
        event = self.Event(self.Type.INFO, msg)
        logger.info('Notification: {}'.format(event))
        self.cb(event)

    def warn(self, msg):
        event = self.Event(self.Type.WARNING, msg)
        logger.warn('Notification: {}'.format(event))
        self.cb(event)

    def error(self, msg):
        event = self.Event(self.Type.ERROR, msg)
        logger.error('Notification: {}'.format(event))
        self.cb(event)

    def set_status_callback(self, cb):
        """Define the callback that fires when the sync operation state is changed"""
        self.status_cb = cb

    def sync_status(self, enum_choice):
        """Communicate the status of the sync operation. Used to change progress indicators such as tray icon"""
        self.status_cb(enum_choice)
