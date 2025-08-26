from datetime import datetime, timedelta
from typing import Iterable, Dict, Optional


def calculate_streak(progress_entries: Iterable[Dict], today: Optional[datetime.date] = None) -> int:
    """Calculate consecutive study streak.

    Args:
        progress_entries: Iterable of progress records sorted by date descending.
        today: Date to use as starting point. Defaults to current UTC date.

    Returns:
        int: Number of consecutive days with study activity starting from ``today``.
    """
    if today is None:
        today = datetime.utcnow().date()

    streak = 0
    expected_date = today
    for progress in progress_entries:
        try:
            progress_date = datetime.strptime(progress["date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            break

        if progress_date != expected_date or progress.get("cards_studied", 0) <= 0:
            break

        streak += 1
        expected_date -= timedelta(days=1)

    return streak
