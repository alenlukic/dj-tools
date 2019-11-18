from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import session as sezzion, sessionmaker

from src.definitions.common import CONFIG


class Database:
    """ Encapsulates interface to DB for storing collection data. """

    Base = None
    BoundSessionInstantiator = None
    db = None

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
            self.engine = self.db.engine
            self.conn = self.db.conn
            self.metadata = self.db.metadata
            self.Base = declarative_base(metadata=self.metadata)
            self.BoundSessionInstantiator = sessionmaker(bind=self.engine)

    def create_session(self):
        """ Creates and returns a new DB session. """
        return self.BoundSessionInstantiator()

    def close_sessions(self, sessions):
        """
        Closes the given sessions.

        :param sessions - sessions to close
        """

        for session in sessions:
            session.close()

    def close_all_sessions(self):
        """ Closes all open sessions. """
        sezzion.close_all_sessions()

    def get_base(self):
        """ Get ORM base entity. """
        self._ensure_connection()
        return self.Base

    def get_connnection(self):
        """ Returns DB connection. """
        self._ensure_connection()
        return self.conn

    def get_db(self):
        """ Returns DB object. """
        self._ensure_connection()
        return self.db

    def get_engine(self):
        """ Returns engine object. """
        self._ensure_connection()
        return self.engine

    def get_metadata(self):
        """ Returns metadata object. """
        self._ensure_connection()
        return self.metadata

    def get_tables(self):
        """ Returns list of entities in this DB. """
        self._ensure_connection()
        return self.metadata.tables

    def close_connection(self):
        """ Closes the connection to the DB. """

        if self.db is not None:
            self.conn.close()
            self.close_all_sessions()
            self.db = None

    def _ensure_connection(self):
        """ Opens connection to the database if it doesn't exist. """

        if self.db is None:
            self.db = self.__Database()
            self.engine = self.db.engine
            self.conn = self.db.conn
            self.metadata = self.db.metadata
            self.Base = automap_base()
            self.Base.prepare(self.engine, reflect=True)
            self.BoundSessionInstantiator = sessionmaker(bind=self.engine)


class QueryExecutionException(Exception):
    pass
