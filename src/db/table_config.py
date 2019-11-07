from sqlalchemy import Table

# user = Table('user', metadata,
#     Column('user_id', Integer, primary_key=True),
#     Column('user_name', String(16), nullable=False),
#     Column('email_address', String(60)),
#     Column('nickname', String(50), nullable=False)
# )
class TableConfig:
    """ Specifies configuration for a sqlalchemy Table. """

    def __init__(self, name, metadata, columns):
        """
        Constructor. Sets column name and type, along with default values for other instantiation params.

        :param name - the column name.
        :param pg_type - the column's type in Postgres.
        """
        self.table = None
        self.name = name
        self.metadata = metadata
        self.columns = columns

    def create(self):
        """ Creates the column with set class members. """
        if self.table is None:
            self.table = Table(self.name, self.metadata)
            for col in self.columns:
                self.table.append_column(col)
            self.table.create()



    def as_index(self):
        """ Creates column as an index. """
        self.index = True
        return self

    def as_nullable(self):
        """ Allows null values. """
        self.nullable = True
        return self

    def as_primary_key(self):
        """ Creates column as a primary key. """
        self.primary_key = True
        return self

    def with_autoincrement(self, autoincrement='auto'):
        """
        Enables autoincrementing (column must be an integer and primary key).

        :param autoincrement - the autoincrement type.
        """

        self.primary_key = True
        self.type_ = Integer
        self.autoincrement = autoincrement
        return self

    def with_default_value(self, value):
        """
        Sets a default value for the column.

        :param value - the default column value.
        """

        self.default = value
        return self

    def with_update_value(self, value):
        """
        Sets a default update value for the column.

        :param value - the default update value.
        """

        self.onupdate = value
        return self
