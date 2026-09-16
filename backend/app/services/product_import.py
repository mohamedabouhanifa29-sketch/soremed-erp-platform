"""Validation et import transactionnel du catalogue produits au format Excel."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from io import BytesIO
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import Category, Product

EXPECTED_COLUMNS = ["reference", "nom", "description", "categorie", "prix", "stock", "seuil_minimum", "code_barres", "statut"]
OPTIONAL_COLUMNS = ["laboratoire", "dosage", "forme_pharmaceutique", "conditionnement", "image_url"]
MODERN_COLUMNS = ["reference","commercial_name","active_ingredient","description","category","selling_price","stock","minimum_stock","barcode","status","laboratory","dosage","pharmaceutical_form","packaging","image_url"]


def text_value(value) -> str:
    if value is None: return ""
    if isinstance(value, float) and value.is_integer(): return str(int(value))
    return str(value).strip()


def decimal_value(value, field: str) -> Decimal:
    try: result = Decimal(text_value(value).replace(",", "."))
    except (InvalidOperation, ValueError): raise ValueError(f"{field} doit être un nombre")
    if result < 0: raise ValueError(f"{field} doit être supérieur ou égal à 0")
    return result


def integer_value(value, field: str) -> int:
    number = decimal_value(value, field)
    if number != number.to_integral_value(): raise ValueError(f"{field} doit être un entier")
    return int(number)


def import_products_xlsx(content: bytes, db: Session) -> dict:
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.active
    iterator = sheet.iter_rows(values_only=True)
    header = next(iterator, None)
    columns = [text_value(value).lower() for value in header] if header else []
    modern = columns == MODERN_COLUMNS
    if not modern and (not columns or columns[:len(EXPECTED_COLUMNS)] != EXPECTED_COLUMNS or any(x not in EXPECTED_COLUMNS+OPTIONAL_COLUMNS for x in columns)):
        workbook.close()
        raise ValueError("Les colonnes Excel doivent être exactement : " + ", ".join(EXPECTED_COLUMNS))

    products = {item.reference: item for item in db.scalars(select(Product))}
    categories = {item.name.strip().lower(): item for item in db.scalars(select(Category))}
    barcodes = {item.barcode: item for item in products.values() if item.barcode}
    seen_references: set[str] = set()
    result = {"created": 0, "updated": 0, "ignored": 0, "errors": []}

    for row_number, row in enumerate(iterator, start=2):
        if all(value is None or text_value(value) == "" for value in row):
            result["ignored"] += 1; continue
        if modern:
            source=dict(zip(MODERN_COLUMNS,row));values=[source.get(x) for x in ("reference","commercial_name","description","category","selling_price","stock","minimum_stock","barcode","status","laboratory","dosage","pharmaceutical_form","packaging","image_url","active_ingredient")];row_columns=EXPECTED_COLUMNS+OPTIONAL_COLUMNS+["active_ingredient"]
        else:
            values=list(row[:len(columns)])+[None]*max(0,len(columns)-len(row));row_columns=columns
        try:
            reference, name, description, category_name = (text_value(values[i]) for i in range(4))
            if not reference: raise ValueError("reference est obligatoire")
            if reference in seen_references: raise ValueError("reference dupliquée dans le fichier")
            seen_references.add(reference)
            if not name: raise ValueError("nom est obligatoire")
            if not category_name: raise ValueError("categorie est obligatoire")
            price = decimal_value(values[4], "prix")
            stock = integer_value(values[5], "stock")
            minimum_stock = integer_value(values[6], "seuil_minimum")
            barcode = text_value(values[7]) or None
            excel_status = text_value(values[8]).lower()
            if excel_status not in {"actif", "inactif", "active", "inactive"}: raise ValueError("statut doit être actif ou inactif")
            status = "active" if excel_status in {"actif", "active"} else "inactive"
            product = products.get(reference)
            if barcode and barcode in barcodes and barcodes[barcode] is not product:
                raise ValueError("code_barres déjà utilisé par un autre produit")
            category_key = category_name.lower()
            category = categories.get(category_key)
            if not category:
                category = Category(name=category_name); db.add(category); categories[category_key] = category
            if product:
                if product.barcode and product.barcode != barcode: barcodes.pop(product.barcode, None)
                result["updated"] += 1
            else:
                product = Product(reference=reference, name=name, price=price, stock=stock, minimum_stock=minimum_stock)
                db.add(product); products[reference] = product; result["created"] += 1
            product.name = name;product.commercial_name=name; product.description = description or None; product.category = category; product.price = price; product.stock = stock; product.minimum_stock = minimum_stock; product.barcode = barcode; product.status = status
            optional={name:text_value(values[index]) or None for index,name in enumerate(row_columns) if name in OPTIONAL_COLUMNS+["active_ingredient"]}
            product.active_ingredient=optional.get("active_ingredient")
            product.laboratory=optional.get("laboratoire");product.dosage=optional.get("dosage");product.pharmaceutical_form=optional.get("forme_pharmaceutique");product.packaging=optional.get("conditionnement")
            if optional.get("image_url"): product.photo_path=optional["image_url"]
            if barcode: barcodes[barcode] = product
        except ValueError as error:
            result["ignored"] += 1
            result["errors"].append({"row": row_number, "message": str(error)})
    workbook.close()
    return result
