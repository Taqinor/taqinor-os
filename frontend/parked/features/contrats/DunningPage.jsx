import { useEffect, useState } from 'react'
import { BellRing, Plus } from 'lucide-react'
import api from '../../api/axios'
import contratsApi from '../../api/contratsApi'
import {
  Badge, Button, Tabs, TabsList, TabsTrigger, TabsContent, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Checkbox,
} from '../../ui'
import { formatDate } from '../../lib/format'
import SimpleTable from './SimpleTable'

/* ============================================================================
   PACT139 — Relance d'impayé : séquences et étapes.
   ----------------------------------------------------------------------------
   NTSUB8 (`apps/contrats`) livrait déjà ``SequenceDunning``/``EtapeDunning``/
   ``EtapeDunningLog`` SANS AUCUN écran (endpoints `/contrats/sequences-dunning/`
   + `/contrats/etapes-dunning/` — les étapes voyagent déjà imbriquées dans la
   séquence côté lecture). Le journal d'exécution PAR CONTRAT n'a besoin
   d'AUCUN nouvel endpoint : ``services.executer_dunning_contrat`` journalise
   chaque relance envoyée dans le chatter existant (``ContratActivity``,
   CONTRAT15, ``field='dunning'``) — déjà exposé par
   `contratsApi.getHistorique(id)`. Sans séquence rattachée à un contrat, le
   comportement ZCTR2 (suspension à délai unique) reste STRICTEMENT
   inchangé : cet écran n'ajoute qu'un rattachement optionnel.
   ========================================================================== */

