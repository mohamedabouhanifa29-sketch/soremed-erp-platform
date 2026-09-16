"""Réponses locales, courtes et strictement filtrées par rôle JWT."""
from datetime import datetime
from sqlalchemy import func,or_,select
from sqlalchemy.orm import Session,selectinload
from app.chatbot.chatbot_intents import detect_intent
from app.chatbot.chatbot_permissions import allowed
from app.chatbot.chatbot_schemas import ChatRequest,ChatResponse,SuggestedAction
from app.models.entities import ApprovalStatus,AuditLog,ChatMessage,Client,CustomerOrder,OrderStatus,Product,Purchase,PurchaseLine,Role,StockMovement,Supplier,User

FORBIDDEN="Cette information n’est pas accessible avec votre rôle."
UNKNOWN="Je n’ai pas compris votre demande. Voici les questions disponibles pour votre rôle."
def nav(label,path):return SuggestedAction(label=label,path=path)
def ask(label,message):return SuggestedAction(label=label,message=message)

def answer_message(db:Session,user:User,payload:ChatRequest)->ChatResponse:
    intent,term,_=detect_intent(payload.message,user.role)
    if intent=="forbidden" or not allowed(user.role,intent):return save(db,user,payload.message,ChatResponse(answer=FORBIDDEN,intent="forbidden"))
    if intent=="clarification_required":return save(db,user,payload.message,ChatResponse(answer="Votre demande est ambiguë. Parlez-vous des commandes clients ou des achats fournisseurs ?",intent=intent,suggested_actions=[ask("Commandes clients","Combien de commandes clients sont en attente ?"),ask("Achats fournisseurs","Combien d’achats sont à réceptionner ?")]))
    if intent=="sensitive_action":return save(db,user,payload.message,ChatResponse(answer=f"Voulez-vous vraiment effectuer cette action sensible{f' sur {term}' if term else ''} ? Confirmez-la depuis la page métier correspondante.",intent=intent,confirmation_required=True,suggested_actions=[nav("Ouvrir la confirmation","/purchases" if term and term.startswith("ACH") else "/customer-orders")]))
    data=[];actions=[]
    # Comptages administratifs.
    count_queries={"users_count":select(func.count(User.id)),"pending_accounts_count":select(func.count(User.id)).where(User.approval_status==ApprovalStatus.PENDING),"active_clients_count":select(func.count(Client.id)).where(Client.status=="active"),"products_count":select(func.count(Product.id)),"active_suppliers_count":select(func.count(Supplier.id)).where(Supplier.status=="active"),"pending_customer_orders_count":select(func.count(CustomerOrder.id)).where(CustomerOrder.status==OrderStatus.PENDING),"pending_purchases_count":select(func.count(Purchase.id)).where(Purchase.status.in_(["ordered","awaiting_receipt"])),"low_stock_count":select(func.count(Product.id)).where(Product.stock<=Product.minimum_stock)}
    labels={"users_count":"utilisateur(s) enregistré(s)","pending_accounts_count":"compte(s) client en attente", "active_clients_count":"client(s) actif(s)","products_count":"produit(s) enregistré(s)","active_suppliers_count":"fournisseur(s) actif(s)","pending_customer_orders_count":"commande(s) client en attente de traitement", "pending_purchases_count":"achat(s) fournisseur à réceptionner","low_stock_count":"produit(s) sous leur seuil minimum"}
    if intent in count_queries:
        count=db.scalar(count_queries[intent]) or 0;answer=f"Il y a actuellement {count} {labels[intent]}.";data=[{"count":count}]
    elif intent=="total_stock":
        count=db.scalar(select(func.coalesce(func.sum(Product.stock),0))) or 0;answer=f"Le stock total est de {count} unité(s).";data=[{"total_stock":count}]
    elif intent=="purchases_total":
        total=float(db.scalar(select(func.coalesce(func.sum(Purchase.total),0))) or 0);answer=f"Le montant total des achats fournisseurs est de {total:.2f} MAD.";data=[{"total":total}]
    elif intent in {"search_product","product_price","product_availability"}:
        stmt=select(Product).where(Product.status=="active")
        if term:stmt=stmt.where(or_(Product.reference.ilike(f"%{term}%"),Product.name.ilike(f"%{term}%"),Product.barcode.ilike(f"%{term}%")))
        items=list(db.scalars(stmt.order_by(Product.name).limit(10)));data=[{"reference":x.reference,"name":x.name,"price":float(x.price),"available":x.stock>0,**({} if user.role==Role.CLIENT else {"stock":x.stock})} for x in items]
        if not items:answer="Aucun produit correspondant n’a été trouvé."
        elif intent=="product_price" and len(items)==1:answer=f"Le prix du produit {items[0].reference} est de {float(items[0].price):.2f} MAD."
        elif intent=="product_availability" and len(items)==1:answer=f"Le produit {items[0].reference} est {'disponible' if items[0].stock>0 else 'indisponible'}."
        else:answer=f"{len(items)} produit(s) disponible(s) correspondent à votre demande."
        actions=[nav("Ouvrir les produits","/client/produits" if user.role==Role.CLIENT else "/products")]
    elif intent in {"my_orders_count","my_orders_list","my_last_order","my_order_status","my_rejection_reason"}:
        if not user.client_id:items=[]
        else:
            stmt=select(CustomerOrder).where(CustomerOrder.client_id==user.client_id).order_by(CustomerOrder.created_at.desc())
            if term:stmt=stmt.where(CustomerOrder.number==term)
            items=list(db.scalars(stmt.limit(20)))
        data=[{"number":x.number,"status":x.status.value,"total":float(x.total),"rejection_reason":x.rejection_reason} for x in items]
        if intent=="my_orders_count":answer=f"Vous avez actuellement {len(items)} commande(s)."
        elif not items:answer="Aucune commande correspondante n’a été trouvée dans votre compte."
        elif intent=="my_rejection_reason":answer=f"La commande {items[0].number} a été refusée."+(f" Raison : {items[0].rejection_reason}" if items[0].rejection_reason else " Aucune raison n’a été renseignée.")
        elif intent in {"my_last_order","my_order_status"}:answer=f"Votre commande {items[0].number} est actuellement {status_label(items[0].status)}."
        else:answer=f"Voici vos {len(items)} commande(s) récente(s)."
        actions=[nav("Ouvrir mes commandes","/client/commandes")]
    elif intent=="order_status_explanation":answer="En attente : transmise au service achats. Approuvée : validée. Refusée : non retenue. En préparation : en cours de préparation. Expédiée : envoyée. Livrée : remise au client."
    elif intent=="how_to_order":answer="Ajoutez les produits au panier, vérifiez les quantités puis confirmez. Votre compte doit être approuvé et actif.";actions=[nav("Ouvrir les produits","/client/produits")]
    elif intent=="profile_help":answer="Ouvrez votre profil depuis votre nom en haut de l’écran pour modifier votre mot de passe.";actions=[nav("Ouvrir mon profil","/client/profil")]
    elif intent=="pending_customer_orders_list":
        items=list(db.scalars(select(CustomerOrder).options(selectinload(CustomerOrder.client)).where(CustomerOrder.status==OrderStatus.PENDING).order_by(CustomerOrder.created_at).limit(20)));data=[{"number":x.number,"client":x.client.name,"total":float(x.total)} for x in items];answer=f"{len(items)} commande(s) client sont à traiter.";actions=[nav("Ouvrir les commandes","/customer-orders")]
    elif intent=="pending_purchases_list":
        items=list(db.scalars(select(Purchase).options(selectinload(Purchase.supplier)).where(Purchase.status.in_(["ordered","awaiting_receipt"])).order_by(Purchase.purchase_date).limit(20)));data=[{"number":x.number,"supplier":x.supplier.name if x.supplier else None,"total":float(x.total)} for x in items];answer=f"{len(items)} achat(s) fournisseur sont à réceptionner.";actions=[nav("Ouvrir les achats","/purchases")]
    elif intent=="received_purchases_month":
        now=datetime.now();items=list(db.scalars(select(Purchase).where(Purchase.status=="received",func.strftime("%m",Purchase.received_at)==f"{now.month:02d}",func.strftime("%Y",Purchase.received_at)==str(now.year))));answer=f"{len(items)} achat(s) ont été reçus ce mois-ci.";data=[{"count":len(items)}]
    elif intent=="low_stock_products":
        items=list(db.scalars(select(Product).where(Product.stock<=Product.minimum_stock).order_by(Product.stock).limit(20)));data=[{"reference":x.reference,"name":x.name,"stock":x.stock,"minimum_stock":x.minimum_stock} for x in items];answer=f"{len(items)} produit(s) sont sous leur seuil minimum.";actions=[nav("Ouvrir le stock","/stock")]
    elif intent in {"search_supplier","search_client","search_user"}:
        model=Supplier if intent=="search_supplier" else Client if intent=="search_client" else User;stmt=select(model)
        if term:
            fields=[model.name] if model is not User else [User.full_name,User.email]
            if model is Supplier:fields+=[Supplier.company_name,Supplier.email,Supplier.ice]
            if model is Client:fields+=[Client.company_name,Client.email,Client.ice]
            stmt=stmt.where(or_(*[field.ilike(f"%{term}%") for field in fields]))
        items=list(db.scalars(stmt.limit(10)));data=[safe_party(x,intent) for x in items];answer=f"{len(items)} résultat(s) trouvé(s).";actions=[nav("Ouvrir la liste",{"search_supplier":"/suppliers","search_client":"/clients","search_user":"/users"}[intent])]
    elif intent=="last_purchase_price":
        stmt=select(PurchaseLine,Product).join(Product,PurchaseLine.product_id==Product.id).join(Purchase,PurchaseLine.purchase_id==Purchase.id)
        if term:stmt=stmt.where(or_(Product.reference.ilike(f"%{term}%"),Product.name.ilike(f"%{term}%")))
        row=db.execute(stmt.order_by(Purchase.purchase_date.desc()).limit(1)).first();answer="Aucun prix d’achat antérieur n’a été trouvé." if not row else f"Le dernier prix d’achat de {row[1].reference} est de {float(row[0].unit_price):.2f} MAD HT.";data=[] if not row else [{"reference":row[1].reference,"unit_purchase_price":float(row[0].unit_price)}]
    elif intent=="recent_stock_movements":
        items=list(db.scalars(select(StockMovement).order_by(StockMovement.created_at.desc()).limit(10)));data=[{"type":x.reference_type or x.type.value,"quantity":x.quantity,"reference":x.reference,"created_at":x.created_at.isoformat()} for x in items];answer=f"Voici les {len(items)} derniers mouvements de stock.";actions=[nav("Ouvrir le stock","/stock")]
    elif intent=="recent_audit_logs":
        items=list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10)));data=[{"action":x.action,"entity":x.entity,"created_at":x.created_at.isoformat()} for x in items];answer=f"Voici les {len(items)} dernières activités du journal.";actions=[nav("Ouvrir le journal","/audit")]
    elif intent in {"dashboard_summary","purchases_dashboard_summary"}:
        users=db.scalar(select(func.count(User.id))) or 0;clients=db.scalar(select(func.count(Client.id)).where(Client.status=="active")) or 0;products=db.scalar(select(func.count(Product.id))) or 0;orders=db.scalar(select(func.count(CustomerOrder.id)).where(CustomerOrder.status==OrderStatus.PENDING)) or 0;purchases=db.scalar(select(func.count(Purchase.id)).where(Purchase.status.in_(["ordered","awaiting_receipt"]))) or 0;low=db.scalar(select(func.count(Product.id)).where(Product.stock<=Product.minimum_stock)) or 0;suppliers=db.scalar(select(func.count(Supplier.id)).where(Supplier.status=="active")) or 0
        if intent=="dashboard_summary":answer=f"Résumé : {users} utilisateurs, {clients} clients actifs, {products} produits, {orders} commande(s) en attente et {purchases} achat(s) à réceptionner.";data=[{"users":users,"clients":clients,"products":products,"pending_orders":orders,"pending_purchases":purchases}]
        else:answer=f"Résumé Achats : {orders} commande(s) à traiter, {purchases} achat(s) à réceptionner, {low} alerte(s) stock et {suppliers} fournisseur(s) actifs.";data=[{"pending_orders":orders,"pending_purchases":purchases,"low_stock":low,"active_suppliers":suppliers}]
        actions=[nav("Ouvrir le tableau de bord","/dashboard")]
    elif intent=="help":answer=welcome(user.role);actions=suggestions(user.role)
    else:answer=UNKNOWN;actions=suggestions(user.role);intent="unknown"
    return save(db,user,payload.message,ChatResponse(answer=answer,intent=intent,data=data,suggested_actions=actions))

