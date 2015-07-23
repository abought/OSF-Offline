from osfoffline.models import Base
from appdirs import user_data_dir
from osfoffline.settings import PROJECT_NAME,PROJECT_AUTHOR
import shutil
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import SingletonThreadPool


DB_DIR = user_data_dir(PROJECT_NAME, PROJECT_AUTHOR)
DB_FILE_PATH = os.path.join(DB_DIR, 'osf.db')
URL = 'sqlite:///{}'.format(DB_FILE_PATH)

Session = None


def setup_db(dir=None):
    if dir:
        global DB_DIR
        global DB_FILE_PATH
        global URL
        # todo: determine if we change db_dir, then do the other constants already get updated as we need them???
        DB_DIR = dir
        DB_FILE_PATH = os.path.join(DB_DIR, 'osf.db')
        # # sqlite+pysqlcipher://:passphrase/file_path
        #
        # #Unix/Mac - 4 initial slashes in total
        # engine = create_engine('sqlite:////absolute/path/to/foo.db')
        # #Windows
        # engine = create_engine('sqlite:///C:\\path\\to\\foo.db')
        # #Windows alternative using raw string
        # engine = create_engine(r'sqlite:///C:\path\to\foo.db')
        URL = 'sqlite+pysqlcipher://:PASSWORD/{DB_FILE_PATH}'.format(DB_FILE_PATH=DB_FILE_PATH)
        # URL = 'sqlite:///{}'.format(DB_FILE_PATH)

    create_models()
    create_session()


def remove_db():
    shutil.rmtree(DB_DIR)

def get_session():
    if Session:
        return Session()
    else:
        raise ValueError

def create_models():
    """ Create sql alchemy engine and models for all file systems.
    """
    if not os.path.isdir(DB_DIR):
        os.makedirs(DB_DIR)
    engine = create_engine(
        URL,
        poolclass=SingletonThreadPool,
        connect_args={'check_same_thread':False},
    )
    Base.metadata.create_all(engine)


def create_session():
    """
    this function sets up the Session global variable using the previously setup db.
    The Session object in this case uses the identity map pattern.
    There is a single Session map. Whenever we create a new session via get_session(),
    we are really just getting the currently stored session in that thread.
    Session object here refers to getting a db session from a map from identity map pattern ma
    :return:
    """

    # for this application, that should only lead to 2 connections in total
    engine = create_engine(URL, echo=False)
    session_factory = sessionmaker(bind=engine)

    # todo: figure out safer way to do this
    global Session
    Session = scoped_session(session_factory)


def save(session, item=None):
    if item:
        session.add(item)
    try:
        session.commit()
    except:
        session.rollback()
        raise
