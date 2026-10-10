from sqlalchemy import Column, DateTime, String, Uuid, text
from sqlalchemy.sql import func

from .db import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    email = Column(String(254), unique=True, index=True, nullable=False)
    full_name = Column(String(120), nullable=False)
    password_hash = Column(String, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())