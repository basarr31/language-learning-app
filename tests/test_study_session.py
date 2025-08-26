import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from datetime import datetime
import asyncio
import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost")
os.environ.setdefault("DB_NAME", "testdb")

with patch("motor.motor_asyncio.AsyncIOMotorClient"):
    from backend.server import create_study_session, StudySessionCreate


def test_correct_rate_updates_with_multiple_sessions():
    today = datetime.utcnow().date().isoformat()
    existing = {
        "date": today,
        "cards_studied": 5,
        "correct_rate": 0.6,
        "study_time": 10,
    }

    fake_db = SimpleNamespace(
        study_sessions=SimpleNamespace(insert_one=AsyncMock()),
        daily_progress=SimpleNamespace(
            find_one=AsyncMock(return_value=existing),
            update_one=AsyncMock(),
        ),
    )

    session = StudySessionCreate(
        cards_studied=5,
        correct_answers=4,
        session_duration=10,
        study_mode="flashcards",
    )

    async def run():
        with patch("backend.server.db", fake_db):
            await create_study_session(session)

    asyncio.run(run())

    fake_db.daily_progress.update_one.assert_awaited_once()
    _, update_doc = fake_db.daily_progress.update_one.call_args[0]
    assert update_doc["$inc"] == {
        "cards_studied": 5,
        "study_time": 10,
    }
    assert pytest.approx(update_doc["$set"]["correct_rate"], rel=1e-5) == 0.7
