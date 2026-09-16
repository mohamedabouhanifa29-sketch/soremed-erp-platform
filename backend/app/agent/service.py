from sqlalchemy import func,or_,select
from sqlalchemy.orm import Session,selectinload
from app.agent.actions import restock_preview
from app.agent.confirmations import create
from app.agent.intents import detect
from app.agent.permissions import allowed
from app.agent.schemas import AgentResponse
from app.core.purchase_status import PurchaseStatus
from app.models.entities import Client,CustomerOrder,OrderStatus,Product,Purchase,Role,Supplier,User
from app.services.audit import record_action

UNKNOWN="Je n’ai pas compris précisément la demande. Vous pouvez me demander le stock d’un produit, les commandes en attente, les achats à réceptionner ou une proposition de réapprovisionnement."
def audit(db:Session,user:User,message:str,intent:str,result:str,ip:str|None):
 record_action(db,user,"agent: message","agent métier",None,f"rôle={user.role.value}; intention={intent}; résultat={result}; message={message[:300]}",ip);db.commit()

def answer(db:Session,user:User,message:str,ip:str|None=None)->AgentResponse:
 intent,query=detect(message)
 if intent in {"UNKNOWN","FORBIDDEN"}:audit(db,user,message,intent,"refusé",ip);return AgentResponse(type="error",message=UNKNOWN if intent=="UNKNOWN" else "Votre rôle ne permet pas cette action.")
 if not allowed(user.role,intent):audit(db,user,message,intent,"interdit",ip);return AgentResponse(type="error",message="Votre rôle ne permet pas cette action.")
 response:AgentResponse
 if intent=="PRODUCT_SEARCH":
  stmt=select(Product).where(Product.status=="active");
  if query:stmt=stmt.where(or_(Product.name.ilike(f"%{query}%"),Product.commercial_name.ilike(f"%{query}%"),Product.reference.ilike(f"%{query}%")))
  items=list(db.scalars(stmt.order_by(Product.name).limit(20)));data=[{"id":x.id,"reference":x.reference,"name":x.commercial_name or x.name,"price":float(x.price),"available":x.stock>0} for x in items];response=AgentResponse(type="answer",message=f"J’ai trouvé {len(items)} produit(s).",data=data,suggested_navigation="/client/produits" if user.role==Role.CLIENT else "/products")
 elif intent=="PRODUCT_STOCK":
  if not query:response=AgentResponse(type="answer",message="Précisez le nom ou la référence du produit.")
  else:
   product=db.scalar(select(Product).where(or_(Product.name.ilike(f"%{query}%"),Product.commercial_name.ilike(f"%{query}%"),Product.reference.ilike(f"%{query}%"))).limit(1));response=AgentResponse(type="answer",message=(f"{product.commercial_name or product.name} est {'disponible' if product.stock>0 else 'indisponible'}." if user.role==Role.CLIENT and product else f"Stock de {product.commercial_name or product.name} : {product.stock} unité(s)." if product else "Produit introuvable."),data=({"id":product.id,"available":product.stock>0} if product else None))
 elif intent=="LOW_STOCK_PRODUCTS":
  items=list(db.scalars(select(Product).where(Product.status=="active",Product.stock<=Product.minimum_stock).order_by(Product.stock)));response=AgentResponse(type="answer",message=f"{len(items)} produit(s) sont sous le seuil minimum.",data=[{"id":x.id,"reference":x.reference,"name":x.commercial_name or x.name,"stock":x.stock,"minimum_stock":x.minimum_stock} for x in items],suggested_navigation="/stock/alerts")
 elif intent=="ACTIVE_SUPPLIERS":
  count=db.scalar(select(func.count(Supplier.id)).where(Supplier.status=="active")) or 0;response=AgentResponse(type="answer",message=f"{count} fournisseur(s) actif(s).",data={"count":count},suggested_navigation="/suppliers")
 elif intent=="PENDING_CUSTOMER_ORDERS":
  items=list(db.scalars(select(CustomerOrder).where(CustomerOrder.status==OrderStatus.PENDING).order_by(CustomerOrder.created_at.desc()).limit(20)));response=AgentResponse(type="answer",message=f"{len(items)} commande(s) client sont en attente.",data=[{"id":x.id,"number":x.number,"total":float(x.total)} for x in items],suggested_navigation="/customer-orders")
 elif intent=="PURCHASES_TO_RECEIVE":
  items=list(db.scalars(select(Purchase).where(Purchase.status==PurchaseStatus.CONFIRMED).order_by(Purchase.purchase_date).limit(20)));response=AgentResponse(type="answer",message=f"{len(items)} achat(s) sont à réceptionner.",data=[{"id":x.id,"number":x.number,"total":float(x.total)} for x in items],suggested_navigation="/receipts")
 elif intent in {"MY_ORDERS","ORDER_STATUS"} and user.role==Role.CLIENT:
  items=list(db.scalars(select(CustomerOrder).where(CustomerOrder.client_id==user.client_id).order_by(CustomerOrder.created_at.desc()).limit(20)));shown=items[:1] if intent=="ORDER_STATUS" else items;response=AgentResponse(type="answer",message=(f"Votre dernière commande {shown[0].number} est au statut {shown[0].status.value}." if shown and intent=="ORDER_STATUS" else f"Vous avez {len(items)} commande(s)."),data=[{"id":x.id,"number":x.number,"status":x.status.value,"total":float(x.total)} for x in shown],suggested_navigation="/client/commandes")
 elif intent=="DASHBOARD_SUMMARY":
  products=db.scalar(select(func.count(Product.id))) or 0;orders=db.scalar(select(func.count(CustomerOrder.id))) or 0;purchases=db.scalar(select(func.count(Purchase.id))) or 0;response=AgentResponse(type="answer",message=f"Résumé : {products} produits, {orders} commandes clients et {purchases} achats fournisseurs.",data={"products":products,"orders":orders,"purchases":purchases},suggested_navigation="/dashboard")
 elif intent in {"RESTOCK_PROPOSAL","CREATE_PURCHASE_DRAFT"}:
  preview=restock_preview(db)
  if intent=="RESTOCK_PROPOSAL":response=AgentResponse(type="answer",message=f"Proposition calculée pour {len(preview['items'])} produit(s), selon un stock cible égal à deux fois le seuil minimum.",data=preview)
  elif not preview["supplier_id"] or not preview["items"]:response=AgentResponse(type="error",message="Je peux préparer le brouillon, mais aucun fournisseur ou prix d’achat exploitable n’est associé aux produits concernés.",preview=preview)
  else:
   token=create(user.id,user.role.value,intent,preview);response=AgentResponse(type="confirmation_required",message=f"J’ai trouvé {len(preview['items'])} produit(s). Je peux créer un brouillon d’achat. Aucune commande ne sera envoyée et le stock ne sera pas modifié.",action=intent,confirmation_token=token,preview=preview)
 elif intent=="GENERATE_REPORT":response=AgentResponse(type="answer",message="Les rapports existants sont prêts à être générés depuis la page Rapports.",suggested_navigation="/reports")
 elif intent=="NAVIGATE":
  pages={"produit":"/products","commande":"/customer-orders","achat":"/purchases","stock":"/stock/inventory","fournisseur":"/suppliers","rapport":"/reports"};path=next((v for k,v in pages.items() if k in (query or "")),"/dashboard");response=AgentResponse(type="answer",message="Vous pouvez ouvrir la page demandée.",suggested_navigation=path)
 else:response=AgentResponse(type="error",message=UNKNOWN)
 audit(db,user,message,intent,response.type,ip);return response
