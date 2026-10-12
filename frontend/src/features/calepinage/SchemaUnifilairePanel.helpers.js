// ENF22 — helpers extraits de SchemaUnifilairePanel.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.
import { telechargerBlob } from './exportImage'
import { motifDuRefusBlob } from './motifRefusBlob'
import { svgTexteEnPng } from './documents/deposerImage'

/* ============================================================================
   CAL195 — LE SCHÉMA UNIFILAIRE, DANS LE MODULE.
   ----------------------------------------------------------------------------
   Le schéma existait déjà — mais seulement à l'intérieur du PDF de devis. Un
   calepinage sans devis n'en avait aucun, et personne ne pouvait le regarder
   avant d'avoir chiffré.

   CE PANNEAU NE DESSINE RIEN. Le SVG est composé PAR LE SERVEUR (le MÊME
   moteur `core.electrique` que le devis, à travers la porte
   `apps.ventes.selectors.schema_unifilaire_svg`) : deux surfaces ne peuvent
   donc pas montrer deux schémas qui se contredisent. L'écran l'insère tel
   quel et n'ajoute pas un trait.

   FICHE INCOMPLÈTE ⇒ PAS DE SCHÉMA, et on le DIT. `svg: null` n'est jamais
   affiché comme un cadre vide : les libellés français du serveur
   (`manquantes`, `bloquants`) sont rendus TELS QUELS — l'écran ne reformule
   aucun motif et n'en invente aucun. Même discipline que PVFCH-ANNEXE côté
   devis : un schéma d'aspect officiel bâti sur des caractéristiques devinées
   est un défaut invisible.

   CALX236 — EXPORTER LE SCHÉMA, DEPUIS LE NAVIGATEUR, JAMAIS DEPUIS LE
   SERVEUR (D1 : aucun rastériseur SVG côté serveur). Le SVG est DÉJÀ dans le
   DOM (inséré ci-dessus) : l'export PNG le sérialise dans un canvas hors
   écran (même patron que `features/ged/capture.js`) et télécharge l'image —
   AUCUN second appel à `schemaUnifilaire()`, aucune route neuve. Le lien SVG
   télécharge le TEXTE déjà reçu, tel quel. Les deux boutons n'existent QUE
   quand `balisage` est vrai (`svg` non nul) : un schéma absent n'a rien à
   exporter.

   CALX235/236 — LE TROISIÈME BOUTON : LE DXF. La route existe désormais
   (`views/schema.py`, `url_path='schema-unifilaire.dxf'`, service
   `services/sld_export.py::exporter_sld_dxf`) et
   `calepinageApi.calepinages.sldDxf(id)` a été ajoutée EN FIN de
   `calepinageApi.js` (`// CALX235`). Contrairement au PNG et au SVG, le DXF
   n'est PAS dans le DOM : il est produit par le serveur depuis le MÊME
   dessin (blocs, positions éditées, liaisons), donc un appel réseau est ici
   la seule façon de l'obtenir — et c'est le SEUL de ce panneau. Une
   conception incomplète ou bloquée ne produit aucun fichier : le serveur
   refuse en 400 en nommant le champ, et ce motif-là est affiché tel quel.
   ========================================================================== */

/** Le nom du fichier exporté : porte la RÉFÉRENCE du calepinage servie par
    CETTE réponse (`data.calepinage`, le seul identifiant que ce contrat
    publie — aucun titre n'y est servi, donc aucun titre n'est inventé ici). */
export function nomFichierSchema(referenceCalepinage, extension) {
  const base = referenceCalepinage === null || referenceCalepinage === undefined
    ? 'calepinage'
    : `calepinage-${referenceCalepinage}`
  return `${base}-schema-unifilaire.${extension}`
}

/**
 * Sérialise le SVG (déjà reçu, déjà affiché) dans un canvas hors écran et
 * télécharge le PNG obtenu. Aucun appel réseau : Blob/URL.createObjectURL
 * sont locaux au navigateur. Un échec de rastérisation (navigateur trop
 * ancien, contexte 2D indisponible) revient en REJET avec un motif
 * affichable — jamais une exception qui casserait l'écran.
 */
export function exporterSchemaPng(svgTexte, nomFichier, { telecharger = telechargerBlob } = {}) {
  // Le rastériseur est UN seul exemplaire (documents/deposerImage.js) : ici on
  // télécharge le Blob obtenu au lieu de l'envoyer au serveur.
  return svgTexteEnPng(svgTexte).then((blobPng) => {
    telecharger(blobPng, nomFichier)
    return { ok: true, nom: nomFichier }
  })
}

/** Télécharge le SVG texte tel quel — aucune conversion, aucun appel réseau. */
export function exporterSchemaSvg(svgTexte, nomFichier, { telecharger = telechargerBlob } = {}) {
  telecharger(new Blob([svgTexte], { type: 'image/svg+xml;charset=utf-8' }), nomFichier)
}

/**
 * CALX235 — le MOTIF d'un refus de DXF, lu sur la réponse du serveur.
 *
 * La réponse est demandée en `blob` : un refus 400 arrive donc lui aussi en
 * Blob, et son JSON (`{champ: motif}`) doit être relu pour qu'on affiche la
 * phrase du serveur — jamais une phrase reformulée ici. Un corps illisible
 * (panne réseau, HTML d'un proxy) rend un motif générique qui DIT qu'il est
 * générique, plutôt qu'un motif métier inventé.
 */
export async function motifDuRefusDxf(erreur) {
  return motifDuRefusBlob(erreur, 'Le DXF n’a pas pu être produit par le serveur.')
}

/**
 * ACAL161 — l'ÉDITEUR du schéma : renommer le libellé ou le repère d'un bloc DESSINÉ. L'écran
 * ne crée ni ne supprime aucun organe et ne change aucune grandeur : il poste
 * `{libelles: {clef: texte}, reperes: {clef: texte}}` (les rubriques MODIFIÉES seulement ; un
 * champ vidé vaut `null`, qui efface l'édition de cette rubrique). Le refus du serveur
 * (`edition.libelles.<clef>`, `edition.reperes.<clef>`) se pose SOUS le champ nommé, mot pour mot.
 */
export function corpsEdition(blocs, saisie) {
  const corps = {}
  for (const [rubrique, cle] of [['libelles', 'titre'], ['reperes', 'repere']]) {
    for (const bloc of blocs) {
      const v = saisie[rubrique]?.[bloc.clef]
      if (v === undefined || v === (bloc[cle] ?? '')) continue
      corps[rubrique] = { ...(corps[rubrique] ?? {}), [bloc.clef]: v.trim() === '' ? null : v }
    }
  }
  return corps
}
