"""Intentions strictement cloisonnées selon le rôle issu du JWT."""
from app.models.entities import Role

ROLE_INTENTS={
 Role.ADMIN:{"sensitive_action","users_count","pending_accounts_count","active_clients_count","products_count","active_suppliers_count","pending_customer_orders_count","pending_purchases_count","low_stock_count","total_stock","purchases_total","recent_audit_logs","search_user","search_product","search_client","search_supplier","dashboard_summary","help","unknown","clarification_required","forbidden"},
 Role.PURCHASES:{"sensitive_action","pending_customer_orders_count","pending_customer_orders_list","pending_purchases_count","pending_purchases_list","received_purchases_month","low_stock_count","low_stock_products","search_product","search_supplier","last_purchase_price","recent_stock_movements","purchases_dashboard_summary","help","unknown","clarification_required","forbidden"},
 Role.CLIENT:{"search_product","product_price","product_availability","my_orders_count","my_orders_list","my_last_order","my_order_status","my_rejection_reason","order_status_explanation","how_to_order","profile_help","help","unknown","forbidden"},
}
def allowed(role:Role,intent:str)->bool:return intent in ROLE_INTENTS[role]
