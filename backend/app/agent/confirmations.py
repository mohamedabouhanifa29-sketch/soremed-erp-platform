from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from secrets import token_urlsafe
from threading import Lock
from typing import Any

@dataclass
class PendingConfirmation:
 user_id:int;role:str;intent:str;parameters:dict[str,Any];expires_at:datetime

_pending:dict[str,PendingConfirmation]={};_lock=Lock()
def create(user_id:int,role:str,intent:str,parameters:dict[str,Any])->str:
 token=token_urlsafe(32)
 with _lock:_pending[token]=PendingConfirmation(user_id,role,intent,parameters,datetime.now(timezone.utc)+timedelta(minutes=10))
 return token
def consume(token:str,user_id:int,role:str)->PendingConfirmation:
 with _lock:
  item=_pending.get(token)
  if not item:raise ValueError("Confirmation introuvable ou déjà utilisée")
  if item.expires_at<datetime.now(timezone.utc):
   _pending.pop(token,None);raise ValueError("La confirmation a expiré")
  if item.user_id!=user_id or item.role!=role:raise PermissionError("Cette confirmation appartient à un autre utilisateur")
  _pending.pop(token,None);return item
def cancel(token:str,user_id:int,role:str)->PendingConfirmation:
 return consume(token,user_id,role)
