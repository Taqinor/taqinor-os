import { useState } from 'react'
import {
  Check, SkipForward, Phone, MessageCircle, Clock3,
} from 'lucide-react'
import {
  Badge, Button, Textarea, Input, Label,
} from '../../../ui'
import ScoreBadge from '../ScoreBadge'
import { PRIORITE_LABELS } from '../stages'
import { toastInfo } from '../../../lib/toast'
import crmApi from '../../../api/crmApi'
import PanneauProposerVisite from './PanneauProposerVisite'
import PlanifierVisiteModal from './PlanifierVisiteModal'
import { suiteAnnoncee } from './suite'

/* ============================================================================
   MRY31 — `RelanceEtapeRow` EXTRAIT de `pages/crm/RelancesDuJourWidget.jsx`
   (MRY14), à l'IDENTIQUE (comportement/markup préservés — les tests existants
   du widget restent verts), pour être PARTAGÉ par trois écrans qui en ont
   chacun besoin dans un contexte différent :
     - le widget Cockpit « Relances du jour » (liste multi-leads, format
       complet) ;
     - l'écran « Suivi des relances » (MRY31, `RelancesSuiviPage.jsx` — liste
       multi-leads + statut, tous jours/tous statuts) ;
     - la frise de la fiche lead (MRY32, `CadenceFrise.jsx` — un seul lead
       déjà visible à l'écran, format compact).

   Props ajoutées par cette extraction (au-delà de celles du widget d'origine) :
     - `compact`    : masque l'en-tête (nom du lead, sous-titre libellé,
                      ScoreBadge, badge de priorité) — la fiche lead sait déjà
                      de qui/quoi il s'agit, et la frise affiche déjà juste
                      au-dessus sa propre ligne cadence/canal/libellé/date ;
                      RÉAFFICHER le libellé ici dupliquerait ce texte (deux
                      correspondances pour `getByText`) — le mode compact
                      va donc directement aux badges + boutons d'action ;
     - `readOnly`   : aucun bouton d'action — une ligne qui se LIT seulement
                      (jours futurs du widget, MRY32) ;
     - `showStatut` : ajoute un badge de statut (Fait à HH:MM + auteur /
                      Sautée / À faire / En retard) — l'écran de suivi (MRY31)
                      affiche TOUS les statuts, pas seulement les étapes à
                      faire du widget/de la frise — et la note serveur le cas
                      échéant.
   ========================================================================== */

// Libellés FR des canaux SUGGÉRÉS de la cadence — jamais un envoi, juste
// l'indication du prochain geste attendu (appel/WhatsApp/e-mail/visite).
// Non exportés — react-refresh/only-export-components interdit de mélanger
// composant et constantes dans un fichier de composant (fast-refresh Vite) ;
// aucun autre fichier n'en a besoin (`CadenceFrise.jsx` garde sa PROPRE copie
// locale, motif déjà en place avant cette extraction : page → section, sens
// d'import inverse).
const CANAL_LABELS = {
  appel: 'Appel',
  whatsapp: 'WhatsApp',
  email: 'E-mail',
  visite: 'Visite',
}

const CADENCE_LABELS = {
  contact: 'Contact',
  apres_devis: 'Après devis',
  reveil: 'Réveil',
  generique: 'Générique',
}

const CADENCE_TONE = {
  contact: 'info',
  apres_devis: 'primary',
  reveil: 'neutral',
  generique: 'outline',
}

// QJ-QUESTIONS (fondateur 07/09/2026) — chaque touche pose LA bonne question,
// et la réponse choisie décide seule de la suite (routage serveur
// QJ-INVARIANT : la liste de relances d'un lead ne se termine que par Froid
// ou Signé). Les réponses restent les issues serveur (LeadActivity.OUTCOMES) :
// aucun nouveau contrat — seulement la bonne question au bon moment.
// CAD17 — les réponses ne portent PLUS de phrase « suite » écrite par cadence
// (elle mentait dès que le libellé ou le rang de la touche changeait la suite
// réelle : CAD1, CAD3, CAD16, CAD97). La suite annoncée vient du SERVEUR
// (`etape.suites`, dérivée du moteur) et se traduit dans `./suite.js`.
// `precision` ne porte qu'un geste d'ÉCRAN, jamais un effet moteur.
const QUESTIONS = {
  contact: {
    question: 'Résultat de la touche ?',
    reponses: [
      { outcome: 'joint', label: 'Client joint' },
      { outcome: 'non_joint', label: 'Pas de réponse' },
      { outcome: 'rappel', label: 'À rappeler le…', rappel: true },
      { outcome: 'refuse', label: 'Refus' },
    ],
  },
  apres_devis: {
    question: 'Réponse du client sur la proposition ?',
    aide: 'Le client accepte ? Marquez le devis ACCEPTÉ (Ventes → Devis) : le dossier passe en Signé et toutes les relances s’arrêtent.',
    reponses: [
      { outcome: 'interesse', label: 'Intéressé' },
      // VISCAD6 (fondateur 15/09/2026) — « la visite devient une étape du
      // suivi commercial » : issue SERVEUR existante (LeadActivity.OUTCOMES,
      // jamais une nouvelle valeur inventée ici), choisie quand le client dit
      // oui à la visite pendant le suivi de proposition — ouvre la modale de
      // planification juste après confirmation (confirmerFait ci-dessous).
      { outcome: 'visite_acceptee', label: 'Visite acceptée',
        precision: 'La planification s’ouvre juste après la confirmation.' },
      { outcome: 'non_joint', label: 'Sans réponse' },
      { outcome: 'rappel', label: 'À rappeler le…', rappel: true },
      { outcome: 'refuse', label: 'Refuse la proposition' },
    ],
  },
  generique: {
    question: 'Où en est ce dossier ?',
    reponses: [
      { outcome: '', label: 'Fait — passer à la suite' },
      { outcome: 'rappel', label: 'À rappeler le…', rappel: true },
      { outcome: 'refuse', label: 'Client refuse' },
    ],
  },
}
QUESTIONS.reveil = {
  question: 'Résultat du réveil ?',
  reponses: [
    { outcome: 'joint', label: 'Client joint' },
    { outcome: 'non_joint', label: 'Pas de réponse' },
    { outcome: 'rappel', label: 'À rappeler le…', rappel: true },
    { outcome: 'refuse', label: 'Refus' },
  ],
}

