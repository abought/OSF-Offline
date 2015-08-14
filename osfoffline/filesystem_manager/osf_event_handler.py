"""
This is the most important file in the system. OSFEventHandler is responsible for updating the models,
storing the data into the db, and then sending a request to the remote server.
"""
import asyncio

from watchdog.events import FileSystemEventHandler, DirModifiedEvent
import logging
from osfoffline.database_manager.models import Node, File,User
from osfoffline.database_manager.db import session
from osfoffline.database_manager.utils import save, session_scope
from osfoffline.utils.path import ProperPath
from osfoffline.exceptions.event_handler_exceptions import MovedNodeUnderFile
from osfoffline.exceptions.item_exceptions import ItemNotInDB
import osfoffline.alerts as AlertHandler

EVENT_TYPE_MOVED = 'moved'
EVENT_TYPE_DELETED = 'deleted'
EVENT_TYPE_CREATED = 'created'
EVENT_TYPE_MODIFIED = 'modified'


class OSFEventHandler(FileSystemEventHandler):
    """
    Base file system event handler that you can override methods from.
    """
    def __init__(self, osf_folder, loop):
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self.osf_folder = ProperPath(osf_folder, True)
        self.user = session.query(User).filter(User.logged_in).one()



    @asyncio.coroutine
    def on_any_event(self, event):
        pass

    @asyncio.coroutine
    def on_moved(self, event):
        """Called when a file or a directory is moved or renamed.

        :param event:
            Event representing file/directory movement.
        :type event:
            :class:`DirMovedEvent` or :class:`FileMovedEvent`
        """
        src_path = ProperPath(event.src_path, event.is_directory)
        dest_path = ProperPath(event.dest_path, event.is_directory)


        # determine and get what moved
        item = self._get_item_by_path(src_path)


        if isinstance(item, Node):
            if src_path.name != dest_path.name:
               pass
            elif src_path.full_path != dest_path.full_path:
                AlertHandler.warn('Cannot move projects and components. {} will stop syncing'.format(item.title))
            return

        # File

        # rename
        if item.name != dest_path.name:
            item.name = dest_path.name
            item.locally_renamed = True
            save(session, item)
            logging.info("renamed a file")
        # move
        elif src_path != dest_path:

            # check if file already exists in this moved location. If so, delete it from db.
            try:
                item_to_replace = self._get_item_by_path(dest_path)
                session.delete(item_to_replace)
                save(session)
            except ItemNotInDB:
                logging.info('file does not already exist in moved destination')


            new_parent = self._get_parent_item_from_path(dest_path)


            # move item
            if isinstance(new_parent, Node):
                item.parent = None
                item.node = new_parent.node
            elif isinstance(new_parent, File):
                item.previous_provider = item.provider
                item.previous_node_osf_id = item.node.osf_id

                item.parent = new_parent
                item.node = new_parent.node
                item.provider = new_parent.provider

                item.locally_moved = True

            # save(session, dummy)
            save(session, item)
            logging.info('moved from {} to {}'.format(src_path.name, dest_path.name))


    @asyncio.coroutine
    def on_created(self, event):
        """Called when a file or directory is created.

        :param event:
            Event representing file/directory creation.
        :type event:
            :class:`DirCreatedEvent` or :class:`FileCreatedEvent`
        """
        src_path = ProperPath(event.src_path, event.is_directory)


        # create new model
        if self._already_exists(src_path):
            return


        # assert: whats being created is a file folder

        containing_item = self._get_parent_item_from_path(src_path)

        if isinstance(containing_item, Node):
            node = containing_item
        else: # file
            node = containing_item.node
        new_item = File(
            name=src_path.name,
            type=File.FOLDER if event.is_directory else File.FILE,
            user=self.user,
            locally_created=True,
            provider=File.DEFAULT_PROVIDER,
            node=node
        )
        containing_item.files.append(new_item)
        if new_item.is_file:
            try:
                new_item.update_hash()
            except FileNotFoundError:
                # if file doesnt exist just as we create it, then file is likely temp file. thus don't put it in db.
                return
        save(session, new_item)
        save(session, containing_item)
        logging.info("created new {}".format('folder' if event.is_directory else 'file'))

    @asyncio.coroutine
    def on_modified(self, event):
        """Called when a file or directory is modified.

        :param event:
            Event representing file/directory modification.
        :type event:
            :class:`DirModifiedEvent` or :class:`FileModifiedEvent`
        """

        if isinstance(event, DirModifiedEvent):
            return
        src_path = ProperPath(event.src_path, event.is_directory)
        # update model

        # get item
        try:
            item = self._get_item_by_path(src_path)
        except ItemNotInDB:
            #todo: create file folder
            logging.error('unimplemented right now. implement bro.')
            logging.warning('file was modified but not already in db. create it in db.')
            return #todo: remove this once above is implemented

        # update hash
        item.update_hash()

        # save
        save(session, item)


    @asyncio.coroutine
    def on_deleted(self, event):
        """Called when a file or directory is deleted.

        :param event:
            Event representing file/directory deletion.
        :type event:
            :class:`DirDeletedEvent` or :class:`FileDeletedEvent`
        """
        src_path = ProperPath(event.src_path, event.is_directory)

        if not self._already_exists(src_path):
            return

        # get item
        item = self._get_item_by_path(src_path)

        # put item in delete state
        item.locally_deleted = True

        # nodes cannot be deleted online. THUS, delete it inside database. It will be recreated locally.
        if isinstance(item, Node):
            session.delete(item)
            save(session)
            return

        save(session, item)



    def dispatch(self, event):
        #basically, ignore all events that occur for 'Components' file or folder
        if self._event_is_for_components_file_folder(event):
            AlertHandler.warn('Cannot have a custom file or folder named Components')
            return


        _method_map = {
            EVENT_TYPE_MODIFIED: self.on_modified,
            EVENT_TYPE_MOVED: self.on_moved,
            EVENT_TYPE_CREATED: self.on_created,
            EVENT_TYPE_DELETED: self.on_deleted,
        }

        handlers = [self.on_any_event, _method_map[event.event_type]]
        for handler in handlers:
            self._loop.call_soon_threadsafe(
                asyncio.async,
                handler(event)
            )


    def _already_exists(self, path):
        try:
            self._get_item_by_path(path)
            return True
        except ItemNotInDB:
            return False


    def _get_parent_item_from_path(self, path):
        assert isinstance(path, ProperPath)
        containing_folder_path = path.parent

        if containing_folder_path == self.osf_folder:
            raise ItemNotInDB

        return self._get_item_by_path(containing_folder_path)

    # todo: figure out how you can improve this
    def _get_item_by_path(self, path):
        assert isinstance(path, ProperPath)
        for node in session.query(Node):
            if ProperPath(node.path, True) == path:
                return node
        for file_folder in session.query(File):
            file_path = ProperPath(file_folder.path, file_folder.is_folder)
            if file_path == path:
                return file_folder
        raise ItemNotInDB


    def _event_is_for_components_file_folder(self, event):
        if ProperPath(event.src_path, True).name == 'Components':
            return True
        try:
            if ProperPath(event.dest_path,True).name == 'Components':
                return True
            return False
        except AttributeError:
            return False
