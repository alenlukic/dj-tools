from sqlalchemy import Column, Integer


class DBColumn:
    """ Specifies configuration for a sqlalchemy Column. """

    def __init__(self, name, pg_type):
        """
        Constructor. Sets column name and type, along with default values for other instantiation params.

        :param name - the column name.
        :param pg_type - the column's type in Postgres.
        """

        self.name = name
        self.type_ = pg_type
        self.primary_key = False
        self.autoincrement = None
        self.default = None
        self.nullable = False
        self.index = False
        self.onupdate = None

    def create(self):
        """ Creates the column with set class members. """

        args = {'name': self.name, 'type_': self.type_, 'primary_key': self.primary_key,
                'nullable': self.nullable, 'index': self.index}
        if self.autoincrement is not None:
            args['autoincrement'] = self.autoincrement
        if self.default is not None:
            args['default'] = self.default
        if self.onupdate is not None:
            args['onupdate'] = self.onupdate

        return Column(**args)

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
