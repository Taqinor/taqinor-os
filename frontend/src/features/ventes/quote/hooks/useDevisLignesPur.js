// QJR90 — moitié PURE de `useDevisLignes` : lignes, verrou `prixManuel`,
// résolution de tarif et suggestion de TVA.
//
// LES DEUX RÈGLES QUE CES FONCTIONS RENDENT EXÉCUTABLES :
//   · N2 — un prix TAPÉ À LA MAIN n'est JAMAIS réécrit par la résolution de
//     liste de prix (`DevisGenerator.jsx:2024-2030`) ; seul un changement de
//     PRODUIT sur la ligne lève le verrou (`:2051-2053`) ;
//   · VX249(b) — la TVA attendue est une SUGGESTION : elle signale une
//     incohérence, elle ne recale jamais la frappe (la frappe reste souveraine)
//     et une modification manuelle du taux retire le style « suggéré » de
//     CETTE ligne seulement.
//
// Module AJOUTÉ TESTÉ, IMPORTÉ PAR PERSONNE (vague M4).
import { expectedTvaForDesignation } from '../../solar.js'

/** Écrit un champ de ligne. Le prix tapé pose le verrou `prixManuel` (N2). */
export function ecrireChamp(lignes, key, champ, valeur) {
  return (lignes ?? []).map((l) => (l._key !== key ? l : {
    ...l,
    [champ]: valeur,
    ...(champ === 'taux_tva' ? { _tvaSuggested: false } : {}),
    ...(champ === 'prix_unit_ttc' ? { prixManuel: true } : {}),
  }))
}

/** Resélectionner un produit reprend la main sur son prix catalogue (N2). */
export function changerProduit(lignes, key, produit) {
  return (lignes ?? []).map((l) => (l._key !== key ? l : {
    ...l,
    produit: produit?.id != null ? String(produit.id) : '',
    designation: produit?.nom ?? l.designation,
    prixManuel: false,      // le verrou tombe : le catalogue peut réécrire
  }))
}

/**
 * Applique un prix résolu (liste de prix client) à UNE ligne. Ne touche JAMAIS
 * une ligne verrouillée `prixManuel`, et ne touche jamais les autres lignes.
 * Rend `{ lignes, badge }` — `badge` = nom de la liste quand la source n'est
 * pas `standard`, sinon `null` (le badge doit alors être RETIRÉ).
 */
export function appliquerTarif(lignes, key, tarif) {
  const horsStandard = !!tarif && tarif.source && tarif.source !== 'standard'
  if (!horsStandard) return { lignes: lignes ?? [], badge: null }
  return {
    lignes: (lignes ?? []).map((l) => (
      (l._key === key && !l.prixManuel)
        ? { ...l, prix_unit_ttc: String(tarif.prix) }
        : l)),
    badge: tarif.liste_nom ?? null,
  }
}

/**
 * Suggestion de TVA d'après la désignation (10 % panneaux / 20 % le reste,
 * surchargeable par les repères société). Rend `{ attendu, coherent }` :
 * l'écran SIGNALE, il ne recale pas.
 */
export function suggestionTva(ligne, tvaConfig) {
  const attendu = expectedTvaForDesignation(ligne?.designation ?? '', tvaConfig)
  const pose = Number.parseFloat(ligne?.taux_tva)
  return {
    attendu,
    coherent: Number.isFinite(pose) ? pose === attendu : false,
  }
}

/** Lignes réellement enregistrables : un produit ET une quantité > 0. */
export const lignesUtilisables = (lignes) =>
  (lignes ?? []).filter((l) => l.produit && (Number.parseFloat(l.quantite) || 0) > 0)
