/* ============================================================================
   LOGISTIQUE (XSTK2) — logique métier PURE (sans JSX, testable au node).
   ----------------------------------------------------------------------------
   Miroir front des choix de statut backend (`models_livraison.py`,
   `models_comptage.py`, `models_demande_transfert.py`) + petits helpers de
   présentation (regroupement des écarts de comptage, rendu de la tournée
   proposée FG332). Aucune dépendance React : alimente les écrans ET les tests
   unitaires. Ne JAMAIS diverger des libellés backend (TextChoices).
   ========================================================================== */

// ── Libellés de statut (copie fidèle des TextChoices backend) ──

export const LIVRAISON_STATUTS = {
  planifiee: 'Planifiée',
  en_transit: 'En transit',
  livree: 'Livrée',
  annulee: 'Annulée',
}

export const MODE_ACHEMINEMENT = {
  depot: 'Via le dépôt',
  direct_site: 'Direct site',
}

export const SESSION_COMPTAGE_STATUTS = {
  planifie: 'Planifié',
  en_cours: 'En cours',
  termine: 'Terminé',
}

export const CLASSE_ABC = {
  A: 'A (forte valeur)',
  B: 'B (valeur moyenne)',
  C: 'C (faible valeur)',
  toutes: 'Toutes',
}

export const DEMANDE_TRANSFERT_STATUTS = {
  demande: 'Demandée',
  approuve: 'Approuvée',
  refuse: 'Refusée',
  execute: 'Exécutée',
}

// Options {value,label} pour un <Select>/<Segmented> à partir d'un map de choix.
export function optionsFrom(map) {
  return Object.entries(map).map(([value, label]) => ({ value, label }))
}

// ── FG332 — tournée de livraison proposée ──

/**
 * Normalise la réponse de `GET tournee-livraison/` (FG332) en une liste
 * d'arrêts numérotés pour l'affichage, en gardant les livraisons non
 * géolocalisées à la fin (non ordonnables) — jamais de crash sur une réponse
 * absente/partielle.
 */
export function tourneeToStops(tournee) {
  const ordonnees = Array.isArray(tournee?.ordre) ? tournee.ordre
    : Array.isArray(tournee?.itineraire) ? tournee.itineraire
    : Array.isArray(tournee) ? tournee
    : []
  const sansGps = Array.isArray(tournee?.sans_gps) ? tournee.sans_gps : []
  const stops = ordonnees.map((liv, i) => ({
    position: i + 1,
    livraisonId: liv.livraison_id ?? liv.id,
    reference: liv.reference ?? '—',
    installationId: liv.installation_id ?? null,
    gpsLat: liv.gps_lat ?? null,
    gpsLng: liv.gps_lng ?? null,
    geolocalisee: true,
  }))
  const nonGeoloc = sansGps.map((liv) => ({
    position: null,
    livraisonId: liv.livraison_id ?? liv.id,
    reference: liv.reference ?? '—',
    installationId: liv.installation_id ?? null,
    gpsLat: null,
    gpsLng: null,
    geolocalisee: false,
  }))
  return [...stops, ...nonGeoloc]
}

// ── FG324 — comptages cycliques : regroupement par écart ──

/**
 * Écart d'une ligne de comptage (comptée − théorique), ou `null` si pas
 * encore compté. Miroir de la `@property ecart` backend — tolère une ligne
 * partielle/absente.
 */
export function ecartLigne(ligne) {
  const comptee = ligne?.quantite_comptee
  if (comptee == null) return null
  const theorique = Number(ligne?.quantite_theorique ?? 0)
  return Number(comptee) - theorique
}

/**
 * Regroupe les lignes d'une session de comptage en trois seaux : `nonComptees`
 * (pas encore saisies), `conformes` (écart nul) et `ecarts` (écart non nul —
 * ce qu'un responsable doit valider avant de clôturer). Ne mute jamais la
 * liste d'entrée ; tolère `lignes` absent/non-tableau (retourne trois seaux
 * vides plutôt que de planter).
 */
export function grouperLignesParEcart(lignes) {
  const rows = Array.isArray(lignes) ? lignes : []
  const nonComptees = []
  const conformes = []
  const ecarts = []
  for (const l of rows) {
    const ecart = ecartLigne(l)
    if (ecart === null) nonComptees.push(l)
    else if (ecart === 0) conformes.push(l)
    else ecarts.push({ ...l, ecart })
  }
  return { nonComptees, conformes, ecarts }
}

/** Nombre de lignes déjà comptées sur le total — pour une barre de progression. */
export function progressionComptage(lignes) {
  const rows = Array.isArray(lignes) ? lignes : []
  const total = rows.length
  const comptees = rows.filter((l) => l?.quantite_comptee != null).length
  return { comptees, total, pct: total > 0 ? Math.round((comptees / total) * 100) : 0 }
}

// ── FG325 — demandes de transfert : actions disponibles selon statut ──

/**
 * Détermine les actions valides pour une demande de transfert selon son
 * statut courant (miroir des gardes 409 côté vues). Renvoie un tableau parmi
 * `['approuver','refuser','executer']` — vide si la demande est dans un état
 * terminal (refusée/exécutée).
 */
export function actionsDisponiblesTransfert(statut) {
  if (statut === 'demande') return ['approuver', 'refuser']
  if (statut === 'approuve') return ['executer']
  return []
}

// ── FG330 — preuve de livraison (POD) ──

/** Une livraison a-t-elle déjà sa preuve de livraison (POD) ? */
export function aPreuveLivraison(livraison) {
  return !!(livraison?.preuve || livraison?.preuve_id)
}

/** Une preuve de livraison est-elle complète (signature ET nom du signataire) ? */
export function podComplete(pod) {
  return !!(pod?.signature_data && (pod?.signataire_nom || '').trim())
}
