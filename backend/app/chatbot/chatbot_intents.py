"""Détection ordonnée et distincte pour ADMIN, ACHATS et CLIENT."""
import re
from app.chatbot.chatbot_abbreviations import normalize_message
from app.models.entities import Role

def has(text:str,*words:str)->bool:return any(word in text for word in words)
def reference(text:str,prefix:str)->str|None:
    match=re.search(rf"\b{prefix}-[a-z0-9-]+\b",text,re.I);return match.group(0).upper() if match else None

def detect_intent(message:str,role:Role)->tuple[str,str|None,str]:
    text=normalize_message(message,role.value);cmd=reference(text,"cmd");product_ref=re.search(r"\b(?!cmd-|ach-)[a-z]{2,5}-[a-z0-9-]+\b",text,re.I)
    if has(text,"approuve","approuvee","refuse","refusee","receptionne") and "pourquoi" not in text:
        return ("forbidden",None,text) if role==Role.CLIENT else ("sensitive_action",cmd or reference(text,"ach"),text)
    # Domaines interdits : ils sont reconnus avant les intentions autorisées.
    if role!=Role.ADMIN and has(text,"utilisateur","compte administrateur","journal","audit"):return "forbidden",None,text
    if role==Role.CLIENT and has(text,"fournisseur","achat","stock faible","mouvements stock","tableau de bord","tous les clients","commandes en attente"):return "forbidden",None,text
    if role!=Role.ADMIN and has(text,"clients actifs","recherche client"):return "forbidden",None,text
    if role!=Role.CLIENT and re.search(r"\bcombien\b.*\battente\b",text) and not has(text,"commande","achat"):return "clarification_required",None,text
    detector=detect_admin if role==Role.ADMIN else detect_purchases if role==Role.PURCHASES else detect_client
    intent,term=detector(text,cmd,product_ref.group(0).upper() if product_ref else None)
    return intent,term,text

def detect_admin(text:str,cmd:str|None,product_ref:str|None)->tuple[str,str|None]:
    if has(text,"resume","tableau de bord","statistiques dashboard"):return "dashboard_summary",None
    if has(text,"journal","audit","dernieres activites"):return "recent_audit_logs",None
    if "utilisateur" in text:return ("users_count",None) if has(text,"combien","nombre") else ("search_user",clean(text,"utilisateur"))
    if "compte" in text and "attente" in text:return "pending_accounts_count",None
    if "client" in text:return ("active_clients_count",None) if has(text,"combien","nombre","actif") else ("search_client",clean(text,"client"))
    if "fournisseur" in text:return ("active_suppliers_count",None) if has(text,"combien","nombre","actif") else ("search_supplier",clean(text,"fournisseur"))
    if "commande" in text and "attente" in text:return "pending_customer_orders_count",None
    if "achat" in text and has(text,"reception","attente"):return "pending_purchases_count",None
    if "stock" in text and has(text,"faible","bas","alerte"):return "low_stock_count",None
    if "stock" in text and has(text,"total","combien"):return "total_stock",None
    if "achat" in text and has(text,"montant","total"):return "purchases_total",None
    if has(text,"produit","article"):return ("products_count",None) if has(text,"combien","nombre") else ("search_product",product_ref or clean(text,"produit","article"))
    if has(text,"aide","bonjour","salut"):return "help",None
    return "unknown",None

def detect_purchases(text:str,cmd:str|None,product_ref:str|None)->tuple[str,str|None]:
    if has(text,"resume","statistiques","service achats"):return "purchases_dashboard_summary",None
    if "commande" in text and "attente" in text:return ("pending_customer_orders_count",None) if has(text,"combien","nombre") else ("pending_customer_orders_list",None)
    if "commande" in text and has(text,"a traiter","traiter"):return "pending_customer_orders_list",None
    if "achat" in text and has(text,"reception","attente"):return ("pending_purchases_count",None) if has(text,"combien","nombre") else ("pending_purchases_list",None)
    if "achat" in text and "recu" in text and has(text,"mois","combien"):return "received_purchases_month",None
    if "stock" in text and has(text,"faible","bas","alerte"):return ("low_stock_count",None) if has(text,"combien","nombre") else ("low_stock_products",None)
    if "mouvements" in text and "stock" in text:return "recent_stock_movements",None
    if "prix" in text and "achat" in text and has(text,"produit","article"):return "last_purchase_price",product_ref or clean(text,"prix","achat","produit","article","dernier")
    if "fournisseur" in text:return "search_supplier",clean(text,"fournisseur","actif")
    if has(text,"produit","article") and has(text,"combien","nombre"):return "forbidden",None
    if has(text,"produit","article"):return "search_product",product_ref or clean(text,"produit","article")
    if has(text,"aide","bonjour","salut"):return "help",None
    return "unknown",None

def detect_client(text:str,cmd:str|None,product_ref:str|None)->tuple[str,str|None]:
    if has(text,"comment passer","comment commander"):return "how_to_order",None
    if "profil" in text:return "profile_help",None
    if has(text,"explique","signifie") and has(text,"statut","attente","approuvee","refusee"):return "order_status_explanation",None
    if "pourquoi" in text and has(text,"refusee","refus"):return "my_rejection_reason",cmd
    if cmd:return "my_order_status",cmd
    if "commande" in text and (has(text,"derniere","statut ma","statut de ma") or ("statut" in text and not cmd)):return "my_last_order",None
    if "commande" in text and has(text,"combien","nombre"):return "my_orders_count",None
    if has(text,"mes commandes","mes commande","voir ma commande","voir mes commandes"):return "my_orders_list",None
    if has(text,"prix") and has(text,"produit","article"):return "product_price",product_ref or clean(text,"prix","produit","article")
    if has(text,"disponible","indisponible") and has(text,"produit","article"):return "product_availability",product_ref or clean(text,"disponible","indisponible","produit","article","est ce que")
    if has(text,"produit","article"):return "search_product",product_ref or clean(text,"produit","article","combien","nombre")
    if has(text,"aide","bonjour","salut"):return "help",None
    return "unknown",None

def clean(text:str,*words:str)->str|None:
    for word in words:text=text.replace(word," ")
    text=re.sub(r"\b(recherche|chercher|trouve|affiche|montre|moi|quel|quelle|combien|nombre|de|du|des|un|une|le|la|les)\b"," ",text)
    value=" ".join(text.split());return value or None
