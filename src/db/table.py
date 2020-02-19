from sqlalchemy import Table


class DBTable:
    """ Specifies configuration for a sqlalchemy Table. """

    def __init__(self, name, metadata, columns):
        """
        Constructor. Sets table name, metadata, and columns as class variables.

        :param name: The table name.
        :param metadata: Sqlalchemy metadata object.
        :param columns: Table columns.
        """
        self.table = Table(name, metadata)
        for col in columns:
            self.table.append_column(col)

    def create(self):
        """ Creates the table. """
        self.table.create()

    def get_table(self):
        """ Returns the table."""
        return self.table
