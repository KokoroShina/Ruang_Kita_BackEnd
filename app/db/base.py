import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# DATETIME(fsp=6) di MySQL — presisi mikrodetik.
# Tanpa ini, pesan user & balasan AI yang tersimpan dalam detik yang sama
# jadi ambigu urutannya (UUID PK tidak bisa dipakai untuk sorting).
DateTimeMicro = DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")

# Default server HARUS dengan fsp=6 agar mikrodetik terisi. func.now() merender
# CURRENT_TIMESTAMP tanpa argumen -> MySQL memotong ke detik meski kolom datetime(6).
SERVER_NOW_6 = text("CURRENT_TIMESTAMP(6)")

# Naming convention konsisten agar Alembic tidak menghasilkan diff "phantom"
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """UUID v4 sebagai PK — non-enumerable, cocok untuk data sensitif & memudahkan export data."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    # MySQL DATETIME menyimpan naive — konsisten simpan UTC (session tz dipaksa +00:00)
    created_at: Mapped[datetime] = mapped_column(
        DateTimeMicro, server_default=SERVER_NOW_6, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTimeMicro,
        server_default=SERVER_NOW_6,
        onupdate=func.now(),
        nullable=False,
    )
