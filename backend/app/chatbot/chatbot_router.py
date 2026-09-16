"""Routes JWT de l'assistant et historique strictement privé."""
from fastapi import APIRouter,Depends,Response
from sqlalchemy import delete,select
from sqlalchemy.orm import Session
from app.chatbot.chatbot_schemas import ChatHistoryRead,ChatRequest,ChatResponse
from app.chatbot.chatbot_service import answer_message
from app.database.session import get_db
from app.models.entities import ChatMessage,User
from app.security.auth import get_current_user

router=APIRouter()

@router.post("/message",response_model=ChatResponse)
def message(payload:ChatRequest,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return answer_message(db,user,payload)

@router.get("/history",response_model=list[ChatHistoryRead])
def history(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return list(db.scalars(select(ChatMessage).where(ChatMessage.user_id==user.id).order_by(ChatMessage.created_at.desc()).limit(50)))

@router.delete("/history",status_code=204)
def clear_history(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    db.execute(delete(ChatMessage).where(ChatMessage.user_id==user.id));db.commit();return Response(status_code=204)
