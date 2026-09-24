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
//
// CAD175 — LA SECONDE LIVRAISON EST FAITE : l'agricole (pompage) et
// l'industriel/commercial ont chacun LEUR jeu de questions (mêmes trois
// pièces que le résidentiel : filtrées par ce qui manque, script par touche,
// écriture par le chemin de la fiche). Seule une clé de segment INCONNUE est
// encore refusée. Garde-fou tenu : sur ces deux segments, AUCUN chiffre
// d'économie n'est annoncé — le moteur horaire ne sait pas les traiter.

/** Clés `crm.Lead.TypeInstallation`. */
export const SEGMENT_RESIDENTIEL = 'residentiel'
export const SEGMENT_AGRICOLE = 'agricole'
export const SEGMENTS_PRO = Object.freeze(['industriel', 'commercial'])
/** Les segments dont le panneau guidé est livré (CAD161 puis CAD175). */
export const SEGMENTS_LIVRES = Object.freeze([
  SEGMENT_RESIDENTIEL, SEGMENT_AGRICOLE, ...SEGMENTS_PRO,
])

/** Le panneau guidé est-il livré pour ce segment ? (vide = résidentiel). */
export function segmentLivre(segment) {
  const valeur = typeof segment === 'string' ? segment.trim() : ''
  return valeur === '' || SEGMENTS_LIVRES.includes(valeur)
}

/** La FAMILLE de questions d'un segment livré : `residentiel` (vide
 *  compris), `agricole` ou `pro` (industriel et commercial partagent la
 *  même variante B2B, comme les gabarits de messages — CAD126). */
