/* ============================================================================
   NTIDE9 — Détection du contexte courant à partir de l'URL.
   ----------------------------------------------------------------------------
   Contexte (ex. « leads → CRM ») : dérivé du premier segment du chemin, pour
   TOUT écran de l'ERP — table de correspondance simple, extensible sans
   toucher aux autres apps.
   ========================================================================== */

const CONTEXTE_PAR_PREFIXE = [
  ['/crm', 'CRM'],
  ['/ventes/devis', 'Devis'],
  ['/ventes', 'Ventes'],
  ['/sav', 'SAV'],
  ['/chantiers', 'Chantiers'],
  ['/interventions', 'Chantiers'],
  ['/stock', 'Stock'],
  ['/achats', 'Achats'],
  ['/compta', 'Comptabilité'],
  ['/rh', 'RH'],
  ['/paie', 'Paie'],
  ['/qhse', 'QHSE'],
  ['/kb', 'Base de connaissances'],
  ['/litiges', 'Litiges'],
  ['/contrats', 'Contrats'],
  ['/parametres', 'Paramètres'],
]

/** Contexte FR lisible dérivé du chemin courant (NTIDE9), ou '' si inconnu. */
export function contexteFromPath(pathname) {
  const p = pathname || ''
  const match = CONTEXTE_PAR_PREFIXE.find(([prefix]) => p.startsWith(prefix))
  return match ? match[1] : ''
}
