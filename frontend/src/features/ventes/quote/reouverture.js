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
