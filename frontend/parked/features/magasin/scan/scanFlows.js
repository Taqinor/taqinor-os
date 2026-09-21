/* ============================================================================
   XSTK5 — Opérations pilotées par scan : logique métier PURE (sans JSX,
   testable au node/vitest), miroir front des 3 flux scan-first (réception,
   picking, comptage). Le scan lui-même (caméra `BarcodeScanner`/clavier-wedge
   `useKeyboardWedge`) reste dans les composants ; ce module ne fait AUCUN
   appel réseau — il consomme un code déjà résolu en produit
   (`stockApi.resolveCode`, N20/XSTK3/XSTK4 — GTIN/EAN + GS1-128/DataMatrix,
   déjà existant, réutilisé ici plutôt que dupliqué) et retourne des décisions
   pures (ligne trouvée ou non, quantité suivante, etc.).
   ========================================================================== */

// Les 3 flux partagent un mode « scan-par-unité » (chaque scan = +1) vs
// « saisie quantité » (le scan sélectionne la ligne, la quantité est saisie
// à la main). Valeurs stables utilisées comme value de <Segmented>.
export const SCAN_MODES = {
  PAR_UNITE: 'par_unite',
  SAISIE_QUANTITE: 'saisie_quantite',
}

export function scanModeOptions() {
  return [
    { value: SCAN_MODES.PAR_UNITE, label: 'Scan par unité' },
    { value: SCAN_MODES.SAISIE_QUANTITE, label: 'Saisie quantité' },
  ]
}

/**
 * Retrouve la ligne (BCF/pick-list/comptage) correspondant à un produit déjà
 * résolu (`resolveCode` renvoie `{id, ...}`). Toutes nos lignes de lignes
 * portent un champ `produit` (FK id) — comparaison stricte après coercition
 * en Number (l'id peut arriver en string depuis un formulaire).
 *
 * Renvoie `null` si aucune ligne ne porte ce produit (scan HORS-LISTE — à
 * rejeter par l'appelant, jamais silencieusement ignoré).
 */
export function matchLigneByProduitId(produitId, lignes = []) {
  const pid = Number(produitId)
  if (!Number.isFinite(pid)) return null
  return (lignes || []).find((l) => Number(l?.produit) === pid) || null
}

/**
 * Alias explicite pour le flux PICKING (FG321) — un scan hors bon de
 * prélèvement doit être REFUSÉ (erreur sonore/visuelle côté composant),
 * jamais coché sur une ligne au hasard.
 */
export function matchPickListLine(produitId, lignes = []) {
  return matchLigneByProduitId(produitId, lignes)
}

/**
 * Alias explicite pour le flux COMPTAGE (FG324) — une session ne compte que
 * les SKU déjà ajoutés (`ajouter-ligne`) ; un scan hors session est refusé.
 */
export function matchComptageLine(produitId, lignes = []) {
  return matchLigneByProduitId(produitId, lignes)
}

/**
 * Alias explicite pour le flux RÉCEPTION — un scan hors bon de commande
 * (produit absent des lignes du BCF) est refusé plutôt que de créer une
 * réception fantôme.
 */
export function matchBcfLigne(produitId, lignes = []) {
  return matchLigneByProduitId(produitId, lignes)
}

/**
 * RÉCEPTION — prochaine quantité à envoyer à `recevoirBcf` pour une ligne,
 * selon le mode. En scan-par-unité, +1 par scan (plafonné au reste dû,
 * jamais négatif). En saisie-quantité, la quantité tapée est utilisée telle
 * quelle (toujours plafonnée au reste dû — jamais plus que commandé).
 */
export function nextReceptionQuantite(ligne, { mode, saisie } = {}) {
  const restant = Math.max(
    (ligne?.quantite ?? 0) - (ligne?.quantite_recue ?? 0), 0)
  if (restant <= 0) return 0
  if (mode === SCAN_MODES.SAISIE_QUANTITE) {
    const qte = Number(saisie)
    if (!Number.isFinite(qte) || qte <= 0) return 0
    return Math.min(qte, restant)
  }
  // Scan-par-unité : +1 par scan.
  return Math.min(1, restant)
}

/**
 * PICKING — prochaine `quantite_prelevee` pour une ligne selon le mode.
 * Scan-par-unité incrémente de 1 (plafonné à `quantite_demandee`) ; en
 * saisie-quantité la valeur tapée remplace la quantité prélevée (plafonnée).
 * Renvoie aussi `preleve` (coché dès que la quantité atteint la demande).
 */
export function nextPickingState(ligne, { mode, saisie } = {}) {
  const demandee = ligne?.quantite_demandee ?? 0
  const actuelle = ligne?.quantite_prelevee ?? 0
  let quantite
  if (mode === SCAN_MODES.SAISIE_QUANTITE) {
    const qte = Number(saisie)
    quantite = Number.isFinite(qte) && qte >= 0 ? qte : actuelle
  } else {
    quantite = actuelle + 1
  }
  quantite = Math.min(quantite, demandee)
  return {
    quantite_prelevee: quantite,
    preleve: demandee > 0 ? quantite >= demandee : true,
  }
}

/**
 * COMPTAGE — prochaine `quantite_comptee` pour une ligne selon le mode.
 * Scan-par-unité incrémente depuis la valeur déjà saisie (0 si jamais
 * comptée) ; en saisie-quantité la valeur tapée remplace le compte.
 */
export function nextComptageQuantite(ligne, { mode, saisie } = {}) {
  const actuelle = ligne?.quantite_comptee ?? 0
  if (mode === SCAN_MODES.SAISIE_QUANTITE) {
    const qte = Number(saisie)
    return Number.isFinite(qte) && qte >= 0 ? qte : actuelle
  }
  return actuelle + 1
}

/**
 * Résultat d'un scan hors-liste — forme stable utilisée par les 3 panneaux
 * pour déclencher l'alerte sonore/visuelle (jamais une exception qui casse
 * le flux de scan continu).
 */
export function rejectedScan(code, reason = 'hors-liste') {
  return { ok: false, code, reason }
}

export function acceptedScan(ligne) {
  return { ok: true, ligne }
}
