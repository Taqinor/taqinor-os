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

const enTexte = (v) => (v === null || v === undefined ? '' : Array.isArray(v) ? v.join(', ') : String(v))

const estObjet = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)

/** L'entrée stockée → l'état du formulaire (chaînes) ; rien n'est inventé. */
export function depuisEntree(entree) {
  const b = estObjet(entree?.batterie) ? entree.batterie : {}
  const h = estObjet(entree?.hors_reseau) ? entree.hors_reseau : {}
  const etat = { strategie: enTexte(b.strategie), couplage: enTexte(b.couplage), actif: h.actif === true, jours: enTexte(h.jours_autonomie) }
  for (const { cle } of CHAMPS_BATTERIE) etat[cle] = enTexte(b[cle])
  return etat
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
  const stockeH = estObjet(entree?.hors_reseau) ? entree.hors_reseau : null
  const horsReseau = { ...(stockeH ?? {}) }
  const jours = nombreOuNull(etat.jours)
  if (etat.actif || stockeH) horsReseau.actif = Boolean(etat.actif)
  if (jours !== null || 'jours_autonomie' in horsReseau) horsReseau.jours_autonomie = jours
  const corps = {}
  if (stockeB || Object.keys(batterie).length) corps.batterie = batterie
  if (stockeH || Object.keys(horsReseau).length) corps.hors_reseau = horsReseau
  return corps
}
