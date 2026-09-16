"""Catalogue B2B fictif de 120 produits, déterministe et sans marque réelle."""
from decimal import Decimal
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from app.models.entities import Category, Product

SUFFIXES=("via","med","care","nova","zen","plus","ora","fort")
LABS=("Atlas Santé Démo","NovaCare Démo","Horizon Médical Démo","PharmaVerte Démo")
CATALOG=(
("Antalgiques","Dolé",("Paracétamol","Néfopam"),("500 mg","1 g"),("Comprimé","Sachet")),
("Antibiotiques","Bacté",("Amoxicilline","Azithromycine"),("500 mg","1 g"),("Gélule","Suspension buvable")),
("Cardiologie","Cardio",("Amlodipine","Bisoprolol"),("5 mg","10 mg"),("Comprimé","Comprimé sécable")),
("Diabète","Glyco",("Metformine","Gliclazide"),("500 mg","850 mg"),("Comprimé","Comprimé LP")),
("Digestif","Gastro",("Oméprazole","Alginate de sodium"),("20 mg","500 mg"),("Gélule","Suspension buvable")),
("Dermatologie","Derma",("Dexpanthénol","Clotrimazole"),("2 %","30 g"),("Crème","Pommade")),
("ORL","Rhino",("Solution saline hypertonique","Oxymétazoline"),("20 ml","30 ml"),("Spray nasal","Gouttes nasales")),
("Allergie","Aller",("Loratadine","Cétirizine"),("5 mg","10 mg"),("Comprimé","Sirop")),
("Ophtalmologie","Opti",("Hyaluronate de sodium","Larmes artificielles"),("10 ml","15 ml"),("Collyre","Gel ophtalmique")),
("Vitamines","Vita",("Vitamine C","Vitamine D3"),("1000 mg","1000 UI"),("Comprimé effervescent","Gélule")),
("Gynécologie","Gyné",("Clotrimazole","Acide folique"),("100 mg","400 µg"),("Comprimé vaginal","Comprimé")),
("Urologie","Uro",("Tamsulosine","Citrate de potassium"),("0,4 mg","1 g"),("Gélule LP","Sachet")),
("Pneumologie","Pulmo",("Salbutamol","Acétylcystéine"),("100 µg","200 mg"),("Aérosol-doseur","Sachet")),
("Neurologie","Neuro",("Prégabaline","Bétahistine"),("75 mg","16 mg"),("Gélule","Comprimé")),
("Matériel médical","Medi",("Dispositif médical","Sans principe actif"),("Taille standard","Usage unique"),("Dispositif","Kit")),
("Hygiène","Hygia",("Solution nettoyante douce","Solution saline"),("250 ml","500 ml"),("Flacon","Lingettes")),
("Consommables","Conso",("Sans principe actif","Matériau médical"),("Taille M","Taille L"),("Boîte","Sachet")),
)

def install_professional_catalog(db:Session)->dict[str,int]:
    products=list(db.scalars(select(Product).order_by(Product.id).limit(120)))
    if len(products)<120:raise RuntimeError("La base doit contenir au moins 120 produits")
    keep_ids={p.id for p in products}
    db.execute(update(Product).values(barcode=None));db.flush()
    referenced={row[0] for row in db.execute(select(Product.id).where(Product.id.in_(keep_ids)))}
    categories={c.name:c for c in db.scalars(select(Category))}
    for index,product in enumerate(products):
        category_name,prefix,ingredients,dosages,forms=CATALOG[index%len(CATALOG)];variant=index//len(CATALOG)
        category=categories.get(category_name)
        if not category:category=Category(name=category_name);db.add(category);categories[category_name]=category
        ingredient=ingredients[variant%len(ingredients)];dosage=dosages[(variant//2)%len(dosages)];form=forms[(variant//3)%len(forms)];commercial=f"{prefix}{SUFFIXES[variant%len(SUFFIXES)]}".title()+f" {dosage}"
        packaging=f"Boîte de {10+(variant%4)*10} unités" if form in {"Comprimé","Gélule","Comprimé LP","Comprimé sécable","Comprimé vaginal","Gélule LP"} else f"{form} — {dosage}"
        product.reference=f"MED-{index+1:04d}";product.name=commercial;product.commercial_name=commercial;product.active_ingredient=ingredient;product.category=category;product.description=f"Produit fictif de démonstration de la catégorie {category_name.lower()}, à base de {ingredient}. Présentation : {packaging}.";product.dosage=dosage;product.pharmaceutical_form=form;product.packaging=packaging;product.laboratory=LABS[(index+variant)%len(LABS)];product.price=Decimal("12.00")+Decimal(index%17)*Decimal("3.20")+Decimal(variant)*Decimal("1.35");product.minimum_stock=5+(index%4)*5;product.status="active";product.barcode=f"611{index+1:010d}";product.photo_path=None
    removed=db.execute(delete(Product).where(Product.id.not_in(keep_ids))).rowcount or 0
    db.flush()
    db.execute(delete(Category).where(~Category.products.any()))
    db.commit()
    return {"kept":len(products),"removed":removed,"referenced_kept":len(referenced)}
