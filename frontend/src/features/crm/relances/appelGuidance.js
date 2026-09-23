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

// ── CAD162 — l'ordre de l'appel 1 ───────────────────────────────────────────
// Décision fondateur du 21/09/2026 (Q8) : l'appel 1 pose CINQ questions, dans
// cet ordre — facture → été différent → occupation en journée → toit et type
// de bien → objectif du projet. L'ouverture promet « deux minutes »
// (`apps/parametres/models_messages.py`, gabarit `appel_ouverture`) : le budget
// de cinq est une contrainte DURE, toute question de plus attend le rappel.
//
// Chaque étape nomme les colonnes `crm.Lead` qu'elle obtient. La PREMIÈRE
// encore à obtenir porte la question (son `help_text`, servi par le contrat) ;
// les suivantes en sont le complément, dans la même question (le montant de
// l'été ne se note que si l'été est différent).
// « Toit et type de bien » = `type_bien` seul : son `help_text` dit qu'il
// REMPLACE la saisie du type de toit au téléphone (chemin fermé depuis la
// décision du 18/08/2026) — `type_toiture` n'est donc pas une question d'appel.
export const ORDRE_APPEL_1 = Object.freeze([
  Object.freeze({ etape: 'facture', champs: Object.freeze(['facture_hiver']) }),
  Object.freeze({ etape: 'ete', champs: Object.freeze(['ete_differente', 'facture_ete']) }),
  Object.freeze({ etape: 'occupation', champs: Object.freeze(['occupation_jour']) }),
  Object.freeze({ etape: 'toit_type_bien', champs: Object.freeze(['type_bien']) }),
  Object.freeze({ etape: 'objectif', champs: Object.freeze(['objectif_projet']) }),
])

/** Le budget de l'appel 1 : le nombre de ses étapes, jamais un chiffre à part. */
export const BUDGET_APPEL_1 = ORDRE_APPEL_1.length

// Q8 — « propriétaire ou locataire » se pose au RAPPEL, jamais à l'appel 1 (il
// vient souvent naturellement avec la question du toit). Il suit les étapes de
// l'appel 1 restées sans réponse.
export const QUESTIONS_DU_RAPPEL = Object.freeze([
  Object.freeze({ etape: 'proprietaire_locataire', champs: Object.freeze(['ownership']) }),
])

// L'appel 1, c'est la PREMIÈRE CONVERSATION. Toutes les touches de la cadence
// « contact » (et de la cadence courte « deuxième affaire ») n'en sont que des
// TENTATIVES : la cadence s'arrête dès que le client est joint
// (`apps/crm/services.py`, `_OUTCOMES_ARRET_CADENCE`). Le RAPPEL, c'est toute
// touche posée APRÈS : suivi après devis, étapes du filet (« rappel convenu »,
// clé de gabarit vide), réveil. Clés reprises des gabarits par défaut —
// `apps/parametres/models_relance.py` (CADENCE_CONTACT_DEFAUT,
// CADENCE_DEUXIEME_AFFAIRE_DEFAUT) et `models_messages.py`
// (CLES_IDENTITE_PAR_ORIGINE) — jamais inventées ici.
// LIMITE ASSUMÉE : le contrat ne sert pas la cadence de la touche. Deux étapes
// du filet sans clé de gabarit (« il a répondu au message », « il l'a
// demandé ») peuvent être une première conversation : elles sont traitées en
// rappel — la question du statut arrive alors APRÈS les cinq, jamais avant.
// Une touche absente (aucune cadence active) garde le budget de l'appel 1.
export const CLES_TOUCHES_APPEL_1 = Object.freeze([
  'identite', 'identite_reference', 'identite_telephone',
  'identite_whatsapp_entrant', 'identite_ancien_dossier', 'deuxieme_affaire',
  'appel_ouverture', 'repondeur', 'appel_relance', 'valeur_j1', 'vocal_j3',
  'appel_dimanche', 'je_classe_j7', 'appel_dernier', 'cloture_j14',
])

/** La touche en cours est-elle un RAPPEL (après la première conversation) ? */
export function estToucheDeRappel(touche) {
  if (!touche) return false
  return !CLES_TOUCHES_APPEL_1.includes(touche.template_cle || '')
}

