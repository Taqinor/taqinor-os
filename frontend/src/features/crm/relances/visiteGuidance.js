// VISCAD (fondateur 15/09/2026) — « la visite technique devient une étape du
// suivi commercial » : coaching QUAND/COMMENT proposer la visite, câblé sur
// la cadence 'apres_devis' (le suivi après l'envoi du devis). Fichier PUR
// (aucun JSX, aucun appel réseau) — testable en `.test.mjs`, comme
// `lib/contactLinks.js`.
//
// La touche exposée par le contrat `relance_etape_v2.json` ne porte PAS de
// date de départ de cadence (`cadence_depart`) : impossible de calculer un
// « jour de cadence » depuis `due_date` seul. On dérive donc le jour
// approximatif de la touche depuis son `ordre`, via la MÊME table que le
// gabarit par défaut de la cadence apres_devis
// (`backend/django_core/apps/parametres/models_relance.py`
// `CADENCE_APRES_DEVIS_DEFAUT`) — jamais un chiffre réinventé ici : si le
// fondateur retouche cette cadence dans Paramètres, le repli ordinal
// ci-dessous (position 1 / 2-5 / 6+) reste correct même si les jours créditent.

// ordre (barreau apres_devis) -> jour approximatif du barreau par défaut.
const JOUR_PAR_ORDRE_APRES_DEVIS_DEFAUT = {
  1: 1, 2: 2, 3: 3, 4: 4, 5: 6, 6: 7, 7: 9, 8: 11, 9: 13, 10: 14,
}

/** Phase de proposition de la visite (1/2/3) pour une touche 'apres_devis'.
 *  `etape` : objet touche (`relance_etape_v2.json`) — seul `ordre` est utilisé.
 *  Repli ORDINAL (position dans la cadence, jamais un jour halluciné) quand
 *  l'ordre dépasse le gabarit par défaut (cadence personnalisée par la
 *  société) : 1er barreau = phase 1, 2ᵉ-5ᵉ = phase 2, 6ᵉ et au-delà = phase 3
 *  — même répartition que le gabarit par défaut (1 barreau J0-J1, 4 barreaux
 *  J2-J6, 5 barreaux J7+). */
export function phaseVisite(etape) {
  const ordre = etape?.ordre
  if (ordre == null) return 1
  const jour = JOUR_PAR_ORDRE_APRES_DEVIS_DEFAUT[ordre]
  if (jour != null) {
    if (jour <= 1) return 1
    if (jour <= 6) return 2
    return 3
  }
  // Repli ordinal — cadence personnalisée, ordre hors table par défaut.
  if (ordre <= 1) return 1
  if (ordre <= 5) return 2
  return 3
}

/** Contenu de coaching par phase — textes FR fournis par le fondateur
 *  (15/09/2026), jamais reformulés. */
export const PHASE_GUIDANCE = {
  1: {
    titre: 'Pas encore',
    texte: 'Pas encore — laissez le devis vivre. Répondez, écoutez.',
    script: null,
  },
  2: {
    titre: 'Semez la visite',
    texte: 'Semez la visite.',
    script: "Le chiffrage est basé sur vos factures et photos ; quand le "
      + "technicien passe, il confirme juste l'orientation du toit et la "
      + 'charpente pour verrouiller le prix, pas pour le changer.',
  },
  3: {
    titre: 'Proposez activement, en choix alternatif',
    texte: 'Proposez activement, en choix alternatif.',
    script: 'On a un créneau mardi matin ou jeudi après-midi — lequel vous arrange ?',
    jamais: 'jamais « voulez-vous qu\'on passe ? »',
  },
}

// Toujours affiché, quelle que soit la phase — signaux d'achat qui appellent
// une proposition IMMÉDIATE de visite (peu importe où on en est dans la
// cadence).
export const SIGNAUX_ACHAT = [
  "Questions sur le délai d'installation",
  'Questions sur les garanties',
  'Questions sur le financement',
  'Questions sur SA toiture / sa maison',
  'Demande de références ou de témoignages',
  'Toute question « comment ça se passe quand… » (installation, entretien, panne)',
]

export const REGLE_OBJECTION =
  'Toute objection technique se ferme par la visite, jamais par un débat au téléphone.'

// Règle fondateur (15/09/2026) : le rendez-vous ne vaut que si le DÉCIDEUR
// est là — une visite faite devant le gardien ou la bonne ne fait jamais
// avancer un dossier.
export const REGLE_VRAI_CLIENT =
  'La visite se fait avec le client lui-même — jamais le gardien ni la bonne. '
  + 'Confirmez sa présence au créneau choisi.'

// Statut RÉEL des visites du module `apps/visites` (VISCAD1, distinct des
// statuts RelanceEtape) — tons de badge SEULEMENT, le LIBELLÉ affiché reste
// TOUJOURS `statut_libelle` (rendu serveur, jamais réinventé ici).
export const STATUT_VISITE_TONE = {
  brouillon: 'outline',
  en_cours: 'info',
  terminee: 'success',
  validee: 'success',
  a_refaire: 'warning',
}

// Une visite compte comme « passée » (repliable avec l'historique de la
// frise) une fois son cycle terrain conclu — jamais tant qu'elle reste à
// planifier/en cours/à refaire.
export function visitePassee(visite) {
  return visite?.statut === 'terminee' || visite?.statut === 'validee'
}
