from datetime import datetime

from backend.utils import calculate_streak


def test_calculate_streak_with_gap():
    today = datetime(2023, 1, 5).date()
    progress = [
        {"date": "2023-01-05", "cards_studied": 1},
        {"date": "2023-01-04", "cards_studied": 2},
        {"date": "2023-01-02", "cards_studied": 3},  # gap: missing 2023-01-03
    ]
    assert calculate_streak(progress, today) == 2


def test_calculate_streak_continuous():
    today = datetime(2023, 1, 5).date()
    progress = [
        {"date": "2023-01-05", "cards_studied": 1},
        {"date": "2023-01-04", "cards_studied": 1},
        {"date": "2023-01-03", "cards_studied": 1},
    ]
    assert calculate_streak(progress, today) == 3
