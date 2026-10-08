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
// '0' en dur faisait monter le total client en silence au 1er enregistrement),
// lot (QJR667 — rattachement à un lot multi-sites posé par « Lots /
// multi-sites » ; sans lui, replace-lines recréait les lignes hors lot),
// ligne_composee ⇄ compose (ERR-QJR570 — provenance composée / ajoutée à la
// main, persistée : D-QJR5-4), tva_base_legale ⇄ tvaBaseLegale (AGR218 —
// la base légale d'une exonération à 0 %, saisie, jamais pré-remplie).
//
// Module PUR (aucun React, aucun import.meta) : exécuté par `node --test`.
import { ttcExactFromHt, htFromTtc, tauxTvaOuDefaut } from '../solar.js'

const TYPES_STRUCTURE = new Set(['section', 'note'])

/**
 * ERR-QJR570 (D-QJR5-4) — une ligne serveur est-elle COMPOSÉE par le moteur ?
 * La provenance PERSISTÉE (`ligne_composee`) fait foi : true ⇒ composée (une
 * recomposition la remplace), false ⇒ ajoutée à la main (gardée). Absente ou
 * null (lignes antérieures, aucun backfill) ⇒ règle de repli : une ligne
 * produit relue sans verrou ni option est tenue pour composée.
 */
function composeRelu(l) {
  if ((l.type_ligne ?? 'produit') !== 'produit') return false
  if (l.ligne_composee === true) return true
  if (l.ligne_composee === false) return false
  return !l.prix_manuel && !l.quantite_manuelle && !l.optionnelle
}

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
      // ATOT20 — UNE règle avec le serveur : une ligne relue SANS taux est
      // chiffrée au taux du DEVIS (le serveur et le PDF lui appliquent ce
      // taux) ; jamais celui de la fiche produit (`produit_tva`), qui changeait
      // le total au premier « Enregistrer » sans saisie. Les lignes NOUVELLES
      // naissent avec le taux de leur produit (serveur `creer_ligne`,
      // TVA-LIGNE). 0 % reste 0 % (AGR216).
      const taux = tauxTvaOuDefaut(l.taux_tva ?? tauxDevis, 20)
      const produit = l.produit ?? l.produit_id
      // Marqueur d'écran `compose` ⇄ provenance persistée `ligne_composee`
      // (ERR-QJR570) : composée ⇒ remplacée par la prochaine recomposition,
      // ajoutée à la main ⇒ gardée.
      const compose = composeRelu(l)
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
        compose,
        variante: l.variante ?? '',
        prixManuel: !!l.prix_manuel,
        quantiteManuelle: !!l.quantite_manuelle,
        // AGNR16 — prix RELU du serveur : l'effet de tarif de l'écran
        // (`[clientId, lines.length]`) ne le réécrit jamais sans geste. Marqueur
        // d'écran seulement, jamais envoyé (absent de `lignesEcranVersPayload`).
        prixRelu: true,
        groupeIndex: l.groupe_index ?? null,
        groupeLabel: l.groupe_label ?? '',
        role_devis: l.role_devis ?? '',
        lot: l.lot ?? null,
        // AGR218 (contrat AGR200) — base légale d'un taux à 0 %, telle que
        // saisie (vide = aucune).
        tvaBaseLegale: l.tva_base_legale ?? '',
      }
    })
}

const estStructure = (l) => TYPES_STRUCTURE.has(l.typeLigne)

// Les lignes d'écran qui PARTENT au serveur (même filtre que le payload) :
// l'index `lignes[i]` d'un refus serveur se lit dans CETTE liste.
const lignesEnvoyees = (lines) => (lines || []).filter((l) => (estStructure(l)
  ? !!(l.designation || '').trim()
  : (l.produit && parseFloat(l.quantite) > 0)))

/**
 * Lignes d'écran → corps `lignes` de replace-lines / devis atomique.
 * Retient les produits utilisables (produit + quantité > 0) et les
 * sections/notes à intitulé non vide ; `ordre` = position visuelle.
 * @param {Array<object>} lines  lignes d'écran
 * @param {{multiMode?: string}} [opts]  groupes villa envoyés seulement en mode 'villas'
 */
export function lignesEcranVersPayload(lines, { multiMode } = {}) {
  const villas = multiMode === 'villas'
  const gardees = lignesEnvoyees(lines)
  return gardees.map((l, idx) => {
    if (estStructure(l)) {
      // Une ligne section/note ne porte ni produit ni prix (ni provenance).
      return {
        type_ligne: l.typeLigne, ordre: idx, designation: l.designation,
        ligne_composee: null,
      }
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
      // QJR667 — le lot de la ligne (id d'un lot de CE devis, sinon null).
      lot: l.lot ?? null,
      // ERR-QJR570 (D-QJR5-4) — la provenance PERSISTÉE : true = posée par
      // le moteur (une recomposition la remplace), false = ajoutée à la main
      // (« Ajouter une ligne », jamais remplacée, même après réouverture).
      ligne_composee: !!l.compose,
      // AGR218 — base légale de l'exonération (obligatoire à 0 %, refus 400
      // serveur sinon) ; vide = aucune. Jamais de texte proposé par défaut.
      tva_base_legale: String(l.tvaBaseLegale ?? ''),
    }
  })
}

/**
 * AGR218 — une ligne PRODUIT à 0 % de TVA sans base légale saisie ? (Même
 * règle que le serveur, `domain/lignes.exiger_base_legale_tva`.) Le taux
 * n'est jamais changé ici : on signale, on ne corrige pas.
 */
export function baseLegaleManquante(l) {
  if (!l || estStructure(l)) return false
  const taux = parseFloat(l.taux_tva)
  if (!Number.isFinite(taux) || taux !== 0) return false
  return !String(l.tvaBaseLegale ?? '').trim()
}

const CHAMP_BASE_LEGALE = /^lignes\[(\d+)\]\.tva_base_legale$/

/**
 * AGR218 — refus 400 du serveur (`{detail, champ: 'lignes[i].tva_base_legale'}`,
 * contrat `exemple_400_tva_base_legale`) → `{ [_key de la ligne]: detail }`,
 * l'index étant celui des lignes ENVOYÉES. Tout autre refus → `{}`.
 */
export function erreursBaseLegaleServeur(data, lines) {
  const m = CHAMP_BASE_LEGALE.exec(String(data?.champ ?? ''))
  if (!m) return {}
  const ligne = lignesEnvoyees(lines)[Number(m[1])]
  if (!ligne || ligne._key == null) return {}
  return { [ligne._key]: String(data.detail ?? '') }
}
