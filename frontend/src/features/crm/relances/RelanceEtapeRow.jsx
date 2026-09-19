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
import PanneauProposerVisite from './PanneauProposerVisite'
import PlanifierVisiteModal from './PlanifierVisiteModal'

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
const QUESTIONS = {
  contact: {
    question: 'Résultat de la touche ?',
    reponses: [
      { outcome: 'joint', label: 'Client joint',
        suite: 'La prise de contact s’arrête. Message répondu → prochaine étape : l’appeler (prochain créneau d’appel). Appel fait → « préparer et envoyer le devis » demain. Le suivi de proposition démarre à l’envoi du devis.' },
      { outcome: 'non_joint', label: 'Pas de réponse',
        suite: 'La cadence continue ; si c’était la dernière touche, le dossier part au Froid avec deux réveils.' },
      { outcome: 'rappel', label: 'À rappeler le…', rappel: true,
        suite: 'La prochaine touche est déplacée à la date choisie.' },
      { outcome: 'refuse', label: 'Refus',
        suite: 'Les relances s’arrêtent ; une étape « décider la suite » (perdu ou relance ultérieure) est posée.' },
    ],
  },
  apres_devis: {
    question: 'Réponse du client sur la proposition ?',
    aide: 'Le client accepte ? Marquez le devis ACCEPTÉ (Ventes → Devis) : le dossier passe en Signé et toutes les relances s’arrêtent.',
    reponses: [
      { outcome: 'interesse', label: 'Intéressé',
        suite: 'Le suivi de proposition continue (une étape de suite est posée si c’était la dernière touche).' },
      // VISCAD6 (fondateur 15/09/2026) — « la visite devient une étape du
      // suivi commercial » : issue SERVEUR existante (LeadActivity.OUTCOMES,
      // jamais une nouvelle valeur inventée ici), choisie quand le client dit
      // oui à la visite pendant le suivi de proposition — ouvre la modale de
      // planification juste après confirmation (confirmerFait ci-dessous).
      { outcome: 'visite_acceptee', label: 'Visite acceptée',
        suite: 'La cadence se met en veille jusqu’au retour de la visite — planifiez-la juste après.' },
      { outcome: 'non_joint', label: 'Sans réponse',
        suite: 'La cadence continue ; si c’était la dernière touche, le dossier part au Froid avec deux réveils.' },
      { outcome: 'rappel', label: 'À rappeler le…', rappel: true,
        suite: 'La prochaine touche est déplacée à la date choisie.' },
      { outcome: 'refuse', label: 'Refuse la proposition',
        suite: 'Le suivi s’arrête ; une étape « décider la suite » est posée — marquer perdu reste votre décision.' },
    ],
  },
  generique: {
    question: 'Où en est ce dossier ?',
    reponses: [
      { outcome: '', label: 'Fait — passer à la suite',
        suite: 'Devis envoyé → le suivi de proposition démarre (pour l’étape « préparer et envoyer le devis », un devis parti hors ERP compte aussi) ; sinon la prochaine étape est posée pour demain.' },
      { outcome: 'rappel', label: 'À rappeler le…', rappel: true,
        suite: 'L’étape est déplacée à la date choisie.' },
      { outcome: 'refuse', label: 'Client refuse',
        suite: 'Une étape « décider la suite » est posée — marquer perdu reste votre décision.' },
    ],
  },
}
QUESTIONS.reveil = {
  question: 'Résultat du réveil ?',
  reponses: [
    { outcome: 'joint', label: 'Client joint',
      suite: 'Le dossier SORT du Froid ; prochaine étape : l’appeler (message répondu) ou préparer le devis (appel fait). Les réveils restants sont annulés.' },
    { outcome: 'non_joint', label: 'Pas de réponse',
      suite: 'Le réveil suivant reste programmé ; le dossier reste au Froid.' },
    { outcome: 'rappel', label: 'À rappeler le…', rappel: true,
      suite: 'Le prochain réveil est déplacé à la date choisie.' },
    { outcome: 'refuse', label: 'Refus',
      suite: 'Les réveils s’arrêtent ; le dossier reste au Froid.' },
  ],
}

