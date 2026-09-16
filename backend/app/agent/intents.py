import re
import unicodedata

ABBREVIATIONS={"cmd":"commande","cmds":"commandes","prod":"produit","prd":"produit","stk":"stock","qte":"quantite","qté":"quantite","frs":"fournisseur","fourn":"fournisseur","ach":"achat","rec":"reception","ref":"reference","stat":"statut","liv":"livraison","dispo":"disponible","cmb":"combien"}
def normalize(message:str)->str:
 text=unicodedata.normalize("NFKD",message.lower()).encode("ascii","ignore").decode()
 words=re.findall(r"[a-z0-9-]+",text)
 return " ".join(ABBREVIATIONS.get(word,word) for word in words)

def detect(message:str)->tuple[str,str|None]:
 text=normalize(message)
 if any(x in text for x in ("ignore les instructions","mot de passe","token","fichier env","execute sql","execute python")):return "FORBIDDEN",None
 if "rapport" in text or "export" in text:return "GENERATE_REPORT",None
 if any(x in text for x in ("proposition de reappro","reapprovisionnement","produits en rupture","sous le stock minimum","sous le seuil")) and any(x in text for x in ("prepare","propose","brouillon","achat")):return ("CREATE_PURCHASE_DRAFT" if "brouillon" in text or "prepare" in text else "RESTOCK_PROPOSAL"),None
 if "stock faible" in text or "sous le stock minimum" in text or "sous le seuil" in text:return "LOW_STOCK_PRODUCTS",None
 if "achat" in text and any(x in text for x in ("recevoir","receptionner","a recevoir")):return "PURCHASES_TO_RECEIVE",None
 if "fournisseur" in text and any(x in text for x in ("actif","combien","nombre")):return "ACTIVE_SUPPLIERS",None
 if "mes commandes" in text:return "MY_ORDERS",None
 if "derniere commande" in text or ("statut" in text and "commande" in text):return "ORDER_STATUS",None
 if "commande" in text and any(x in text for x in ("attente","traiter")):return "PENDING_CUSTOMER_ORDERS",None
 if "resume" in text or "tableau de bord" in text:return "DASHBOARD_SUMMARY",None
 if any(x in text for x in ("ouvre ","aller ","affiche la page")):return "NAVIGATE",text
 if "stock" in text:
  query=text.replace("stock"," ").replace("disponible"," ").strip();return "PRODUCT_STOCK",query or None
 if "produit" in text:
  query=text.replace("combien"," ").replace("produits"," ").replace("produit"," ").strip();return "PRODUCT_SEARCH",query or None
 return "UNKNOWN",None