export function familleDuSegment(segment) {
  const valeur = typeof segment === 'string' ? segment.trim() : ''
  if (valeur === SEGMENT_AGRICOLE) return 'agricole'
  if (SEGMENTS_PRO.includes(valeur)) return 'pro'
  return 'residentiel'
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
  return "Le script d'appel guidé couvre le résidentiel, l'agricole et "
    + `l'industriel/commercial. Le segment « ${nom} » n'en fait pas partie : `
    + 'posez vos questions depuis la fiche du lead.'
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

// Décision fondateur du 24/09/2026 : « propriétaire ou locataire » ne se pose
// PLUS — ni à l'appel 1, ni au rappel. TAQINOR n'a pas besoin de cette
// information : un locataire qui veut installer et qui paie est installé. La
// colonne `ownership` reste sur la fiche (renseignable, jamais demandée à
// l'appel) ; le rappel repose seulement les étapes de l'appel 1 restées sans
// réponse. (Remplace la décision Q8 du 21/09/2026.)

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

// ── CAD175 — l'ordre des questions agricoles et industrielles ──────────────
// Mêmes règles que l'appel 1 résidentiel : des étapes nommées, CHAQUE colonne
// est une colonne `crm.Lead` existante servie par le contrat (aucune n'est
// fabriquée ici), et une étape déjà répondue saute. Cinq étapes au plus,
// comme le budget de l'appel 1 (l'ouverture promet « deux minutes »).
// Agricole : la pompe d'abord (puissance, HMT, débit voulu — les trois
// entrées du générateur en mode agricole), puis les heures de pompage et
// l'énergie actuelle (le carburant consommé n'a de sens qu'ensuite).
export const ORDRE_AGRICOLE = Object.freeze([
  Object.freeze({ etape: 'pompe', champs: Object.freeze(['pompe_cv']) }),
  Object.freeze({ etape: 'hmt', champs: Object.freeze(['pompe_hmt_m']) }),
  Object.freeze({ etape: 'debit', champs: Object.freeze(['pompe_debit_m3h']) }),
  Object.freeze({ etape: 'heures_pompage', champs: Object.freeze(['pompage_heures_jour']) }),
  Object.freeze({
    etape: 'energie_actuelle',
    champs: Object.freeze(['pompe_alim_actuelle', 'carburant_litres_mois']),
  }),
])

// Industriel et commercial : la consommation en kWh (la donnée pro qui prime
// sur les dirhams, CAD166), la puissance souscrite du compteur (question
// PREMIÈRE en pro), la surface disponible, puis qui décide. Les réponses
// pro qui n'ont AUCUNE colonne (tension, rythme d'activité, groupe
// électrogène, process critiques) sont des consignes À NOTER, plus bas.
export const ORDRE_PRO = Object.freeze([
  Object.freeze({ etape: 'conso', champs: Object.freeze(['conso_mensuelle_kwh']) }),
  Object.freeze({ etape: 'puissance_souscrite', champs: Object.freeze(['compteur_puissance_kva']) }),
  Object.freeze({ etape: 'surface', champs: Object.freeze(['surface_toiture_m2']) }),
  Object.freeze({ etape: 'decideur', champs: Object.freeze(['decideur']) }),
])

/** Les étapes d'un panneau : résidentiel (appel 1 et rappel : les MÊMES
 *  cinq étapes, filtrées par ce qui est déjà renseigné — décision fondateur
 *  du 24/09/2026), agricole ou industriel/commercial (CAD175). */
export function etapesDuPanneau(panneau) {
  const famille = familleDuSegment(panneau?.segment)
  if (famille === 'agricole') return ORDRE_AGRICOLE
  if (famille === 'pro') return ORDRE_PRO
  return ORDRE_APPEL_1
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
  const etapes = etapesDuPanneau(panneau)
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

// Décision fondateur du 24/09/2026 (revue des questions d'appel) : le
// `help_text` d'un champ porte la QUESTION à dire (entre guillemets « … »)
// suivie de remarques internes (« vide = pas encore posée », ce que la
// réponse pilote, l'historique d'une décision). Pendant l'appel, seule la
// question se lit ; le reste est une consigne d'écran, en retrait. Ce
// découpage ne RÉÉCRIT rien : les deux moitiés sont le texte servi, tel quel
// (une formulation se corrige toujours dans le modèle, jamais ici).
const BOILERPLATE_VIDE = /\s*\([^()]*?vide = pas encore posée\)/g

/** `{ question, consigne }` d'un texte servi : `question` = le premier
 *  passage entre « … » (guillemets compris), `consigne` = ce qui suit la
 *  question, sans la mention « vide = pas encore posée » ni la ponctuation de
 *  raccord — `null` quand il ne reste rien. Sans guillemets, le texte entier
 *  est la question (libellé de fiche, question sans `help_text`). */
export function decouperQuestion(texte) {
  const brut = typeof texte === 'string' ? texte.trim() : ''
  const trouve = /«\s*([^»]+?)\s*»/.exec(brut)
  if (!trouve) return { question: brut, consigne: null }
  const question = `« ${trouve[1]} »`
  const reste = brut.slice(trouve.index + trouve[0].length)
    .replace(BOILERPLATE_VIDE, '')
    .replace(/^[\s—.,;:]+/, '')
    .trim()
  return { question, consigne: reste || null }
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

// Décision fondateur du 24/09/2026 : le flux « locataire » du panneau (Q19 du
// 21/09/2026 — coordonnées du propriétaire, sinon Refus motif « Locataire »)
// est RETIRÉ avec la question : un locataire qui paie est un client comme un
// autre. Le motif de perte « Locataire » et `GET/POST leads/<id>/locataire/`
// existent toujours côté serveur ; le panneau d'appel ne les propose plus.

/** L'accroche de CET appel : le texte SERVI par le serveur
 *  (`panneau.script.message`, même rendu que `relance_etape_message.json`),
 *  jamais réécrite ici. `null` quand aucune touche n'est active. */
export function texteAccroche(panneau) {
  return panneau?.script?.message || null
}

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

// ── CAD152 — le panneau SOUS LES YEUX pendant l'appel ──────────────────────
// Textes d'ÉCRAN (consignes à la commerciale, jamais lus au client). Source :
// `docs/crm/messages_meryem.md`, section « Panneau d'appel — consignes
// d'écran » (lignes `CLE : texte`) — le test re-dérive ces textes de ce
// fichier : une modification se fait LÀ-BAS et ici, dans le même commit.

/** Décision D7 (tranchée, `apps/crm/selectors.py` « NE PAS LES SUPPRIMER, NE
 *  PAS LES CÂBLER ») : l'écran DIT que ces trois réponses ne font pas le
 *  chiffre — la phrase de la tâche CAD152, complétée de l'inclinaison par
 *  CAD157 (la décision D7 porte sur les trois). */
export const MENTION_D7 = 'Orientation, inclinaison et ombrage servent au '
  + 'dossier et à la visite, pas au chiffre.'

// ── CAD157 — dire à l'écran ce qui n'est PAS compté ────────────────────────
// Quatre réponses données au téléphone n'entrent dans aucun calcul : D7
// (ci-dessus), les charges futures cochées sur le site (lues par aucun
// calcul de ventes), la tranche ONEE (texte libre qu'aucun calcul ne lit :
// elle se dérive de la facture) et tout équipement déclaré sans sa grandeur
// (il ne compose aucune couche, `courbes_journalieres.composer_equipements`).
// On n'ouvre PAS ces champs au calcul (D7 est tranchée) : on arrête seulement
// de laisser croire qu'ils comptent.
export const NON_COMPTE_TITRE = 'Ce que le chiffre ne compte pas'
export const NON_COMPTE_FUTURES_CHARGES = 'Charges futures cochées sur le '
  + 'site (clim, véhicule électrique, pompe) : servent au dossier et à la '
  + 'visite, pas au chiffre.'
export const NON_COMPTE_TRANCHE_ONEE = 'Tarif / tranche ONEE : sert au '
  + "dossier, pas au chiffre — l'estimation part du montant de la facture."
export const NON_COMPTE_PLAQUE = 'Pas compté dans le chiffre tant que la '
  + 'puissance manque : photo de la plaque pour que ce soit compté.'

/** La mention d'un équipement DÉCLARÉ mais PAS compté, d'après le drapeau
 *  SERVI (`panneau.equipements[]` — le serveur applique la règle de
 *  composition, jamais ce module). Le champ qui manque est NOMMÉ
 *  (`libelleChamp` : clé → libellé d'écran). `null` sinon. */
export function mentionEquipementNonCompte(equipement, libelleChamp = (c) => c) {
  if (!equipement?.declare || equipement.compte_dans_etude) return null
  const manquants = equipement.champs_manquants || []
  const puissance = manquants.some((c) => /_kw$/.test(c))
  const manque = manquants.map(libelleChamp).join(', ')
  return `${equipement.libelle} : pas compté dans le chiffre`
    + (manque ? ` (il manque : ${manque})` : '')
    + (puissance ? ' — photo de la plaque pour que ce soit compté.' : '.')
}

/** Q5 (décision fondateur du 21/09/2026) : sans réponse à la présence en
 *  journée, l'estimation SUPPOSE une présence — elle porte le bandeau
 *  « profil supposé, à confirmer » et la question remonte en tête. */
export const CHAMP_PRESENCE_JOUR = 'occupation_jour'
export const BANDEAU_PROFIL_SUPPOSE = 'Profil supposé, à confirmer'
export const EXPLICATION_PROFIL_SUPPOSE = "La présence en journée n'a pas "
  + "été posée : l'estimation suppose quelqu'un à la maison en journée. "
  + 'Posez cette question en premier.'

/** Le geste d'issue : le vocabulaire EXISTANT de la ligne (CKP4), jamais une
 *  liste refaite ici — le panneau ne fait qu'y mener. */
export const CONSIGNE_ISSUE = "L'issue se saisit avec les réponses de la "
  + 'touche (« Fait ») : client joint, pas de réponse, répondeur, à '
  + 'rappeler, refus.'
export const ISSUE_VERROUILLEE = 'Touche à venir : l’issue se saisira à son '
  + 'échéance (« Fait » verrouillé).'
export const AUCUNE_QUESTION = 'Rien à demander sur cet appel : tout ce que '
  + 'le script pose est déjà sur la fiche.'

// ── CAD155 — la fenêtre RÉELLE du jour : pendant le Ramadan, pas de soir ───
// La fenêtre vient du SERVEUR (`panneau.fenetre_du_jour`, lue par
// `apps/crm/horaires.py::fenetre_du_jour`, celle que le moteur appliquera —
// Ramadan saisi et pause du vendredi compris). Ce module n'écrit AUCUNE
// heure : il ne fait que découper ce qui est servi en créneaux proposables.
// Pendant le Ramadan, la journée d'appel s'arrête plus tôt et aucun créneau
// du soir n'existe (décision fondateur du 21/09/2026, CAD39) : le script ne
// peut donc proposer qu'un créneau DANS la fenêtre servie.
export const CONSIGNE_CRENEAU = "Si le client n'est pas disponible, "
  + 'proposez un rappel dans un de ces créneaux :'
export const RAMADAN_PAS_DE_SOIR = "Ramadan : pas d'appel le soir. La "
  + "journée d'appel s'arrête plus tôt — ne proposez aucun rappel après la "
  + 'fin de la fenêtre.'
export const JOUR_NON_APPELABLE = "Aujourd'hui n'est pas un jour d'appel : "
  + 'proposez un rappel un jour ouvré.'

/** La fenêtre servie, lisible par l'écran — ou `null` quand le serveur n'a
 *  rien pu lire (on ne dit alors rien de l'horaire : jamais un supposé).
 *  `creneaux` : la fenêtre découpée par la pause du vendredi, et RIEN
 *  d'autre — aucun créneau n'est inventé hors de ce que le moteur ouvre. */
export function fenetreAppel(panneau) {
  const f = panneau?.fenetre_du_jour
  if (!f) return null
  const ramadan = Boolean(f.ramadan)
  if (!f.appelable || !f.debut || !f.fin) {
    return { appelable: false, ramadan, plage: null, pause: null, creneaux: [] }
  }
  const pause = f.pause?.debut && f.pause?.fin ? `${f.pause.debut}–${f.pause.fin}` : null
  const creneaux = pause
    ? [`${f.debut}–${f.pause.debut}`, `${f.pause.fin}–${f.fin}`]
    : [`${f.debut}–${f.fin}`]
  return { appelable: true, ramadan, plage: `${f.debut}–${f.fin}`, pause, creneaux }
}

/** L'entrée du contrat qui remonte EN TÊTE du panneau (Q5) : la présence en
 *  journée tant qu'elle reste à poser — `null` sinon. Lue dans
 *  `champs_a_poser`, jamais supposée : une colonne déjà dans `prefill` n'est
 *  jamais reposée. */
export function questionEnTete(panneau) {
  const dejaRenseigne = panneau?.prefill || {}
  if (CHAMP_PRESENCE_JOUR in dejaRenseigne) return null
  return (panneau?.champs_a_poser || []).find(
    (e) => e?.champ === CHAMP_PRESENCE_JOUR) || null
}

/** La valeur à ÉCRIRE pour une saisie libre, ou l'erreur qui NOMME le champ
 *  (règle fondateur du 08/09 : jamais un « non enregistré » générique). Un
 *  nombre tapé à la française (« 1 200,50 ») est NORMALISÉ plutôt que
 *  refusé : l'intention est claire. */
export function normaliserSaisie(entree, brut) {
  const libelle = entree?.libelle || entree?.champ || 'Réponse'
  const texte = typeof brut === 'string' ? brut.trim() : brut
  if (texte === '' || texte === null || texte === undefined) {
    return { erreur: `« ${libelle} » : saisissez la réponse avant d’enregistrer.` }
  }
  if (entree?.nature === 'nombre') {
    // `\s` couvre aussi les espaces insécables d'un nombre tapé à la
    // française (« 1 200 ») : on les retire avant de lire la virgule.
    const nettoye = String(texte).replace(/\s/g, '').replace(',', '.')
    if (!/^-?\d+(\.\d+)?$/.test(nettoye)) {
      return { erreur: `« ${libelle} » : « ${texte} » n’est pas un nombre.` }
    }
    return { valeur: nettoye }
  }
  return { valeur: texte }
}

/** Le refus du serveur (400 DRF `{champ: [message]}`) rendu SOUS le champ,
 *  précédé de son libellé. `null` quand la réponse ne vise pas ce champ. */
export function messageErreurServeur(entree, donnees) {
  const brut = donnees?.[entree?.champ]
  const message = Array.isArray(brut) ? brut.join(' ') : brut
  if (!message) return null
  return `« ${entree?.libelle || entree?.champ} » : ${message}`
}

// ── CAD175 — ce qui se note sans colonne, et ce qui ne se chiffre pas ──────
// Des réponses agricoles et industrielles attendues au téléphone n'ont AUCUNE
// colonne `crm.Lead` (la vague 1 a écarté la tension bt/mt, le rythme
// d'activité et le week-end — CAD160 ; rien ne porte la force motrice, la
// culture, le groupe électrogène ni les process). Le panneau ne peut donc
// pas les ÉCRIRE : il les liste comme consignes À NOTER dans la note de
// l'appel (réponses « Fait »), jamais comme des champs inventés. Textes ✎
// dans `docs/crm/messages_meryem.md` (re-dérivés par la garde CAD153).
export const A_NOTER_FORCE_MOTRICE = 'À noter dans la note d’appel : le '
  + 'compteur de la pompe est-il en abonnement force motrice ?'
export const A_NOTER_SURFACE_CULTURE = 'À noter dans la note d’appel : la '
  + 'surface irriguée et la culture.'
export const A_NOTER_TENSION = 'À noter dans la note d’appel : le site est-il '
  + 'raccordé en basse ou en moyenne tension ?'
export const A_NOTER_RYTHME = 'À noter dans la note d’appel : le rythme '
  + "d'activité (journée, jusqu'au soir, en continu) et le week-end."
export const A_NOTER_GROUPE = 'À noter dans la note d’appel : le site '
  + 'a-t-il un groupe électrogène ?'
export const A_NOTER_PROCESS = 'À noter dans la note d’appel : les process '
  + 'critiques, qui ne doivent jamais s’arrêter.'

// Décision fondateur du 24/09/2026 : la question CAD168 « Votre montant
// inclut l'abonnement et l'entretien du compteur ? » est RETIRÉE. Toute
// facture porte ces deux lignes fixes, toujours — aucun client ne les reçoit
// gratuitement, la question n'apprenait rien. Le calcul continue de les
// porter des deux côtés (`etude_horaire.part_non_solarisable`) sans rien
// demander au téléphone.

/** Les consignes à noter, par famille (le résidentiel n'en a aucune). */
export const A_NOTER_PAR_FAMILLE = Object.freeze({
  residentiel: Object.freeze([]),
  agricole: Object.freeze([A_NOTER_FORCE_MOTRICE, A_NOTER_SURFACE_CULTURE]),
  pro: Object.freeze([
    A_NOTER_TENSION, A_NOTER_RYTHME, A_NOTER_GROUPE, A_NOTER_PROCESS,
  ]),
})

// Garde-fou de CAD175 : le moteur horaire ne sait traiter ni l'agricole ni
// l'industriel (aucune silhouette, barème « BT DOMESTIQUE », aucun barème
// moyenne tension sourcé) — AUCUN chiffre d'économie ne s'annonce sur ces
// segments. Et l'économie de carburant ne se calcule que sur ce que le client
// DÉCLARE (CAD173, Q17) : aucun prix de gasoil de référence n'existe.
export const AUCUNE_ESTIMATION_SEGMENT = "Aucun chiffre d'économie au "
  + 'téléphone pour ce segment : le calcul ne sait pas encore le traiter.'
export const CARBURANT_DECLARE_SEUL = "L'économie de carburant se calcule "
  + 'uniquement sur ce que le client déclare (litres ou dirhams par mois) — '
  + 'jamais sur un prix de gasoil supposé.'

export const GARDE_FOUS_PAR_FAMILLE = Object.freeze({
  residentiel: Object.freeze([]),
  agricole: Object.freeze([AUCUNE_ESTIMATION_SEGMENT, CARBURANT_DECLARE_SEUL]),
  pro: Object.freeze([AUCUNE_ESTIMATION_SEGMENT]),
})

/** Ce que le panneau affiche pour CE lead.
 *  - segment non livré : `{ livre: false, segment, message }` ;
 *  - segment livré (CAD161 résidentiel, CAD175 agricole et pro) :
 *    `{ livre: true, segment, famille, segmentAConfirmer, avertissement,
 *    phase, accroche, questions, objections, interdits, issues, enTete,
 *    profilSuppose, fenetre, aNoter, gardeFous }`, `phase` valant
 *    `'appel_1'` ou `'rappel'`. La question « en tête » (Q5, présence en
 *    journée) est RÉSIDENTIELLE : le profil d'un site pro vient de son
 *    rythme d'activité, pas de la présence à la maison.
 *  `options.touche` (CAD152) : la touche de la LIGNE d'où le panneau est
 *  ouvert — elle prime sur la prochaine touche du lead servie par le contrat
 *  (la frise peut ouvrir une touche à venir : sa phase est la sienne). */
export function guidanceAppel(panneau, options = {}) {
  const segment = panneau?.segment || null
  if (!segmentLivre(segment)) {
    return { livre: false, segment, message: messageSegmentNonLivre(panneau) }
  }
  const touche = options.touche !== undefined ? options.touche : panneau?.touche
  const vu = { ...(panneau || {}), touche }
  const famille = familleDuSegment(segment)
  const segmentAConfirmer = !segment
  // CAD172 — LE drapeau du serveur (`profil_suppose`, le même que la
  // proposition) décide ; à défaut (réponse d'avant CAD172), la présence
  // encore à poser en tient lieu. Résidentiel seulement.
  const entreePresence = questionEnTete(vu)
  const drapeau = typeof vu.profil_suppose === 'boolean' ? vu.profil_suppose : null
  const profilSuppose = famille === 'residentiel'
    && (drapeau === null ? Boolean(entreePresence) : drapeau)
  const enTete = profilSuppose ? entreePresence : null
  return {
    livre: true,
    segment,
    famille,
    segmentAConfirmer,
    avertissement: segmentAConfirmer ? MESSAGE_SEGMENT_A_CONFIRMER : null,
    phase: estToucheDeRappel(touche) ? 'rappel' : 'appel_1',
    accroche: texteAccroche(vu),
    questions: questionsDeLAppel(vu),
    objections: OBJECTIONS,
    interdits: INTERDITS_APPEL,
    issues: ISSUES_APPEL,
    enTete,
    profilSuppose,
    fenetre: fenetreAppel(vu),
    aNoter: A_NOTER_PAR_FAMILLE[famille],
    gardeFous: GARDE_FOUS_PAR_FAMILLE[famille],
  }
}