const listData = (res) => (Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const CANAUX = [
  { value: 'email', label: 'E-mail' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'notification_interne', label: 'Notification interne' },
]

export default function DunningPage() {
  const [sequences, setSequences] = useState([])
  const [contrats, setContrats] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [dialog, setDialog] = useState(null) // 'sequence' | { type: 'etape', sequenceId }

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([
      api.get('/contrats/sequences-dunning/').then((r) => setSequences(listData(r))),
      contratsApi.getContrats({ page_size: 200 }).then((r) => setContrats(listData(r))),
    ])
      .catch(() => setError('Impossible de charger les séquences de relance.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const onCreated = (message) => {
    setDialog(null)
    toast.success(message)
    load()
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <BellRing className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">Relance d’impayé</h1>
      </div>

      <Tabs defaultValue="sequences">
        <TabsList className="flex-wrap">
          <TabsTrigger value="sequences">Séquences ({sequences.length})</TabsTrigger>
          <TabsTrigger value="journal">Journal par contrat</TabsTrigger>
        </TabsList>

        <TabsContent value="sequences">
          <div className="mb-2 flex justify-end">
            <Button size="sm" variant="outline" onClick={() => setDialog('sequence')}><Plus /> Nouvelle séquence</Button>
          </div>
          {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
          {!loading && !error && sequences.length === 0 && (
            <p className="py-4 text-sm text-muted-foreground">Aucune séquence de relance.</p>
          )}
          <div className="flex flex-col gap-4">
            {sequences.map((seq) => (
              <div key={seq.id} className="rounded-lg border border-border p-3">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{seq.nom}</span>
                    <Badge tone={seq.actif ? 'success' : 'neutral'}>{seq.actif ? 'Active' : 'Inactive'}</Badge>
                  </div>
                  <Button
                    size="sm" variant="outline"
                    onClick={() => setDialog({ type: 'etape', sequenceId: seq.id })}
                  >
                    <Plus /> Ajouter une étape
                  </Button>
                </div>
                <SimpleTable
                  emptyText="Aucune étape — une séquence sans étape n’a aucun effet."
                  rows={seq.etapes || []}
                  columns={[
                    { header: 'Jour', cell: (e) => `J+${e.jour_offset}` },
                    { header: 'Canal', cell: (e) => e.canal_display || e.canal },
                    { header: 'Gabarit', cell: (e) => e.template_ref || '—' },
                    { header: 'Ordre', cell: (e) => e.ordre },
                    {
                      header: 'Suspension',
                      cell: (e) => (e.declenche_suspension
                        ? <Badge tone="danger">Déclenche la suspension</Badge>
                        : '—'),
                    },
                  ]}
                />
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="journal">
          <JournalContratTab contrats={contrats} />
        </TabsContent>
      </Tabs>

      {dialog === 'sequence' && (
        <SequenceDialog
          onClose={() => setDialog(null)}
          onDone={() => onCreated('Séquence de relance créée.')}
        />
      )}
      {dialog && dialog.type === 'etape' && (
        <EtapeDialog
          sequenceId={dialog.sequenceId}
          onClose={() => setDialog(null)}
          onDone={() => onCreated('Étape ajoutée à la séquence.')}
        />
      )}
    </div>
  )
}

// ── Journal d'exécution par contrat (chatter CONTRAT15, field='dunning') ────
function JournalContratTab({ contrats }) {
  const [contratId, setContratId] = useState('')
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- vide la liste quand aucun contrat n'est choisi
    if (!contratId) { setEntries([]); return }
    setLoading(true)
    setError(null)
    contratsApi.getHistorique(contratId)
      .then((r) => setEntries(listData(r).filter((e) => e.field === 'dunning')))
      .catch(() => setError('Impossible de charger le journal de relance.'))
      .finally(() => setLoading(false))
  }, [contratId])

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5 sm:max-w-xs">
        <Label htmlFor="dun-contrat">Contrat</Label>
        <select
          id="dun-contrat"
          value={contratId}
          onChange={(e) => setContratId(e.target.value)}
          className="h-9 rounded-md border border-border bg-card px-3 text-sm"
        >
          <option value="">Choisir un contrat…</option>
          {contrats.map((c) => (
            <option key={c.id} value={c.id}>{c.reference || c.objet || `Contrat #${c.id}`}</option>
          ))}
        </select>
      </div>

      {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      {!loading && !error && contratId && (
        <SimpleTable
          emptyText="Aucune relance de dunning exécutée pour ce contrat."
          rows={entries}
          columns={[
            { header: 'Date', cell: (e) => (e.date_creation ? formatDate(e.date_creation) : '—') },
            { header: 'Étape', cell: (e) => e.new_value || '—' },
            { header: 'Message', cell: (e) => e.message || '—' },
          ]}
        />
      )}
    </div>
  )
}

function SequenceDialog({ onClose, onDone }) {
  const [nom, setNom] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!nom.trim()) { setErr('Le nom est requis.'); return }
    setSaving(true)
    setErr(null)
    try {
      await api.post('/contrats/sequences-dunning/', { nom: nom.trim() })
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouvelle séquence de relance</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sq-nom" required>Nom</Label>
            <Input id="sq-nom" value={nom} onChange={(e) => setNom(e.target.value)} placeholder="ex. Relance standard" />
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer la séquence'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function EtapeDialog({ sequenceId, onClose, onDone }) {
  const [jourOffset, setJourOffset] = useState('')
  const [canal, setCanal] = useState('notification_interne')
  const [templateRef, setTemplateRef] = useState('')
  const [ordre, setOrdre] = useState('0')
  const [declencheSuspension, setDeclencheSuspension] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (jourOffset === '') { setErr('Le nombre de jours est requis.'); return }
    setSaving(true)
    setErr(null)
    const data = {
      sequence: sequenceId, jour_offset: Number(jourOffset), canal,
      ordre: Number(ordre) || 0, declenche_suspension: declencheSuspension,
    }
    if (templateRef.trim()) data.template_ref = templateRef.trim()
    try {
      await api.post('/contrats/etapes-dunning/', data)
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouvelle étape de relance</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="et-jour" required>Jours après l’échéance</Label>
              <Input id="et-jour" type="number" step="1" value={jourOffset} onChange={(e) => setJourOffset(e.target.value)} placeholder="ex. 7" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="et-ordre">Ordre</Label>
              <Input id="et-ordre" type="number" step="1" value={ordre} onChange={(e) => setOrdre(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="et-canal">Canal</Label>
            <select
              id="et-canal"
              value={canal}
              onChange={(e) => setCanal(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              {CANAUX.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="et-gabarit">Référence de gabarit</Label>
            <Input id="et-gabarit" value={templateRef} onChange={(e) => setTemplateRef(e.target.value)} placeholder="Optionnel" />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={declencheSuspension}
              onCheckedChange={(v) => setDeclencheSuspension(Boolean(v))}
            />
            Déclenche la suspension du contrat (ZCTR2)
          </label>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : "Créer l'étape"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
