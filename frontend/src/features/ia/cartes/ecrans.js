// Copilote vague 2 (FND10) — MIROIR de la table des écrans que l'assistant peut
// ouvrir (`backend/django_core/apps/agent/contract_samples/assistant_ecrans.json`,
// testé égal au contrat). Le SERVEUR construit le chemin (`GET agent/ouvrir/`) ;
// l'écran ne suit un chemin de la carte `lien_ecran` que s'il a la forme d'un
// gabarit d'ici : un chemin venu d'ailleurs (texte du modèle, lien externe,
// écran d'administration) ne donne aucun bouton. Module PUR (aucun React).

/** Gabarit de chemin par écran ; `{id}` = identifiant entier > 0. */
export const ECRANS = Object.freeze({
  lead: '/crm/leads/{id}',
  leads: '/crm/leads',
  relances_crm: '/crm/relances',
  cockpit_crm: '/crm/cockpit',
  client: '/crm?id={id}',
  devis: '/ventes/devis?devis={id}',
  devis_conception: '/ventes/devis/{id}/design',
  devis_nouveau: '/ventes/devis/nouveau?lead={id}',
  devis_a_traiter: '/ventes/devis/action-requise',
  facture: '/ventes/factures?facture={id}',
  relances_ventes: '/ventes/relances',
  paiements: '/ventes/paiements',
  cockpit_ventes: '/ventes/cockpit',
  calepinage: '/calepinage/{id}',
  visites: '/visites',
  visites_toutes: '/visites/toutes',
  visites_planifier: '/visites/planifier',
  visites_revue: '/visites/revue',
  visite: '/visites/{id}',
  visite_calage: '/visites/{id}/calage',
  chantier: '/chantiers?id={id}',
  chantiers: '/chantiers',
  approvisionnement: '/chantiers/approvisionnement',
  demandes_achat: '/chantiers/demandes-achat?chantier={id}',
  intervention: '/interventions?id={id}',
  planning: '/planification',
  ma_journee: '/ma-journee',
  ticket: '/sav?id={id}',
  sav_cockpit: '/sav/cockpit',
  sav_a_traiter: '/sav/action-requise',
  equipements: '/equipements',
  produit_mouvements: '/stock/mouvements?produit={id}',
  stock: '/stock',
  taches: '/taches',
  approbations: '/approbations',
  reporting_commercial: '/reporting/commercial',
  balance_agee: '/reporting/balance-agee',
})

/** Écrans dont le chemin peut porter `?onglet=` (calepinage seulement). */
export const ECRANS_A_ONGLETS = Object.freeze(['calepinage'])

/** Onglets du calepinage que l'assistant peut ouvrir. */
export const ONGLETS_CALEPINAGE = Object.freeze([
  'production', 'pertes', 'postes-pertes', 'reprise-visite', 'verdict-electrique',
  'approbation', 'versions', 'plan', 'documents', 'dossiers',
])

const echapper = (texte) => texte.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

function motif(ecran, gabarit) {
  const corps = echapper(gabarit).replace(echapper('{id}'), '[1-9][0-9]{0,9}')
  const onglet = ECRANS_A_ONGLETS.includes(ecran)
    ? `(?:${gabarit.includes('?') ? '&' : '\\?'}onglet=(?:${ONGLETS_CALEPINAGE.map(echapper).join('|')}))?`
    : ''
  return new RegExp(`^${corps}${onglet}$`)
}

const MOTIFS = Object.entries(ECRANS).map(([ecran, gabarit]) => motif(ecran, gabarit))

/**
 * Chemin de l'écran `ecran` pour l'objet `id` (entier > 0), construit depuis le gabarit de la
 * table — pour une carte dont la réponse du serveur porte l'identifiant sans champ `lien`.
 * `null` hors table ou sans identifiant valide.
 */
export function cheminDeLEcran(ecran, id) {
  const gabarit = Object.hasOwn(ECRANS, ecran) ? ECRANS[ecran] : null
  if (!gabarit || !Number.isInteger(id) || id <= 0) return null
  const chemin = gabarit.replace('{id}', String(id))
  return cheminAutorise(chemin) ? chemin : null
}

/** Vrai si `chemin` est un chemin INTERNE de la table (sinon : aucun bouton). */
export function cheminAutorise(chemin) {
  if (typeof chemin !== 'string' || !chemin.startsWith('/') || chemin.startsWith('//')) return false
  // Motifs ancrés (^…$) : ni espace, ni caractère de contrôle, ni « \ » ne passe.
  return MOTIFS.some((m) => m.test(chemin))
}
