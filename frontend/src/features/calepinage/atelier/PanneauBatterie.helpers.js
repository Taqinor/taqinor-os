// ENF22 — helpers extraits de PanneauBatterie.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.
import { nombreOuNull, texteOuNull } from '../electrique/entreeElectrique'

/* ============================================================================
   ACAL167 — DÉCLARER LA BATTERIE ET LE MODE HORS RÉSEAU.
   Les champs se pré-remplissent de l'entrée STOCKÉE (`GET entree-electrique/`) ; le corps
   posté ne porte que `batterie` et `hors_reseau` (la fusion par clé du serveur laisse le
   reste intact). Un champ vidé vaut `null`, jamais 0 ; une clé jamais saisie et absente du
   stock n'est pas inventée.
   ========================================================================== */

export const STRATEGIES = [
  'autoconso', 'peak_shaving', 'backup', 'decalage', 'plafond_injection', 'heures_tarif',
]

export const CHAMPS_BATTERIE = [
  { cle: 'packs', libelle: 'Nombre de packs', genre: 'nombre' },
  { cle: 'seuil_effacement_kw', libelle: 'Seuil d’effacement (kW)', genre: 'nombre' },
  { cle: 'reserve_backup_kwh', libelle: 'Réserve de secours (kWh)', genre: 'nombre' },
  { cle: 'heures_charge', libelle: 'Heures de charge (0-23, séparées par des virgules)', genre: 'heures' },
  { cle: 'heures_decharge', libelle: 'Heures de décharge (0-23, séparées par des virgules)', genre: 'heures' },
]

export const SEUILS_HORS_RESEAU = ['veille_pct', 'entretien_pct', 'arret_pct']

/** ACAL799 — les champs de `batterie.coupures` (serveur : `batterie_declaration.py::CHAMPS_COUPURES`). */
export const CHAMPS_COUPURES = ['nombre_par_an', 'duree_h', 'heure_debut']

/** ACAL803 — les nombres de `hors_reseau.groupe` (serveur : `groupe_appoint.py::CLES_GROUPE`, hors `actif`). */
const CHAMPS_GROUPE = ['puissance_kw', 'soc_demarrage_pct', 'soc_arret_pct', 'heures_max_par_jour']

const enTexte = (v) => (v === null || v === undefined ? '' : Array.isArray(v) ? v.join(', ') : String(v))

const estObjet = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)

/** L'entrée stockée → l'état du formulaire (chaînes) ; rien n'est inventé. */
export function depuisEntree(entree) {
  const b = estObjet(entree?.batterie) ? entree.batterie : {}
  const h = estObjet(entree?.hors_reseau) ? entree.hors_reseau : {}
  const etat = { strategie: enTexte(b.strategie), couplage: enTexte(b.couplage), actif: h.actif === true, jours: enTexte(h.jours_autonomie) }
  for (const { cle } of CHAMPS_BATTERIE) etat[cle] = enTexte(b[cle])
  // ACAL788 — appareils à tenir pendant une coupure : relus du stock, jamais préremplis.
  etat.appareils = Array.isArray(b.appareils)
    ? b.appareils.map((a) => ({
      nom: enTexte(a?.nom),
      puissance_continue_kw: enTexte(a?.puissance_continue_kw),
      puissance_pointe_kw: enTexte(a?.puissance_pointe_kw),
      quantite: enTexte(a?.quantite),
    }))
    : []
  etat.duree_secours_h = enTexte(b.duree_secours_h)
  // ACAL799 — les trois réponses sur les coupures : relues du stock, jamais préremplies.
  const coupures = estObjet(b.coupures) ? b.coupures : {}
  etat.coupures = Object.fromEntries(CHAMPS_COUPURES.map((cle) => [cle, enTexte(coupures[cle])]))
  // ACAL792 — fenêtres de la commande horaire, part et plafond effaçables : relus du stock.
  const fen = estObjet(b.fenetres) ? b.fenetres : {}
  etat.fenetres = {
    charge: Array.isArray(fen.charge) ? fen.charge.map(fenetreDepuis) : [],
    decharge: Array.isArray(fen.decharge) ? fen.decharge.map(fenetreDepuis) : [],
  }
  etat.part_effacable_pct = enTexte(b.part_effacable_pct)
  etat.plafond_effacable_kw = enTexte(b.plafond_effacable_kw)
  // ACAL791 — seuils de protection hors réseau : relus du stock, jamais préremplis.
  const seuils = estObjet(h.seuils) ? h.seuils : {}
  etat.seuils = Object.fromEntries(SEUILS_HORS_RESEAU.map((cle) => [cle, enTexte(seuils[cle])]))
  // ACAL803 — le groupe d'appoint : relu du stock, jamais prérempli.
  const groupe = estObjet(h.groupe) ? h.groupe : {}
  etat.groupe = { actif: groupe.actif === true, ...Object.fromEntries(CHAMPS_GROUPE.map((cle) => [cle, enTexte(groupe[cle])])) }
  return etat
}

