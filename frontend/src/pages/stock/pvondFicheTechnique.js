// PVOND — mini-formulaire « fiche technique » (onduleur/panneau/batterie),
// logique PURE hors de tout composant : même contrainte que
// `ficheCompletude.js` (react-refresh/only-export-components interdit
// d'exporter des fonctions non-composant depuis un fichier de composants).
// `ProduitForm.jsx` importe ce module ; aucune dépendance ici (testable en
// isolation, `node --test` sans node_modules).
//
// Objectif fondateur (18/08) : compléter la fiche technique d'un onduleur
// (ou d'un panneau/d'une batterie) depuis Stock doit être une tâche de 2
// minutes, pas une chasse au trésor. Ce module porte deux choses :
//
//   1. Le VERROU DE COMPLÉTUDE onduleur, recalculé EN LOCAL pendant la frappe
//      — MIROIR EXACT de `CONTRAT_ONDULEUR` (apps/stock/selectors.py) : même
//      ordre, mêmes libellés français. C'est cette identité qui garantit que
//      ce que cet écran affiche et ce que la bannière du générateur de devis
//      affiche après enregistrement (`onduleurSpecsManquantes`,
//      frontend/src/features/ventes/solar.js) disent EXACTEMENT la même
//      phrase. Si le contrat backend change, ce tableau DOIT être répercuté
//      à l'identique (même discipline que GHI/DC9 pour la table
//      d'irradiance).
//   2. La lecture/écriture de la « plage de tension batterie » d'un onduleur
//      hybride. `FicheTechnique` (PV5) n'a AUCUN champ dédié pour cette
//      variable du contrat — elle vit dans une LIGNE MARQUÉE de
//      `Produit.description` (« Plage batterie : 40-60 V » / « aucune »),
//      exactement le patron que `seed_catalogue.py` écrit déjà et que le
//      fondateur éditait jusqu'ici À LA MAIN, en pleine description libre.
//      Ce mini-formulaire ne fait qu'éviter la faute de frappe sur le
//      format : la donnée finale reste la MÊME ligne de texte, dans le MÊME
//      champ — aucune nouvelle exposition créée par cet écran.

// ── Plage de tension batterie (onduleur hybride) ────────────────────────────
export const MARQUEUR_PLAGE_BATTERIE = 'Plage batterie :'
export const PLAGE_BATTERIE_AUCUNE = 'aucune'

