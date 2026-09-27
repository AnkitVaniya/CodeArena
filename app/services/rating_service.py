"""
Elo-style rating system, modeled on how Codeforces/chess ratings work.

Each question has a numeric `rating` (difficulty, e.g. 800-2400) instead of
just a label. Each user has a numeric `rating` too, starting at 1200.

When a user solves a question for the FIRST time, we treat it like a "match"
between the user and the problem:
  - expected_score = probability the user "should" solve a problem of this
    rating, given their current rating (the standard Elo expectation curve)
  - actual_score = 1 (they solved it)
  - new_rating = old_rating + K * (actual_score - expected_score)

Solving something rated well above you moves your rating up a lot (you beat
a strong "opponent"). Solving something far below you barely moves it (you
were expected to win anyway). This is why re-solving the same question
should NOT trigger another rating change — see `has_already_solved()` below,
called from the submission flow before applying any update.
"""
import math

K_FACTOR = 32  # how aggressively rating moves per solve — 32 is Codeforces' typical value for new-ish users


def expected_score(user_rating: int, problem_rating: int) -> float:
    """Probability the user is expected to solve a problem of this rating."""
    return 1 / (1 + math.pow(10, (problem_rating - user_rating) / 400))


def compute_new_rating(user_rating: int, problem_rating: int, solved: bool = True) -> tuple[int, int]:
    """
    Returns (new_rating, rating_change).
    Only call this once per (user, question) pair — see has_already_solved().
    """
    expected = expected_score(user_rating, problem_rating)
    actual = 1.0 if solved else 0.0
    change = round(K_FACTOR * (actual - expected))
    new_rating = max(0, user_rating + change)  # ratings never go negative
    return new_rating, change


def rating_to_difficulty_label(rating: int) -> str:
    """Maps a numeric problem rating to a human-friendly label for filtering/display."""
    if rating < 1000:
        return "easy"
    if rating < 1600:
        return "medium"
    return "hard"
