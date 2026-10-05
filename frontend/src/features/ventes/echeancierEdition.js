// QJR624 (D-QJR5-10) — l'échéancier d'un devis (acompte / matériel / solde)
// tel que l'Édition complète l'édite et que le dialogue PDF y écrit l'acompte
// personnalisé. La forme serveur est celle de `serializers.validate_echeancier`
// (`[{libelle, type, unite, pct_or_montant}]`, unité pct | montant — QJR21) ;
// la dernière tranche vaut le RESTE côté serveur (`utils/echeancier.next_tranche`).

export const UNITE_PCT = 'pct'
export const UNITE_MONTANT = 'montant'

// Défauts documentés de `utils/echeancier.py` (PAYMENT_TERMS_BY_MODE) — servent
// seulement de point de départ quand le commercial personnalise un devis qui
// n'a pas encore d'échéancier propre (le serveur garde sinon celui de la société).
const DEFAUTS = {
  residentiel: [30, 60, 10],
  agricole: [30, 60, 10],
  industriel: [50, 40, 10],
  commercial: [50, 40, 10],
}

const LIBELLES = [
  ['Acompte', 'acompte'],
  ['Livraison du matériel', 'materiel'],
  ['Solde', 'solde'],
]

export const LIBELLE_SOLDE_AGRICOLE = 'Solde après récolte'

const MOTS_MONTANT = new Set(['montant', 'mad', 'dh', 'dhs', 'amount', 'fixe'])

function nombre(v) {
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? '').replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

function arrondi2(n) {
  return Math.round(n * 100) / 100
}

/** Échéancier par défaut (saisie) pour un mode d'installation. */
export function saisieParDefaut(mode) {
  const pcts = DEFAUTS[mode] || DEFAUTS.residentiel
  return LIBELLES.map(([libelle, type], i) => ({
    // AGR220 — en agricole, le solde se règle après la récolte (modifiable).
    libelle: mode === 'agricole' && type === 'solde' ? LIBELLE_SOLDE_AGRICOLE : libelle,
    type, unite: UNITE_PCT, valeur: String(pcts[i]), date_prevue: '',
  }))
}

/** `Devis.echeancier` (serveur) → lignes de saisie, ou `null` (aucun
 *  échéancier propre : le devis suit celui de la société). */
export function echeancierVersSaisie(echeancier) {
  if (!Array.isArray(echeancier) || echeancier.length === 0) return null
  return echeancier.map((t, i) => {
    const declaree = String(t?.unite ?? '').trim().toLowerCase()
    const valeur = nombre(t?.pct_or_montant)
    const unite = MOTS_MONTANT.has(declaree) ? UNITE_MONTANT
      : declaree ? UNITE_PCT
        : (valeur > 100 ? UNITE_MONTANT : UNITE_PCT)
    return {
      libelle: t?.libelle || LIBELLES[i]?.[0] || `Tranche ${i + 1}`,
      type: t?.type && !MOTS_MONTANT.has(String(t.type).toLowerCase())
        ? t.type : (LIBELLES[i]?.[1] || ''),
      unite,
      valeur: String(t?.pct_or_montant ?? ''),
      // AGR220 — date facultative (AAAA-MM-JJ) relue telle que le serveur la sert.
      date_prevue: typeof t?.date_prevue === 'string' ? t.date_prevue : '',
    }
  })
}

/** Lignes de saisie → `Devis.echeancier` (serveur). `null` → `[]` (retour à
 *  l'échéancier de la société). */
export function saisieVersEcheancier(saisie) {
  if (!Array.isArray(saisie)) return []
  return saisie.map((t) => {
    const tranche = {
      libelle: t.libelle,
      type: t.type,
      unite: t.unite === UNITE_MONTANT ? UNITE_MONTANT : UNITE_PCT,
      pct_or_montant: nombre(t.valeur),
    }
    // AGR220 — `date_prevue` seulement si saisie (le serveur l'omet quand null :
    // enregistrer sans toucher redonne l'échéancier serveur à l'identique).
    const d = String(t.date_prevue ?? '').trim()
    if (d) tranche.date_prevue = d
    return tranche
  })
}

/** Somme des pourcentages quand toutes les tranches sont en %, sinon `null`. */
export function sommePourcentages(saisie) {
  if (!Array.isArray(saisie) || saisie.some(t => t.unite !== UNITE_PCT)) return null
  return arrondi2(saisie.reduce((s, t) => s + nombre(t.valeur), 0))
}

/** L'« acompte personnalisé » du dialogue PDF écrit dans l'échéancier : la
 *  première tranche devient `montant` MAD ; sur un échéancier à trois
 *  tranches en %, le matériel absorbe l'écart (le solde garde son %), comme
 *  l'ancien mode « personnalisé » du rendu. */
export function echeancierAvecAcompte(echeancier, montant, totalTtc, mode) {
  const base = echeancierVersSaisie(echeancier) || saisieParDefaut(mode)
  const acompte = Math.max(0, nombre(montant))
  const saisie = base.map(t => ({ ...t }))
  saisie[0] = { ...saisie[0], unite: UNITE_MONTANT, valeur: String(acompte) }
  const total = nombre(totalTtc)
  if (saisie.length === 3 && total > 0
      && saisie[1].unite === UNITE_PCT && saisie[2].unite === UNITE_PCT) {
    const pctAcompte = (acompte / total) * 100
    const pctSolde = nombre(saisie[2].valeur)
    saisie[1] = { ...saisie[1],
                  valeur: String(Math.max(0, arrondi2(100 - pctSolde - pctAcompte))) }
  }
  return saisieVersEcheancier(saisie)
}
