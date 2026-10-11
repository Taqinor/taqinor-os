// ENF22 — helpers extraits de SaisiesElectriques.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.
import { nombreOuNull, texteOuNull } from './entreeElectrique'

/** Les champs à nombre ou texte simple, à plat dans l'entrée. `groupe` ordonne l'écran. */
export const CHAMPS = [
  { cle: 'temperature_min_c', libelle: 'Température minimale du site', unite: '°C', genre: 'nombre', groupe: 'Site' },
  { cle: 'temperature_max_c', libelle: 'Température maximale du site', unite: '°C', genre: 'nombre', groupe: 'Site' },
  { cle: 'dc_m', libelle: 'Longueur de liaison DC', unite: 'm', genre: 'nombre', groupe: 'Liaisons' },
  { cle: 'ac_m', libelle: 'Longueur de liaison AC', unite: 'm', genre: 'nombre', groupe: 'Liaisons' },
  { cle: 'descente_m', libelle: 'Descente de toiture', unite: 'm', genre: 'nombre', groupe: 'Liaisons', dans: 'cheminement' },
  { cle: 'coffret_vers_onduleur_m', libelle: 'Coffret vers onduleur', unite: 'm', genre: 'nombre', groupe: 'Liaisons', dans: 'cheminement' },
  { cle: 'onduleur_vers_tgbt_m', libelle: 'Onduleur vers TGBT', unite: 'm', genre: 'nombre', groupe: 'Liaisons', dans: 'cheminement' },
  { cle: 'phases', libelle: 'Phases du branchement', unite: '1 ou 3', genre: 'nombre', groupe: 'Réseau' },
  { cle: 'regime', libelle: 'Régime de neutre', unite: 'TT, TN ou IT', genre: 'texte', groupe: 'Réseau' },
  { cle: 'plafond_kwc_par_onduleur', libelle: 'Plafond de kWc par onduleur', unite: 'kWc', genre: 'nombre', groupe: 'Options' },
  { cle: 'longueur_chaine_forcee', libelle: 'Longueur de chaîne imposée', unite: 'modules', genre: 'nombre', groupe: 'Options' },
  { cle: 'zone_keraunique', libelle: 'Zone kéraunique', unite: '', genre: 'booleen', groupe: 'Options' },
  { cle: 'inclure_prise_terre', libelle: 'Inclure la prise de terre', unite: '', genre: 'booleen', groupe: 'Options' },
]

/** L'exigence du marché : un objet `{ratio_dc_ac_max, ratio_dc_ac_alerte, reference}`. */
export const EXIGENCE = [
  { cle: 'ratio_dc_ac_max', libelle: 'Ratio DC/AC maximal imposé', genre: 'nombre' },
  { cle: 'ratio_dc_ac_alerte', libelle: 'Seuil d’alerte DC/AC', genre: 'nombre' },
  { cle: 'reference', libelle: 'Référence du cahier des charges', genre: 'texte' },
]

/** Les trois grandeurs sourcées du transformateur. */
export const GRANDEURS = [
  { cle: 'perte_a_vide_kw', libelle: 'Perte à vide', unite: 'kW' },
  { cle: 'perte_en_charge_kw_nominale', libelle: 'Perte en charge nominale', unite: 'kW' },
  { cle: 'puissance_nominale_kw', libelle: 'Puissance nominale', unite: 'kW' },
]

const enTexte = (v) => (v === null || v === undefined ? '' : String(v))

const BOOL_VERS_TEXTE = (v) => (v === true ? 'oui' : v === false ? 'non' : '')

const TEXTE_VERS_BOOL = (t) => (t === 'oui' ? true : t === 'non' ? false : null)

const estObjet = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)

/** L'entrée stockée (GET) → l'état du formulaire, en chaînes : rien n'est inventé. */
export function depuisEntree(entree) {
  const e = entree ?? {}
  const saisie = { exigence: {}, transformateur: { declare: '' } }
  for (const { cle, genre, dans } of CHAMPS) {
    const brut = dans ? (estObjet(e[dans]) ? e[dans][cle] : null) : e[cle]
    saisie[cle] = genre === 'booleen' ? BOOL_VERS_TEXTE(brut) : enTexte(brut)
  }
  for (const { cle } of EXIGENCE) saisie.exigence[cle] = enTexte(estObjet(e.exigence_marche) ? e.exigence_marche[cle] : null)
  const t = estObjet(e.transformateur) ? e.transformateur : {}
  saisie.transformateur.declare = BOOL_VERS_TEXTE(t.declare)
  for (const { cle } of GRANDEURS) {
    const g = estObjet(t[cle]) ? t[cle] : {}
    saisie.transformateur[cle] = { valeur: enTexte(g.valeur), source: enTexte(g.source), reference: enTexte(g.reference) }
  }
  return saisie
}

