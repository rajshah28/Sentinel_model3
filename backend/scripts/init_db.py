import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import Base, engine
from app.db import models  # noqa: F401  ensures models are registered


def main():
    Base.metadata.create_all(bind=engine)
    print("Tables created:", list(Base.metadata.tables.keys()))


if __name__ == "__main__":
    main()
