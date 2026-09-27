import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.rating_service import expected_score, compute_new_rating, rating_to_difficulty_label


def test_expected_score_is_fifty_fifty_when_ratings_equal():
    assert abs(expected_score(1200, 1200) - 0.5) < 0.001


def test_expected_score_favors_higher_rated_problem_being_harder():
    # a 1200-rated user facing a 1600-rated problem should be "expected" to lose (solve less often)
    assert expected_score(1200, 1600) < 0.5


def test_solving_a_much_harder_problem_gains_more_rating():
    _, change_hard = compute_new_rating(1200, 1800)   # big underdog win
    _, change_easy = compute_new_rating(1200, 900)    # expected win
    assert change_hard > change_easy
    assert change_hard > 0
    assert change_easy > 0  # still gains something, just very little


def test_solving_a_much_easier_problem_gains_almost_nothing():
    new_rating, change = compute_new_rating(1800, 900)
    assert 0 <= change <= 2  # near-zero gain, but never negative for a solve


def test_rating_never_goes_negative():
    new_rating, _ = compute_new_rating(5, 3000, solved=False)
    assert new_rating >= 0


def test_rating_to_difficulty_label_boundaries():
    assert rating_to_difficulty_label(999) == "easy"
    assert rating_to_difficulty_label(1000) == "medium"
    assert rating_to_difficulty_label(1599) == "medium"
    assert rating_to_difficulty_label(1600) == "hard"
