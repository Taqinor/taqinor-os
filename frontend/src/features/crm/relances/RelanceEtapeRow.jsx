import { useState } from 'react'
import {
  Check, SkipForward, Phone, MessageCircle, Clock3,
} from 'lucide-react'
import {
  Badge, Button, Textarea, Input, Label,
} from '../../../ui'
import ScoreBadge from '../ScoreBadge'
import { PRIORITE_LABELS } from '../stages'
import { OUTCOME_LABELS } from '../../../components/ChatterTimeline'

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

// Choix d'issue proposés au mini-formulaire « Fait » (miroir de
// LeadActivity.OUTCOMES, même liste que CallLogPopover — hors la clé vide).
const OUTCOME_CHOICES = Object.entries(OUTCOME_LABELS).filter(([k]) => k !== '')

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
  if (etape.statut === 'sautee') return <Badge tone="neutral">Sautée</Badge>
  if (etape.overdue) return <Badge tone="danger">En retard</Badge>
  return <Badge tone="outline">À faire</Badge>
}

export default function RelanceEtapeRow({
  etape, onFait, onSauter, onReporter, onOuvrirMessage, busyId, navigate,
  compact = false, readOnly = false, showStatut = false,
}) {
  // '' | 'sauter' | 'fait' | 'reporter' — un seul panneau ouvert à la fois.
  const [panel, setPanel] = useState('')
  const [note, setNote] = useState('')
  const [outcome, setOutcome] = useState('')
  const [rappelLe, setRappelLe] = useState('')
  const [rappelHeure, setRappelHeure] = useState('')
  const [reportDate, setReportDate] = useState('')
  const [reportHeure, setReportHeure] = useState('')
  const busy = busyId === etape.id

  const fermer = () => {
    setPanel('')
    setNote(''); setOutcome(''); setRappelLe(''); setRappelHeure('')
    setReportDate(''); setReportHeure('')
  }

  const confirmerFait = () => {
    const payload = {}
    if (note.trim()) payload.note = note.trim()
    if (outcome) payload.outcome = outcome
    if (rappelLe) {
      payload.rappel_le = rappelLe
      if (rappelHeure) payload.rappel_heure = rappelHeure
    }
    onFait(etape.id, payload)
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
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Résultat de la touche">
            {OUTCOME_CHOICES.map(([key, label]) => (
              <Button
                key={key} type="button" size="sm"
                variant={outcome === key ? 'default' : 'outline'}
                onClick={() => setOutcome((cur) => (cur === key ? '' : key))}
              >
                {label}
              </Button>
            ))}
          </div>
          {(outcome === 'joint' || outcome === 'interesse') && (
            <p className="text-xs text-muted-foreground" data-testid="hint-joint">
              Client joint : la cadence s’arrête. Donnez une date de rappel
              ci-dessous — sinon une étape « envoyer le devis ou fixer un
              rappel » sera posée automatiquement pour demain.
            </p>
          )}
          <Textarea
            rows={2} placeholder="Note (optionnelle)"
            value={note} onChange={(e) => setNote(e.target.value)}
          />
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
          <div className="flex justify-end gap-1.5">
            <Button size="sm" variant="outline" disabled={busy} onClick={fermer}>
              Annuler
            </Button>
            <Button size="sm" disabled={busy} onClick={confirmerFait}>
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
    </li>
  )
}
