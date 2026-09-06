import { useEffect, useState } from 'react'
import {
  CalendarClock, Check, SkipForward, Phone, MessageCircle, Clock3,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import crmApi from '../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Badge, Button,
  Spinner, Textarea, Input, Label,
} from '../../ui'
import ScoreBadge from '../../features/crm/ScoreBadge'
import { PRIORITE_LABELS } from '../../features/crm/stages'
import { OUTCOME_LABELS } from '../../components/ChatterTimeline'
import ToucheMessageDialog from './ToucheMessageDialog'

/* ============================================================================
   RELANCE FOUNDATION / MRY14 — panneau « Relances du jour » v2 (plan de
   relance structuré multi-touches, crm.RelanceEtape). Liste les étapes dues
   AUJOURD'HUI + EN RETARD (scope=all, mêmes règles de portée que le reste du
   CRM — voir crm.selectors.relance_etapes_dues). Trois cadences nommées
   (contact/après devis/réveil, MRY4/MRY5) : message prêt + WhatsApp (MRY13,
   aperçu-puis-clic, décision D5 — AUCUN envoi automatique), appel (`tel:`),
   Fait (avec issue/note/rappel — MRY10, déclenche les règles d'arrêt de
   MRY9), Sauter, Reporter (décale cette touche ET les suivantes, MRY10).
   ========================================================================== */

// Libellés FR des canaux SUGGÉRÉS de la cadence — jamais un envoi, juste
// l'indication du prochain geste attendu (appel/WhatsApp/e-mail/visite).
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

function RelanceEtapeRow({ etape, onFait, onSauter, onReporter, onOuvrirMessage, busyId, navigate }) {
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
    const heure = reportHeure || '09:00'
    const d = new Date(`${reportDate}T${heure}:00`)
    if (Number.isNaN(d.getTime())) return
    onReporter(etape.id, d.toISOString())
  }

  const heure = heureDue(etape)

  return (
    <li className="rounded-md border border-border p-2" data-testid="relance-etape-row">
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
        {etape.lead_priorite && etape.lead_priorite !== 'normale' && (
          <Badge tone={etape.lead_priorite === 'haute' ? 'warning' : 'neutral'}>
            {PRIORITE_LABELS[etape.lead_priorite] ?? etape.lead_priorite}
          </Badge>
        )}
      </div>
      {panel === '' && (
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
      {panel === 'sauter' && (
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
      {panel === 'fait' && (
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
      {panel === 'reporter' && (
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

export default function RelancesDuJourWidget() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [etapes, setEtapes] = useState([])
  const [busyId, setBusyId] = useState(null)
  const [messageEtape, setMessageEtape] = useState(null)

  const charger = () => {
    let active = true
    crmApi.getRelanceEtapesDues({ scope: 'all' })
      .then((r) => { if (active) setEtapes(r.data?.results ?? []) })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }

  useEffect(() => {
    queueMicrotask(() => setLoading(true))
    return charger()
  }, [])

  const retirer = (id) => setEtapes((prev) => prev.filter((e) => e.id !== id))

  const traiter = async (id, action, payload) => {
    setBusyId(id)
    try {
      if (action === 'fait') await crmApi.marquerRelanceEtapeFait(id, payload)
      else if (action === 'sauter') await crmApi.marquerRelanceEtapeSautee(id, payload)
      else if (action === 'reporter') await crmApi.reporterRelanceEtape(id, { due_at: payload })
      retirer(id)
      // MRY9/MRY11 — une action peut faire naître une NOUVELLE touche due
      // (report, clôture de cadence…) : refetch silencieux, jamais bloquant.
      setTimeout(() => { charger() }, 1000)
    } catch {
      // best-effort UI — l'échec reste silencieux, la ligne redevient cliquable
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Card data-testid="relances-du-jour-widget">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4" /> Relances du jour
        </CardTitle>
        <CardDescription>
          Étapes de plan de relance dues aujourd&apos;hui ou en retard.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Spinner />
        ) : error ? (
          <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
        ) : etapes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucune touche due — les cadences démarrent seules à l&apos;arrivée d&apos;un lead.
          </p>
        ) : (
          <ul className="space-y-2">
            {etapes.map((etape) => (
              <RelanceEtapeRow
                key={etape.id} etape={etape} busyId={busyId} navigate={navigate}
                onFait={(id, payload) => traiter(id, 'fait', payload)}
                onSauter={(id, note) => traiter(id, 'sauter', note)}
                onReporter={(id, dueAt) => traiter(id, 'reporter', dueAt)}
                onOuvrirMessage={setMessageEtape}
              />
            ))}
          </ul>
        )}
      </CardContent>
      <ToucheMessageDialog
        etape={messageEtape}
        open={!!messageEtape}
        onOpenChange={(o) => { if (!o) setMessageEtape(null) }}
        onSent={(id) => { retirer(id); setTimeout(() => { charger() }, 1000) }}
      />
    </Card>
  )
}
