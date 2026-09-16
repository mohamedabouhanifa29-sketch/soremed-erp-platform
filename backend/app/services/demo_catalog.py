"""Enrichissement déterministe du catalogue de démonstration, sans toucher aux stocks."""
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import Product

SUFFIXES=("via","care","med","zen","plus","ora","elis","nova","calm","fort","lix","dora","vital","nex","pure","sol","gen","lys","max","one")
LABS=("Atlas Santé Démo","NovaCare Démo","Medinova Démo","PharmaVerte Démo","Horizon Médical Démo")
CONFIG={
"Antalgique":("Dolé",("Paracétamol","Acide acétylsalicylique"),("500 mg","1 g"),("Comprimé","Sachet")),
"Anti-inflammatoire":("Inflam",("Ibuprofène","Diclofénac"),("200 mg","400 mg","50 mg"),("Comprimé","Gel")),
"Antibiotique":("Bacté",("Amoxicilline","Azithromycine","Cefixime"),("500 mg","1 g","200 mg"),("Gélule","Comprimé","Suspension buvable")),
"Vitamines":("Vita",("Vitamine C","Vitamine D3","Complexe vitamines B"),("500 mg","1000 mg","1000 UI"),("Comprimé effervescent","Gélule")),
"Digestif":("Gastro",("Oméprazole","Pantoprazole","Alginate de sodium"),("20 mg","40 mg","500 mg"),("Gélule","Comprimé","Suspension buvable")),
"Allergie":("Aller",("Loratadine","Cétirizine","Desloratadine"),("5 mg","10 mg"),("Comprimé","Sirop")),
"Diabète":("Glyco",("Metformine","Gliclazide"),("500 mg","850 mg","1000 mg"),("Comprimé","Comprimé LP")),
"Cardiologie":("Cardio",("Amlodipine","Bisoprolol","Losartan"),("5 mg","10 mg","50 mg"),("Comprimé","Comprimé sécable")),
"Hygiène":("Hygia",("Solution saline","Solution nettoyante douce"),("100 ml","250 ml","500 ml"),("Flacon","Lingettes")),
"Désinfection":("Septi",("Éthanol 70 %","Chlorhexidine"),("100 ml","250 ml","500 ml"),("Gel","Solution")),
"Ophtalmologie":("Opti",("Larmes artificielles","Hyaluronate de sodium"),("10 ml","15 ml"),("Collyre","Gel ophtalmique")),
"ORL":("Rhino",("Solution saline hypertonique","Oxymétazoline"),("10 ml","20 ml","30 ml"),("Spray nasal","Gouttes nasales")),
"Dermatologie":("Derma",("Dexpanthénol","Hydrocortisone","Clotrimazole"),("1 %","2 %","30 g"),("Crème","Pommade","Gel")),
"Pédiatrie":("Pédia",("Paracétamol pédiatrique","Solution de réhydratation"),("100 mg/5 ml","150 ml"),("Sirop","Sachet")),
"Nutrition":("Nutri",("Magnésium","Zinc","Oméga 3"),("100 mg","300 mg","1000 mg"),("Gélule","Comprimé")),
}

def enrich_demo_catalog(db:Session)->int:
    """Met à jour uniquement l'identité descriptive et le prix des produits existants."""
    products=list(db.scalars(select(Product).order_by(Product.id)))
    counters:dict[str,int]={}
    for product in products:
        category=product.category.name if product.category else "Nutrition"
        prefix,ingredients,dosages,forms=CONFIG.get(category,CONFIG["Nutrition"])
        index=counters.get(category,0);counters[category]=index+1
        ingredient=ingredients[index%len(ingredients)];dosage=dosages[(index//len(ingredients))%len(dosages)];form=forms[(index//3)%len(forms)]
        brand=f"{prefix}{SUFFIXES[index%len(SUFFIXES)]}".replace("  "," ").strip().title()
        commercial=f"{brand} {dosage}" if dosage not in brand else brand
        packaging=(f"Boîte de {10+(index%5)*10} {form.lower()}s" if form in {"Comprimé","Gélule","Comprimé LP","Comprimé sécable"} else f"{form} — {dosage}")
        product.name=commercial;product.commercial_name=commercial;product.active_ingredient=ingredient;product.dosage=dosage;product.pharmaceutical_form=form;product.packaging=packaging;product.laboratory=LABS[index%len(LABS)]
        product.description=f"Produit de démonstration {category.lower()} à base de {ingredient}. Présentation : {packaging}."
        product.price=Decimal("10.00")+Decimal(str(list(CONFIG).index(category) if category in CONFIG else 0))*Decimal("3.25")+Decimal(index)*Decimal("1.15")
    db.commit();return len(products)
