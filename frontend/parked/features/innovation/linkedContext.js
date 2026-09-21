/* ============================================================================
   NTIDE9/NTIDE11 — Détection du contexte courant à partir de l'URL.
   ----------------------------------------------------------------------------
   Contexte (NTIDE9, ex. « leads → CRM ») : dérivé du premier segment du
   chemin, pour TOUT écran de l'ERP — table de correspondance simple,
   extensible sans toucher aux autres apps.

   Idée liée (NTIDE11, string-FK opaque devis/ticket/chantier) : détectée
   UNIQUEMENT quand l'URL porte explicitement l'identifiant du document ouvert
   (``?edit=<id>`` sur /ventes/devis, patron déjà utilisé par DevisList/
   DevisGenerator). Aucune détection inventée pour ticket/chantier tant que ces
   écrans ne portent pas eux-mêmes un signal d'URL équivalent — mieux vaut ne
   rien pré-remplir que de deviner faux (l'utilisateur reste libre de choisir
   le contexte manuellement).
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

/** Idée liée pré-détectée (NTIDE11) : {type, id} ou null. */
export function linkedFromLocation(pathname, search) {
  const params = new URLSearchParams(search || '')
  if ((pathname || '').startsWith('/ventes/devis')) {
    const editId = params.get('edit')
    if (editId) return { type: 'devis', id: editId }
  }
  return null
}
