from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.mysql import get_db
from app.ml.recommender import recommend_next_question
from app.models.user import User

router = APIRouter(tags=["ml-features"])

@router.get("/recommend/next-question")
async def next_question(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await recommend_next_question(db, current_user.id, current_user.rating)
