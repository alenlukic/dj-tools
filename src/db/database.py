import logging

from sqlalchemy import create_engine, inspect, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import session as sezzion, sessionmaker

from src.definitions.common import CONFIG
from src.lib.error_management.service import handle


class Database:
    """ Encapsulates interface to DB for storing collection data. """

    Base = None
    BoundSessionInstantiator = None
    db = None
    dry_run = False

    class __Database:
        """ Singleton database class. """

        def __init__(self):
            db_config = CONFIG['DB']
            user = db_config['USER']
            password = db_config['PASSWORD']
            host = db_config['HOST']
            port = db_config['PORT']
            name = db_config['NAME']
            conn_string = 'postgresql+psycopg2://%s:%s@%s:%s/%s' % (user, password, host, port, name)
            self.engine = create_engine(conn_string)
            self.conn = self.engine.connect()
            self.metadata = MetaData(self.engine, reflect=True)

    def __init__(self):
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

        def __init__(self, session, dry_run=False, session_limit=10):
            self.session = session
            self.dry_run = dry_run
            self.updates_executed = 0
            self.session_limit = session_limit

        def query(self, query):
            if self.dry_run:
                return None
            return self.session.query(query)

        def add(self, entity):
            if not self.dry_run:
                self.session.add(entity)

        def guarded_add(self, entity):
            try:
                self.add(entity)
                self.commit()
                return True
            except Exception as e:
                str_entity = str({c.key: getattr(entity, c.key) for c in inspect(entity).mapper.column_attrs})
                handle(e, 'Failed to add %s to DB' % str_entity, print, False)
                self.rollback()
                return False

        def delete(self, entity):
            if not self.dry_run:
                self.session.delete(entity)

        def safe_delete(self, entity):
            if entity is not None:
                self.delete(entity)
                return True
            return False

        def commit(self):
            if not self.dry_run:
                self.session.commit()
                self.updates_executed += 1

        def rollback(self):
            if not self.dry_run:
                self.session.rollback()

        def close(self, rollback_on_error=False, error=False):
            if rollback_on_error and error:
                self.rollback()
            self.session.close()

    def enable_dry_run(self):
        self.dry_run = True

    def disable_dry_run(self):
        self.dry_run = False

    # ==============
    # Getter methods
    # ==============

    def get_base(self):
        return self.Base

    def get_connnection(self):
        return self.conn

    def get_db(self):
        return self.db

    def get_engine(self):
        return self.engine

    def get_metadata(self):
        return self.metadata

    def get_tables(self):
        return self.metadata.tables

    # ===============
    # Session methods
    # ===============

    def create_session(self, session_limit=10):
        if self.dry_run:
            logging.warning('Creating DB session in dry run mode')
        session = self.BoundSessionInstantiator()
        return Database.__Session(session, self.dry_run, session_limit)

    def recreate_session(self, session, session_limit=10):
        session.close()
        return self.create_session(session_limit)

    def recreate_session_contingent(self, session, session_limit=10):
        if session.updates_executed >= session.session_limit:
            return self.recreate_session(session, session_limit)
        return session

    @staticmethod
    def close_sessions(sessions):
        for session in sessions:
            session.close()

    @staticmethod
    def close_all_sessions():
        sezzion.close_all_sessions()

    # =================
    # DB update methods
    # =================

    def add_column(self, table_name, column_name, column_type='varchar'):
        self.engine.execute('ALTER TABLE %s ADD COLUMN IF NOT EXISTS %s %s' % (table_name, column_name, column_type))
