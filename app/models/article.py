from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from sqlalchemy import func

class Article(Base):
    __tablename__ = "articles"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column()
    source: Mapped[str] = mapped_column()
    url: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None] = mapped_column()
    niche: Mapped[str] = mapped_column()
    published_at: Mapped[datetime] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())