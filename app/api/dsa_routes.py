from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.mongo import questions_collection
from app.db.mysql import get_db
from app.dsa.trie import build_trie_from_words
from app.dsa.heap import LeaderboardEntry, build_leaderboard
from app.dsa.graph import topic_graph
from app.models.user import User
from app.models.submission import Submission
from app.models.topic_progress import UserTopicProgress

router = APIRouter(tags=["dsa-features"])


@router.get("/search/autocomplete")
async def autocomplete(prefix: str, limit: int = 10):
    """Trie-backed prefix search over question titles."""
    titles = [doc["title"] async for doc in questions_collection.find({}, {"title": 1})]
    trie = build_trie_from_words(titles)
    return {"prefix": prefix, "matches": trie.search_prefix(prefix, limit)}


@router.get("/leaderboard")
def leaderboard(db: Session = Depends(get_db), top_n: int = 10):
    """
    Heap-backed ranking by rating. Ties are broken by earliest join date
    (older accounts rank slightly higher on a tie — arbitrary but deterministic).
    """
    users = db.query(User).all()
    entries = [
        LeaderboardEntry(
            user_id=u.id,
            user_name=u.name,
            score=u.rating,
            last_submission_ts=u.created_at.timestamp() if u.created_at else 0,
        )
        for u in users
    ]
    top = build_leaderboard(entries, top_n=top_n)
    return [
        {"rank": i + 1, "user_id": e.user_id, "user_name": e.user_name, "rating": e.score}
        for i, e in enumerate(top)
    ]


@router.get("/topics/order")
def topic_learning_order():
    """Full recommended study order via topological sort of the topic DAG."""
    return {"order": topic_graph.topological_order()}


@router.get("/topics/next-unlocked")
def next_unlocked_topics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Topics the user can move to next, given what they've already mastered (mastery >= 0.7)."""
    rows = db.query(UserTopicProgress).filter(UserTopicProgress.user_id == current_user.id).all()
    mastered = {r.topic for r in rows if r.mastery_score >= 0.7}
    return {"mastered": sorted(mastered), "unlocked_next": topic_graph.unlocked_topics(mastered)}
