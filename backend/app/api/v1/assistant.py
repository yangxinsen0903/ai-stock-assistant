from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.models import User
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.assistant import ChatRequest, ChatResponse
from app.services.recommendation_service import RecommendationService


router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    reply = RecommendationService.generate_reply(db, current_user, payload.message)
    return ChatResponse(reply=reply)