def suggestions(role:Role):
    if role==Role.ADMIN:return [ask("Combien d’utilisateurs ?","Combien d’utilisateurs ?"),ask("Combien de produits ?","Combien de produits ?"),ask("Comptes en attente","Combien de comptes clients sont en attente ?"),ask("Résumé","Résumé du tableau de bord")]
    if role==Role.PURCHASES:return [ask("Commandes à traiter","Commandes clients à traiter"),ask("Achats à réceptionner","Achats à réceptionner"),ask("Stock faible","Produits en stock faible"),ask("Fournisseur","Rechercher un fournisseur")]
    return [ask("Rechercher un produit","Rechercher un produit"),ask("Mes commandes","Mes commandes"),ask("Dernière commande","Statut de ma dernière commande"),ask("Comment commander ?","Comment passer une commande ?")]
def save(db,user,message,result):db.add(ChatMessage(user_id=user.id,role=user.role.value,message=message,response=result.answer,intent=result.intent));db.commit();return result
def status_label(status):return {OrderStatus.PENDING:"en attente",OrderStatus.APPROVED:"approuvée",OrderStatus.REJECTED:"refusée",OrderStatus.IN_PREPARATION:"en préparation",OrderStatus.SHIPPED:"expédiée",OrderStatus.DELIVERED:"livrée"}.get(status,status.value)
def safe_party(item,intent):
    if intent=="search_user":return {"id":item.id,"full_name":item.full_name,"email":item.email,"role":item.role.value,"is_active":item.is_active}
    return {"id":item.id,"name":item.name,"company_name":item.company_name,"email":item.email,"city":item.city,"status":item.status}
def welcome(role):return "Bonjour, je peux vous aider à consulter les utilisateurs, les produits et les statistiques." if role==Role.ADMIN else "Bonjour, je peux vous aider à consulter les commandes clients, les achats fournisseurs et le stock." if role==Role.PURCHASES else "Bonjour, je peux vous aider à rechercher un produit et consulter uniquement vos commandes."