// CKP4 (fondateur 2026-09-10) — un canal APPEL clôturé « Fait » exige TOUJOURS
// une issue : Joint/Pas de réponse restent les réponses existantes ci-dessus
// (`joint`/`non_joint`, JAMAIS réinventées) ; Répondeur/Occupé s'y AJOUTENT
// (jamais un remplacement — rappel/refus restent disponibles) pour les
// appels seulement, l'écran Meryem étant d'abord un écran d'appels. La suite
// est celle de « Pas de réponse » (même issue serveur, donc mêmes codes
// d'effet dans `etape.suites.non_joint`).
// Réconciliation de fold (CKP2↔CKP4) : le serveur ne connaît QUE les issues
// de `LeadActivity.OUTCOMES` — Répondeur/Occupé s'envoient donc comme
// `non_joint` (même règle de suite), la précision partant dans la `note`.
// Aucune nouvelle valeur d'énumération côté serveur = aucun risque de
// migration ; l'information reste tracée mot pour mot dans le chatter.
const APPEL_REPONSES_SUPPLEMENTAIRES = [
  { outcome: 'non_joint', note: 'Répondeur', label: 'Répondeur' },
  { outcome: 'non_joint', note: 'Occupé', label: 'Occupé' },
  // CAD11 — un numéro MORT n'a pas à épuiser les six tentatives : même patron
  // (issue `non_joint` + note typée, aucune nouvelle énumération), plus la
  // PROPOSITION « perdu, motif junk » en un clic (`junk` = le motif junk
  // pré-choisi s'il existe dans la liste de la société). Le clic décide.
  { outcome: 'non_joint', note: 'Numéro invalide', label: 'Numéro invalide',
    junk: 'Numéro invalide',
    precision: 'La touche est close « non joint » avec la note « Numéro invalide ». Cochez ci-dessous pour marquer le lead perdu (motif junk) en un clic.' },
  { outcome: 'non_joint', note: 'A bloqué / signalé', label: 'A bloqué / signalé',
    junk: 'Jamais répondu',
    precision: 'La touche est close « non joint » avec la note « A bloqué / signalé ». Cochez ci-dessous pour marquer le lead perdu (motif junk) en un clic.' },
]

// CAD-A — RÉPONSES DU CLIENT (clé `reponse`, table `services.REPONSES_TOUCHE`
// côté serveur) : l'écran n'envoie que la CLÉ, jamais l'issue — le serveur en
// dérive l'issue existante (aucune nouvelle valeur d'énumération) ET la suite.
// `message` : le texte d'accusé PROPOSÉ juste après (aperçu + clic humain,
// décision D5 — jamais un envoi automatique).
// CAD5 — « Ne plus me contacter » vaut sur TOUTES les cadences : l'opposition
// (loi 09-08 art. 9 al. 2) s'enregistre au moment où elle est dite.
const REPONSES_TOUTES_CADENCES = [
  { reponse: 'ne_plus_contacter', label: 'Ne plus me contacter', message: 'stop_contact',
    precision: 'L’accusé « je ne vous rappellerai plus » vous est proposé juste après.' },
]

// CAD6 — « Plus tard — pas maintenant » (la réponse la plus fréquente du
// résidentiel) : la date convenue est OBLIGATOIRE (`rappel: true`), aucun
// barreau n'est consommé — le dossier se met en VEILLE (mécanique CAD26).
const REPONSE_PLUS_TARD = {
  reponse: 'plus_tard', label: 'Plus tard — pas maintenant', rappel: true,
  message: 'rappel_plus_tard',
  precision: 'Le message « je vous rappelle [jour] à [heure] » vous est proposé juste après — complétez les crochets avant de l’envoyer.',
}

// CAD7 — la réponse la plus fréquente sur une PROPOSITION : le client
// négocie. Issue « à rappeler » + note typée côté serveur ; le suivi se met
// en pause le temps de préparer l'appel du fondateur (aucune offre ne part
// avant sa décision).
const REPONSE_QUESTION_PRIX = {
  reponse: 'question_prix', label: 'Question de prix — veut négocier',
  precision: 'Aucune offre n’est envoyée avant la décision du fondateur.',
}

// CAD8 — une VARIANTE demandée au téléphone : l'étape « Préparer le devis
// modifié — rappeler le client » (déjà écrite pour le retour de visite) est
// posée, le protocole du devis écarté se tait.
const REPONSE_DEVIS_MODIFIE = {
  reponse: 'devis_modifie', label: 'Demande un devis modifié',
}

