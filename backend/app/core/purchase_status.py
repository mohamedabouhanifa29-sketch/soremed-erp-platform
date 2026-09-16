"""Source de vérité du workflow des achats fournisseurs."""
from enum import StrEnum


class PurchaseStatus(StrEnum):
    PREPARATION = "EN_PREPARATION"
    SENT = "COMMANDE_ENVOYEE"
    CONFIRMED = "CONFIRMEE_PAR_FOURNISSEUR"
    RECEIVED = "RECEPTIONNEE"
    CANCELLED = "ANNULEE"


PURCHASE_STATUSES = {status.value for status in PurchaseStatus}
