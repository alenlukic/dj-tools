from src.db.database import Database

database = Database()
metadata = database.get_metadata()
Base = database.get_base()
