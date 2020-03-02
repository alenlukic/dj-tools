import logging

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import session as sezzion, sessionmaker

from src.definitions.common import CONFIG


class Database:
    """ Encapsulates interface to DB for storing collection data. """

    Base = None
    BoundSessionInstantiator = None
    db = None
    dry_run = False

    class __Database:
        """ Singleton database class. """

        def __init__(self):
            """ Constructor. Opens connection to the database and initializes useful sqlalchemy structures. """

            user = CONFIG['DB_USER']
            password = CONFIG['DB_PASSWORD']
            host = CONFIG['DB_HOST']
            port = CONFIG['DB_PORT']
            name = CONFIG['DB_NAME']
            conn_string = 'postgresql+psycopg2://%s:%s@%s:%s/%s' % (user, password, host, port, name)
            self.engine = create_engine(conn_string)
            self.conn = self.engine.connect()
            self.metadata = MetaData(self.engine, reflect=True)

    def __init__(self):
        """ Constructor. Opens connection to the database if it doesn't exist. """

        if self.db is None:
            self.db = self.__Database()
            self.dry_run = False
            self.conn = self.db.conn
            self.engine = self.db.engine
            self.metadata = self.db.metadata
            self.Base = declarative_base(metadata=self.metadata)
            self.BoundSessionInstantiator = sessionmaker(bind=self.engine)

    class __Session:
        """ Session wrapper. Used to enable dry run functionality during testing. """

        def __init__(self, session, dry_run=False):
            self.session = session
            self.dry_run = dry_run

        def query(self, query):
            if self.dry_run:
                return None
            return self.session.query(query)

        def add(self, entity):
            if not self.dry_run:
                self.session.add(entity)

        def delete(self, entity):
            if not self.dry_run:
                self.session.delete(entity)

        def commit(self):
            if not self.dry_run:
                self.session.commit()

        def rollback(self):
            if not self.dry_run:
                self.session.rollback()

        def close(self, rollback_on_error=False, error=False):
            if rollback_on_error and error:
                self.rollback()
            self.session.close()

    def enable_dry_run(self):
        """ Switches DB session to dry run mode (no queries executed or data persisted. """
        self.dry_run = True

    def disable_dry_run(self):
        """ Disables dry run mode. """
        self.dry_run = False

    # ==============
    # Getter methods
    # ==============

    def get_base(self):
        """ Get ORM base entity. """
        return self.Base

    def get_connnection(self):
        """ Returns DB connection. """
        return self.conn

    def get_db(self):
        """ Returns DB object. """
        return self.db

    def get_engine(self):
        """ Returns engine object. """
        return self.engine

    def get_metadata(self):
        """ Returns metadata object. """
        return self.metadata

    def get_tables(self):
        """ Returns list of entities in this DB. """
        return self.metadata.tables

    # ===============
    # Session methods
    # ===============

    def create_session(self):
        """ Creates and returns a new DB session. """
        if self.dry_run:
            logging.warning('Creating DB sessio in dry run mode')
        session = self.BoundSessionInstantiator()
        return Database.__Session(session, self.dry_run)

    @staticmethod
    def close_sessions(sessions):
        """
        Closes the given sessions.

        :param sessions - sessions to close
        """

        for session in sessions:
            session.close()

    @staticmethod
    def close_all_sessions():
        """ Closes all open sessions. """
        sezzion.close_all_sessions()

    # =================
    # DB update methods
    # =================

    def add_column(self, table_name, column_name, column_type='varchar'):
        """
        Adds column to an existing table, if it does not exist.

        :param table_name: Name of the table being updated.
        :param column_name: Name of the column being added.
        :param column_type: Type of the column being added.
        """

        self.engine.execute('ALTER TABLE %s ADD COLUMN IF NOT EXISTS %s %s' % (table_name, column_name, column_type))