/** Les étapes à poser sur CET appel, dans l'ordre figé, filtrées par ce qui
 *  est déjà renseigné. Chaque entrée reprend TELLE QUELLE l'entrée du contrat
 *  (`champ`, `section`, `libelle`, `question`, `choix`) de la première colonne
 *  encore à obtenir, plus `etape` et `complements` (les autres colonnes de la
 *  même étape encore à obtenir). Une colonne que le serveur ne sert pas n'est
 *  jamais fabriquée ici. */
export function questionsDeLAppel(panneau) {
  const dejaRenseigne = panneau?.prefill || {}
  const aPoser = new Map()
  for (const entree of panneau?.champs_a_poser || []) {
    if (entree?.champ && !(entree.champ in dejaRenseigne)) {
      aPoser.set(entree.champ, entree)
    }
  }
  const etapes = estToucheDeRappel(panneau?.touche)
    ? [...ORDRE_APPEL_1, ...QUESTIONS_DU_RAPPEL]
    : ORDRE_APPEL_1
  const out = []
  for (const { etape, champs } of etapes) {
    const entrees = champs.map((champ) => aPoser.get(champ)).filter(Boolean)
    if (!entrees.length) continue
    const [principale, ...complements] = entrees
    out.push({ ...principale, etape, complements })
  }
  return out
}

/** Le texte à lire : la question servie (le `help_text`), sinon le libellé
 *  du champ — tous deux lus au serveur, jamais réécrits ici. */
export function texteQuestion(entree) {
  return entree?.question || entree?.libelle || ''
}

// ── CAD163 — la loi 82-21 : rien de spontané ────────────────────────────────
// Décision fondateur du 21/09/2026 (Q9) : on n'aborde JAMAIS la loi 82-21
// spontanément. Si — et seulement si — le client en parle, la réponse est UNE
// phrase factuelle, dictée mot pour mot par la décision, SANS aucun tarif,
// aucun pourcentage, aucun délai : le tarif de cession qui circule n'est
// confirmé par aucune source lue, le prononcer serait un chiffre inventé.
// C'est une réponse d'OBJECTION, jamais une ligne de script d'ouverture.
// Source : `docs/crm/messages_meryem.md`, section « Script d'appel guidé »
// (`#### objection_loi_8221`) — le test re-dérive ces quatre lignes de ce
// fichier : une modification se fait LÀ-BAS et ici, dans le même commit.
export const OBJECTION_LOI_8221 = Object.freeze({
  cle: 'objection_loi_8221',
  titre: 'Le client parle lui-même de la loi 82-21 (revente du surplus)',
  quand: 'Seulement si le client aborde lui-même la loi 82-21 ou la revente du '
    + "surplus — jamais à l'initiative de la commerciale, jamais dans un script "
    + "d'ouverture.",
  reponse: 'La loi permet de revendre une part du surplus ; je vous confirme '
    + 'les conditions par écrit.',
  jamais: 'Aucun tarif, aucun pourcentage, aucun délai.',
  ensuite: 'Envoyer la confirmation écrite par un canal traçable ; aucune '
    + "promesse de rachat tant qu'une décision ANRE datée n'a pas été lue.",
})

// ── CAD151 — l'objection « générateur » ─────────────────────────────────────
// Source : `docs/crm/messages_meryem.md`, section « Script d'appel guidé »
// (`#### objection_generateur`). Un onduleur solaire raccordé au réseau,
// SANS batterie, s'arrête pendant une coupure (protection anti-îlotage) :
// « le solaire travaille tous les jours » est donc une réponse INTENABLE à
// cette objection précise — elle laisserait croire que le solaire tient
// pendant une coupure. Aucune durée ni aucun nombre d'heures d'autonomie
// n'est promis (règle CAD173 Q15 : aucun dimensionnement de secours n'est
// calculé, donc aucun chiffre de secours n'existe).
export const OBJECTION_GENERATEUR = Object.freeze({
  cle: 'objection_generateur',
  titre: 'Le client dit qu\'il a déjà un générateur',
  quand: "Le client oppose son générateur pour dire qu'il n'a pas besoin du "
    + 'solaire.',
  reponse: "Sans batterie, l'onduleur solaire s'arrête pendant une coupure, "
    + "comme le réseau ; ce n'est pas un concurrent de votre générateur, "
    + "c'est un complément qui réduit votre facture les jours sans coupure. "
    + 'Si vous voulez aussi tenir pendant les coupures, on regarde une offre '
    + 'avec batterie.',
  jamais: 'Ne jamais répondre « le solaire travaille tous les jours » à '
    + "cette objection — faux sans batterie ; aucune durée ni aucun nombre "
    + "d'heures d'autonomie promis.",
})

