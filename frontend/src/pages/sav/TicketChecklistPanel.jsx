import { useEffect, useState } from 'react'
import { ClipboardCheck } from 'lucide-react'
import savApi from '../../api/savApi'
import {
  Button, Checkbox, Input, Spinner, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

// WR11 / FG82 — checklist de visite de maintenance d'un ticket SAV.
// GET liste les items ; POST initialise depuis un template (idempotent côté
// serveur) ; PATCH coche/décoche un item ou met à jour sa note. Toute la
// règle vit côté serveur — ce panneau ne fait que refléter l'état.

export default function TicketChecklistPanel({ ticketId }) {
  const [items, setItems] = useState(null)
  const [templates, setTemplates] = useState([])
  const [templateId, setTemplateId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const load = () => {
    savApi.getTicketChecklist(ticketId)
      .then((r) => setItems(r.data ?? []))
      .catch(() => setItems([]))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItems(null)
    savApi.getTicketChecklist(ticketId)
      .then((r) => setItems(r.data ?? []))
      .catch(() => setItems([]))
    savApi.getChecklistTemplates()
      .then((r) => setTemplates(r.data?.results ?? r.data ?? []))
      .catch(() => {})
  }, [ticketId])

  const initialiser = async () => {
    if (!templateId) return
    setBusy(true)
    setError(null)
    try {
      const r = await savApi.initTicketChecklist(ticketId, templateId)
      setItems(r.data ?? [])
      toast.success('Checklist initialisée')
    } catch (err) {
      setError(err?.response?.data?.detail
        ?? "Initialisation de la checklist impossible.")
    } finally {
      setBusy(false)
    }
  }

  const toggleItem = async (item) => {
    setError(null)
    try {
      const r = await savApi.patchTicketChecklistItem(
        ticketId, { cle: item.cle, coche: !item.coche })
      setItems((list) => (list ?? []).map(
        (it) => (it.cle === item.cle ? r.data : it)))
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Mise à jour impossible.')
    }
  }

  const saveNote = async (item, note) => {
    if ((item.note ?? '') === note) return
    setError(null)
    try {
      const r = await savApi.patchTicketChecklistItem(
        ticketId, { cle: item.cle, note })
      setItems((list) => (list ?? []).map(
        (it) => (it.cle === item.cle ? r.data : it)))
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Note non enregistrée.')
      load()
    }
  }

  if (items == null) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner className="size-4" /> Chargement de la checklist…
      </p>
    )
  }

  const cochees = items.filter((i) => i.coche).length

  return (
    <div className="flex flex-col gap-3" data-testid="ticket-checklist">
      {items.length === 0 ? (
        <>
          <p className="text-sm text-muted-foreground">
            Aucune checklist sur ce ticket. Initialisez-la depuis un modèle
            (Paramètres → Checklists).
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={templateId || '__none'}
                    onValueChange={(v) => setTemplateId(v === '__none' ? '' : v)}>
              <SelectTrigger className="w-auto min-w-[220px]">
                <SelectValue placeholder="— Modèle de checklist —" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Modèle de checklist —</SelectItem>
                {templates.map((t) => (
                  <SelectItem key={t.id} value={String(t.id)}>{t.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button type="button" size="sm" variant="outline"
                    loading={busy} disabled={!templateId} onClick={initialiser}>
              <ClipboardCheck /> Initialiser
            </Button>
          </div>
        </>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            {cochees}/{items.length} point{items.length > 1 ? 's' : ''} coché{cochees > 1 ? 's' : ''}.
          </p>
          <ul className="flex flex-col divide-y divide-border rounded-lg border border-border">
            {items.map((it) => (
              <li key={it.cle} className="flex flex-col gap-1.5 p-2.5 text-sm">
                <label className="flex items-center gap-2">
                  <Checkbox checked={!!it.coche}
                            onCheckedChange={() => toggleItem(it)} />
                  <span className={it.coche ? 'line-through text-muted-foreground' : ''}>
                    {it.libelle}
                  </span>
                  {it.coche && it.coche_par_nom && (
                    <span className="text-xs text-muted-foreground">
                      — par {it.coche_par_nom}
                    </span>
                  )}
                </label>
                <Input defaultValue={it.note ?? ''} placeholder="Note…"
                       aria-label={`Note — ${it.libelle}`}
                       onBlur={(e) => saveNote(it, e.target.value)} />
              </li>
            ))}
          </ul>
        </>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">{error}</p>
      )}
    </div>
  )
}
