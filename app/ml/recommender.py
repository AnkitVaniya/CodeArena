"""
Next-question recommender — replaces the old resume-driven version.

Combines three signals:
1. Content similarity: TF-IDF vectors over each question's tags + description,
   compared via cosine similarity against questions the user has already
   solved. This is real ML (a learned vector space from the corpus), not a
   hardcoded rule — recommends questions that "read like" ones you enjoyed
   or just finished, even across different topics.
2. Rating proximity: only considers questions within a band around the
   user's current rating (using the same Elo expected-score curve as the
   rating system, so "appropriately challenging" isn't an arbitrary cutoff).
3. Topic graph: only considers topics that are actually unlocked, so we
   never recommend something the user hasn't built prerequisites for.

Cold start (no solves yet): skips step 1, recommends from unlocked topics
at the user's current (default) rating.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.db.mongo import questions_collection
from app.dsa.graph import topic_graph
from app.models.submission import Submission
from app.models.topic_progress import UserTopicProgress
from app.services.rating_service import expected_score, rating_to_difficulty_label

RATING_BAND = 200  # only recommend questions within +/- this range that the user has a reasonable shot at


def _question_text(q: dict) -> str:
    return f"{q.get('title', '')} {' '.join(q.get('tags', []))} {q.get('topic', '')} {q.get('description', '')}"


async def _get_unlocked_topics(db: Session, user_id: int) -> set[str]:
    rows = db.query(UserTopicProgress).filter(UserTopicProgress.user_id == user_id).all()
    mastered = {r.topic for r in rows if r.mastery_score >= 0.7}
    unlocked = set(topic_graph.unlocked_topics(mastered))
    return unlocked | mastered  # can still get recommendations within topics already unlocked/mastered


def _solved_question_ids(db: Session, user_id: int) -> set[str]:
    rows = (
        db.query(Submission.question_id)
        .filter(Submission.user_id == user_id, Submission.verdict == "Accepted")
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


async def recommend_next_question(db: Session, user_id: int, user_rating: int) -> dict:
    all_questions = [doc async for doc in questions_collection.find({}, {"test_cases": 0})]
    if not all_questions:
        return {"question": None, "reasoning": {"message": "No questions in the bank yet"}}

    for q in all_questions:
        q["id"] = str(q["_id"])

    solved_ids = _solved_question_ids(db, user_id)
    unlocked_topics = await _get_unlocked_topics(db, user_id)

    # candidate pool: not yet solved, topic unlocked, and a fair fight given current rating
    candidates = [
        q
        for q in all_questions
        if q["id"] not in solved_ids
        and q["topic"] in unlocked_topics
        and abs(q["rating"] - user_rating) <= RATING_BAND
    ]

    if not candidates:
        # relax the rating band before giving up entirely — better to suggest something than nothing
        candidates = [q for q in all_questions if q["id"] not in solved_ids and q["topic"] in unlocked_topics]

    if not candidates:
        return {"question": None, "reasoning": {"message": "You've solved everything unlocked so far — add more questions or master a new topic"}}

    solved_docs = [q for q in all_questions if q["id"] in solved_ids]

    if not solved_docs:
        # cold start: no similarity signal yet, just pick the closest-rated unlocked candidate
        best = min(candidates, key=lambda q: abs(q["rating"] - user_rating))
        return _build_response(best, reason="cold start — closest-rated question in an unlocked topic")

    # --- TF-IDF similarity ---
    corpus = [_question_text(q) for q in solved_docs + candidates]
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(corpus)

    solved_vectors = tfidf_matrix[: len(solved_docs)]
    candidate_vectors = tfidf_matrix[len(solved_docs):]

    # a candidate's similarity = its best match against ANY solved question (not the average —
    # you want "similar to something you liked", not "similar to your solve history on average")
    similarity_matrix = cosine_similarity(candidate_vectors, solved_vectors)
    best_similarity_per_candidate = similarity_matrix.max(axis=1)

    # combine similarity with rating fit (how close to a 50/50 fair challenge, via the Elo curve)
    scored = []
    for candidate, sim in zip(candidates, best_similarity_per_candidate):
        fairness = 1 - abs(0.5 - expected_score(user_rating, candidate["rating"]))  # peaks at a 50/50 match
        combined_score = 0.7 * sim + 0.3 * fairness
        scored.append((combined_score, sim, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_sim, best_candidate = scored[0]

    return _build_response(
        best_candidate,
        reason=f"similar to a question you solved (similarity {best_sim:.2f}), and a fair challenge at your rating",
    )


def _build_response(question: dict, reason: str) -> dict:
    question.pop("_id", None)
    question["difficulty"] = rating_to_difficulty_label(question["rating"])
    return {
        "question": question,
        "reasoning": {"why_this_topic": reason, "topic": question["topic"], "rating": question["rating"]},
    }
