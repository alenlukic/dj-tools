from sqlalchemy import Table


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
