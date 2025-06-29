import logging
from typing import Optional
from datetime import datetime
from sqlalchemy import DateTime, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sqlalchemy import create_engine

logger = logging.getLogger('meshmtx:storage')

class Base(DeclarativeBase):
  pass

class NodeState(Base):
  __tablename__ = "node"

  id: Mapped[int] = mapped_column(primary_key=True)
  #name: Mapped[str] = mapped_column(String(32))
  timestamp: Mapped[datetime] = mapped_column(DateTime)
  latitude: Mapped[Optional[float]] = mapped_column(Float)
  longitude: Mapped[Optional[float]] = mapped_column(Float)

def get_engine(path: str = 'state.db', debug: bool = False):
  return create_engine(f"sqlite:///{path}", echo=debug)