// CAD9 — « Décision à plusieurs » pose l'étiquette AU MOMENT où le client le
// dit : le « dimanche famille » réapparaît dans le plan s'il n'est pas encore
// dépassé. Deux nuances, distinguées dans la note : la famille (un délai) et
// le propriétaire (un interlocuteur à changer).
const REPONSES_DECISION_A_PLUSIEURS = [
  { reponse: 'decision_famille', label: 'Décision à plusieurs — en famille' },
  { reponse: 'decision_proprietaire', label: 'Décision à plusieurs — le propriétaire',
    precision: 'La note dit qu’il faut joindre le propriétaire.' },
]

// Les réponses du client propres à CHAQUE cadence de protocole (les étapes de
// filet `generique` n'en ont pas : « À rappeler le… » y reporte déjà, CAD3).
const REPONSES_CLIENT = {
  contact: [REPONSE_PLUS_TARD],
  apres_devis: [
    REPONSE_PLUS_TARD, REPONSE_QUESTION_PRIX, REPONSE_DEVIS_MODIFIE,
    ...REPONSES_DECISION_A_PLUSIEURS,
  ],
  reveil: [REPONSE_PLUS_TARD],
}

/** Lit la PROCHAINE touche depuis la RÉPONSE serveur du « Fait » (jamais
 *  calculée côté écran — un appel programmé à tort aurait pu fausser
 *  l'agenda). `prochaine_touche` (contrat CKP2, à venir) : `{due_at, canal}`
 *  ou absent tant que la matérialisation réactive n'a rien programmé
 *  (dernière touche, cadence arrêtée…) — silence, jamais un message inventé. */
function messageProchaineTouche(prochaine) {
  if (!prochaine?.due_at) return null
  const t = new Date(prochaine.due_at).getTime()
  if (Number.isNaN(t)) return null
  const quand = new Intl.DateTimeFormat('fr-FR', {
    day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit',
    timeZone: 'Africa/Casablanca',
  }).format(t)
  const canal = CANAL_LABELS[prochaine.canal] ?? prochaine.canal
  return canal
    ? `Prochain${canal === 'Appel' ? ' appel' : ` ${canal.toLowerCase()}`} programmé le ${quand}.`
    : `Prochaine touche programmée le ${quand}.`
}

/** `due_at` (ISO) → « HH:MM » heure Casablanca, ou « maintenant » si déjà
    passé. Repli sur `null` (pas d'heure connue) pour laisser l'appelant
    afficher la date seule. Fuseau EXPLICITE (comme `crm.horaires`, jamais
    l'heure locale du navigateur — un commercial en déplacement verrait sinon
    une heure fausse). */
function heureDue(etape) {
  if (!etape.due_at) return null
  const t = new Date(etape.due_at).getTime()
  if (Number.isNaN(t)) return null
  if (t <= Date.now()) return 'maintenant'
  return new Intl.DateTimeFormat('fr-FR', {
    hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Casablanca',
  }).format(t)
}

/** « AAAA-MM-JJ » d'aujourd'hui À CASABLANCA (jamais le fuseau du
    navigateur : un commercial en déplacement comparerait sinon ses dates à
    une autre journée que celle du serveur). */
function aujourdhuiCasablanca() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date())
}

/** Jours calendaires entre deux dates « AAAA-MM-JJ » (arithmétique pure sur
    les dates, aucun fuseau en jeu). */
function joursEntre(debut, fin) {
  return Math.round((Date.parse(`${fin}T00:00:00Z`) - Date.parse(`${debut}T00:00:00Z`)) / 86400000)
}

// CAD26 — au-delà de ce report (7 à 10 jours dans l'audit : on retient le bas
// de la fourchette), « Mettre en veille jusqu'au… » est PROPOSÉ de lui-même :
// un client qui fixe une date lointaine demande du temps, pas que tout le plan
// glisse. Le serveur, lui, bascule la veille en réveil daté au-delà d'un mois.
const VEILLE_PROPOSEE_APRES_JOURS = 7

// RLC3 (relevé fondateur du 08/09/2026) — les canaux dont la touche consiste à
// ÉCRIRE : c'est là, et seulement là, que la question « le message a-t-il été
// ouvert ? » a un sens. Un appel a déjà son issue obligatoire (CKP2/CKP4).
const CANAUX_MESSAGE = ['whatsapp', 'email']

/** `traite_le` (ISO, MRY30/MRY31) → « HH:MM » heure Casablanca — JAMAIS le
    repli « maintenant » de `heureDue` ci-dessus (c'est un horodatage PASSÉ,
    pas une échéance à venir). `null` si absent/invalide. */
function heureTraite(iso) {
  if (!iso) return null
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return null
  return new Intl.DateTimeFormat('fr-FR', {
    hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Casablanca',
  }).format(t)
}

// MRY31 — badge de statut de l'écran de suivi (tous statuts confondus,
// jamais juste les étapes à faire du widget/de la frise).
// CKP1/CKP4 (fondateur 2026-09-10, « vérité des sautées ») — SAUTEE reste
// EXCLUSIVEMENT l'action humaine `sauter` (qui/quand affichés en clair) ;
// ANNULEE est un arrêt du MOTEUR (`arreter_cadence`, reprises…) — jamais
// confondue avec un saut humain, jamais d'auteur (traite_par = null côté
// serveur), seulement le motif conservé en note.
function StatutBadge({ etape }) {
  if (etape.statut === 'fait') {
    const heure = heureTraite(etape.traite_le)
    const qui = etape.traite_par_nom
    return (
      <Badge tone="success">
        Fait{heure ? ` · ${heure}` : ''}{qui ? ` · ${qui}` : ''}
      </Badge>
    )
  }
  if (etape.statut === 'sautee') {
    const heure = heureTraite(etape.traite_le)
    const qui = etape.traite_par_nom
    return (
      <Badge tone="neutral">
        Sautée{qui ? ` · ${qui}` : ''}{heure ? ` · ${heure}` : ''}
      </Badge>
    )
  }
  if (etape.statut === 'annulee') {
    return (
      <Badge tone="outline">
        Annulée (moteur){etape.note ? ` · ${etape.note}` : ''}
      </Badge>
    )
  }
  if (etape.overdue) return <Badge tone="danger">En retard</Badge>
  return <Badge tone="outline">À faire</Badge>
}

