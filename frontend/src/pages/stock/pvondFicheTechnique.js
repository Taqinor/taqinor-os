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
const CHAMPS_PAR_TYPE = {
  onduleur: [
    'ond_ac_kw', 'ond_phases', 'ond_n_mppt', 'ond_mppt_v_min',
    'ond_mppt_v_max', 'ond_v_max_abs', 'ond_i_max_mppt_a',
    'ond_rendement_euro_pct',
  ],
  module: ['pmax_wc', 'longueur_mm', 'largeur_mm'],
  batterie: ['bat_kwh_nominal', 'bat_kwh_usable', 'bat_v_nominal', 'bat_dod_pct'],
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
  return null
}

/** Liste vide de départ (toutes chaînes vides) pour l'état local du
 * formulaire — un seul objet, quel que soit le type détecté. */
export function ficheFieldsVides() {
  const out = {}
  for (const cles of Object.values(CHAMPS_PAR_TYPE)) {
    for (const cle of cles) out[cle] = ''
  }
  return out
}

/** Convertit une `FicheTechnique` chargée du serveur (nombres/Decimal→string
 * JSON) vers l'état local du formulaire (toutes chaînes, '' = non
 * renseigné). */
export function champsFicheDepuisServeur(fiche) {
  const out = ficheFieldsVides()
  if (!fiche) return out
  for (const cles of Object.values(CHAMPS_PAR_TYPE)) {
    for (const cle of cles) {
      const v = fiche[cle]
      out[cle] = (v === null || v === undefined) ? '' : String(v)
    }
  }
  return out
}

/** Sous-ensemble de `ficheFields` pertinent pour ce type, converti en
 * nombres (`null` si vide/invalide) — prêt pour le payload
 * `FicheTechniqueSerializer` (POST/PATCH `/stock/fiches-techniques/`). */
export function champsFichePourType(ficheType, ficheFields) {
  const typeBackend = typeFicheBackend(ficheType)
  const cles = CHAMPS_PAR_TYPE[typeBackend] ?? []
  const out = {}
  for (const cle of cles) {
    const brut = ficheFields?.[cle]
    if (brut === '' || brut === null || brut === undefined) { out[cle] = null; continue }
    const n = Number(brut)
    out[cle] = Number.isFinite(n) ? n : null
  }
  return out
}
