// AGR420 — les entrées de pompage DÉCLARÉES ou MESURÉES d'un lead
// (`lead.entrees_pompage`, AGR404 ; contrat `crm/contract_samples/
// lead_pompage.json`) → les états du générateur agricole. Fonction PURE : le
// JS ne calcule rien de neuf (D-AGR-1), il recopie ce que le serveur a servi
// avec sa provenance. Une entrée absente n'écrit RIEN : aucun état n'est jamais
// rempli d'une région, d'une culture, d'une énergie ou d'une distance
// par défaut.
//
// Jamais recopiés : `pompe_actuelle_cv` dans un CV CIBLE (le CV du générateur
// reste la plaque de la pompe ACTUELLE) ni `pompage_heures_jour` dans les
// heures de pompage SOLAIRE (celles-ci ne viennent d'aucun lead).

// colonne du lead → état d'écran du générateur (texte tel que tapé)
const ECRAN_PAR_COLONNE = {
  pompe_hmt_m: 'pompeHmt',
  pompe_debit_m3h: 'pompeDebit',
  niveau_statique_m: 'farmHmtStatic',
  profondeur_forage_m: 'pompeProfondeur',
  distance_forage_champ_m: 'pompeDistance',
  pompe_actuelle_cv: 'pompeCv',
  pompe_actuelle_type: 'pompeType',
  region_agricole: 'farmRegion',
  culture: 'farmCrop',
  surface_irriguee_ha: 'farmSurfaceHa',
  irrigation_methode: 'farmIrrigation',
}

// Libellés affichés à côté de chaque valeur pré-remplie.
export const LIBELLES_ENTREES_LEAD = {
  pompe_hmt_m: 'HMT (m)',
  pompe_debit_m3h: 'Débit souhaité (m³/h)',
  niveau_statique_m: 'Niveau statique (m)',
  profondeur_forage_m: 'Profondeur du forage (m)',
  distance_forage_champ_m: 'Distance forage–champ (m)',
  pompe_actuelle_cv: 'Pompe actuelle (CV, information)',
  pompe_actuelle_type: 'Type de pompe',
  region_agricole: 'Région',
  culture: 'Culture',
  surface_irriguee_ha: 'Surface irriguée (ha)',
  irrigation_methode: 'Irrigation',
  pompe_alim_actuelle: 'Énergie actuelle',
  butane_bouteilles_jour: 'Butane (bouteilles / jour d’irrigation)',
  carburant_litres_mois: 'Carburant (L / mois)',
  carburant_prix_unitaire_mad: 'Prix payé (MAD)',
  mois_irrigation: 'Mois d’irrigation',
  jours_irrigation_semaine: 'Jours d’irrigation / semaine',
  mode_pompe: 'Mode de pompe',
  pompe_actuelle_kw: 'Plaque : puissance (kW)',
  pompe_actuelle_tension_v: 'Plaque : tension (V)',
  pompe_actuelle_phases: 'Plaque : phases',
}

// AGQ39 (D-AGQ-10) — colonne du lead → chemin de `pompageSaisie` (mode de
// pompe et plaque de la pompe ACTUELLE). Les phases arrivent du serveur en
// 1 / 3 (moteur) ; l'écran les choisit en « mono » / « tri ».
const SAISIE_PAR_COLONNE = {
  mode_pompe: 'mode_pompe',
  pompe_actuelle_kw: 'plaque.kw',
  pompe_actuelle_tension_v: 'plaque.tension_v',
  pompe_actuelle_phases: 'plaque.phases',
}
const PHASES_ECRAN = { 1: 'mono', 3: 'tri' }

const vide = (v) => v === null || v === undefined || v === ''

const provenance = (e) => ({
  origine: 'lead', detail: e.provenance || null, date: e.date || null,
})

/**
 * `lead` (détail) → `{ ecran, eco, saisie, provenances }`, ou `null` quand le
 * lead ne sert aucune entrée.
 *  - `ecran` : `{cléÉtat: 'texte'}` pour les états `useState` du générateur ;
 *  - `eco`   : morceaux de l'état `ecoPompage` (→ `saisies_economie_pompage`,
 *    forme AGR3) avec la provenance `lead` ;
 *  - `saisie` : `{chemin: 'texte'}` pour `pompageSaisie` (mode de pompe et
 *    plaque, AGQ39) ;
 *  - `provenances` : `[{colonne, libelle, valeur, provenance}]` à afficher.
 */
export function entreesPompageDuLead(lead) {
  const entrees = lead?.entrees_pompage?.entrees
  if (!Array.isArray(entrees) || entrees.length === 0) return null
  const ecran = {}
  const eco = {}
  const saisie = {}
  const provenances = []
  for (const e of entrees) {
    if (!e || vide(e.valeur)) continue
    const col = e.colonne
    const cle = ECRAN_PAR_COLONNE[col]
    if (cle) {
      // « ne sait pas » n'est pas un type de pompe : non transmis.
      if (col === 'pompe_actuelle_type' && e.valeur === 'ne_sait_pas') continue
      ecran[cle] = String(e.valeur)
    } else if (col === 'pompe_alim_actuelle') {
      eco.energie = String(e.valeur)
      eco.energieProvenance = provenance(e)
    } else if (col === 'butane_bouteilles_jour') {
      eco.quantite = String(e.valeur)
      eco.unite = 'bouteille_12kg'
      eco.periode = 'jour_irrigation'
    } else if (col === 'carburant_litres_mois') {
      eco.quantite = String(e.valeur)
      eco.unite = 'litre'
      eco.periode = 'mois'
    } else if (col === 'carburant_prix_unitaire_mad') {
      eco.prix = String(e.valeur)
      if (e.date) eco.dateDeclaration = e.date
    } else if (col === 'mois_irrigation') {
      if (!Array.isArray(e.valeur) || e.valeur.length === 0) continue
      eco.mois = e.valeur.map(Number)
      eco.moisProvenance = provenance(e)
    } else if (col === 'jours_irrigation_semaine') {
      // AGQ10 (D-AGQ-6) — les jours d'une conso « par jour d'irrigation ».
      eco.joursSemaine = String(e.valeur)
    } else if (SAISIE_PAR_COLONNE[col]) {
      const valeur = col === 'pompe_actuelle_phases'
        ? PHASES_ECRAN[Number(e.valeur)] : String(e.valeur)
      if (!valeur) continue
      saisie[SAISIE_PAR_COLONNE[col]] = valeur
    } else {
      continue
    }
    provenances.push({
      colonne: col,
      libelle: LIBELLES_ENTREES_LEAD[col] || col,
      valeur: Array.isArray(e.valeur) ? e.valeur.join(', ') : String(e.valeur),
      provenance: provenance(e),
    })
  }
  if (provenances.length === 0) return null
  return { ecran, eco, saisie, provenances }
}

/**
 * AGQ39 (D-AGQ-10) — mode de pompe et plaque du lead → `pompageSaisie` :
 * rend l'updater `(s) => s'` ; une saisie du vendeur (`libre` faux) n'est
 * jamais écrasée ; `poses` reçoit les chemins posés depuis le lead.
 */
export function appliquerSaisiePompageLead(saisie, libre, poses, poserSaisie) {
  const entrees = Object.entries(saisie || {})
  if (!entrees.length) return (s) => s
  return (s) => entrees.reduce((suite, [chemin, valeur]) => {
    const courant = chemin.split('.').reduce((n, k) => (n == null ? n : n[k]), suite)
    if (!libre(`saisie.${chemin}`, courant)) return suite
    poses[`saisie.${chemin}`] = valeur
    return poserSaisie(suite, chemin, valeur)
  }, s)
}
