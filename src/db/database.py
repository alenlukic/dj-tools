from sqlalchemy import create_engine, MetaData

from src.definitions.common import CONFIG


class Database:
    """ Encapsulates interface to DB for storing collection data. """

    db = None

    class __Database:
        """ Singleton database class. """

        def __init__(self):
            """ Constructor. Opens connection to the database and initializes useful sqlalchemy structures. """

            db_user = CONFIG['DB_USER']
            db_password = CONFIG['DB_PASSWORD']
            db_host = CONFIG['DB_HOST']
            db_port = CONFIG['DB_PORT']
            db_name = CONFIG['DB_NAME']
            conn_string = 'postgresql+psycopg2://%s:%s@%s:%s/%s' % (db_user, db_password, db_host, db_port, db_name)
            self.engine = create_engine(conn_string)
            self.conn = self.engine.connect()
            self.meta = MetaData(self.engine)

    def __init__(self):
        """ Constructor. Opens connection to the database if it doesn't exist. """

        if self.db is None:
            self.db = self.__Database()
            self.engine = self.db.engine
            self.conn = self.db.conn
            self.meta = self.db.meta

    def close_connection(self):
        """ Closes the connection to the DB. """

        if self.db is not None:
            self.conn.close()
            self.db = None

    def create_table(self, table_name, column_configs):
        return

    def get_connnection(self):
        """ Returns DB connection. """
        self._ensure_connection()
        return self.conn

    def _ensure_connection(self):
        """ Opens connection to the database if it doesn't exist. """
        if self.db is None:
            self.db = self.__Database()
            self.engine = self.db.engine
            self.conn = self.db.conn
            self.meta = self.db.meta


class QueryExecutionException(Exception):
    pass
