from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    source: str
    url: str
    niche: str
    published_at: datetime
    created_at: datetime

class ScriptResponse(BaseModel):
    article_id: int
    title: str
    script: str