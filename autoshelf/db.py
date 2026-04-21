from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import JSON, ForeignKey, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    root: Mapped[str] = mapped_column(String, index=True)
    path: Mapped[str] = mapped_column(String, unique=True)
    parent_name: Mapped[str] = mapped_column(String)
    filename: Mapped[str] = mapped_column(String)
    stem: Mapped[str] = mapped_column(String)
    extension: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int]
    mtime: Mapped[float]
    ctime: Mapped[float]
    file_hash: Mapped[str] = mapped_column(String(32))
    contexts: Mapped[list[ContextRecord]] = relationship(back_populates="file")


class ContextRecord(Base):
    __tablename__ = "contexts"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"), unique=True)
    title: Mapped[str] = mapped_column(String, default="")
    head_text: Mapped[str] = mapped_column(String, default="")
    extra_meta: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    file: Mapped[FileRecord] = relationship(back_populates="contexts")


class TransactionRecord(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    root: Mapped[str] = mapped_column(String, index=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String)
    source_path: Mapped[str] = mapped_column(String)
    target_path: Mapped[str] = mapped_column(String)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


@dataclass(slots=True)
class Database:
    path: Path

    def engine(self):
        return create_engine(f"sqlite:///{self.path}")

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(self.engine())

    @contextmanager
    def session(self) -> Iterator[Session]:
        self.initialize()
        with Session(self.engine()) as session:
            yield session
            session.commit()

    def last_run_id(self, root: Path) -> str | None:
        with self.session() as session:
            statement = (
                select(TransactionRecord.run_id)
                .where(TransactionRecord.root == str(root))
                .order_by(TransactionRecord.id.desc())
                .limit(1)
            )
            return session.execute(statement).scalar_one_or_none()


def default_db_path(root: Path) -> Path:
    return root / ".autoshelf" / "autoshelf.sqlite"
