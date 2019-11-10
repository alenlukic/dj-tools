from sqlalchemy import Table


class DBTable:
    """ Specifies configuration for a sqlalchemy Table. """

    def __init__(self, name, metadata, columns):
        """
        Constructor. Sets table name, metadata, and columns as class variables.

        :param name - the table name.
        :param metadata - sqlalchemy metadata object.
        :param columns - table columns.
        """
        self.table = None
        self.name = name
        self.metadata = metadata
        self.columns = columns

    def create(self):
        """ Creates the table (if it doesn't exist). """

        if self.table is None:
            self.table = Table(self.name, self.metadata)
            for col in self.columns:
                self.table.append_column(col)

            self.table.create()

    def get_table(self):
        """ Returns the table."""
        if self.table is None:
            self.create()
        return self.table
