/** Source de vérité unique des statuts d'achats fournisseurs côté interface. */
export const PURCHASE_STATUS = {
  PREPARATION: 'EN_PREPARATION', SENT: 'COMMANDE_ENVOYEE',
  CONFIRMED: 'CONFIRMEE_PAR_FOURNISSEUR', RECEIVED: 'RECEPTIONNEE', CANCELLED: 'ANNULEE',
} as const
export type PurchaseStatus=typeof PURCHASE_STATUS[keyof typeof PURCHASE_STATUS]
export const PURCHASE_STATUS_LABELS:Record<PurchaseStatus,string>&{draft:string}={EN_PREPARATION:'En préparation',COMMANDE_ENVOYEE:'Commande envoyée',CONFIRMEE_PAR_FOURNISSEUR:'Confirmée par le fournisseur',RECEPTIONNEE:'Réceptionnée',ANNULEE:'Annulée',draft:'En préparation'}
export const PURCHASE_STATUS_TONES:Record<PurchaseStatus,'gray'|'blue'|'green'|'red'|'amber'>={EN_PREPARATION:'gray',COMMANDE_ENVOYEE:'blue',CONFIRMEE_PAR_FOURNISSEUR:'amber',RECEPTIONNEE:'green',ANNULEE:'red'}
export const PURCHASE_STATUS_DESCRIPTIONS:Record<PurchaseStatus,string>&{draft:string}={EN_PREPARATION:'Cet achat est en préparation et ne modifie pas le stock.',COMMANDE_ENVOYEE:'La commande est envoyée et attend la confirmation du fournisseur.',CONFIRMEE_PAR_FOURNISSEUR:'Le fournisseur a confirmé la commande. Elle peut être réceptionnée.',RECEPTIONNEE:'La réception est terminée et le stock a été mis à jour.',ANNULEE:'Cet achat est annulé et ne modifiera pas le stock.',draft:'Cet achat est en préparation et ne modifie pas le stock.'}
export const PURCHASE_STATUS_OPTIONS=(Object.values(PURCHASE_STATUS) as PurchaseStatus[]).map(value=>({value:value as string,label:PURCHASE_STATUS_LABELS[value]}))
export const purchaseStatus=(value:string):PurchaseStatus=>Object.values(PURCHASE_STATUS).includes(value as PurchaseStatus)?value as PurchaseStatus:PURCHASE_STATUS.PREPARATION
