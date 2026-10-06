// QJR526 — ce que la RÉOUVERTURE d'un devis (`?edit=`) doit re-dériver de ses
// LIGNES, parce que rien d'autre ne le stocke : le wattage panneau, la
// structure (bouton acier/alu + produit catalogue), le hors-réseau et
// « Composition libre ».
//
// Constat (EN DIRECT, devis 637) : 10 × 550 W revenaient à 710 W (défaut du
// reducer) — 7,1 kWc au lieu de 5,5 — et l'aluminium revenait en acier ; en
// industriel/commercial le kWc faux re-persistait taux / payback, imprimés ;
// un devis « Composition libre » rouvert échouait à la validation.
//
// Fonction PURE (node --test) ; mêmes prédicats que l'écran (solar.js).
import {
  parseWatt, structureRoleForName, classifyProduct,
  isPanel, isOffgridInverter, isReseauInverter, isHybridInverter, isPompe,
} from '../solar.js'

const quantite = (l) => parseFloat(l?.quantite) || 0
const typeLigne = (l) => l?.typeLigne ?? l?.type_ligne ?? 'produit'

/**
 * @param {Array<object>} lignes  lignes d'écran (lignesServeurVersEcran) ou
 *   serveur — seuls designation / produit / quantite / type de ligne sont lus
 * @param {{mode?: string}} [opts]  marché du devis ('agricole' : pompe)
 * @returns {{panelW: string|null, structure: string|null,
 *   structureProduitId: string|null, horsReseau: boolean,
 *   accessoiresOnly: boolean}}
 *   `null` = rien de lisible sur les lignes → l'écran garde son défaut.
 */
export function deriverReouverture(lignes, { mode } = {}) {
  const produits = (Array.isArray(lignes) ? lignes : [])
    .filter(l => typeLigne(l) === 'produit' && quantite(l) > 0)
  const des = (l) => l.designation || ''

  // Wattage : celui de la ligne panneau DOMINANTE (le plus grand compte),
  // même règle que domain/scenario.py `ligne_panneau_dominante`.
  const panneaux = produits.filter(l => isPanel(des(l)))
  const dominante = panneaux.reduce(
    (best, l) => (!best || quantite(l) > quantite(best) ? l : best), null)
  const watt = dominante ? parseWatt(des(dominante)) : null

  // Structure : la première ligne de structure du devis.
  const ligneStructure = produits.find(l => classifyProduct(des(l)) === 'structure')
  let structure = null
  let structureProduitId = null
  if (ligneStructure) {
    const role = structureRoleForName(des(ligneStructure))
    if (role === 'structure_alu') structure = 'aluminium'
    else if (role === 'structure_acier') structure = 'acier'
    const pid = ligneStructure.produit
    if (pid != null && String(pid) !== '') structureProduitId = String(pid)
  }

  const horsReseau = produits.some(l => isOffgridInverter(des(l)))

  // « Composition libre » : aucune paire panneau + onduleur (agricole : aucune
  // pompe) — seulement s'il y a au moins une ligne produit.
  let accessoiresOnly = false
  if (produits.length) {
    if (mode === 'agricole') {
      accessoiresOnly = !produits.some(l => isPompe(des(l)))
    } else {
      const aOnduleur = produits.some(l => isReseauInverter(des(l))
        || isHybridInverter(des(l)) || isOffgridInverter(des(l)))
      accessoiresOnly = !(panneaux.length && aOnduleur)
    }
  }

  return {
    panelW: watt ? String(watt) : null,
    structure,
    structureProduitId,
    horsReseau,
    accessoiresOnly,
  }
}

// ── CIQ222 — `etude_params.tarif_declare` stocké → état d'écran (`?edit=`) ──
// Inverse exact de `tarifDeclareDepuisSaisie` (etudeMarcheBloc.js) : la date
// de saisie revient telle quelle, aucun nombre n'est reformaté.
const texteTarif = (v) => (v === null || v === undefined ? '' : String(v))

export function saisieDepuisTarifDeclare(td) {
  const t = td && typeof td === 'object' ? td : null
  if (!t) return null
  const mt = t.mt || {}
  return {
    contrat: t.contrat || '',
    baseTarifs: t.base_tarifs || '',
    optionBiHoraire: t.option_bi_horaire === true,
    pointe: texteTarif(mt.tarif_pointe),
    pleines: texteTarif(mt.tarif_pleines),
    creuses: texteTarif(mt.tarif_creuses),
    primeFixe: texteTarif(mt.prime_fixe_kva_an),
    puissance: texteTarif(mt.puissance_souscrite_kva),
    dateFacture: t.date_facture || '',
    provenance: t.provenance || '',
    saisiLe: t.saisi_le || '',
  }
}

// ── CIQ223 — `etude_params.saisies_economie_ci` stocké → état d'écran ──
// Les nombres reviennent en texte (l'écran les tient tels que tapés) ; les
// dates de saisie et les sources reviennent telles quelles.
const enTexte = (o) => (o && typeof o === 'object'
  ? Object.fromEntries(Object.entries(o).map(([k, v]) => [k,
    typeof v === 'number' ? String(v) : (v === null || v === undefined ? '' : v)]))
  : null)

export function ecoCiDepuisSaisies(s) {
  const e = s && typeof s === 'object' ? s : {}
  return {
    tva_recuperable: enTexte(e.tva_recuperable),
    taux_actualisation_client: enTexte(e.taux_actualisation_client),
    revente_demandee: e.revente_demandee === true,
    parcours_aide: e.parcours_aide || null,
    offre_financement: enTexte(e.offre_financement),
    offre_cse_concurrente: enTexte(e.offre_cse_concurrente),
    fiscalite_client: enTexte(e.fiscalite_client),
  }
}