// ── CAD151 — l'objection « subventions » ────────────────────────────────────
// Dérivée mot pour mot de la décision fondateur du 21/09/2026 (CAD173, Q22) :
// « on ne promet RIEN […] on renvoie le client aux conditions officielles du
// programme concerné ». Source : `docs/crm/messages_meryem.md`, section
// « Script d'appel guidé » (`#### objection_subventions`).
export const OBJECTION_SUBVENTIONS = Object.freeze({
  cle: 'objection_subventions',
  titre: "Le client demande une subvention ou une aide de l'État",
  quand: 'Le client demande si une subvention ou une aide de l\'État existe '
    + 'pour son projet.',
  reponse: 'Je ne vous promets rien sur une subvention ; je vous renvoie aux '
    + 'conditions officielles du programme concerné.',
  jamais: 'Aucun montant, aucun taux, aucune éligibilité, aucun délai.',
})

/** Les réponses d'objection du panneau — affichées à la demande, jamais lues
 *  d'office. */
export const OBJECTIONS = Object.freeze([
  OBJECTION_LOI_8221, OBJECTION_GENERATEUR, OBJECTION_SUBVENTIONS,
])

// ── CAD151 — ce qu'on ne dit JAMAIS au téléphone ────────────────────────────
// Doctrine du groupe, valable sur TOUTE touche d'appel (pas seulement les
// objections ci-dessus) : consignes internes affichées à la commerciale,
// jamais des phrases à lire au client.
export const INTERDITS_APPEL = Object.freeze([
  'Aucun chiffre au téléphone : ni tarif, ni tranche horaire, ni '
    + 'pourcentage — les tranches par défaut de `solar_design.py` sont '
    + 'marquées « à confirmer », jamais prononcées (règle checked-facts).',
  "Jamais la grille tarifaire des agrégateurs : la seule grille canonique "
    + "est interne (`apps/ventes/pricing/models_tariff.py`), et elle ne se "
    + 'cite pas non plus au téléphone.',
  "Jamais une annotation entre crochets lue à voix haute ou recopiée dans "
    + 'une note — un crochet part au client tel quel.',
  "Objection générateur : jamais « le solaire travaille tous les jours » "
    + "seul en réponse — voir `OBJECTION_GENERATEUR`.",
  'Jamais une promesse sur les subventions — voir `OBJECTION_SUBVENTIONS`.',
])

// ── CAD151 — l'issue à saisir en fin d'appel ────────────────────────────────
// SCR-13 (audit) — les SIX issues réelles : vocabulaire EXISTANT de
// `apps/crm/models.py` (`LeadActivity.OUTCOMES`), servi tel quel par l'écran
// qui saisit l'issue (CAD152) — ce module ne fait que NOMMER le champ à
// remplir, il ne redéfinit jamais la liste.
export const ISSUES_APPEL = Object.freeze([
  'joint', 'non_joint', 'rappel', 'refuse', 'interesse', 'visite_acceptee',
])

// ── CAD151 — Q19 : un locataire ne décide pas des travaux ──────────────────
// Décision fondateur du 21/09/2026 (Q19) : demander les coordonnées du
// propriétaire, créer SA fiche reliée par une note d'historique (jamais une
// fusion automatique — même patron que `deuxieme_affaire`, CAD128) ; sans
// elles, l'issue est un Refus avec le motif EXISTANT « Locataire »
// (`apps/crm/views.py` `_DEFAULT_MOTIFS_PERTE`, seedé par
// `seed_motifs_perte` — aucun nouveau motif inventé ici).
export const FLUX_LOCATAIRE = Object.freeze({
  quand: 'La question « propriétaire ou locataire » (posée au rappel, champ '
    + '`ownership`) répond « Locataire ».',
  consigne: 'Demander les coordonnées du propriétaire et créer sa fiche, '
    + "reliée à celle du locataire par une note d'historique — jamais une "
    + 'fusion automatique.',
  sinon: 'Sans coordonnées du propriétaire : issue « Refus », motif '
    + '« Locataire ».',
})