// CKP4 (fondateur 2026-09-10) — un canal APPEL clôturé « Fait » exige TOUJOURS
// une issue : Joint/Pas de réponse restent les réponses existantes ci-dessus
// (`joint`/`non_joint`, JAMAIS réinventées) ; Répondeur/Occupé s'y AJOUTENT
// (jamais un remplacement — rappel/refus restent disponibles) pour les
// appels seulement, l'écran Meryem étant d'abord un écran d'appels. La suite
// (cadence continue / dossier au Froid après la dernière touche) est celle
// des règles d'arrêt MRY9 déjà en vigueur pour « Pas de réponse ».
// Réconciliation de fold (CKP2↔CKP4) : le serveur ne connaît QUE les issues
// de `LeadActivity.OUTCOMES` — Répondeur/Occupé s'envoient donc comme
// `non_joint` (même règle de suite), la précision partant dans la `note`.
// Aucune nouvelle valeur d'énumération côté serveur = aucun risque de
// migration ; l'information reste tracée mot pour mot dans le chatter.
const APPEL_REPONSES_SUPPLEMENTAIRES = [
  { outcome: 'non_joint', note: 'Répondeur', label: 'Répondeur',
    suite: 'La cadence continue ; si c’était la dernière touche, le dossier part au Froid avec deux réveils.' },
  { outcome: 'non_joint', note: 'Occupé', label: 'Occupé',
    suite: 'La cadence continue ; si c’était la dernière touche, le dossier part au Froid avec deux réveils.' },
]

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
  // CKP4 — erreur DE CHAMP renvoyée par le serveur (400
  // `{erreurs: {outcome: "…"}}` pour un canal APPEL clôturé sans issue) :
  // s'affiche SOUS le contrôle concerné, jamais un toast générique qui
  // masquerait le champ fautif (règle « le champ fautif, message exact »).
  const [erreurOutcome, setErreurOutcome] = useState('')
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
    setSansOuverture(false)
  }

  const questionsTouche = QUESTIONS[etape.cadence] ?? QUESTIONS.contact
  // CKP4 — canal APPEL : Répondeur/Occupé s'ajoutent aux réponses de la
  // cadence (jamais un remplacement, voir commentaire plus haut).
  const reponsesDisponibles = etape.canal === 'appel'
    ? [...questionsTouche.reponses, ...APPEL_REPONSES_SUPPLEMENTAIRES]
    : questionsTouche.reponses
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

  const confirmerFait = () => {
    if (!reponseChoisie) return
    if (reponseChoisie.rappel && !rappelLe) return
    if (confirmationOuvertureRequise) return
    const payload = {}
    if (note.trim()) payload.note = note.trim()
    else if (reponseChoisie.note) payload.note = reponseChoisie.note
    if (reponseChoisie.outcome) payload.outcome = reponseChoisie.outcome
    if (reponseChoisie.rappel && rappelLe) {
      payload.rappel_le = rappelLe
      if (rappelHeure) payload.rappel_heure = rappelHeure
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
    }).catch((err) => {
      const champ = err?.response?.status === 400
        ? err?.response?.data?.erreurs?.outcome : null
      if (champ) setErreurOutcome(champ)
    })
  }

  const confirmerReporter = () => {
    if (!reportDate) return
    // F1 — forme SÛRE ancrée Casablanca CÔTÉ SERVEUR (`_parse_rappel`) :
    // jamais un `new Date(...).toISOString()`, qui interprète
    // `${date}T${heure}:00` dans le fuseau du NAVIGATEUR et décale l'heure
    // réellement reportée dès que l'agent n'est pas sur ce fuseau.
    onReporter(etape.id, { rappel_le: reportDate, rappel_heure: reportHeure || '09:00' })
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
                onClick={() => { setReponseIdx((cur) => (cur === idx ? null : idx)); setErreurOutcome('') }}
              >
                {r.label}
              </Button>
            ))}
          </div>
          {reponseChoisie && (
            <p className="text-xs text-muted-foreground" data-testid="suite-reponse">
              {reponseChoisie.suite}
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
                       value={rappelLe} onChange={(e) => setRappelLe(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs" htmlFor={`rappel-heure-${etape.id}`}>Heure</Label>
                <Input id={`rappel-heure-${etape.id}`} type="time" className="w-28"
                       value={rappelHeure} onChange={(e) => setRappelHeure(e.target.value)} />
              </div>
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
                || (reponseChoisie.rappel && !rappelLe)
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
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex flex-col gap-1">
              <Label className="text-xs" htmlFor={`report-date-${etape.id}`}>Reporter au</Label>
              <Input id={`report-date-${etape.id}`} type="date" className="w-40"
                     value={reportDate} onChange={(e) => setReportDate(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs" htmlFor={`report-heure-${etape.id}`}>Heure</Label>
              <Input id={`report-heure-${etape.id}`} type="time" className="w-28"
                     value={reportHeure} onChange={(e) => setReportHeure(e.target.value)} />
            </div>
          </div>
          <div className="flex justify-end gap-1.5">
            <Button size="sm" variant="outline" disabled={busy} onClick={fermer}>
              Annuler
            </Button>
            <Button size="sm" disabled={busy || !reportDate} onClick={confirmerReporter}>
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
