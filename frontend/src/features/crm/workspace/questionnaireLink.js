// LANE Q-C (fondateur 25/08/2026) — dialogue « Envoyer un questionnaire » sur
// la fiche lead : logique PURE (co-localisée, testable sans DOM via
// `node --test`, même patron que missingFields.js / draftCore.js). La vérité
// affichée vient TOUJOURS de la réponse serveur — jamais devinée (même règle
// que L-SECT/sectionsDepuisServeur, DevisTab.jsx, dont ce dialogue reprend le
// patron : whitelist de sections cochables + mint idempotent via POST).
//
// Contrat serveur (lane backend parallèle, code contre CE contrat verbatim) :
//   POST /api/django/crm/leads/<id>/questionnaire-lien/
//   body {"questions": {"<cle>": bool}}  (facultatif — omis = « donne l'état
//   actuel sans rien changer »)
//   → {"url", "url_interne", "token", "expires_at", "questions": {…},
//      "manquantes": {"<cle>": true}}
//
// `url` est le SEUL lien à envoyer au client (copier/WhatsApp/ouvrir pour un
// ENVOI) ; `url_interne` (ADDENDUM fondateur, même mint, jeton DIFFÉRENT) est
// l'aperçu du commercial SANS notifier le lead ni laisser de trace côté
// client — jamais mélangé au message WhatsApp (voir questionnaireWhatsappText
// ci-dessous, qui ne reçoit jamais que `url`).

// Whitelist serveur EXACTE — une clé hors de cette liste est refusée en 400
// côté serveur (même garde que SECTIONS_ENVOI de DevisTab.jsx) : les deux
// listes ne peuvent pas diverger en silence.
export const SECTIONS_QUESTIONNAIRE = [
  { key: 'contact', label: 'Coordonnées (email, adresse, ville)' },
  { key: 'gps', label: 'Position GPS de la maison' },
  { key: 'energie', label: "Factures d'électricité" },
  { key: 'photo_facture', label: 'Photo de la facture' },
  { key: 'photo_compteur', label: 'Photo du compteur' },
  { key: 'photo_tableau', label: 'Photo du tableau électrique' },
  { key: 'toiture', label: 'Toiture (type, surface, âge, propriétaire)' },
  { key: 'occupation', label: 'Présence en journée' },
  { key: 'equipements', label: 'Équipements (piscine, VE, clim, chauffe-eau)' },
]

// État des cases à l'ouverture / après un mint : `data` est la réponse BRUTE
// du serveur ({questions, manquantes, ...}) — jamais devinée localement.
// Deux cas :
//   (1) un lien existait déjà avec des questions choisies → on repart de CES
//       questions (source de vérité serveur, `data.questions` non vide) ;
//   (2) rien n'a jamais été choisi → défaut = ce qui MANQUE au lead
//       (`data.manquantes`, seules les clés manquantes valent true).
export function questionsDepuisReponse(data) {
  const questions = data && typeof data === 'object' ? data.questions : null
  const dejaChoisies = questions && typeof questions === 'object'
    && Object.keys(questions).length > 0
  if (dejaChoisies) {
    return Object.fromEntries(
      SECTIONS_QUESTIONNAIRE.map(({ key }) => [key, !!questions[key]]),
    )
  }
  const manquantes = (data && typeof data === 'object' && data.manquantes
    && typeof data.manquantes === 'object') ? data.manquantes : {}
  return Object.fromEntries(
    SECTIONS_QUESTIONNAIRE.map(({ key }) => [key, !!manquantes[key]]),
  )
}

// Payload à poster — jamais une clé hors whitelist, même si `sel` en portait
// une par accident (état local corrompu, etc.).
export function questionsPourEnvoi(sel) {
  const src = sel && typeof sel === 'object' ? sel : {}
  return Object.fromEntries(
    SECTIONS_QUESTIONNAIRE.map(({ key }) => [key, !!src[key]]),
  )
}

export function nbSectionsChoisies(sel) {
  const src = sel && typeof sel === 'object' ? sel : {}
  return SECTIONS_QUESTIONNAIRE.filter(({ key }) => src[key]).length
}

// Message WhatsApp — sobre, ne reçoit QUE `url` (jamais `url_interne` : le
// lien d'aperçu interne ne doit JAMAIS partir dans un message client, voir
// ADDENDUM ci-dessus). Même famille de ton que `proposalWhatsappText`
// (clientProposalLink.js), formulation dédiée au questionnaire.
export function questionnaireWhatsappText(prenom, url) {
  const hello = prenom?.trim() ? `Bonjour ${prenom.trim()}, ` : 'Bonjour, '
  return (
    `${hello}pour préparer votre étude solaire, pouvez-vous répondre à `
    + `quelques questions (2 min, depuis votre téléphone) : ${url}`
  )
}
