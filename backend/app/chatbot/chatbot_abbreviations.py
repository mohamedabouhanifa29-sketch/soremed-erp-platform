"""Normalisation linguistique contrôlée, indépendante des permissions métier."""
import re
import unicodedata

ABBREVIATIONS={"cmb":"combien","cb":"combien","nb":"nombre","nbr":"nombre","cmd":"commande","cmds":"commandes","cde":"commande","cdes":"commandes","prod":"produit","prods":"produits","prd":"produit","art":"article","util":"utilisateur","utils":"utilisateurs","usr":"utilisateur","users":"utilisateurs","cli":"client","clt":"client","clts":"clients","frs":"fournisseur","four":"fournisseur","fourn":"fournisseur","fourns":"fournisseurs","stck":"stock","stk":"stock","ach":"achat","rec":"reception","recept":"reception","att":"attente","appr":"approuvee","ref":"reference","refs":"references","ajd":"aujourd hui","auj":"aujourd hui","mnt":"maintenant","der":"dernier","info":"information","infos":"informations","stat":"statut","stats":"statistiques","dispo":"disponible","indispo":"indisponible","mouv":"mouvements"}
DARJA_ALIASES={"ch7al":"combien","wach":"est ce que","fin":"ou","wslet":"statut","dyali":"ma","3lach":"pourquoi","trfdat":"refusee","bghit":"je veux","nchof":"voir","ga3":"tous"}
COMMON_TYPOS={"utilisater":"utilisateur","utiliseteur":"utilisateur","produi":"produit","comande":"commande","commnde":"commande","fourniseur":"fournisseur","stok":"stock","aprouvee":"approuvee","refuse":"refusee"}

def normalize_message(message:str,role:str|None=None)->str:
    """Préserve les références, retire accents/ponctuation puis étend les alias connus."""
    value="".join(c for c in unicodedata.normalize("NFD",message.lower()) if unicodedata.category(c)!="Mn")
    value=re.sub(r"\b([a-z]{2,4})\s+(\d{3,})\b",r"\1-\2",value)
    value=re.sub(r"[^a-z0-9@._\-\s]"," ",value)
    tokens=value.split();expanded=[]
    for index,token in enumerate(tokens):
        replacement=DARJA_ALIASES.get(token,COMMON_TYPOS.get(token,ABBREVIATIONS.get(token,token)))
        if token=="app":replacement="approuvee" if index>0 and tokens[index-1] in {"cmd","commande"} else "application"
        expanded.extend(replacement.split())
    normalized=" ".join(expanded)
    normalized=re.sub(r"\ben\s+attente\b","en attente",normalized)
    return re.sub(r"\s+"," ",normalized).strip()
