from sqlalchemy import create_engine, MetaData

from src.definitions.common import CONFIG


class Database:
    """ Encapsulates interface to DB for storing collection data. """

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
            self.metadata = MetaData(self.engine)

    def __init__(self):
        """ Constructor. Opens connection to the database if it doesn't exist. """

        if self.db is None:
            self.db = self.__Database()
            self.engine = self.db.engine
            self.conn = self.db.conn
            self.metadata = self.db.metadata

    def get_connnection(self):
        """ Returns DB connection. """
        self._ensure_connection()
        return self.conn

    def get_db(self):
        """ Returns DB object. """
        self._ensure_connection()
        return self.db

    def get_metadata(self):
        """ Returns metadata object. """
        self._ensure_connection()
        return self.metadata

    def close_connection(self):
        """ Closes the connection to the DB. """

        if self.db is not None:
            self.conn.close()
            self.db = None

    def _ensure_connection(self):
        """ Opens connection to the database if it doesn't exist. """

        if self.db is None:
            self.db = self.__Database()
            self.engine = self.db.engine
            self.conn = self.db.conn
            self.meta = self.db.metadata


class QueryExecutionException(Exception):
    pass