/** ACAL792 — l'état d'une fenêtre : début/fin quand les heures se suivent, sinon les heures telles qu'enregistrées. */
function fenetreDepuis(f) {
  const heures = Array.isArray(f?.heures) ? [...f.heures].sort((a, b) => a - b) : []
  const suivies = heures.length > 0 && heures.every((h, i) => i === 0 || h === heures[i - 1] + 1)
  return {
    debut: suivies ? String(heures[0]) : '',
    fin: suivies ? String(heures[heures.length - 1] + 1) : '',
    soc: enTexte(f?.soc_cible_pct),
    brut: heures.length && !suivies ? heures : null,
  }
}

/** ACAL792 — « de 10 h à 14 h » (fin exclue) → `[10, 11, 12, 13]` ; une plage non lisible → `[]` (le serveur refuse, nommé). */
function heuresDeFenetre(f) {
  if (f.brut) return f.brut
  const debut = nombreOuNull(f.debut)
  const fin = nombreOuNull(f.fin)
  if (debut === null || fin === null || fin <= debut) return []
  return Array.from({ length: fin - debut }, (_, i) => debut + i)
}

const lireHeures = (texte) => String(texte).split(/[,;]/).map((t) => t.trim()).filter(Boolean).map(Number)

/** Le corps POSTÉ : `{batterie?, hors_reseau?}`, fusionné sur l'existant (clés inconnues conservées). */
export function corpsDeclaration(etat, entree) {
  const stockeB = estObjet(entree?.batterie) ? entree.batterie : null
  const batterie = { ...(stockeB ?? {}) }
  const pose = (cle, valeur) => {
    if (valeur !== null || cle in batterie) batterie[cle] = valeur
  }
  pose('strategie', texteOuNull(etat.strategie))
  pose('couplage', texteOuNull(etat.couplage))
  for (const { cle, genre } of CHAMPS_BATTERIE) {
    pose(cle, genre === 'heures'
      ? (String(etat[cle]).trim() === '' ? null : lireHeures(etat[cle]))
      : nombreOuNull(etat[cle]))
  }
  // ACAL788 — appareils et durée (nombres, jamais du texte) ; la réserve en bloc est remplacée.
  const appareils = (etat.appareils ?? []).map((a) => ({
    nom: texteOuNull(a.nom),
    puissance_continue_kw: nombreOuNull(a.puissance_continue_kw),
    puissance_pointe_kw: nombreOuNull(a.puissance_pointe_kw),
    quantite: nombreOuNull(a.quantite),
  }))
  pose('appareils', appareils.length ? appareils : null)
  pose('duree_secours_h', nombreOuNull(etat.duree_secours_h))
  // ACAL799 — `batterie.coupures` : posé dès qu'une réponse est donnée (ou déjà au stock), jamais inventé.
  const coupures = Object.fromEntries(CHAMPS_COUPURES.map((cle) => [cle, nombreOuNull(etat.coupures?.[cle])]))
  pose('coupures', Object.values(coupures).some((v) => v !== null) ? coupures : null)
  // ACAL792 — des fenêtres posées remplacent les deux listes d'heures (jamais les deux formes).
  const fenetres = etat.fenetres ?? { charge: [], decharge: [] }
  if (fenetres.charge.length || fenetres.decharge.length) {
    const versCorps = (f) => ({ heures: heuresDeFenetre(f), soc_cible_pct: nombreOuNull(f.soc) })
    batterie.fenetres = { charge: fenetres.charge.map(versCorps), decharge: fenetres.decharge.map(versCorps) }
    batterie.heures_charge = null
    batterie.heures_decharge = null
  } else {
    pose('fenetres', null)
  }
  pose('part_effacable_pct', nombreOuNull(etat.part_effacable_pct))
  pose('plafond_effacable_kw', nombreOuNull(etat.plafond_effacable_kw))
  if (appareils.length) batterie.reserve_backup_kwh = null
  const stockeH = estObjet(entree?.hors_reseau) ? entree.hors_reseau : null
  const horsReseau = { ...(stockeH ?? {}) }
  const jours = nombreOuNull(etat.jours)
  if (etat.actif || stockeH) horsReseau.actif = Boolean(etat.actif)
  if (jours !== null || 'jours_autonomie' in horsReseau) horsReseau.jours_autonomie = jours
  // ACAL791 — jamais postés si aucun champ n'est rempli et qu'aucun seuil n'est enregistré.
  const seuils = Object.fromEntries(SEUILS_HORS_RESEAU.map((cle) => [cle, nombreOuNull(etat.seuils?.[cle])]))
  if (Object.values(seuils).some((v) => v !== null) || 'seuils' in horsReseau) horsReseau.seuils = seuils
  // ACAL803 — case cochée : le groupe et ses quatre nombres ; décochée : `{actif: false}` seulement s'il était au stock.
  if (etat.actif && etat.groupe?.actif) {
    horsReseau.groupe = { actif: true, ...Object.fromEntries(CHAMPS_GROUPE.map((cle) => [cle, nombreOuNull(etat.groupe[cle])])) }
  } else if ('groupe' in horsReseau) {
    horsReseau.groupe = { actif: false }
  }
  const corps = {}
  if (stockeB || Object.keys(batterie).length) corps.batterie = batterie
  if (stockeH || Object.keys(horsReseau).length) corps.hors_reseau = horsReseau
  return corps
}
