// CAD151/CAD161 (décisions fondateur du 21/09/2026) — LE CONTENU du panneau
// d'appel guidé. Fichier PUR (aucun JSX, aucun appel réseau), sur le patron
// de `visiteGuidance.js` : testable en `.test.mjs` par `node --test`.
//
// Ce module ne FORMULE aucune question. La question d'un champ est son
// `help_text` (règle `apps/crm/models.py` : « chaque champ EST le script
// d'appel »), servie telle quelle par le contrat `panneau_appel.json`
// (`champs_a_poser[].question`) — une formulation à améliorer se corrige dans
// le modèle, jamais ici. Ce module ne porte que ce que le serveur ne décide
// pas : quel segment est livré, dans quel ORDRE les questions se posent, et ce
// qu'on répond (ou ne dit jamais) au téléphone.
//
// Entrée de toutes les fonctions : la réponse de
// `GET /api/django/crm/leads/<id>/panneau-appel/` — contrat
// `backend/django_core/apps/crm/contract_samples/panneau_appel.json` (CAD147).

// ── CAD161 — le résidentiel d'abord ─────────────────────────────────────────
// Décision fondateur du 21/09/2026 : le panneau d'appel couvre le RÉSIDENTIEL
// d'abord ; l'agricole (pompage) et l'industriel/commercial arrivent en
// SECONDE livraison (CAD175). Raison : le moteur horaire ne sait traiter que
// le résidentiel (aucune silhouette agricole ni industrielle, barème « BT
// DOMESTIQUE », `apps/ventes/bareme.py`). Le contrat porte déjà `segment`
// (CAD147) : la seconde livraison n'aura aucune migration de contrat à faire.
//
// Segment VIDE (`null`) : le lead n'a pas de type d'installation saisi. Même
// règle que les gabarits de messages (`variante_segment`, CAD126 : un segment
// vide n'a jamais de variante, le texte de base EST le résidentiel) — le script
// résidentiel est servi, marqué « segment à confirmer ». Un segment connu autre
// que le résidentiel est REFUSÉ avec un message explicite : jamais une page
// vide, jamais un script résidentiel déguisé.

/** Clé `crm.Lead.TypeInstallation` du seul segment livré aujourd'hui. */
export const SEGMENT_RESIDENTIEL = 'residentiel'

/** Le panneau guidé est-il livré pour ce segment ? (vide = résidentiel). */
export function segmentLivre(segment) {
  const valeur = typeof segment === 'string' ? segment.trim() : ''
  return valeur === '' || valeur === SEGMENT_RESIDENTIEL
}

/** Bandeau affiché quand le lead n'a pas de segment saisi. */
export const MESSAGE_SEGMENT_A_CONFIRMER =
  "Segment non renseigné sur la fiche : script résidentiel par défaut, à "
  + 'confirmer avec le client.'

/** Message de refus d'un segment non livré — toujours une phrase complète,
 *  qui nomme le segment avec le libellé servi par le serveur (repli sur sa
 *  clé : un refus ne survient que pour un segment NON vide). */
export function messageSegmentNonLivre(panneau) {
  const nom = panneau?.segment_libelle || panneau?.segment
  return "Le script d'appel guidé couvre le résidentiel pour l'instant. Le "
    + `segment « ${nom} » arrive dans une prochaine livraison : posez vos `
    + 'questions depuis la fiche du lead.'
}

/** Ce que le panneau affiche pour CE lead.
 *  - segment non livré : `{ livre: false, segment, message }` ;
 *  - résidentiel (ou segment vide) : `{ livre: true, segment,
 *    segmentAConfirmer, avertissement }`. */
export function guidanceAppel(panneau) {
  const segment = panneau?.segment || null
  if (!segmentLivre(segment)) {
    return { livre: false, segment, message: messageSegmentNonLivre(panneau) }
  }
  const segmentAConfirmer = !segment
  return {
    livre: true,
    segment,
    segmentAConfirmer,
    avertissement: segmentAConfirmer ? MESSAGE_SEGMENT_A_CONFIRMER : null,
  }
}
