// QJR523 — UN SEUL couple de mappeurs lignes serveur ⇄ écran du générateur.
//
// Avant : trois constructions divergentes dans DevisGenerator.jsx — le mappeur
// de la réouverture `?edit=` (gardait optionnelle / type / variante / verrous /
// ordre mais PERDAIT groupe_*), celui d'un modèle appliqué (handlePresetApplied :
// l'inverse) et le `lignesPayload` inline de persisterDevis. `role_devis` ne
// survivait à aucun : `remplacer_lignes` re-devinait alors le rôle
// (domain/lignes.py) et écrasait un rôle posé par la composition (ex.
// 'onduleur_offgrid').
//
// Champs portés dans les DEUX sens : produit, designation, quantite, prix
// (HT serveur ⇄ TTC écran), taux_tva, optionnelle, type_ligne, ordre, variante,
// prix_manuel, quantite_manuelle, groupe_index / groupe_label, role_devis,
// remise (QJR529 — la remise PAR LIGNE stockée, '0' par défaut : l'envoyer à
// '0' en dur faisait monter le total client en silence au 1er enregistrement).
//
// Module PUR (aucun React, aucun import.meta) : exécuté par `node --test`.
import { ttcExactFromHt, htFromTtc } from '../solar.js'

const TYPES_STRUCTURE = new Set(['section', 'note'])

/**
 * Lignes servies par l'API (HT, snake_case) → lignes d'écran (TTC, forme
 * attendue par `withKeys` du générateur). Triées par (ordre, id) pour que les
 * sections/notes reviennent à leur place.
 * @param {Array<object>} lignes  lignes serveur (devis ou modèle appliqué)
 * @param {number|string} [tauxDevis]  taux du devis, repli d'une ligne sans taux
 */
export function lignesServeurVersEcran(lignes, tauxDevis) {
  if (!Array.isArray(lignes)) return []
  return lignes
    .slice()
    .sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0) || (a.id ?? 0) - (b.id ?? 0))
    .map((l) => {
      const taux = parseFloat(l.taux_tva ?? tauxDevis) || 20
      const produit = l.produit ?? l.produit_id
      return {
        produit: String(produit ?? ''),
        designation: l.designation ?? '',
        quantite: l.quantite == null ? '1' : String(parseFloat(l.quantite) || 0),
        // ERR-QAH-FIG-EDITION-PU-TTC-ARRONDI — prix PERSISTÉ : TTC au centime,
        // jamais arrondi au dirham (sinon rouvrir change le total et
        // ré-enregistrer modifie les prix en silence).
        prix_unit_ttc: String(ttcExactFromHt(l.prix_unitaire ?? l.prix_unit_ht ?? 0, taux)),
        taux_tva: String(taux),
        remise: String(parseFloat(l.remise) || 0),
        optionnelle: !!l.optionnelle,
        typeLigne: l.type_ligne ?? 'produit',
        variante: l.variante ?? '',
        prixManuel: !!l.prix_manuel,
        quantiteManuelle: !!l.quantite_manuelle,
        groupeIndex: l.groupe_index ?? null,
        groupeLabel: l.groupe_label ?? '',
        role_devis: l.role_devis ?? '',
      }
    })
}

const estStructure = (l) => TYPES_STRUCTURE.has(l.typeLigne)

/**
 * Lignes d'écran → corps `lignes` de replace-lines / devis atomique.
 * Retient les produits utilisables (produit + quantité > 0) et les
 * sections/notes à intitulé non vide ; `ordre` = position visuelle.
 * @param {Array<object>} lines  lignes d'écran
 * @param {{multiMode?: string}} [opts]  groupes villa envoyés seulement en mode 'villas'
 */
export function lignesEcranVersPayload(lines, { multiMode } = {}) {
  const villas = multiMode === 'villas'
  const gardees = (lines || []).filter((l) => (estStructure(l)
    ? !!(l.designation || '').trim()
    : (l.produit && parseFloat(l.quantite) > 0)))
  return gardees.map((l, idx) => {
    if (estStructure(l)) {
      // Une ligne section/note ne porte ni produit ni prix.
      return { type_ligne: l.typeLigne, ordre: idx, designation: l.designation }
    }
    return {
      produit: parseInt(l.produit, 10),
      designation: l.designation,
      quantite: l.quantite,
      prix_unitaire: htFromTtc(l.prix_unit_ttc, l.taux_tva ?? 20),
      remise: String(parseFloat(l.remise) || 0),
      taux_tva: String(l.taux_tva ?? 20),
      groupe_index: villas ? (l.groupeIndex ?? null) : null,
      groupe_label: villas ? (l.groupeLabel || '') : '',
      optionnelle: !!l.optionnelle,
      type_ligne: 'produit',
      ordre: idx,
      variante: l.variante || '',
      prix_manuel: !!l.prixManuel,
      quantite_manuelle: !!l.quantiteManuelle,
      // Rôle STOCKÉ de la ligne : renvoyé tel quel (vide ⇒ le serveur le
      // déduit du produit, comportement historique).
      role_devis: l.role_devis || '',
    }
  })
}