const valeurPosee = (genre, texte) => {
  if (genre === 'booleen') return TEXTE_VERS_BOOL(texte)
  return genre === 'nombre' ? nombreOuNull(texte) : texteOuNull(texte)
}

/** Le bloc `cheminement` : fusionné sur l'existant, une clé vide et absente n'est pas créée. */
function cheminementPoste(saisie, entree) {
  const existant = estObjet(entree?.cheminement) ? entree.cheminement : null
  const champs = CHAMPS.filter((c) => c.dans === 'cheminement')
  const saisies = champs.filter((c) => String(saisie[c.cle] ?? '').trim() !== '')
  if (!existant && saisies.length === 0) return undefined
  const bloc = { ...(existant ?? {}) }
  for (const { cle } of champs) {
    const v = nombreOuNull(saisie[cle])
    if (v !== null || cle in bloc) bloc[cle] = v
  }
  return bloc
}

function exigencePosee(saisie, entree) {
  const existant = estObjet(entree?.exigence_marche) ? entree.exigence_marche : null
  const remplis = EXIGENCE.filter((c) => String(saisie.exigence[c.cle] ?? '').trim() !== '')
  if (remplis.length === 0) return existant ? null : undefined
  const bloc = { ...(existant ?? {}) }
  for (const { cle, genre } of EXIGENCE) {
    const v = valeurPosee(genre, saisie.exigence[cle])
    if (v !== null || cle in bloc) bloc[cle] = v
  }
  return bloc
}

function transformateurPoste(saisie, entree) {
  const t = saisie.transformateur
  const stocke = estObjet(entree?.transformateur) ? entree.transformateur : {}
  const rempli = GRANDEURS.some(({ cle }) => String(t[cle].valeur).trim() !== '' || String(t[cle].source).trim() !== '')
  if (t.declare === '' && !rempli) return undefined
  const bloc = { declare: TEXTE_VERS_BOOL(t.declare) ?? false }
  for (const { cle } of GRANDEURS) {
    const g = t[cle]
    const saisi = String(g.valeur).trim() !== '' || String(g.source).trim() !== '' || String(g.reference).trim() !== ''
    if (!saisi) {
      if (cle in stocke) bloc[cle] = null
      continue
    }
    const grandeur = { valeur: nombreOuNull(g.valeur), source: texteOuNull(g.source) }
    const reference = texteOuNull(g.reference)
    if (reference !== null || (estObjet(stocke[cle]) && 'reference' in stocke[cle])) grandeur.reference = reference
    bloc[cle] = grandeur
  }
  return bloc
}

/**
 * Le corps POSTÉ : les champs du formulaire seulement (la fusion par clé du serveur laisse
 * les autres intacts). Un champ vidé vaut `null`, jamais `0` ; une clé jamais saisie et
 * absente du stock n'est pas inventée — `entree` est l'entrée relue, qui sert de repère.
 */
export function corpsDeSaisie(saisie, entree) {
  const corps = {}
  for (const { cle, genre, dans } of CHAMPS) {
    if (dans) continue
    const v = valeurPosee(genre, saisie[cle])
    // Une valeur stockée que le formulaire ne sait pas lire (booléen attendu, autre chose
    // servi) n'est jamais écrasée par un « non précisé » : la clé n'est pas renvoyée.
    const illisible = genre === 'booleen' && v === null && entree != null
      && entree[cle] !== null && entree[cle] !== undefined && typeof entree[cle] !== 'boolean'
    if (illisible) continue
    if (v !== null || entree == null || cle in entree) corps[cle] = v
  }
  const cheminement = cheminementPoste(saisie, entree)
  if (cheminement !== undefined) corps.cheminement = cheminement
  const exigence = exigencePosee(saisie, entree)
  if (exigence !== undefined) corps.exigence_marche = exigence
  const transformateur = transformateurPoste(saisie, entree)
  if (transformateur !== undefined) corps.transformateur = transformateur
  return corps
}