/** L'accroche de CET appel : le texte SERVI par le serveur
 *  (`panneau.script.message`, même rendu que `relance_etape_message.json`),
 *  jamais réécrite ici. `null` quand aucune touche n'est active. */
export function texteAccroche(panneau) {
  return panneau?.script?.message || null
}

/** Le budget d'un appel de RAPPEL : les cinq étapes de l'appel 1, plus la
 *  question du rappel — jamais un chiffre à part. */
export const BUDGET_RAPPEL = ORDRE_APPEL_1.length + QUESTIONS_DU_RAPPEL.length

// ── CAD151 — la structure PAR TOUCHE ────────────────────────────────────────
// Les cinq touches d'appel qui n'avaient aucun script avant CAD67/CAD98
// (`apps/parametres/models_relance.py` — Appel 4 et Appel 6 de la cadence
// contact, appels de suivi J2/J7/J11 de la cadence après-devis), plus le
// réveil J30 (CAD74, canal APPEL) et le débrief après visite (CAD151,
// envoi manuel). L'accroche de chacune vit dans
// `apps/parametres/models_messages.py` (`MESSAGE_TEMPLATE_DEFAULTS`) et se
// LIT depuis `panneau.script.message` (`texteAccroche`) — ce module ne la
// duplique jamais. `phase` détermine les questions filtrées servies par
// `guidanceAppel` (`estToucheDeRappel`) ; `manuel: true` signale une touche
// HORS cadence (aucun barreau ne la déclenche, comme `annonce_appel_reda`).
export const SCRIPTS_TOUCHES = Object.freeze({
  repondeur: Object.freeze({
    titre: 'Appel 2 / Appel 4 — répondeur', phase: 'appel_1', manuel: false,
  }),
  appel_dernier: Object.freeze({
    titre: 'Appel 6 — dernier avant clôture', phase: 'appel_1', manuel: false,
  }),
  appel_suivi_j2: Object.freeze({
    titre: 'Appel de suivi — J2', phase: 'rappel', manuel: false,
  }),
  appel_suivi_j7: Object.freeze({
    titre: 'Appel de suivi — J7', phase: 'rappel', manuel: false,
  }),
  appel_suivi_j11: Object.freeze({
    titre: 'Appel de suivi — J11', phase: 'rappel', manuel: false,
  }),
  reveil_a1: Object.freeze({
    titre: 'Réveil — J30', phase: 'rappel', manuel: false,
  }),
  debrief_visite: Object.freeze({
    titre: 'Débrief après visite technique', phase: 'rappel', manuel: true,
  }),
})

/** La structure de CETTE touche (titre, phase, manuel), ou `null` pour une
 *  clé hors de `SCRIPTS_TOUCHES` (ex. `appel_ouverture`, déjà couvert par
 *  `ORDRE_APPEL_1`/`estToucheDeRappel` sans entrée dédiée nécessaire). */
export function scriptTouche(templateCle) {
  return SCRIPTS_TOUCHES[templateCle || ''] || null
}

/** Ce que le panneau affiche pour CE lead.
 *  - segment non livré : `{ livre: false, segment, message }` ;
 *  - résidentiel (ou segment vide) : `{ livre: true, segment,
 *    segmentAConfirmer, avertissement, phase, accroche, questions,
 *    objections, interdits, issues }`, `phase` valant `'appel_1'` ou
 *    `'rappel'`. */
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
    phase: estToucheDeRappel(panneau?.touche) ? 'rappel' : 'appel_1',
    accroche: texteAccroche(panneau),
    questions: questionsDeLAppel(panneau),
    objections: OBJECTIONS,
    interdits: INTERDITS_APPEL,
    issues: ISSUES_APPEL,
  }
}
