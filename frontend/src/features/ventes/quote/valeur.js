// QJR86 — LA PRIMITIVE DE LA VALEUR SIGNÉE (module PUR, aucun import).
// ---------------------------------------------------------------------------
// LA règle unique de flux de données du parcours devis : **aucun nombre nu ne
// peut être rendu ni persisté**. Tout chiffre voyage signé de son origine :
//
//     { valeur, source: 'moteur' | 'saisie' | 'apercu' | null, motif? }
//
//   · `moteur` — chiffré par le SERVEUR (moteur horaire, dry-run de
//     composition, pipeline) : la seule source qui peut être publiée telle
//     quelle au client.
//   · `saisie` — tapé par le vendeur à l'écran. Ne se fait JAMAIS écraser par
//     un `moteur` arrivé après (invariant du reducer QJR87).
//   · `apercu` — dérivé LOCALEMENT à l'écran (miroir JS : `computeROI`,
//     `computeEtudeIndustrielle`, la moitié pompage…). C'est un repère de
//     vente, PAS une mesure : il est rendu avec la puce « estimation
//     d'exemple » (QJR35, rendu structurel par QJR89/QJR90).
//   · `null` — RIEN à montrer, avec le `motif` FRANÇAIS **VERBATIM** du
//     serveur (« ville manquante », « catalogue incomplet »…). Jamais un
//     défaut forfaitaire, jamais un 0 déguisé (règle fondateur « zéro chiffre
//     inventé », CLAUDE.md règle #4).
//
// `unwrap` EST LE DÉBALLEUR DE RENDU : elle refuse un nombre nu (TypeError) —
// c'est ce refus qui rend la règle exécutable au lieu d'être une convention de
// revue. QJR426 (relecture honnêteté, 02/09/2026) — elle N'EST PAS le SEUL
// code qui lit `.valeur` : `paireDimensionnement.js` lit `mSans.valeur` /
// `mAvec.valeur` directement APRÈS avoir vérifié `estFait` (une garde
// équivalente, écrite à la main plutôt que via `unwrap`) — c'est un second
// débaleur, pas un contournement de la règle « aucun nombre nu » (la garde
// `estFait` y joue le même rôle), mais l'en-tête ne doit pas prétendre
// qu'`unwrap` est seul à le faire.
//
// Module IMPORTÉ (QJR426, 02/09/2026) : `generator/CarteMetrique.jsx` (le
// déballeur de rendu), `paireDimensionnement.js` (ci-dessus) et
// `DevisGenerator.jsx` (signe les 13 cartes de métrique de l'écran).

/** Puce affichée À CÔTÉ d'une valeur d'aperçu — jamais à la place. */
export const PUCE_APERCU = "estimation d'exemple"

const SOURCES = ['moteur', 'saisie', 'apercu']

/** Une valeur est SIGNÉE si c'est un objet plat portant une `source` connue. */
const estSignee = (v) => (
  !!v && typeof v === 'object' && !Array.isArray(v)
  && 'source' in v && (v.source === null || SOURCES.includes(v.source))
)

const signer = (valeur, source) => {
  if (estSignee(valeur)) {
    throw new TypeError(
      `valeur.js : ${source}() a reçu une valeur DÉJÀ signée (${valeur.source}) — `
      + 'une valeur ne se re-signe pas, elle se transporte.')
  }
  return Object.freeze({ valeur, source })
}

/** Chiffré par le SERVEUR — publiable au client tel quel. */
export const moteur = (v) => signer(v, 'moteur')

/** Tapé par le vendeur — priorité absolue sur toute valeur moteur ultérieure. */
export const saisie = (v) => signer(v, 'saisie')

/** Dérivé localement à l'écran — rendu avec la puce « estimation d'exemple ». */
export const apercu = (v) => signer(v, 'apercu')

/**
 * RIEN à montrer, avec le motif FRANÇAIS verbatim (serveur ou écran). Le motif
 * est OBLIGATOIRE : un vide sans explication est exactement ce que cette
 * primitive existe pour empêcher.
 */
export function absent(motif) {
  if (typeof motif !== 'string' || motif.trim() === '') {
    throw new TypeError('valeur.js : absent(motif) exige un motif FR non vide — '
      + 'un vide sans explication est interdit.')
  }
  return Object.freeze({ valeur: null, source: null, motif })
}

/**
 * Y a-t-il un chiffre exploitable ? `false` pour un `absent`, pour une valeur
 * nulle/indéfinie et pour un NaN — un NaN signé reste un trou, pas un nombre.
 */
export function estFait(v) {
  if (!estSignee(v) || v.source === null) return false
  if (v.valeur === null || v.valeur === undefined) return false
  return !(typeof v.valeur === 'number' && Number.isNaN(v.valeur))
}

/**
 * LE SEUL DÉBALLEUR (aide de rendu). Rend `{ valeur, source, puce, motif }` :
 *   · `puce` = « estimation d'exemple » pour une valeur d'aperçu, sinon null ;
 *   · `motif` = le texte FR VERBATIM pour un `absent`, sinon null.
 * Refuse un nombre NU : c'est la garde qui rend la règle exécutable.
 */
export function unwrap(v) {
  if (!estSignee(v)) {
    throw new TypeError('valeur.js : unwrap() a reçu une valeur NON SIGNÉE — '
      + 'aucun nombre nu ne se rend ni ne se persiste (signez-la avec '
      + 'moteur()/saisie()/apercu(), ou omettez-la avec absent(motif)).')
  }
  if (v.source === null) {
    return Object.freeze({
      valeur: null, source: null, puce: null, motif: v.motif ?? null,
    })
  }
  return Object.freeze({
    valeur: v.valeur,
    source: v.source,
    puce: v.source === 'apercu' ? PUCE_APERCU : null,
    motif: null,
  })
}
