import { useEffect, useState } from 'react'
import { CalendarClock, Check, SkipForward } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import crmApi from '../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Badge, Button,
  Spinner, Textarea,
} from '../../ui'
import { formatDate } from '../../lib/format'

/* ============================================================================
   RELANCE FOUNDATION — panneau « Relances du jour » (plan de relance
   structuré multi-touches, crm.RelanceEtape). Liste les étapes dues
   AUJOURD'HUI + EN RETARD (scope=all, mêmes règles de portée que le reste du
   CRM — voir crm.selectors.relance_etapes_dues), avec un bouton Fait
   one-click et un bouton Sauter (note optionnelle). AUCUN envoi automatique
   (WhatsApp/e-mail) : ce sont des rappels VISUELS pour le commercial — les
   deux actions marquent seulement l'étape et journalisent le chatter du lead
   côté serveur (crm.services.marquer_etape_relance).
   ========================================================================== */

// Libellés FR des canaux SUGGÉRÉS de la cadence — jamais un envoi, juste
// l'indication du prochain geste attendu (appel/WhatsApp/e-mail/visite).
const CANAL_LABELS = {
  appel: 'Appel',
  whatsapp: 'WhatsApp',
  email: 'E-mail',
  visite: 'Visite',
}

function RelanceEtapeRow({ etape, onFait, onSauter, busyId, navigate }) {
  const [sauterOpen, setSauterOpen] = useState(false)
  const [note, setNote] = useState('')
  const busy = busyId === etape.id

  return (
    <li className="rounded-md border border-border p-2" data-testid="relance-etape-row">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          className="truncate text-left text-sm font-medium hover:underline"
          onClick={() => navigate(`/crm/leads?lead=${etape.lead}`)}
        >
          {etape.lead_nom || 'Lead'}
          <span className="block text-xs font-normal text-muted-foreground">
            {CANAL_LABELS[etape.canal] || etape.canal}
            {etape.lead_owner_nom ? ` · ${etape.lead_owner_nom}` : ''}
          </span>
        </button>
        <div className="flex shrink-0 items-center gap-1.5">
          {etape.overdue ? (
            <Badge tone="danger">En retard · {formatDate(etape.due_date)}</Badge>
          ) : (
            <Badge tone="neutral">{formatDate(etape.due_date)}</Badge>
          )}
        </div>
      </div>
      {!sauterOpen ? (
        <div className="mt-2 flex justify-end gap-1.5">
          <Button
            size="sm" variant="outline" disabled={busy}
            onClick={() => setSauterOpen(true)}
          >
            <SkipForward className="size-3.5" /> Sauter
          </Button>
          <Button size="sm" disabled={busy} onClick={() => onFait(etape.id)}>
            <Check className="size-3.5" /> Fait
          </Button>
        </div>
      ) : (
        <div className="mt-2 flex flex-col gap-1.5">
          <Textarea
            rows={2} placeholder="Note (optionnelle) — pourquoi sauter cette relance ?"
            value={note} onChange={(e) => setNote(e.target.value)}
          />
          <div className="flex justify-end gap-1.5">
            <Button
              size="sm" variant="outline" disabled={busy}
              onClick={() => { setSauterOpen(false); setNote('') }}
            >
              Annuler
            </Button>
            <Button
              size="sm" disabled={busy}
              onClick={() => onSauter(etape.id, note)}
            >
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

  useEffect(() => {
    let active = true
    queueMicrotask(() => { if (active) setLoading(true) })
    crmApi.getRelanceEtapesDues({ scope: 'all' })
      .then((r) => { if (active) setEtapes(r.data?.results ?? []) })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const traiter = async (id, action, note) => {
    setBusyId(id)
    try {
      if (action === 'fait') await crmApi.marquerRelanceEtapeFait(id, note)
      else await crmApi.marquerRelanceEtapeSautee(id, note)
      setEtapes((prev) => prev.filter((e) => e.id !== id))
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
          <p className="text-sm text-muted-foreground">Aucune relance due. 🎉</p>
        ) : (
          <ul className="space-y-2">
            {etapes.map((etape) => (
              <RelanceEtapeRow
                key={etape.id} etape={etape} busyId={busyId} navigate={navigate}
                onFait={(id) => traiter(id, 'fait')}
                onSauter={(id, note) => traiter(id, 'sauter', note)}
              />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
