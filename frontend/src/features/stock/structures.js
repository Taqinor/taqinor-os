/* ── STKCAT10 — LES STRUCTURES SÉLECTIONNABLES, PURES ──────────────────────
   Moitié SANS RENDU de `StructureSelector.jsx` (la règle `react-refresh/
   only-export-components` interdit d'exporter autre chose qu'un composant
   depuis un `.jsx` ; ces fonctions vivent donc ici, testables sans DOM).

   Décision fondateur du 16/09/2026 (audit L3 stock ↔ CRM ↔ devis, « Pergola
   introuvable ») : le bouton acier / aluminium est REMPLACÉ par un sélecteur
   ouvert sur TOUTES les structures de la société — celles d'aujourd'hui ET
   celles de demain. Une pergola, un carport, un bac lesté n'ont jamais pu
   être devisés parce que deux valeurs figées dans le code décidaient à la
   place du catalogue ; ce module ne connaît AUCUNE liste de structures, il ne
   connaît que la CATÉGORIE TYPÉE `structure` (`typeOfProduit`, STKCAT11 —
   l'enum serveur `stock.Categorie.TypeEquipement`, stable même si la
   catégorie est renommée ou traduite). */
import { typeOfProduit } from './catalogue'

/**
 * Le produit est-il une structure ÉLIGIBLE ? TROIS gardes, dans cet ordre :
 *   1. `is_archived` — une fiche archivée ne se devise plus ;
 *   2. `prix_vente > 0` — règle maison : une auto-composition ne cote JAMAIS
 *      un produit sans prix (mêmes mots que « prix à renseigner ») ;
 *   3. `typeOfProduit(p) === 'structure'` — la catégorie TYPÉE, jamais un
 *      mot-clé du nom (c'est précisément ce que le mot-clé ne savait pas voir).
 */
export const estStructureEligible = (p) => (
  !!p
  && !p.is_archived
  && parseFloat(p.prix_vente) > 0
  && typeOfProduit(p) === 'structure'
)

/**
 * Structures éligibles, ORDONNÉES comme le catalogue les range : `categorie.
 * ordre` (l'ordre délibéré du seeder) d'abord, puis le nom de la catégorie
 * (départage deux catégories de même rang), puis le nom du produit. Jamais
 * l'ordre d'arrivée réseau — deux ouvertures de l'écran montrent la même
 * liste dans le même ordre.
 */
export function structuresEligibles(produits) {
  const liste = Array.isArray(produits) ? produits.filter(estStructureEligible) : []
  return liste.slice().sort((a, b) => (
    (a.categorie?.ordre ?? 999) - (b.categorie?.ordre ?? 999)
    || String(a.categorie?.nom ?? '').localeCompare(String(b.categorie?.nom ?? ''))
    || String(a.nom ?? '').localeCompare(String(b.nom ?? ''))
  ))
}

/**
 * Les mêmes structures, GROUPÉES par catégorie (un `<optgroup>` par
 * catégorie), dans l'ordre de `structuresEligibles`. Une société peut très
 * bien avoir plusieurs catégories typées `structure` (« Structures »,
 * « Pergolas », « Carports ») : le groupement les montre telles qu'elle les a
 * rangées, jamais dans un ordre inventé.
 */
export function groupesStructures(produits) {
  const groupes = []
  const parNom = new Map()
  for (const p of structuresEligibles(produits)) {
    const nom = p.categorie?.nom || 'Structures'
    if (!parNom.has(nom)) {
      const groupe = { categorie: nom, items: [] }
      parNom.set(nom, groupe)
      groupes.push(groupe)
    }
    parNom.get(nom).items.push(p)
  }
  return groupes
}
