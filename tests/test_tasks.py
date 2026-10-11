import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import tasks
from app.database.base import Base
from app.models.article import Article


NOW = tasks._utc_now()


def _research(article, research="Research brief"):
    return {"article_id": article.id, "research": research}


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def add_article(session_factory, title, url=None, age=timedelta(hours=1), **values):
    with session_factory() as db:
        article = Article(
            title=title,
            source="Test Source",
            url=url or f"https://example.com/{len(title)}-{abs(hash(title))}",
            description="",
            niche="technology",
            published_at=NOW - age,
            **values,
        )
        db.add(article)
        db.commit()
        return article.id


def get_article(session_factory, article_id):
    with session_factory() as db:
        return db.get(Article, article_id)


@pytest.fixture
def pipeline(session_factory):
    message_ids = iter(range(100, 200))
    opened_sessions = []

    def tracking_session_factory():
        db = session_factory()
        opened_sessions.append(db)
        return db

    def assert_no_open_transaction(*args, **kwargs):
        assert not any(db.in_transaction() for db in opened_sessions)

    # Rank by insertion order so tests control which article is "best".
    with patch.object(tasks, "RSS_SOURCES", []), patch.object(
        tasks, "SessionLocal", tracking_session_factory
    ), patch.object(
        tasks, "rank_articles", side_effect=lambda articles: sorted(articles, key=lambda a: a.id)
    ), patch.object(
        tasks,
        "generate_research_brief",
        new=AsyncMock(side_effect=lambda article: _research(article)),
    ) as research, patch.object(
        tasks, "generate_script", new=AsyncMock(return_value="Script")
    ) as script, patch.object(
        tasks,
        "send_telegram_message",
        new=AsyncMock(
            side_effect=lambda message: {"ok": True, "result": {"message_id": next(message_ids)}}
        ),
    ) as telegram:
        yield SimpleNamespace(
            research=research,
            script=script,
            telegram=telegram,
            opened_sessions=opened_sessions,
            assert_no_open_transaction=assert_no_open_transaction,
        )


def run():
    return asyncio.run(tasks.run_pipeline())


def test_pipeline_sends_telegram_message_and_marks_delivered(session_factory, pipeline):
    article_id = add_article(session_factory, "Google launches Fitbit Air in India")

    result = run()

    assert result["article_id"] == article_id
    pipeline.telegram.assert_awaited_once()
    stored = get_article(session_factory, article_id)
    assert stored.delivered_at is not None
    assert stored.telegram_message_id == 100


def test_previously_delivered_topic_is_excluded_on_subsequent_run(session_factory, pipeline):
    fitbit_id = add_article(
        session_factory,
        "Google launches Fitbit Air in India, though its high price might deter the masses",
        "https://techcrunch.com/fitbit-air-india",
    )

    assert run()["article_id"] == fitbit_id

    # Next day: same story from another publisher, plus an unrelated story.
    same_story_id = add_article(
        session_factory,
        "Fitbit Air arrives in India at Rs 9,999",
        "https://gadgets.example.in/fitbit-air",
    )
    fresh_id = add_article(session_factory, "Euro falls to 17-month low against dollar")

    second = run()

    assert second["article_id"] == fresh_id
    assert get_article(session_factory, same_story_id).delivered_at is None


def test_fresh_alternative_selected_when_top_ranked_is_duplicate(session_factory, pipeline):
    add_article(
        session_factory,
        "Apple cuts iPhone 18 prices in India",
        "https://a.com/iphone-price",
        delivered_at=NOW - timedelta(days=1),
        telegram_message_id=1,
    )
    duplicate_id = add_article(
        session_factory, "iPhone 18 prices cut in India by Apple", "https://b.com/iphone"
    )
    same_company_id = add_article(
        session_factory, "Apple faces EU fine over App Store payment rules"
    )

    result = run()

    assert result["article_id"] == same_company_id
    assert pipeline.research.await_args.args[0].id == same_company_id
    assert get_article(session_factory, duplicate_id).delivered_at is None


def test_already_delivered_url_is_not_selected_again(session_factory, pipeline):
    add_article(
        session_factory,
        "Original headline",
        "https://site.com/story",
        delivered_at=NOW - timedelta(days=1),
        telegram_message_id=1,
    )

    assert run() is None
    pipeline.research.assert_not_awaited()


