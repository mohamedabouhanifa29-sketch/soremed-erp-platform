from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.purchase_status import PurchaseStatus
from app.models.entities import Product,Purchase,PurchaseLine,Supplier,SupplierProduct,User
from app.services.audit import record_action

def restock_preview(db:Session)->dict:
 products=list(db.scalars(select(Product).where(Product.status=="active",Product.stock<=Product.minimum_stock).order_by(Product.stock,Product.name)))
 prices=list(db.scalars(select(SupplierProduct).where(SupplierProduct.is_active.is_(True))))
 by_product={};coverage={}
 for price in prices:
  by_product.setdefault(price.product_id,[]).append(price);coverage[price.supplier_id]=coverage.get(price.supplier_id,0)+1
 supplier_id=max(coverage,key=coverage.get) if coverage else None
 supplier=db.get(Supplier,supplier_id) if supplier_id else None
 items=[];missing=[]
 for product in products:
  target=max(product.minimum_stock*2,product.minimum_stock+1);quantity=max(0,target-product.stock)
  match=next((x for x in by_product.get(product.id,[]) if x.supplier_id==supplier_id),None)
  price=Decimal(match.purchase_price) if match else Decimal("0")
  row={"product_id":product.id,"reference":product.reference,"name":product.commercial_name or product.name,"current_stock":product.stock,"minimum_stock":product.minimum_stock,"target_stock":target,"quantity":quantity,"unit_price":float(price),"line_total":float(price*quantity)}
  if quantity and price>0:items.append(row)
  else:missing.append({"product_id":product.id,"name":product.name,"reason":"prix d'achat ou fournisseur indisponible"})
 return {"supplier_id":supplier.id if supplier else None,"supplier":supplier.name if supplier else None,"items":items,"missing_items":missing,"estimated_total":round(sum(x["line_total"] for x in items),2),"warning":"Cette action créera uniquement un brouillon. Le stock ne sera pas modifié."}

def create_purchase_draft(db:Session,user:User,parameters:dict,ip:str|None=None)->Purchase:
 supplier_id=parameters.get("supplier_id");items=parameters.get("items") or []
 if not supplier_id or not db.get(Supplier,supplier_id):raise ValueError("Le fournisseur proposé n'est plus disponible")
 if not items:raise ValueError("Aucune ligne valide à enregistrer")
 purchase=Purchase(number=f"AGT-{datetime.now():%Y%m%d}-{uuid4().hex[:6].upper()}",supplier_id=supplier_id,status=PurchaseStatus.PREPARATION,created_by=user.id,subtotal=Decimal("0"),tax_amount=Decimal("0"),total=Decimal("0"),notes="Brouillon proposé et confirmé depuis l'agent métier")
 subtotal=Decimal("0")
 for item in items:
  product=db.get(Product,int(item["product_id"]));quantity=int(item["quantity"]);price=Decimal(str(item["unit_price"]))
  if not product or quantity<=0 or price<0:raise ValueError("Une ligne de la proposition n'est plus valide")
  total=price*quantity;subtotal+=total;purchase.lines.append(PurchaseLine(product_id=product.id,quantity=quantity,received_quantity=0,unit_price=price,discount=0,tax_rate=0,line_total=total,tax_amount=0,total_amount=total))
 purchase.subtotal=subtotal;purchase.total=subtotal;db.add(purchase);db.flush();record_action(db,user,"agent: création brouillon","achat fournisseur",purchase.id,f"intention=CREATE_PURCHASE_DRAFT; numéro={purchase.number}; lignes={len(items)}; rôle={user.role.value}",ip);db.commit();db.refresh(purchase);return purchase
