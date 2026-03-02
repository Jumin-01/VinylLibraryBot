from sqlalchemy import String, BigInteger, ForeignKey, DateTime, Boolean, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.database.base import Base

# --------------------------
# Таблиця користувачів
# --------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    vinyls: Mapped[list["Vinyl"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# --------------------------
# Таблиця платівок
# --------------------------
class Vinyl(Base):
    __tablename__ = "vinyls"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    discogs_id: Mapped[int] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(500))
    year: Mapped[int | None]
    released: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    catno: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    lowest_price: Mapped[float | None] = mapped_column(nullable=True)
    num_for_sale: Mapped[int | None] = mapped_column(nullable=True)
    rating_average: Mapped[float | None] = mapped_column(nullable=True)
    rating_count: Mapped[int | None] = mapped_column(nullable=True)
    have_count: Mapped[int | None] = mapped_column(nullable=True)
    want_count: Mapped[int | None] = mapped_column(nullable=True)
    genres: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    styles: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    cover_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_playlist_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="vinyls")
    tracks: Mapped[list["Track"]] = relationship(back_populates="vinyl", cascade="all, delete-orphan")
    artists: Mapped[list["Artist"]] = relationship(back_populates="vinyl", cascade="all, delete-orphan")
    formats: Mapped[list["Format"]] = relationship(back_populates="vinyl", cascade="all, delete-orphan")
    images: Mapped[list["Image"]] = relationship(back_populates="vinyl", cascade="all, delete-orphan")
    identifiers: Mapped[list["Identifier"]] = relationship(back_populates="vinyl", cascade="all, delete-orphan")


# --------------------------
# Таблиця треків
# --------------------------
class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    vinyl_id: Mapped[int] = mapped_column(ForeignKey("vinyls.id"))
    position: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(500))
    duration: Mapped[str | None] = mapped_column(String(20), nullable=True)

    vinyl: Mapped["Vinyl"] = relationship(back_populates="tracks")


# --------------------------
# Таблиця артистів
# --------------------------
class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    vinyl_id: Mapped[int] = mapped_column(ForeignKey("vinyls.id"))
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[str | None] = mapped_column(String(20), nullable=True)

    vinyl: Mapped["Vinyl"] = relationship(back_populates="artists")


# --------------------------
# Таблиця форматів
# --------------------------
class Format(Base):
    __tablename__ = "formats"

    id: Mapped[int] = mapped_column(primary_key=True)
    vinyl_id: Mapped[int] = mapped_column(ForeignKey("vinyls.id"))
    name: Mapped[str] = mapped_column(String(100))
    qty: Mapped[int | None] = mapped_column(nullable=True)
    descriptions: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    vinyl: Mapped["Vinyl"] = relationship(back_populates="formats")


# --------------------------
# Таблиця зображень
# --------------------------
class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    vinyl_id: Mapped[int] = mapped_column(ForeignKey("vinyls.id"))
    type: Mapped[str] = mapped_column(String(50))
    uri: Mapped[str] = mapped_column(String(500))
    uri150: Mapped[str | None] = mapped_column(String(500), nullable=True)
    width: Mapped[int | None] = mapped_column(nullable=True)
    height: Mapped[int | None] = mapped_column(nullable=True)

    vinyl: Mapped["Vinyl"] = relationship(back_populates="images")


# --------------------------
# Таблиця ідентифікаторів (штрихкод, matrix)
# --------------------------
class Identifier(Base):
    __tablename__ = "identifiers"

    id: Mapped[int] = mapped_column(primary_key=True)
    vinyl_id: Mapped[int] = mapped_column(ForeignKey("vinyls.id"))
    type: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    vinyl: Mapped["Vinyl"] = relationship(back_populates="identifiers")