def test_articles_older_than_max_age_are_not_selected(session_factory, pipeline):
    add_article(
        session_factory,
        "Old but otherwise eligible story",
        age=timedelta(days=tasks.MAX_ARTICLE_AGE_DAYS, hours=1),
    )
    recent_id = add_article(session_factory, "Recent story", age=timedelta(days=1))

    assert run()["article_id"] == recent_id


def test_failed_telegram_delivery_does_not_mark_story_completed(session_factory, pipeline):
    article_id = add_article(session_factory, "Google launches Fitbit Air in India")
    pipeline.telegram.side_effect = RuntimeError("Telegram sendMessage failed")

    with pytest.raises(RuntimeError):
        run()

    stored = get_article(session_factory, article_id)
    assert stored.delivered_at is None
    assert stored.telegram_message_id is None


def test_dedup_age_limit_and_delivery_tracking_work_together(session_factory, pipeline):
    # Run 1: Telegram fails, so nothing may be marked delivered.
    fitbit_id = add_article(
        session_factory,
        "Google launches Fitbit Air in India, though its high price might deter the masses",
        "https://techcrunch.com/fitbit-air-india",
    )
    pipeline.telegram.side_effect = RuntimeError("Telegram sendMessage failed")

    with pytest.raises(RuntimeError):
        run()

    assert get_article(session_factory, fitbit_id).delivered_at is None

    # Run 2: Telegram recovers; the same story is retried and recorded.
    pipeline.telegram.side_effect = lambda message: {"ok": True, "result": {"message_id": 555}}

    assert run()["article_id"] == fitbit_id
    fitbit = get_article(session_factory, fitbit_id)
    assert fitbit.delivered_at is not None
    assert fitbit.telegram_message_id == 555

    # Run 3: same story from another publisher is skipped, a stale article is
    # too old, and the fresh unrelated story is selected.
    other_publisher_id = add_article(
        session_factory,
        "Google's Fitbit Air goes on sale in India with a steep price tag",
        "https://www.gadgets360.example/fitbit-air-india-sale",
    )
    add_article(
        session_factory,
        "Stale story about Euro exchange rates",
        age=timedelta(days=tasks.MAX_ARTICLE_AGE_DAYS + 1),
    )
    fresh_id = add_article(session_factory, "Greggs announces plans to shut four UK factories")

    assert run()["article_id"] == fresh_id
    assert get_article(session_factory, other_publisher_id).delivered_at is None
    assert [call.args[0].id for call in pipeline.research.await_args_list][-1] == fresh_id
    assert other_publisher_id not in [
        call.args[0].id for call in pipeline.research.await_args_list
    ]

    # Run 4: nothing fresh and uncovered remains, so the run fails instead of
    # resending an old story.
    telegram_calls = pipeline.telegram.await_count

    assert run() is None
    assert pipeline.telegram.await_count == telegram_calls


def test_pipeline_tries_next_article_when_fetch_fails(session_factory, pipeline):
    add_article(session_factory, "Blocked publisher story")
    second_id = add_article(session_factory, "Readable publisher story")
    pipeline.research.side_effect = [None, _research(SimpleNamespace(id=second_id))]

    result = run()

    assert result["article_id"] == second_id
    assert pipeline.research.await_count == 2


def test_pipeline_stops_after_max_fetch_candidates(session_factory, pipeline):
    for index in range(tasks.MAX_ARTICLE_CANDIDATES + 1):
        add_article(session_factory, f"Story number {index}")
    pipeline.research.side_effect = None
    pipeline.research.return_value = None

    assert run() is None
    assert pipeline.research.await_count == tasks.MAX_ARTICLE_CANDIDATES
    pipeline.telegram.assert_not_awaited()


def test_failed_gemini_research_does_not_mark_story_completed(session_factory, pipeline):
    article_id = add_article(session_factory, "Some story")
    pipeline.research.side_effect = lambda article: _research(article, research=None)

    assert run() is None
    assert pipeline.research.await_count == 1
    pipeline.script.assert_not_awaited()
    pipeline.telegram.assert_not_awaited()
    assert get_article(session_factory, article_id).delivered_at is None


def test_failed_script_generation_does_not_mark_story_completed(session_factory, pipeline):
    article_id = add_article(session_factory, "Some story")
    pipeline.script.return_value = None

    assert run() is None
    pipeline.telegram.assert_not_awaited()
    assert get_article(session_factory, article_id).delivered_at is None


def test_pipeline_fails_when_no_articles_exist(session_factory, pipeline):
    assert run() is None
    with session_factory() as db:
        assert db.scalars(select(Article)).all() == []