export default function RelanceEtapeRow({
  etape, onFait, onSauter, onReporter, onOuvrirMessage, busyId, navigate,
  compact = false, readOnly = false, showStatut = false,
  // VISCAD6 — appelé après qu'une visite a été planifiée depuis CETTE ligne
  // (panneau de coaching OU issue « Visite acceptée ») pour laisser le
  // parent rafraîchir (même callback que Fait/Sauter/Reporter, ex.
  // `CadenceFrise.onChanged`) — optionnel, une ligne readOnly n'en a pas besoin.
  onVisiteChanged,
}) {
  // '' | 'sauter' | 'fait' | 'reporter' — un seul panneau ouvert à la fois.
  const [panel, setPanel] = useState('')
  const [note, setNote] = useState('')
  const [reponseIdx, setReponseIdx] = useState(null)
  const [rappelLe, setRappelLe] = useState('')
  const [rappelHeure, setRappelHeure] = useState('')
  const [reportDate, setReportDate] = useState('')
  const [reportHeure, setReportHeure] = useState('')
  // CAD26 — '' = le geste PROPOSÉ selon la date ; 'decaler' | 'veille' = le
  // choix explicite de la commerciale, qui prime toujours.
  const [reportMode, setReportMode] = useState('')
  // CKP4 — erreur DE CHAMP renvoyée par le serveur (400
  // `{erreurs: {outcome: "…"}}` pour un canal APPEL clôturé sans issue) :
  // s'affiche SOUS le contrôle concerné, jamais un toast générique qui
  // masquerait le champ fautif (règle « le champ fautif, message exact »).
  const [erreurOutcome, setErreurOutcome] = useState('')
  // CAD27 — erreur SERVEUR sur la date de rappel (`{erreurs: {rappel_le}}`).
  const [erreurRappel, setErreurRappel] = useState('')
  // CAD10 — le motif de refus FACULTATIF : la liste paramétrée (Paramètres →
  // CRM) n'est chargée qu'au premier refus choisi (`null` = pas encore lue),
  // jamais pour chaque ligne de la file.
  const [motifs, setMotifs] = useState(null)
  const [motifRefus, setMotifRefus] = useState('')
  const [erreurMotif, setErreurMotif] = useState('')
  // CAD11 — la proposition « perdu, motif junk » (case à cocher : le clic
  // humain décide) et le motif junk choisi ('' = celui proposé par défaut).
  const [perduJunk, setPerduJunk] = useState(false)
  const [motifJunk, setMotifJunk] = useState('')
  // VISCAD6 — modale de planification de la visite, PARTAGÉE par le panneau
  // de coaching (ci-dessous) et l'issue « Visite acceptée » du Fait.
  const [planifierOuvert, setPlanifierOuvert] = useState(false)
  // RLC3 — la confirmation explicite « marquer faite sans avoir ouvert le
  // message ? ». Jamais un blocage : la case est TOUJOURS disponible (Meryem
  // peut avoir écrit depuis son téléphone) — elle rend seulement le geste
  // conscient, et le dit dans le chatter.
  const [sansOuverture, setSansOuverture] = useState(false)
  const busy = busyId === etape.id

  const fermer = () => {
    setPanel('')
    setNote(''); setReponseIdx(null); setRappelLe(''); setRappelHeure('')
    setReportDate(''); setReportHeure(''); setErreurOutcome('')
    setSansOuverture(false); setReportMode(''); setErreurRappel('')
    setMotifRefus(''); setErreurMotif('')
    setPerduJunk(false); setMotifJunk('')
  }

  // CAD10 — lecture paresseuse des motifs, au geste (jamais dans un effet) :
  // un échec laisse simplement la liste vide — le motif est FACULTATIF.
  const chargerMotifs = () => {
    if (motifs !== null) return
    setMotifs([])
    Promise.resolve()
      .then(() => crmApi.getMotifsPerte())
      .then((r) => setMotifs(
        (r?.data?.results ?? r?.data ?? []).filter((m) => !m.archived)))
      .catch(() => setMotifs([]))
  }

  const questionsTouche = QUESTIONS[etape.cadence] ?? QUESTIONS.contact
  // CKP4 — canal APPEL : Répondeur/Occupé s'ajoutent aux réponses de la
  // cadence (jamais un remplacement, voir commentaire plus haut).
  // CAD-A — les réponses du client s'ajoutent EN DERNIER (jamais à la place
  // des issues existantes).
  const reponsesDisponibles = [
    ...questionsTouche.reponses,
    ...(etape.canal === 'appel' ? APPEL_REPONSES_SUPPLEMENTAIRES : []),
    ...(REPONSES_CLIENT[etape.cadence] ?? []),
    ...REPONSES_TOUTES_CADENCES,
  ]
  const reponseChoisie = reponseIdx == null
    ? null : reponsesDisponibles[reponseIdx]
  // RLC3 — cette touche consiste-t-elle à écrire, et le message a-t-il été
  // ouvert ? `message_ouvert_le` vient du SERVEUR (activité « WhatsApp
  // ouvert », contrat `relance_etape_v2`) — jamais une mémoire d'écran, qui
  // aurait tout oublié au rechargement de la page.
  const toucheMessage = CANAUX_MESSAGE.includes(etape.canal)
  const messageOuvertLe = toucheMessage
    ? heureTraite(etape.message_ouvert_le) : null
  const confirmationOuvertureRequise = (
    toucheMessage && !messageOuvertLe && !sansOuverture)

  // CAD27 — une date de rappel/report dans le PASSÉ tirait tout le plan en
  // arrière (plusieurs touches « en retard » d'un coup, pour une faute de
  // frappe sur l'année). L'écran la REFUSE : champ borné à aujourd'hui
  // (Casablanca), message sous le champ qui le NOMME, Confirmer désactivé.
  // Le serveur refuse aussi (400 `{erreurs: {rappel_le}}`) — ceinture.
  const aujourdhui = aujourdhuiCasablanca()
  const rappelPasse = Boolean(rappelLe) && rappelLe < aujourdhui
  const reportPasse = Boolean(reportDate) && reportDate < aujourdhui
  const messageRappel = erreurRappel || (rappelPasse
    ? '« Rappeler le » : cette date est déjà passée — choisissez aujourd’hui ou une date à venir.'
    : '')
  // CAD11 — les motifs JUNK de la société ; celui proposé par défaut est le
  // motif nommé par la réponse s'il existe, sinon le premier de la liste.
  const motifsJunk = (motifs ?? []).filter((m) => m.est_junk)
  const motifJunkEffectif = motifJunk
    || (motifsJunk.find((m) => m.nom === reponseChoisie?.junk) ?? motifsJunk[0])?.nom
    || ''

  const confirmerFait = () => {
    if (!reponseChoisie) return
    if (reponseChoisie.rappel && !rappelLe) return
    if (reponseChoisie.rappel && rappelPasse) return
    if (confirmationOuvertureRequise) return
    const payload = {}
    if (note.trim()) payload.note = note.trim()
    else if (reponseChoisie.note) payload.note = reponseChoisie.note
    if (reponseChoisie.outcome) payload.outcome = reponseChoisie.outcome
    // CAD-A — une réponse du client part sous sa CLÉ ; l'issue est dérivée
    // côté serveur (jamais envoyée d'ici).
    if (reponseChoisie.reponse) payload.reponse = reponseChoisie.reponse
    if (reponseChoisie.rappel && rappelLe) {
      payload.rappel_le = rappelLe
      if (rappelHeure) payload.rappel_heure = rappelHeure
    }
    // CAD10 — le motif n'accompagne QUE le refus, et seulement s'il est choisi.
    if (reponseChoisie.outcome === 'refuse' && motifRefus) payload.motif_refus = motifRefus
    // CAD11 — « perdu, motif junk » seulement si la case est COCHÉE.
    if (reponseChoisie.junk && perduJunk && motifJunkEffectif) {
      payload.perdu_junk = motifJunkEffectif
    }
    // RLC3 — le geste assumé est TRACÉ : `body` s'ajoute à la ligne de chatter
    // de la touche (`marquer_etape_relance`), sans toucher à la note libre.
    if (toucheMessage && !messageOuvertLe) {
      payload.body = 'Marquée faite sans ouverture du message depuis l’ERP.'
    }
    setErreurOutcome('')
    // VISCAD6 — l'outcome choisi est lu AVANT l'appel (le state se ferme/se
    // réinitialise dès le succès dans les parents qui retirent la ligne) :
    // ouvrir la modale de planification dépend de CETTE réponse, jamais
    // d'un state relu après coup.
    const outcomeChoisi = reponseChoisie.outcome
    // CAD-A — le texte d'accusé à PROPOSER après une réponse du client, lu
    // AVANT l'appel pour la même raison que `outcomeChoisi`.
    const messageAPropose = reponseChoisie.message
    // CKP4 — `onFait` renvoie désormais une promesse (widget/frise/suivi) :
    // succès → message de confirmation lu de LA RÉPONSE serveur uniquement
    // (jamais calculé ici) ; 400 outcome → affiché SOUS le contrôle, la ligne
    // reste ouverte (le parent ne l'a pas retirée sur un échec).
    Promise.resolve(onFait(etape.id, payload)).then((data) => {
      const message = messageProchaineTouche(data?.prochaine_touche)
      if (message) toastInfo(message)
      // VISCAD6 — « Visite acceptée » confirmée : ouvre tout de suite la
      // modale de planification (le commercial vient de dire oui au client,
      // jamais un second aller-retour pour la planifier).
      if (outcomeChoisi === 'visite_acceptee') setPlanifierOuvert(true)
      // CAD-A — l'accusé convenu (« je ne vous rappellerai plus »…) est
      // PROPOSÉ dans la modale d'aperçu du parent (elle survit au retrait de
      // cette ligne) : rien ne part sans le clic « Ouvrir WhatsApp ».
      if (messageAPropose) onOuvrirMessage?.({ ...etape, message_cle: messageAPropose })
    }).catch((err) => {
      // Règle « le champ fautif, le message exact » : l'issue (CKP4) comme
      // la réponse du client (CAD-A) s'affichent SOUS les réponses.
      const erreurs = err?.response?.status === 400
        ? err?.response?.data?.erreurs : null
      const champ = erreurs?.outcome || erreurs?.reponse
      if (champ) setErreurOutcome(champ)
      // CAD27 — la date refusée par le serveur s'affiche SOUS son champ.
      if (erreurs?.rappel_le) setErreurRappel(erreurs.rappel_le)
      // CAD10 — de même pour le motif de refus (et CAD11, le motif junk).
      if (erreurs?.motif_refus) setErreurMotif(erreurs.motif_refus)
      if (erreurs?.perdu_junk) setErreurMotif(erreurs.perdu_junk)
    })
  }

  // CAD26 — le geste de report : décaler (historique) ou mettre en veille.
  const veilleProposee = Boolean(reportDate)
    && joursEntre(aujourdhuiCasablanca(), reportDate) > VEILLE_PROPOSEE_APRES_JOURS
  const modeReport = reportMode || (veilleProposee ? 'veille' : 'decaler')

  const confirmerReporter = () => {
    if (!reportDate || reportPasse) return
    // F1 — forme SÛRE ancrée Casablanca CÔTÉ SERVEUR (`_parse_rappel`) :
    // jamais un `new Date(...).toISOString()`, qui interprète
    // `${date}T${heure}:00` dans le fuseau du NAVIGATEUR et décale l'heure
    // réellement reportée dès que l'agent n'est pas sur ce fuseau.
    const payload = { rappel_le: reportDate, rappel_heure: reportHeure || '09:00' }
    const enVeille = modeReport === 'veille'
    if (enVeille) payload.mode = 'veille'
    Promise.resolve(onReporter(etape.id, payload)).then((data) => {
      if (!enVeille || !data) return
      // La réponse serveur dit ce qui s'est réellement passé : la touche
      // déplacée (même barreau) ou la première touche d'un réveil daté.
      toastInfo(data.cadence === 'reveil' && etape.cadence !== 'reveil'
        ? 'Plus d’un mois d’attente : la cadence est arrêtée et un réveil est daté.'
        : 'Dossier en veille : la cadence reprendra à cette même touche.')
    })
  }

  const heure = heureDue(etape)

  return (
    <li className="rounded-md border border-border p-2" data-testid="relance-etape-row">
      {!compact && (
        <div className="flex items-start justify-between gap-2">
          <button
            type="button"
            className="flex-1 truncate text-left text-sm font-medium hover:underline"
            onClick={() => navigate(`/crm/leads?lead=${etape.lead}`)}
          >
            {etape.lead_nom || 'Lead'}
            <span className="block text-xs font-normal text-muted-foreground">
              {etape.libelle}
              {etape.lead_owner_nom ? ` · ${etape.lead_owner_nom}` : ''}
            </span>
          </button>
          <ScoreBadge lead={{ score: etape.lead_score }} />
        </div>
      )}
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        <Badge tone={CADENCE_TONE[etape.cadence] ?? 'neutral'}>
          {CADENCE_LABELS[etape.cadence] ?? etape.cadence}
        </Badge>
        {etape.overdue ? (
          <Badge tone="danger">En retard{heure ? ` · ${heure}` : ''}</Badge>
        ) : (
          <Badge tone="neutral">{heure ?? '—'}</Badge>
        )}
        <Badge tone="outline">{CANAL_LABELS[etape.canal] ?? etape.canal}</Badge>
        {!compact && etape.lead_priorite && etape.lead_priorite !== 'normale' && (
          <Badge tone={etape.lead_priorite === 'haute' ? 'warning' : 'neutral'}>
            {PRIORITE_LABELS[etape.lead_priorite] ?? etape.lead_priorite}
          </Badge>
        )}
        {showStatut && <StatutBadge etape={etape} />}
        {/* CAD11 — `lead_est_junk` (contrat `relance_etape_v2`) : le lead
            est perdu avec un motif junk — visible SUR la touche, pour que la
            qualité des numéros venus des publicités se lise dans la file. */}
        {etape.lead_est_junk && (
          <Badge tone="danger" title="Lead perdu — motif junk (pas un vrai prospect)">
            Junk
          </Badge>
        )}
      </div>
      {showStatut && etape.note && (
        <p className="mt-1 text-xs text-muted-foreground">{etape.note}</p>
      )}
      {/* VISCAD — le panneau de coaching se gate lui-même sur cadence ===
          'apres_devis' ; ici on ne gate que sur `readOnly` (une ligne qui se
          LIT seulement — jours futurs du widget, historique du suivi — n'a
          pas d'action à proposer). Rendu dans les DEUX modes (compact ET
          cockpit), jamais seulement compact. */}
      {!readOnly && (
        <PanneauProposerVisite etape={etape} onPlanifier={() => setPlanifierOuvert(true)} />
      )}
      {!readOnly && panel === '' && (
        <div className="mt-2 flex flex-wrap justify-end gap-1.5">
          <Button
            size="sm" variant="outline" disabled={busy || !etape.lead_telephone}
            onClick={() => { if (etape.lead_telephone) window.location.href = `tel:${etape.lead_telephone}` }}
          >
            <Phone className="size-3.5" /> Appeler
          </Button>
          <Button
            size="sm" variant="outline" disabled={busy}
            onClick={() => onOuvrirMessage(etape)}
          >
            <MessageCircle className="size-3.5" /> WhatsApp
          </Button>
          <Button
            size="sm" variant="outline" disabled={busy}
            onClick={() => setPanel('reporter')}
          >
            <Clock3 className="size-3.5" /> Reporter
          </Button>
          <Button
            size="sm" variant="outline" disabled={busy}
            onClick={() => setPanel('sauter')}
          >
            <SkipForward className="size-3.5" /> Sauter
          </Button>
          <Button size="sm" disabled={busy} onClick={() => setPanel('fait')}>
            <Check className="size-3.5" /> Fait
          </Button>
        </div>
      )}
      {!readOnly && panel === 'sauter' && (
        <div className="mt-2 flex flex-col gap-1.5">
          <Textarea
            rows={2} placeholder="Note (optionnelle) — pourquoi sauter cette relance ?"
            value={note} onChange={(e) => setNote(e.target.value)}
          />
          <div className="flex justify-end gap-1.5">
            <Button size="sm" variant="outline" disabled={busy} onClick={fermer}>
              Annuler
            </Button>
            <Button size="sm" disabled={busy} onClick={() => onSauter(etape.id, note)}>
              Confirmer
            </Button>
          </div>
        </div>
      )}
      {!readOnly && panel === 'fait' && (
        <div className="mt-2 flex flex-col gap-1.5">
          <p className="text-sm font-medium">{questionsTouche.question}</p>
          {questionsTouche.aide && (
            <p className="text-xs text-muted-foreground">{questionsTouche.aide}</p>
          )}
          {/* RLC3 — sur une touche MESSAGE, le panneau rappelle d'abord si le
              message a été ouvert. Ouvert : on le dit, et rien n'est demandé.
              Pas ouvert : une confirmation EXPLICITE, jamais un blocage —
              Meryem peut parfaitement avoir écrit depuis son téléphone. */}
          {toucheMessage && messageOuvertLe && (
            <p
              className="text-xs text-muted-foreground"
              data-testid="rappel-message-ouvert"
            >
              Message ouvert à {messageOuvertLe} depuis l’ERP.
            </p>
          )}
          {toucheMessage && !messageOuvertLe && (
            <label
              className="flex items-start gap-1.5 text-xs"
              data-testid="confirmer-sans-ouverture"
            >
              <input
                type="checkbox" className="mt-0.5" checked={sansOuverture}
                onChange={(e) => setSansOuverture(e.target.checked)}
              />
              <span>
                Ce message n’a pas été ouvert depuis l’ERP — marquer faite sans
                avoir ouvert le message ?
              </span>
            </label>
          )}
          <div className="flex flex-wrap gap-1.5" role="group" aria-label={questionsTouche.question}>
            {reponsesDisponibles.map((r, idx) => (
              <Button
                key={r.label} type="button" size="sm"
                variant={reponseIdx === idx ? 'default' : 'outline'}
                onClick={() => {
                  setReponseIdx((cur) => (cur === idx ? null : idx)); setErreurOutcome('')
                  setErreurMotif('')
                  if (r.outcome === 'refuse' || r.junk) chargerMotifs()
                }}
              >
                {r.label}
              </Button>
            ))}
          </div>
          {/* CAD17 — la suite annoncée vient du SERVEUR (`etape.suites`,
              dérivée du moteur) : jamais une phrase écrite par cadence.
              CAD11 — la case « perdu, motif junk » cochée change la suite
              réelle (le lead passe perdu : plus aucune relance, sans suite —
              `suite=False` côté serveur) : la phrase le dit alors. */}
          {reponseChoisie && (
            <p className="text-xs text-muted-foreground" data-testid="suite-reponse">
              {reponseChoisie.junk && perduJunk
                ? 'Le lead passe perdu (motif junk) : toutes ses relances s’arrêtent, sans aucune suite.'
                : suiteAnnoncee(etape, reponseChoisie)}
            </p>
          )}
          {erreurOutcome && (
            <p className="text-xs text-danger" role="alert" data-testid="erreur-outcome">
              {erreurOutcome}
            </p>
          )}
          {reponseChoisie?.rappel && (
            <div className="flex flex-wrap items-end gap-2">
              <div className="flex flex-col gap-1">
                <Label className="text-xs" htmlFor={`rappel-le-${etape.id}`}>Rappeler le</Label>
                <Input id={`rappel-le-${etape.id}`} type="date" className="w-40"
                       min={aujourdhui} aria-invalid={Boolean(messageRappel)}
                       value={rappelLe}
                       onChange={(e) => { setRappelLe(e.target.value); setErreurRappel('') }} />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs" htmlFor={`rappel-heure-${etape.id}`}>Heure</Label>
                <Input id={`rappel-heure-${etape.id}`} type="time" className="w-28"
                       value={rappelHeure} onChange={(e) => setRappelHeure(e.target.value)} />
              </div>
            </div>
          )}
          {reponseChoisie?.rappel && messageRappel && (
            <p className="text-xs text-danger" role="alert" data-testid="erreur-rappel-le">
              {messageRappel}
            </p>
          )}
          {/* CAD10 — le seul moment où la raison du refus est connue : la
              liste courte déjà paramétrée est PROPOSÉE, jamais exigée
              (« perdu » reste une décision humaine). Le motif part sur la
              ligne de chatter de la touche, pas sur le motif de perte. */}
          {reponseChoisie?.outcome === 'refuse' && (
            <div className="flex flex-col gap-1">
              <Label className="text-xs" htmlFor={`motif-refus-${etape.id}`}>
                Motif du refus (facultatif)
              </Label>
              <select
                id={`motif-refus-${etape.id}`}
                className={erreurMotif ? 'form-select is-invalid' : 'form-select'}
                value={motifRefus}
                onChange={(e) => { setMotifRefus(e.target.value); setErreurMotif('') }}
              >
                <option value="">— Sans motif —</option>
                {(motifs ?? []).map((m) => (
                  <option key={m.id ?? m.nom} value={m.nom}>{m.nom}</option>
                ))}
              </select>
              {erreurMotif && (
                <p className="text-xs text-danger" role="alert" data-testid="erreur-motif-refus">
                  {erreurMotif}
                </p>
              )}
            </div>
          )}
          {/* CAD11 — la proposition « perdu, motif junk » en UN clic, jamais
              imposée : la case reste décochée tant que la commerciale ne
              décide pas. Sans motif junk paramétré, rien n'est proposé. */}
          {reponseChoisie?.junk && motifsJunk.length > 0 && (
            <div className="flex flex-col gap-1" data-testid="proposition-perdu-junk">
              <label className="flex items-center gap-1.5 text-xs">
                <input
                  type="checkbox" checked={perduJunk}
                  onChange={(e) => { setPerduJunk(e.target.checked); setErreurMotif('') }}
                />
                <span>Marquer le lead perdu — motif junk (pas un vrai prospect)</span>
              </label>
              {perduJunk && (
                <select
                  aria-label="Motif junk"
                  className={erreurMotif ? 'form-select is-invalid' : 'form-select'}
                  value={motifJunkEffectif}
                  onChange={(e) => { setMotifJunk(e.target.value); setErreurMotif('') }}
                >
                  {motifsJunk.map((m) => (
                    <option key={m.id ?? m.nom} value={m.nom}>{m.nom}</option>
                  ))}
                </select>
              )}
              {erreurMotif && (
                <p className="text-xs text-danger" role="alert" data-testid="erreur-perdu-junk">
                  {erreurMotif}
                </p>
              )}
            </div>
          )}
          <Textarea
            rows={2} placeholder="Note (optionnelle)"
            value={note} onChange={(e) => setNote(e.target.value)}
          />
          <div className="flex justify-end gap-1.5">
            <Button size="sm" variant="outline" disabled={busy} onClick={fermer}>
              Annuler
            </Button>
            <Button
              size="sm"
              disabled={busy || !reponseChoisie
                || (reponseChoisie.rappel && (!rappelLe || rappelPasse))
                || confirmationOuvertureRequise}
              onClick={confirmerFait}
            >
              Confirmer
            </Button>
          </div>
        </div>
      )}
      {!readOnly && panel === 'reporter' && (
        <div className="mt-2 flex flex-col gap-1.5">
          {/* CAD26 — DEUX gestes : décaler (quelques jours, la suite glisse)
              ou mettre en veille (la cadence se tait et reprend au même
              barreau ; au-delà d'un mois, réveil daté). Au-delà de 7 jours,
              la veille est proposée d'elle-même — le choix explicite prime. */}
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Geste de report">
            <Button
              type="button" size="sm"
              variant={modeReport === 'decaler' ? 'default' : 'outline'}
              aria-pressed={modeReport === 'decaler'}
              onClick={() => setReportMode('decaler')}
            >
              Décaler ce rappel
            </Button>
            <Button
              type="button" size="sm"
              variant={modeReport === 'veille' ? 'default' : 'outline'}
              aria-pressed={modeReport === 'veille'}
              onClick={() => setReportMode('veille')}
            >
              Mettre en veille jusqu’au…
            </Button>
          </div>
          <p className="text-xs text-muted-foreground" data-testid="suite-report">
            {modeReport === 'veille'
              ? 'La cadence se tait jusqu’à cette date et reprend à cette même touche — aucune relance ne part d’ici là. Au-delà d’un mois, elle bascule en réveil daté.'
              : 'Cette touche et la suite du plan glissent de l’écart choisi.'}
          </p>
          {veilleProposee && !reportMode && (
            <p className="text-xs text-warning" data-testid="veille-proposee">
              Report de plus de {VEILLE_PROPOSEE_APRES_JOURS} jours : la mise en veille est proposée.
            </p>
          )}
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex flex-col gap-1">
              <Label className="text-xs" htmlFor={`report-date-${etape.id}`}>Reporter au</Label>
              <Input id={`report-date-${etape.id}`} type="date" className="w-40"
                     min={aujourdhui} aria-invalid={reportPasse}
                     value={reportDate} onChange={(e) => setReportDate(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs" htmlFor={`report-heure-${etape.id}`}>Heure</Label>
              <Input id={`report-heure-${etape.id}`} type="time" className="w-28"
                     value={reportHeure} onChange={(e) => setReportHeure(e.target.value)} />
            </div>
          </div>
          {reportPasse && (
            <p className="text-xs text-danger" role="alert" data-testid="erreur-report-date">
              « Reporter au » : cette date est déjà passée — choisissez aujourd’hui ou une date à venir.
            </p>
          )}
          <div className="flex justify-end gap-1.5">
            <Button size="sm" variant="outline" disabled={busy} onClick={fermer}>
              Annuler
            </Button>
            <Button size="sm" disabled={busy || !reportDate || reportPasse} onClick={confirmerReporter}>
              Confirmer
            </Button>
          </div>
        </div>
      )}
      {/* VISCAD6 — PARTAGÉE par le CTA du panneau de coaching ci-dessus ET
          l'issue « Visite acceptée » de `confirmerFait` — une seule modale,
          un seul appel serveur. `etape.lead` porte l'id du lead (contrat
          `relance_etape_v2.json`) : jamais un second prop à faire remonter
          par les trois appelants de `RelanceEtapeRow`. */}
      <PlanifierVisiteModal
        leadId={etape.lead}
        open={planifierOuvert}
        onOpenChange={setPlanifierOuvert}
        onPlanifie={() => onVisiteChanged?.()}
      />
    </li>
  )
}
