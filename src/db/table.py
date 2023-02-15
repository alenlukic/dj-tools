from sqlalchemy import Table


class DBTable:
    """ Encapsulates a database table. """
    def __init__(self, name, metadata, columns):
        self.table = Table(name, metadata)
        for col in columns:
            self.table.append_column(col)

    def create(self):
        self.table.create()

    def get_table(self):
        return self.table
