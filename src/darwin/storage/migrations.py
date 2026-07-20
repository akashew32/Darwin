from sqlalchemy.engine import Engine

from darwin.storage.models import Base


def create_all(engine: Engine) -> None:
    Base.metadata.create_all(engine)