const _normeFr = (s) =>
  (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

/** Lit la ligne marquée dans une description brute.
 * MIROIR de `plage_batterie_onduleur` (apps/stock/selectors.py) : mêmes
 * tolérances (tiret ou tiret demi-cadratin, virgule ou point décimal, ordre
 * bas/haut indifférent). Renvoie { aucune, min, max } — min/max en CHAÎNES
 * prêtes pour un <Input>, '' = non déclaré. */
export function lirePlageBatterieDescription(description) {
  for (const ligneBrute of (description || '').split('\n')) {
    const ligne = ligneBrute.trim()
    if (!ligne.startsWith(MARQUEUR_PLAGE_BATTERIE)) continue
    const valeur = _normeFr(ligne.slice(MARQUEUR_PLAGE_BATTERIE.length))
    if (valeur.includes(PLAGE_BATTERIE_AUCUNE)) {
      return { aucune: true, min: '', max: '' }
    }
    const trouve = /(\d+(?:[.,]\d+)?)\s*[-–]\s*(\d+(?:[.,]\d+)?)/.exec(valeur)
    if (!trouve) return { aucune: false, min: '', max: '' }
    let bas = parseFloat(trouve[1].replace(',', '.'))
    let haut = parseFloat(trouve[2].replace(',', '.'))
    if (haut < bas) { const t = bas; bas = haut; haut = t }
    return { aucune: false, min: String(bas), max: String(haut) }
  }
  return { aucune: false, min: '', max: '' }
}

/** Réécrit la ligne marquée dans la description : la ligne « Plage batterie
 * : » existante (s'il y en a une) est retirée, TOUTES les autres lignes sont
 * préservées telles quelles, puis la nouvelle valeur est reposée en fin de
 * texte si elle est renseignée. */
export function ecrirePlageBatterieDescription(description, { aucune, min, max }) {
  const lignes = (description || '').split('\n')
    .filter((l) => !l.trim().startsWith(MARQUEUR_PLAGE_BATTERIE))
  while (lignes.length && lignes[lignes.length - 1].trim() === '') lignes.pop()

  let ligneNouvelle = null
  if (aucune) {
    ligneNouvelle = `${MARQUEUR_PLAGE_BATTERIE} aucune (onduleur réseau)`
  } else {
    const bas = parseFloat(min)
    const haut = parseFloat(max)
    if (Number.isFinite(bas) && Number.isFinite(haut) && bas > 0 && haut > 0) {
      ligneNouvelle = `${MARQUEUR_PLAGE_BATTERIE} ${Math.min(bas, haut)}-${Math.max(bas, haut)} V`
    }
  }
  if (ligneNouvelle) lignes.push(ligneNouvelle)
  return lignes.join('\n')
}

/** La plage batterie est-elle DÉCLARÉE (valeur pleine, y compris « aucune »)
 * pour cette description ? MIROIR de la lecture `plage_batterie_onduleur`
 * côté serveur (None = manquant). */
export function plageBatterieDeclaree(description) {
  const { aucune, min, max } = lirePlageBatterieDescription(description)
  if (aucune) return true
  const bas = Number(min)
  const haut = Number(max)
  return Number.isFinite(bas) && Number.isFinite(haut) && bas > 0 && haut > 0
}

/** La variable « plage de tension batterie » est-elle ABSENTE (manquante au
 * sens du contrat) pour CET onduleur ? MIROIR de `plage_batterie_onduleur` +
 * `onduleur_specs_manquantes` (apps/stock/selectors.py) sous la RÈGLE
 * CORRIGÉE — ordre fondateur du 18/08/2026 (commit ed34ced9) : la plage
 * n'est exigée QUE d'un onduleur HYBRIDE.
 *
 *   - HYBRIDE  → absente SAUF ligne déclarée (« aucune » ou une plage
 *                numérique) — comportement inchangé, c'est la seule famille
 *                qui a réellement un port batterie à documenter ;
 *   - RÉSEAU   → JAMAIS absente : sa FAMILLE vaut déclaration « aucune »,
 *                exactement comme une ligne écrite à la main (une ligne
 *                déclarée reste prioritaire si présente, mais son absence
 *                n'est plus un trou — un string on-grid n'a pas de port
 *                batterie) ;
 *   - ni hybride ni réseau (famille indéterminée / hors périmètre de cet
 *     écran) → repli sur la dernière valeur SERVEUR connue
 *     (`plageBatterieServeurAbsente`), jamais une régression silencieuse. */
export function plageBatterieAbsenteLocale({
  estHybride, estReseau, description, plageBatterieServeurAbsente = true,
}) {
  if (estHybride) return !plageBatterieDeclaree(description)
  if (estReseau) return false
  return plageBatterieServeurAbsente
}

// ── PVOND-H (fondateur 19/08/2026) — même contrat que les deux fonctions
// ci-dessus, mais lues sur le CHAMP DÉDIÉ (`ond_bat_aucune`/`ond_bat_v_min`/
// `ond_bat_v_max`, désormais un vrai bloc de `FicheTechnique`) plutôt que sur
// l'ancienne ligne de texte de `Produit.description`. C'est la source que
// l'écran Stock ÉCRIT désormais ; `plageBatterieDeclaree`/
// `plageBatterieAbsenteLocale` ci-dessus restent INCHANGÉES (elles gardent
// leur propre couverture de test) — ce sont deux lectures du MÊME concept,
// une par génération de mécanisme, jamais mélangées dans un seul appelant. */
export function plageBatterieDeclareeChamps(ficheFields) {
  if (ficheFields?.ond_bat_aucune) return true
  const bas = Number(ficheFields?.ond_bat_v_min)
  const haut = Number(ficheFields?.ond_bat_v_max)
  return Number.isFinite(bas) && Number.isFinite(haut) && bas > 0 && haut > 0
}

/** Mêmes règles que `plageBatterieAbsenteLocale` (HYBRIDE exigé, RÉSEAU
 * jamais absente, sinon repli SERVEUR) — appliquées à `ficheFields`. */
export function plageBatterieAbsenteChamps({
  estHybride, estReseau, ficheFields, plageBatterieServeurAbsente = true,
}) {
  if (estHybride) return !plageBatterieDeclareeChamps(ficheFields)
  if (estReseau) return false
  return plageBatterieServeurAbsente
}

// ── Verrou de complétude ONDULEUR — MIROIR de CONTRAT_ONDULEUR ─────────────
// (apps/stock/selectors.py CONTRAT_ONDULEUR). Clés préfixées `__` = variables
// qui ne vivent pas sur `FicheTechnique` (voir plus haut).
export const CONTRAT_ONDULEUR_FR = [
  ['ond_ac_kw', 'puissance AC (kW)'],
  ['ond_phases', 'monophasé / triphasé'],
  ['ond_n_mppt', "nombre d'entrées MPPT"],
  ['ond_mppt_v_min', 'plage MPPT — tension mini (V)'],
  ['ond_mppt_v_max', 'plage MPPT — tension maxi (V)'],
  ['ond_v_max_abs', 'tension DC maximale (V)'],
  ['ond_i_max_mppt_a', 'courant maxi par MPPT (A)'],
  ['ond_rendement_euro_pct', 'rendement européen (%)'],
  ['__plage_batterie_v', 'plage de tension batterie (V)'],
  ['__garantie', 'garantie constructeur'],
]

const _vide = (v) => v === null || v === undefined || v === ''

/** Les variables du contrat ONDULEUR encore manquantes, recalculées EN LOCAL
 * pendant la frappe (le serveur ne recalcule qu'après enregistrement) — même
 * liste, même ordre, mêmes libellés que le backend.
 *   ficheFields          → { ond_ac_kw, ond_phases, ... } (chaînes de
 *                           <Input>, '' = vide)
 *   garantieTexte        → `fields.garantie` du formulaire produit (texte,
 *                           champ existant de la section Garantie)
 *   plageBatterieAbsente → true si la plage n'est pas encore déclarée */
export function manquantesOnduleurLocal({ ficheFields = {}, garantieTexte = '', plageBatterieAbsente = true } = {}) {
  const manquantes = []
  for (const [cle, libelle] of CONTRAT_ONDULEUR_FR) {
    if (cle === '__garantie') {
      if (!(garantieTexte || '').trim()) manquantes.push(libelle)
      continue
    }
    if (cle === '__plage_batterie_v') {
      if (plageBatterieAbsente) manquantes.push(libelle)
      continue
    }
    if (_vide(ficheFields[cle])) manquantes.push(libelle)
  }
  return manquantes
}

// ── Champs FicheTechnique (PV5) par type de fiche ───────────────────────────
// PVOND-H (fondateur 19/08/2026, « have a place for every one of this
// information ») — trois champs onduleur AJOUTÉS (tension de démarrage, Isc
// max par MPPT, plage de tension batterie min/max) : le moteur électrique
// (core.electrique.types.SpecOnduleur) sait déjà les lire, ils n'avaient
// simplement aucun champ ``FicheTechnique`` pour les porter. Côté panneau,
// Voc/Isc/Vmp/Imp et les deux coefficients de température EXISTAIENT déjà sur
// le modèle (lus par ``specs_for_produit``/le moteur) mais n'étaient éditables
// NULLE PART à l'écran — champ réutilisé, aucune duplication.
//
// CALX355 — les champs que la chaîne de pertes et l'électrique LISENT
// (CALX60, CAL111, CAL112) existaient en base sans aucune saisie à l'écran :
// rendement maximal / CEC de l'onduleur, NOCT / bifacialité / tolérance de
// puissance du module, C-rate / plage de température du pack, SORTIE de
// l'optimiseur / du micro-onduleur. Ajoutés EN FIN de chaque liste (l'ordre
// existant ne bouge pas) ; la chimie (un choix) et les deux courbes (des
// listes de points) vivent dans leurs propres tables plus bas — jamais
// `Number(brut)` sur une valeur qui n'est pas un nombre.
const CHAMPS_PAR_TYPE = {
  onduleur: [
    'ond_ac_kw', 'ond_phases', 'ond_n_mppt', 'ond_mppt_v_min',
    'ond_mppt_v_max', 'ond_v_max_abs', 'ond_i_max_mppt_a',
    'ond_rendement_euro_pct',
    'ond_v_demarrage_v', 'ond_isc_max_mppt_a',
    'ond_bat_v_min', 'ond_bat_v_max',
    // CALX355 — bloc « rendement onduleur » (la courbe : COURBES_PAR_TYPE).
    'ond_rendement_max_pct', 'ond_rendement_cec_pct',
  ],
  module: [
    'pmax_wc', 'voc_v', 'isc_a', 'vmp_v', 'imp_a',
    'temp_coeff_voc_pct_c', 'temp_coeff_pmax_pct_c',
    'longueur_mm', 'largeur_mm',
    // CALX355 — NOCT (CAL111), bifacialité (CAL112), tolérance de puissance
    // (CALX60). La courbe rendement/irradiance : COURBES_PAR_TYPE.
    'noct_c', 'bifacialite_pct',
    'tolerance_pmax_min_pct', 'tolerance_pmax_max_pct',
  ],
  // BATHOMO (fondateur 26/08/2026) — ``bat_max_modules_par_banc`` : le
  // plafond fondateur-éditable du nombre de modules IDENTIQUES qu'un même
  // banc peut empiler pour ce produit (vide = illimité, 0 invalide — F3).
  batterie: ['bat_kwh_nominal', 'bat_kwh_usable', 'bat_v_nominal', 'bat_dod_pct',
             'bat_max_modules_par_banc',
             // CALX355 — C-rate et plage de température (CALX60) ; la
             // chimie est un CHOIX : CHAMPS_CHOIX_PAR_TYPE.
             'bat_c_rate_charge', 'bat_c_rate_decharge',
             'bat_temp_min_c', 'bat_temp_max_c'],
  // CALX355 — la SORTIE de l'optimiseur / du micro-onduleur (CALX60) : les
  // `opt_ac_*` ne se remplissent que sur un micro-onduleur, les `opt_v_out_*`
  // / `opt_i_out_*` que sur un optimiseur — aucune valeur n'est déduite de
  // l'autre famille.
  optimiseur: [
    'opt_ac_kw', 'opt_ac_tension_v', 'opt_ac_i_max_a',
    'opt_ac_unites_max_par_branche',
    'opt_v_out_nominal_v', 'opt_v_out_min', 'opt_v_out_max',
    'opt_i_out_max_a', 'opt_pmax_out_w', 'opt_modules_max_par_chaine',
  ],
}

// ── CALX355 — champs à CHOIX (CharField non nul côté serveur : vide = '',
// jamais `null` ni `0`). Valeurs et libellés = MIROIR EXACT de
// `FicheTechnique.ChimieBatterie` (apps/stock/models.py).
export const CHOIX_CHIMIE_BATTERIE = [
  ['lfp', 'LFP (lithium fer phosphate)'],
  ['nmc', 'NMC (lithium nickel manganèse cobalt)'],
  ['nca', 'NCA (lithium nickel cobalt aluminium)'],
  ['lmo', 'LMO (lithium manganèse)'],
  ['lto', 'LTO (titanate de lithium)'],
  ['plomb_ouvert', 'Plomb ouvert (à entretien)'],
  ['plomb_agm', 'Plomb AGM (étanche)'],
  ['plomb_gel', 'Plomb gel (étanche)'],
  ['autre', 'Autre (préciser sur la fiche produit)'],
]
export const CHOIX_FICHE = { bat_chimie: CHOIX_CHIMIE_BATTERIE }
const CHAMPS_CHOIX_PAR_TYPE = { batterie: ['bat_chimie'] }

// ── CALX355 — COURBES saisies point par point ───────────────────────────────
// MIROIR de `valider_courbe_irradiance` / `valider_courbe_rendement_onduleur`
// (apps/stock/models.py) : clés requises numériques, abscisse STRICTEMENT
// croissante (à l'intérieur de chaque série de tension pour l'onduleur),
// liste vide refusée — ici une courbe sans aucun point part à `null`
// (« non publiée »), jamais `[]` ni un point à 0. Rien n'est re-trié en
// silence : une abscisse qui recule est une ERREUR nommée sous la cellule.
export const COURBES_FICHE = {
  rendement_par_irradiance: {
    libelle: 'Courbe rendement / irradiance',
    aide: "Rendement RELATIF (% du rendement STC) à chaque niveau d'irradiance, tel que publié par le fabricant.",
    abscisse: 'w_m2',
    serie: null,
    colonnes: [
      { cle: 'w_m2', libelle: 'Irradiance (W/m²)', requise: true },
      { cle: 'rendement_relatif_pct', libelle: 'Rendement relatif (% du STC)', requise: true },
    ],
  },
  ond_courbe_rendement: {
    libelle: 'Courbe de rendement (charge → rendement)',
    aide: "Rendement à chaque taux de charge (% de la puissance nominale). La tension d'entrée est facultative : plusieurs courbes peuvent coexister, une par tension.",
    abscisse: 'charge_pct',
    serie: 'tension_v',
    colonnes: [
      { cle: 'charge_pct', libelle: 'Charge (% de Pnom)', requise: true },
      { cle: 'rendement_pct', libelle: 'Rendement (%)', requise: true },
      { cle: 'tension_v', libelle: "Tension d'entrée (V) — facultative", requise: false },
    ],
  },
}
const COURBES_PAR_TYPE = {
  module: ['rendement_par_irradiance'],
  onduleur: ['ond_courbe_rendement'],
}

const _celluleVide = (v) => v === null || v === undefined || String(v).trim() === ''

/** Nombre saisi dans une cellule de courbe — la virgule décimale est
 * NORMALISÉE (jamais refusée) ; `null` si ce n'est pas un nombre. */
function _nombreCellule(brut) {
  if (_celluleVide(brut)) return null
  const n = Number(String(brut).trim().replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

/** Une ligne vierge (toutes cellules '') pour la courbe `cleCourbe`. */
export function ligneCourbeVide(cleCourbe) {
  const ligne = {}
  for (const col of COURBES_FICHE[cleCourbe]?.colonnes ?? []) ligne[col.cle] = ''
  return ligne
}

/** Points serveur (`[{w_m2: 200, …}, …]` ou `null`) → lignes d'état local
 * (toutes chaînes, '' = cellule vide). Une courbe absente → aucune ligne. */
export function lignesCourbeDepuisServeur(cleCourbe, valeur) {
  if (!Array.isArray(valeur)) return []
  return valeur.map((point) => {
    const ligne = ligneCourbeVide(cleCourbe)
    for (const cle of Object.keys(ligne)) {
      const v = point?.[cle]
      ligne[cle] = (v === null || v === undefined) ? '' : String(v)
    }
    return ligne
  })
}

/** Contrôle d'une courbe saisie, ligne par ligne.
 * Rend `{ points, erreurs }` :
 *   - `erreurs[i]` = `null` (ligne correcte ou entièrement vierge) ou
 *     `{ <colonne>: message }` — CHAQUE message vise la cellule fautive ;
 *   - `points` = les lignes correctes converties en nombres (la tension
 *     facultative omise quand vide), ou `null` si aucune — jamais `[]`.
 * Une ligne entièrement vierge est ignorée (ni point, ni erreur). */
export function validerCourbe(cleCourbe, lignes) {
  const spec = COURBES_FICHE[cleCourbe]
  const erreurs = []
  const points = []
  if (!spec) return { points: null, erreurs }
  // Dernière abscisse retenue PAR SÉRIE (tension d'entrée) : { valeur, ligne }.
  const derniere = {}
  ;(lignes ?? []).forEach((ligne, i) => {
    const toutesVides = spec.colonnes.every((col) => _celluleVide(ligne?.[col.cle]))
    if (toutesVides) { erreurs.push(null); return }
    const err = {}
    const point = {}
    for (const col of spec.colonnes) {
      const brut = ligne?.[col.cle]
      if (_celluleVide(brut)) {
        if (col.requise) err[col.cle] = `Valeur requise — ${col.libelle}.`
        continue
      }
      const n = _nombreCellule(brut)
      if (n === null) { err[col.cle] = `Nombre attendu — ${col.libelle}.`; continue }
      point[col.cle] = n
    }
    if (!(spec.abscisse in err) && spec.abscisse in point) {
      const serie = spec.serie && spec.serie in point ? String(point[spec.serie]) : ''
      const prec = derniere[serie]
      if (prec && point[spec.abscisse] <= prec.valeur) {
        err[spec.abscisse] = `Doit dépasser ${prec.valeur} (point ${prec.ligne}) — `
          + 'une courbe ne recule pas et ne se répète pas.'
      }
    }
    if (Object.keys(err).length) { erreurs.push(err); return }
    const serie = spec.serie && spec.serie in point ? String(point[spec.serie]) : ''
    derniere[serie] = { valeur: point[spec.abscisse], ligne: i + 1 }
    erreurs.push(null)
    points.push(point)
  })
  return { points: points.length ? points : null, erreurs }
}

/** Erreurs de TOUTES les courbes du type `typeBackend` ('module'/'onduleur'…)
 * pour `ficheFields`. Rend `{ parCourbe: { <cle>: erreurs[] }, bandeau }` :
 * `parCourbe` ne liste que les courbes fautives ; `bandeau` NOMME la
 * première cellule fautive (courbe, point, colonne) ou vaut `null`. */
export function erreursCourbesPourType(typeBackend, ficheFields) {
  const parCourbe = {}
  let bandeau = null
  for (const cle of COURBES_PAR_TYPE[typeBackend] ?? []) {
    const { erreurs } = validerCourbe(cle, ficheFields?.[cle])
    const i = erreurs.findIndex((e) => e !== null)
    if (i === -1) continue
    parCourbe[cle] = erreurs
    if (!bandeau) {
      const [colonne, message] = Object.entries(erreurs[i])[0]
      const libCol = COURBES_FICHE[cle].colonnes.find((c) => c.cle === colonne)?.libelle ?? colonne
      bandeau = `« ${COURBES_FICHE[cle].libelle} », point ${i + 1}, « ${libCol} » : ${message}`
    }
  }
  return { parCourbe, bandeau }
}

// ── CALX355 — l'optimiseur / micro-onduleur n'a PAS de famille dans la
// classification du générateur de devis (`classifyProduct`, solar.js : un
// micro-onduleur sans « réseau/injection » y reste non classé) ni dans les
// catégories typées (`Categorie.TypeEquipement`). Ce repli ne s'applique
// QUE quand `classifyProduct` n'a rien rendu — il ne réinterprète jamais un
// produit déjà classé.
export function estOptimiseurNom(nom) {
  const n = _normeFr(nom).replace(/[-_]/g, ' ')
  return /\boptimi[sz]e(u)?r\b|\bmicro ?onduleur\b|\bmicro ?inverter\b/.test(n)
}

/** Type de fiche du FORMULAIRE : la classification client d'abord (source
 * unique partagée avec le générateur de devis), sinon « optimiseur » quand
 * le nom le dit OU que la fiche enregistrée est déjà typée ainsi. */
export function typeFicheFormulaire({ typeClient, nom, typeFicheServeur } = {}) {
  if (typeClient) return typeClient
  if (typeFicheServeur === 'optimiseur' || estOptimiseurNom(nom)) return 'optimiseur'
  return null
}

/** Champs BOOLÉENS du bloc FicheTechnique — traités à part des champs
 * numériques ci-dessus (jamais `Number(brut)`, qui casserait un booléen).
 * Un seul aujourd'hui : la déclaration explicite « aucune batterie »
 * (PVOND-H). */
const CHAMPS_BOOLEENS_PAR_TYPE = {
  onduleur: ['ond_bat_aucune'],
}

// ── PVFCH (fondateur 20/08/2026) — LIRE la fiche là où on la REGARDE ────────
// « i am expecting a fiche produit that includes all the data separately, that
// I can change — number of MPPT, range of each MPPT, battery voltage… »
//
// Ces champs EXISTENT (FicheTechnique, PV5/PVOND-H) et sont éditables dans
// ProduitForm, mais le VISUALISEUR produit (ProduitDetail, onglet « Fiche
// technique ») n'affichait que marque/garantie/description en prose : le
// fondateur en a légitimement conclu que la donnée structurée n'existait pas.
//
// Le tableau ci-dessous est la SOURCE UNIQUE des libellés d'affichage. Ils
// sont MOT POUR MOT ceux des <FormField> de ProduitForm : le fondateur lit la
// fiche, clique « Modifier la fiche », et retrouve le MÊME intitulé — jamais à
// traduire mentalement d'un écran à l'autre. Les libellés du contrat onduleur
// (CONTRAT_ONDULEUR_FR, miroir du backend) restent la source du VERROU ; ici
// il s'agit de l'AFFICHAGE, qui couvre aussi les champs hors contrat.
export const LIBELLES_FICHE = {
  // Onduleur
  ond_ac_kw: 'Puissance AC (kW)',
  ond_phases: 'Phases',
  ond_n_mppt: "Nombre d'entrées MPPT",
  ond_i_max_mppt_a: 'Courant maxi par MPPT (A)',
  ond_mppt_v_min: 'Plage MPPT — tension mini (V)',
  ond_mppt_v_max: 'Plage MPPT — tension maxi (V)',
  ond_v_max_abs: 'Tension DC maximale (V)',
  ond_rendement_euro_pct: 'Rendement européen (%)',
  ond_v_demarrage_v: 'Tension de démarrage (V)',
  ond_isc_max_mppt_a: 'Isc maxi par MPPT (A)',
  ond_bat_v_min: 'Plage batterie — tension mini (V)',
  ond_bat_v_max: 'Plage batterie — tension maxi (V)',
  // CALX355 — rendement onduleur
  ond_rendement_max_pct: 'Rendement maximal (%)',
  ond_rendement_cec_pct: 'Rendement CEC (%)',
  ond_courbe_rendement: COURBES_FICHE.ond_courbe_rendement.libelle,
  // Module
  pmax_wc: 'Puissance crête (Wc)',
  voc_v: 'Tension circuit ouvert — Voc (V)',
  isc_a: 'Courant court-circuit — Isc (A)',
  vmp_v: 'Tension au point de puissance max — Vmp (V)',
  imp_a: 'Courant au point de puissance max — Imp (A)',
  temp_coeff_voc_pct_c: 'Coefficient de température Voc (%/°C)',
  temp_coeff_pmax_pct_c: 'Coefficient de température Pmax (%/°C)',
  longueur_mm: 'Longueur (mm)',
  largeur_mm: 'Largeur (mm)',
  // CALX355 — module
  noct_c: 'NOCT — température nominale de fonctionnement (°C)',
  bifacialite_pct: 'Facteur de bifacialité (%)',
  tolerance_pmax_min_pct: 'Tolérance de puissance — borne basse (%)',
  tolerance_pmax_max_pct: 'Tolérance de puissance — borne haute (%)',
  rendement_par_irradiance: COURBES_FICHE.rendement_par_irradiance.libelle,
  // Batterie
  bat_kwh_nominal: 'Capacité nominale (kWh)',
  bat_kwh_usable: 'Capacité utilisable (kWh)',
  bat_v_nominal: 'Tension nominale (V)',
  bat_dod_pct: 'Profondeur de décharge — plage utile (%)',
  bat_max_modules_par_banc: 'Max modules par banc — vide = illimité',
  // CALX355 — batterie
  bat_c_rate_charge: 'C-rate de charge (C)',
  bat_c_rate_decharge: 'C-rate de décharge (C)',
  bat_temp_min_c: 'Température de fonctionnement mini (°C)',
  bat_temp_max_c: 'Température de fonctionnement maxi (°C)',
  bat_chimie: 'Chimie de cellule',
  // CALX355 — optimiseur / micro-onduleur (SORTIE)
  opt_ac_kw: 'Micro-onduleur — puissance AC nominale (kW)',
  opt_ac_tension_v: 'Micro-onduleur — tension AC de sortie (V)',
  opt_ac_i_max_a: 'Micro-onduleur — courant AC maxi de sortie (A)',
  opt_ac_unites_max_par_branche: 'Micro-onduleur — unités maxi par branche AC',
  opt_v_out_nominal_v: 'Optimiseur — tension de sortie nominale (V)',
  opt_v_out_min: 'Optimiseur — tension de sortie mini (V)',
  opt_v_out_max: 'Optimiseur — tension de sortie maxi (V)',
  opt_i_out_max_a: 'Optimiseur — courant de sortie maxi (A)',
  opt_pmax_out_w: 'Optimiseur — puissance de sortie maxi (W)',
  opt_modules_max_par_chaine: 'Modules équipés maxi par chaîne',
}

/** Titre de la section affichée, par `type_fiche` backend. */
export const TITRES_FICHE = {
  onduleur: 'Onduleur',
  module: 'Panneau photovoltaïque',
  batterie: 'Batterie',
  optimiseur: 'Optimiseur / micro-onduleur',
}

/** Ce qu'affiche une valeur ABSENTE. JAMAIS un défaut, jamais un zéro : un
 * trou doit se VOIR comme un trou — c'est la règle « never invent numbers »
 * appliquée à l'écran (le calcul, lui, refuse ; cf.
 * apps/ventes/electrical_service.py). */
export const VALEUR_ABSENTE = '— à renseigner'

/** Rend une valeur de fiche prête à afficher.
 *  - `null`/`undefined`/'' → `VALEUR_ABSENTE` ;
 *  - phases → « Monophasé » / « Triphasé » (le nombre nu ne se lit pas) ;
 *  - « aucune batterie » déclarée → la plage batterie le DIT au lieu d'être
 *    rendue vide, sinon on croirait à un oubli. */
export function valeurFicheAffichee(cle, fiche) {
  if (!fiche) return VALEUR_ABSENTE
  if (cle === 'ond_bat_v_min' || cle === 'ond_bat_v_max') {
    if (fiche.ond_bat_aucune) return 'Aucune batterie compatible'
  }
  const v = fiche[cle]
  // CALX355 — une courbe se lit par son NOMBRE de points (jamais un
  // « [object Object] ») ; une liste vide est une absence.
  if (COURBES_FICHE[cle]) {
    if (!Array.isArray(v) || v.length === 0) return VALEUR_ABSENTE
    return `${v.length} point${v.length > 1 ? 's' : ''}`
  }
  if (v === null || v === undefined || v === '') return VALEUR_ABSENTE
  // CALX355 — un choix s'affiche par son LIBELLÉ, jamais par sa clé.
  if (CHOIX_FICHE[cle]) {
    const trouve = CHOIX_FICHE[cle].find(([valeur]) => valeur === v)
    return trouve ? trouve[1] : String(v)
  }
  if (cle === 'ond_phases') {
    if (String(v) === '1') return 'Monophasé'
    if (String(v) === '3') return 'Triphasé'
  }
  return String(v)
}

/** Les lignes à AFFICHER pour une fiche chargée du serveur :
 * `{ titre, lignes: [{ cle, libelle, valeur, absente }] }`, ou `null` quand la
 * fiche n'a pas de bloc connu (produit sans fiche, ou `type_fiche` vide).
 *
 * L'ORDRE est celui de `CHAMPS_PAR_TYPE`, c'est-à-dire celui du formulaire :
 * la fiche lue et la fiche éditée se parcourent dans le même ordre. Les champs
 * VIDES sont inclus — c'est même leur raison d'être ici : le fondateur doit
 * voir ce qui manque, pas seulement ce qui est là. */
export function groupeFicheAffichage(fiche) {
  const type = fiche?.type_fiche
  if (!CHAMPS_PAR_TYPE[type]) return null
  // CALX355 — même ordre que le formulaire : nombres, puis choix, puis courbes.
  const cles = [
    ...CHAMPS_PAR_TYPE[type],
    ...(CHAMPS_CHOIX_PAR_TYPE[type] ?? []),
    ...(COURBES_PAR_TYPE[type] ?? []),
  ]
  return {
    type,
    titre: TITRES_FICHE[type] ?? 'Fiche technique',
    lignes: cles.map((cle) => {
      const valeur = valeurFicheAffichee(cle, fiche)
      return { cle, libelle: LIBELLES_FICHE[cle] ?? cle, valeur,
               absente: valeur === VALEUR_ABSENTE }
    }),
  }
}

/** `type_fiche` backend (FicheTechnique.TypeFiche : 'onduleur'/'module'/
 * 'batterie') pour la classification produit CLIENT
 * (`classifyProduct` de solar.js : 'onduleur_hybride'/'onduleur_reseau'/
 * 'panneau'/'batterie'). `null` si le type n'a pas de bloc FicheTechnique
 * (ex. une pompe — read-only, ses champs vivent directement sur `Produit`). */
export function typeFicheBackend(ficheType) {
  if (ficheType === 'onduleur_hybride' || ficheType === 'onduleur_reseau') return 'onduleur'
  if (ficheType === 'panneau') return 'module'
  if (ficheType === 'batterie') return 'batterie'
  // CALX355 — type du formulaire (`typeFicheFormulaire`), pas une famille
  // de `classifyProduct`.
  if (ficheType === 'optimiseur') return 'optimiseur'
  return null
}

/** Liste vide de départ (toutes chaînes vides, booléens à `false`) pour
 * l'état local du formulaire — un seul objet, quel que soit le type
 * détecté. */
export function ficheFieldsVides() {
  const out = {}
  for (const cles of Object.values(CHAMPS_PAR_TYPE)) {
    for (const cle of cles) out[cle] = ''
  }
  for (const cles of Object.values(CHAMPS_BOOLEENS_PAR_TYPE)) {
    for (const cle of cles) out[cle] = false
  }
  // CALX355 — choix vides ('') et courbes sans aucune ligne.
  for (const cles of Object.values(CHAMPS_CHOIX_PAR_TYPE)) {
    for (const cle of cles) out[cle] = ''
  }
  for (const cles of Object.values(COURBES_PAR_TYPE)) {
    for (const cle of cles) out[cle] = []
  }
  return out
}

/** Convertit une `FicheTechnique` chargée du serveur (nombres/Decimal→string
 * JSON) vers l'état local du formulaire (toutes chaînes, '' = non
 * renseigné ; les champs booléens restent des booléens). */
export function champsFicheDepuisServeur(fiche) {
  const out = ficheFieldsVides()
  if (!fiche) return out
  for (const cles of Object.values(CHAMPS_PAR_TYPE)) {
    for (const cle of cles) {
      const v = fiche[cle]
      out[cle] = (v === null || v === undefined) ? '' : String(v)
    }
  }
  for (const cles of Object.values(CHAMPS_BOOLEENS_PAR_TYPE)) {
    for (const cle of cles) out[cle] = !!fiche[cle]
  }
  for (const cles of Object.values(CHAMPS_CHOIX_PAR_TYPE)) {
    for (const cle of cles) out[cle] = fiche[cle] ? String(fiche[cle]) : ''
  }
  for (const cles of Object.values(COURBES_PAR_TYPE)) {
    for (const cle of cles) out[cle] = lignesCourbeDepuisServeur(cle, fiche[cle])
  }
  return out
}

/** Sous-ensemble de `ficheFields` pertinent pour ce type, converti en
 * nombres (`null` si vide/invalide) — les champs booléens en `true`/`false` —
 * prêt pour le payload `FicheTechniqueSerializer` (POST/PATCH
 * `/stock/fiches-techniques/`). */
export function champsFichePourType(ficheType, ficheFields) {
  const typeBackend = typeFicheBackend(ficheType)
  const cles = CHAMPS_PAR_TYPE[typeBackend] ?? []
  const clesBooleennes = CHAMPS_BOOLEENS_PAR_TYPE[typeBackend] ?? []
  const out = {}
  for (const cle of cles) {
    const brut = ficheFields?.[cle]
    if (brut === '' || brut === null || brut === undefined) { out[cle] = null; continue }
    const n = Number(brut)
    out[cle] = Number.isFinite(n) ? n : null
  }
  for (const cle of clesBooleennes) {
    out[cle] = !!ficheFields?.[cle]
  }
  // CALX355 — un choix vide part à '' (CharField non nul), jamais `null` ;
  // une courbe sans point correct part à `null` (« non publiée »), jamais
  // `[]` (refusé par le serveur) ni un point inventé.
  for (const cle of CHAMPS_CHOIX_PAR_TYPE[typeBackend] ?? []) {
    const brut = ficheFields?.[cle]
    out[cle] = brut ? String(brut) : ''
  }
  for (const cle of COURBES_PAR_TYPE[typeBackend] ?? []) {
    out[cle] = validerCourbe(cle, ficheFields?.[cle]).points
  }
  return out
}

/** CALX355 — le refus du serveur sur la fiche (400 DRF), rendu en une phrase
 * qui NOMME le champ fautif par son libellé d'écran (`{champ: [message]}`),
 * ou `detail` tel quel. `null` quand la réponse n'en dit rien d'exploitable. */
export function messageRefusFiche(data) {
  if (!data || typeof data !== 'object') return null
  if (typeof data.detail === 'string') return data.detail
  for (const [cle, valeur] of Object.entries(data)) {
    const message = Array.isArray(valeur)
      ? valeur.find((v) => typeof v === 'string')
      : (typeof valeur === 'string' ? valeur : null)
    if (message) return `« ${LIBELLES_FICHE[cle] ?? cle} » : ${message}`
  }
  return null
}
