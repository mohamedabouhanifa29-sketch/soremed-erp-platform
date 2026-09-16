from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy.orm import Session
from app.agent.actions import create_purchase_draft
from app.agent.confirmations import cancel as cancel_confirmation,consume
from app.agent.schemas import AgentConfirmation,AgentMessage,AgentResponse
from app.agent.service import answer
from app.database.session import get_db
from app.models.entities import User
from app.security.auth import get_current_user
from app.services.audit import record_action

router=APIRouter()

@router.post("/message",response_model=AgentResponse)
def message(payload:AgentMessage,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 return answer(db,user,payload.message,request.client.host if request.client else None)

@router.post("/confirm",response_model=AgentResponse)
def confirm(payload:AgentConfirmation,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 try:
  pending=consume(payload.confirmation_token,user.id,user.role.value)
  if pending.intent!="CREATE_PURCHASE_DRAFT":raise ValueError("Cette action ne peut pas être exécutée")
  purchase=create_purchase_draft(db,user,pending.parameters,request.client.host if request.client else None)
  return AgentResponse(type="action_completed",message=f"Le brouillon {purchase.number} a été créé. Le stock n’a pas été modifié.",data={"purchase_id":purchase.id,"number":purchase.number,"status":purchase.status},suggested_navigation="/purchases")
 except PermissionError as error:
  db.rollback();raise HTTPException(403,str(error))
 except ValueError as error:
  db.rollback();raise HTTPException(409,str(error))
 except Exception:
  db.rollback();raise

@router.post("/cancel",response_model=AgentResponse)
def cancel(payload:AgentConfirmation,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 try:pending=cancel_confirmation(payload.confirmation_token,user.id,user.role.value)
 except PermissionError as error:raise HTTPException(403,str(error))
 except ValueError as error:raise HTTPException(409,str(error))
 record_action(db,user,"agent: annulation","agent métier",None,f"intention={pending.intent}; rôle={user.role.value}",request.client.host if request.client else None);db.commit()
 return AgentResponse(type="cancelled",message="La proposition a été annulée. Aucune donnée n’a été modifiée.")
