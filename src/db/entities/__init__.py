from src.db import database


metadata = database.get_metadata()
Base = database.get_base()
