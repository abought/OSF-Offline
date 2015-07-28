from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from osfoffline.database_manager.models import User
from contextlib import contextmanager
from osfoffline.database_manager.db import DB
def save(session, item=None):
    if item:
        session.add(item)
    try:
        session.commit()
    except:
        session.rollback()
        raise


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = DB.get_session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

# def close_session_safe(session):
#     try:
#         session.close()
#     except:


# def get_current_user(self, session):
#     user = None
#     import threading
#     print('---inside getcurrentuser-----{}----'.format(threading.current_thread()))
#     err = False
#     try:
#         user = session.query(User).filter(User.logged_in).one()
#     except MultipleResultsFound:
#         # log out all users and restart login screen to get a single user to log in
#         print('logging out all users.')
#         for user in session.query(User):
#             user.logged_in = False
#             save(session, user)
#         err = True
#         session.close()
#     except NoResultFound:
#         err = True
#         print('no users are logged in currently. Logging in first user in db.')
#         session.close()
#
#     if err:
#         self.login_action.trigger()
#     else:
#         return user