def test_no_database_transaction_is_open_during_network_calls(session_factory, pipeline):
    add_article(session_factory, "Google launches Fitbit Air in India")
    checks = []

    def research(article):
        pipeline.assert_no_open_transaction()
        checks.append("research")
        return _research(article)

    async def script(article, research_text):
        pipeline.assert_no_open_transaction()
        checks.append("script")
        return "Script"

    async def telegram(message):
        pipeline.assert_no_open_transaction()
        checks.append("telegram")
        return {"ok": True, "result": {"message_id": 1}}

    pipeline.research.side_effect = research
    pipeline.script.side_effect = script
    pipeline.telegram.side_effect = telegram

    assert run() is not None
    assert checks == ["research", "script", "telegram"]
    # One short session to read candidates, one to record the delivery.
    assert len(pipeline.opened_sessions) == 2
    assert not any(db.in_transaction() for db in pipeline.opened_sessions)


@pytest.mark.parametrize(
    "telegram_response",
    [
        {"ok": True},
        {"ok": True, "result": {}},
        {"ok": True, "result": None},
        {"ok": True, "result": {"message_id": "not-a-number"}},
    ],
)
def test_delivery_recorded_when_message_id_missing(
    session_factory, pipeline, telegram_response
):
    article_id = add_article(session_factory, "Google launches Fitbit Air in India")
    pipeline.telegram.side_effect = None
    pipeline.telegram.return_value = telegram_response

    assert run()["article_id"] == article_id
    stored = get_article(session_factory, article_id)
    assert stored.delivered_at is not None
    assert stored.telegram_message_id is None


def test_record_delivery_updates_only_selected_article(session_factory, pipeline):
    selected_id = add_article(session_factory, "Google launches Fitbit Air in India")
    other_id = add_article(session_factory, "Euro falls to 17-month low against dollar")
    before = get_article(session_factory, selected_id)

    assert run()["article_id"] == selected_id

    selected = get_article(session_factory, selected_id)
    other = get_article(session_factory, other_id)
    assert selected.delivered_at is not None
    assert selected.telegram_message_id == 100
    assert (selected.title, selected.url, selected.published_at) == (
        before.title,
        before.url,
        before.published_at,
    )
    assert other.delivered_at is None
    assert other.telegram_message_id is None


def test_commit_failure_after_telegram_is_logged_and_reraised(
    session_factory, pipeline, caplog
):
    article_id = add_article(session_factory, "Google launches Fitbit Air in India")

    with patch.object(
        Session,
        "commit",
        side_effect=OperationalError("UPDATE articles", {}, Exception("connection lost")),
    ), pytest.raises(OperationalError):
        run()

    pipeline.telegram.assert_awaited_once()
    assert "delivery could not be recorded" in caplog.text
    assert get_article(session_factory, article_id).delivered_at is None
    assert not any(db.in_transaction() for db in pipeline.opened_sessions)


def test_recent_covered_story_blocks_same_story(session_factory, pipeline):
    add_article(
        session_factory,
        "Greggs to shut four factories and cut 740 jobs",
        "https://bbc.example/greggs",
        age=timedelta(days=10),
        delivered_at=NOW - timedelta(days=tasks.COVERED_STORY_WINDOW_DAYS - 1),
        telegram_message_id=1,
    )
    add_article(
        session_factory,
        "Greggs announces plans to shut four UK factories that could cost 740 jobs",
        "https://guardian.example/greggs",
    )
    fresh_id = add_article(session_factory, "Euro falls to 17-month low against dollar")

    assert run()["article_id"] == fresh_id


def test_covered_story_older_than_window_no_longer_blocks(session_factory, pipeline):
    add_article(
        session_factory,
        "Greggs to shut four factories and cut 740 jobs",
        "https://bbc.example/greggs",
        age=timedelta(days=40),
        delivered_at=NOW - timedelta(days=tasks.COVERED_STORY_WINDOW_DAYS + 1),
        telegram_message_id=1,
    )
    new_development_id = add_article(
        session_factory,
        "Greggs announces plans to shut four UK factories that could cost 740 jobs",
        "https://guardian.example/greggs",
    )

    assert run()["article_id"] == new_development_id


def test_stale_candidate_rejected_even_when_not_covered(session_factory, pipeline):
    add_article(
        session_factory,
        "Greggs announces plans to shut four UK factories",
        age=timedelta(days=tasks.MAX_ARTICLE_AGE_DAYS, minutes=1),
    )

    assert run() is None
    pipeline.research.assert_not_awaited()
