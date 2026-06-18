import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  Download, Ticket as TicketIcon, AlertTriangle, RotateCcw, Save, FileText,
  Plus, Trash2, StickyNote, Sparkles, Pencil, Wrench, History,
} from 'lucide-react'
import { fetchTickets, updateTicket } from '../../features/sav/store/ticketsSlice'
import savApi from '../../api/savApi'
import api from '../../api/axios'
import { downloadBlob } from '../../utils/downloadBlob'
import importApi, { downloadXlsx } from '../../api/importApi'
import installationsApi from '../../api/installationsApi'
import { INTERVENTION_TYPES } from '../../features/installations/statuses'
import {
  EMPTY_TICKET_FILTERS,
  TICKET_STATUSES,
  TICKET_STATUS_LABELS,
  TICKET_TYPES,
  TICKET_PRIORITES,
  TICKET_PRIORITE_LABELS,
  SOUS_GARANTIE_OPTIONS,
  SOUS_GARANTIE_LABELS,
  filterTickets,
  sortTickets,
  statusLabel,
} from '../../features/sav/ticketStatuses'
import {
  TooltipProvider,
  Button,
  Badge,
  StatusPill,
  Card,
  EmptyState,
  Skeleton,
  Input,
  Textarea,
  Checkbox,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  Form, FormSection, FormField, FormActions, useDirtyGuard,
  DataTable,
  toast,
} from '../../ui'

function timeAgo(iso) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return "à l'instant"
  if (mins < 60) return `il y a ${mins} min`
  const h = Math.round(mins / 60)
  if (h < 24) return `il y a ${h} h`
  return new Date(iso).toLocaleDateString('fr-FR')
}
const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

// Statut de ticket → ton StatusPill (cycle de vie ticketStatuses.js : couche
// indépendante du funnel lead et des statuts de document). La couleur n'est
// jamais le seul signal — le libellé reste explicite.
const TICKET_STATUS_TONES = {
  nouveau: 'neutral',
  planifie: 'info',
  en_cours: 'warning',
  resolu: 'success',
  cloture: 'success',
}
function StatutPill({ statut }) {
  return <StatusPill tone={TICKET_STATUS_TONES[statut] ?? 'neutral'} label={statusLabel(statut)} />
}

const GARANTIE_TONES = { oui: 'success', non: 'danger', a_determiner: 'neutral' }
function GarantieIndicator({ value }) {
  return (
    <Badge tone={GARANTIE_TONES[value] ?? 'neutral'}>
      Sous garantie : {SOUS_GARANTIE_LABELS[value] ?? value}
    </Badge>
  )
}

const PRIORITE_TONES = { basse: 'neutral', normale: 'info', haute: 'warning', urgente: 'danger' }
function PrioriteBadge({ value }) {
  return <Badge tone={PRIORITE_TONES[value] ?? 'neutral'}>{TICKET_PRIORITE_LABELS[value] ?? value}</Badge>
}

function TicketDetail({ ticket, onClose, onSaved }) {
  const dispatch = useDispatch()
  const id = ticket.id
  const [current, setCurrent] = useState(ticket)
  const F = (k, d = '') => current?.[k] ?? d

  const initialFields = useMemo(() => ({
    statut: current.statut ?? 'nouveau',
    type: current.type ?? 'correctif',
    priorite: current.priorite ?? 'normale',
    description: current.description ?? '',
    sous_garantie: current.sous_garantie ?? 'a_determiner',
    equipement: current.equipement ?? '',
    technicien_responsable: current.technicien_responsable ?? '',
    date_resolution: current.date_resolution ?? '',
    cout: current.cout ?? '',
  }), [current])

  const [fields, setFields] = useState(initialFields)
  const set = (k, v) => setFields((f) => ({ ...f, [k]: v }))
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)

  const dirty = useMemo(
    () => Object.keys(initialFields).some((k) => String(fields[k] ?? '') !== String(initialFields[k] ?? '')),
    [fields, initialFields],
  )
  useDirtyGuard(dirty)

  const [equipements, setEquipements] = useState([])
  const [users, setUsers] = useState([])
  const [interventions, setInterventions] = useState([])
  const [interv, setInterv] = useState({ type_intervention: 'depannage', date_prevue: '', compte_rendu: '' })
  const [intervBusy, setIntervBusy] = useState(false)

  const [historique, setHistorique] = useState([])
  const [noteBody, setNoteBody] = useState('')

  // N46 — pièces consommées (le stock peut être décrémenté).
  const [pieces, setPieces] = useState([])
  const [produits, setProduits] = useState([])
  const [pieceForm, setPieceForm] = useState(
    { produit: '', quantite: '1', decrement: false })
  const [pieceBusy, setPieceBusy] = useState(false)
  const [annulerOpen, setAnnulerOpen] = useState(false)
  const [motif, setMotif] = useState('')

  const loadPieces = () => {
    savApi.getTicketPieces(id).then((r) => setPieces(r.data)).catch(() => {})
  }

  const reloadAll = async () => {
    try {
      const r = await savApi.getTicket(id)
      setCurrent(r.data)
    } catch { /* silencieux */ }
  }
  const loadHistorique = () => {
    savApi.getTicketHistorique(id).then((r) => setHistorique(r.data)).catch(() => {})
  }
  const loadInterventions = () => {
    installationsApi.getInterventions({ ticket: id })
      .then((r) => setInterventions(r.data?.results ?? r.data ?? [])).catch(() => {})
  }

  useEffect(() => {
    loadHistorique()
    loadInterventions()
    loadPieces()
    api.get('/stock/produits/')
      .then((r) => setProduits(r.data?.results ?? r.data ?? [])).catch(() => {})
    // Équipements du chantier concerné (pour lier l'équipement précis).
    if (current.installation) {
      savApi.getEquipements({ installation: current.installation })
        .then((r) => setEquipements(r.data?.results ?? r.data ?? [])).catch(() => {})
    }
    // Liste des techniciens — best effort (réservé admin) ; sinon dropdown vide.
    api.get('/users/').then((r) => setUsers(r.data?.results ?? r.data ?? [])).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const nullable = (v) => (v === '' || v === undefined ? null : v)
      const data = {
        statut: fields.statut,
        type: fields.type,
        priorite: fields.priorite,
        description: nullable(fields.description),
        sous_garantie: fields.sous_garantie,
        equipement: fields.equipement === '' ? null : fields.equipement,
        technicien_responsable: fields.technicien_responsable === '' ? null : fields.technicien_responsable,
        date_resolution: nullable(fields.date_resolution),
        cout: nullable(fields.cout),
      }
      const updated = await dispatch(updateTicket({ id, data })).unwrap()
      setCurrent(updated)
      loadHistorique()
      toast.success('Ticket mis à jour')
      onSaved?.()
    } catch (err) {
      setSaveError(typeof err === 'object' ? JSON.stringify(err) : String(err))
    } finally {
      setSaving(false)
    }
  }

  const postNote = async () => {
    const body = noteBody.trim()
    if (!body) return
    try {
      const r = await savApi.noterTicket(id, body)
      setHistorique((h) => [r.data, ...h])
      setNoteBody('')
    } catch { /* silencieux */ }
  }

  const addIntervention = async () => {
    if (!interv.type_intervention) return
    setIntervBusy(true)
    try {
      const nullable = (v) => (v === '' || v === undefined ? null : v)
      await installationsApi.createIntervention({
        installation: current.installation,
        ticket: id,
        type_intervention: interv.type_intervention,
        date_prevue: nullable(interv.date_prevue),
        compte_rendu: nullable(interv.compte_rendu),
      })
      setInterv({ type_intervention: 'depannage', date_prevue: '', compte_rendu: '' })
      loadInterventions()
      loadHistorique()
    } catch { /* silencieux */ } finally { setIntervBusy(false) }
  }

  const addPiece = async () => {
    if (!pieceForm.produit) return
    setPieceBusy(true)
    try {
      await savApi.addTicketPiece(id, {
        produit: pieceForm.produit,
        quantite: pieceForm.quantite || '1',
        decrement: pieceForm.decrement,
      })
      setPieceForm({ produit: '', quantite: '1', decrement: false })
      loadPieces()
      loadHistorique()
    } catch { /* silencieux */ } finally { setPieceBusy(false) }
  }
  const removePiece = async (pieceId) => {
    try {
      await savApi.removeTicketPiece(id, pieceId)
      loadPieces()
    } catch { /* silencieux */ }
  }

  const annuler = async () => {
    try {
      await savApi.annulerTicket(id, motif)
      setAnnulerOpen(false)
      setMotif('')
      await reloadAll()
      loadHistorique()
      onSaved?.()
    } catch { /* silencieux */ }
  }
  const reactiver = async () => {
    try {
      await savApi.reactiverTicket(id)
      await reloadAll()
      loadHistorique()
      onSaved?.()
    } catch { /* silencieux */ }
  }
  const telechargerRapport = async () => {
    try {
      const r = await savApi.rapportPdf(id)
      downloadBlob(r.data, `rapport-intervention-${current.reference || id}.pdf`)
    } catch {
      toast.error('Rapport indisponible.')
    }
  }

  const linkedEquip = equipements.find((e) => String(e.id) === String(fields.equipement))

  return (
    <Sheet open onOpenChange={(o) => { if (!o) onClose() }}>
      <SheetContent side="right" className="w-[min(46rem,calc(100%-1.5rem))] sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle className="flex flex-wrap items-center gap-2">
            Ticket SAV — {current.reference ?? ''}
            <StatutPill statut={current.statut} />
            {current.annule && <Badge tone="danger">Annulé</Badge>}
          </SheetTitle>
          <SheetDescription>
            Suivi, équipement, interventions, pièces et historique du ticket.
          </SheetDescription>
        </SheetHeader>

        {current.annule && (
          <div role="alert"
               className="flex flex-wrap items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <span>
              <strong>Ticket annulé.</strong>
              {current.motif_annulation ? ` Motif : ${current.motif_annulation}` : ''}
            </span>
            <Button size="sm" variant="outline" onClick={reactiver}>Réactiver</Button>
          </div>
        )}

        <Form onSubmit={(e) => { e.preventDefault(); save() }} className="gap-6">
          {/* ── Infos ── */}
          <FormSection title="Ticket">
            <FormField label="Client">
              <Input value={current.client_nom ?? '—'} readOnly />
            </FormField>
            <FormField label="Chantier">
              <Input value={current.installation_reference ?? '—'} readOnly />
            </FormField>
            <FormField label="Ouvert le">
              <Input value={formatDateFR(current.date_ouverture)} readOnly />
            </FormField>
            <FormField label="Statut">
              <Select value={fields.statut} onValueChange={(v) => set('statut', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TICKET_STATUSES.map((k) => (
                    <SelectItem key={k} value={k}>{TICKET_STATUS_LABELS[k]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Type">
              <Select value={fields.type} onValueChange={(v) => set('type', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TICKET_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Priorité">
              <Select value={fields.priorite} onValueChange={(v) => set('priorite', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TICKET_PRIORITES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Description" fullWidth>
              <Textarea rows={2} value={fields.description ?? ''}
                        onChange={(e) => set('description', e.target.value)} />
            </FormField>
          </FormSection>

          {/* ── Équipement & garantie ── */}
          <FormSection title="Équipement concerné"
                       description="La garantie effective est calculée automatiquement à partir de l'équipement lié.">
            <FormField label="Équipement (du chantier)" fullWidth>
              <Select value={fields.equipement ? String(fields.equipement) : '__none'}
                      onValueChange={(v) => set('equipement', v === '__none' ? '' : v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Aucun (garantie manuelle) —</SelectItem>
                  {equipements.map((e) => (
                    <SelectItem key={e.id} value={String(e.id)}>
                      {(e.produit_nom ?? 'Produit')} — {e.numero_serie ?? 'sans n° série'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Sous garantie (si aucun équipement)" fullWidth>
              <Select value={fields.sous_garantie} onValueChange={(v) => set('sous_garantie', v)}
                      disabled={!!fields.equipement}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SOUS_GARANTIE_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </FormField>
            <div className="sm:col-span-2 flex flex-wrap items-center gap-2">
              <GarantieIndicator value={current.sous_garantie_effectif} />
              {linkedEquip && (
                <span className="text-xs text-muted-foreground">
                  {linkedEquip.date_fin_garantie
                    ? `Fin de garantie de l'équipement : ${formatDateFR(linkedEquip.date_fin_garantie)} — calculée automatiquement.`
                    : "Garantie de l'équipement non renseignée."}
                </span>
              )}
            </div>
          </FormSection>

          {/* ── Suivi ── */}
          <FormSection title="Suivi">
            <FormField label="Technicien responsable">
              <Select value={fields.technicien_responsable ? String(fields.technicien_responsable) : '__none'}
                      onValueChange={(v) => set('technicien_responsable', v === '__none' ? '' : v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Non assigné —</SelectItem>
                  {users.map((u) => <SelectItem key={u.id} value={String(u.id)}>{u.username}</SelectItem>)}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Date de résolution">
              <Input type="date" value={fields.date_resolution ?? ''}
                     onChange={(e) => set('date_resolution', e.target.value)} />
            </FormField>
            <FormField label="Coût (interne)">
              <Input type="number" step="any" value={fields.cout ?? ''}
                     onChange={(e) => set('cout', e.target.value)} />
            </FormField>
            {saveError && (
              <div role="alert" className="sm:col-span-2 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
                <span className="break-all">{saveError}</span>
              </div>
            )}
          </FormSection>
        </Form>

        {/* ── Interventions ── */}
        <section className="flex flex-col gap-3">
          <h3 className="flex items-center gap-2 font-display text-base font-semibold text-foreground">
            <Wrench className="size-4 text-muted-foreground" /> Interventions
          </h3>
          {interventions.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune intervention rattachée.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {interventions.map((iv) => (
                <li key={iv.id} className="rounded-lg border border-border bg-card p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">{iv.type_intervention_display ?? iv.type_intervention}</span>
                    <span className="text-xs text-muted-foreground">
                      Prévue {formatDateFR(iv.date_prevue)} · Réalisée {formatDateFR(iv.date_realisee)}
                    </span>
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    {iv.technicien_nom ?? '—'}{iv.compte_rendu ? ` — ${iv.compte_rendu}` : ''}
                  </p>
                </li>
              ))}
            </ul>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField label="Type">
              <Select value={interv.type_intervention}
                      onValueChange={(v) => setInterv((s) => ({ ...s, type_intervention: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {INTERVENTION_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Date prévue">
              <Input type="date" value={interv.date_prevue}
                     onChange={(e) => setInterv((s) => ({ ...s, date_prevue: e.target.value }))} />
            </FormField>
            <FormField label="Compte rendu" fullWidth>
              <Input value={interv.compte_rendu}
                     onChange={(e) => setInterv((s) => ({ ...s, compte_rendu: e.target.value }))} />
            </FormField>
          </div>
          <div>
            <Button type="button" variant="outline" size="sm"
                    loading={intervBusy} disabled={!interv.type_intervention} onClick={addIntervention}>
              <Plus /> Ajouter une intervention
            </Button>
          </div>
        </section>

        {/* ── Pièces consommées (N46) ── */}
        <section className="flex flex-col gap-3">
          <h3 className="flex items-center gap-2 font-display text-base font-semibold text-foreground">
            <Wrench className="size-4 text-muted-foreground" /> Pièces consommées
          </h3>
          {pieces.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune pièce enregistrée.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-border rounded-lg border border-border">
              {pieces.map((p) => (
                <li key={p.id} className="flex items-center gap-2 p-2.5 text-sm">
                  <span className="flex-1">
                    {p.produit_nom}{p.produit_marque ? ` — ${p.produit_marque}` : ''} × {p.quantite}
                    {p.stock_decremente && <Badge tone="info" className="ml-2">stock −</Badge>}
                  </span>
                  <Button type="button" variant="ghost" size="sm" onClick={() => removePiece(p.id)}>
                    <Trash2 /> Retirer
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <div className="grid items-end gap-3 sm:grid-cols-[2fr_auto_auto]">
            <FormField label="Produit">
              <Select value={pieceForm.produit ? String(pieceForm.produit) : '__none'}
                      onValueChange={(v) => setPieceForm((s) => ({ ...s, produit: v === '__none' ? '' : v }))}>
                <SelectTrigger><SelectValue placeholder="— Produit —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Produit —</SelectItem>
                  {produits.map((pr) => (
                    <SelectItem key={pr.id} value={String(pr.id)}>
                      {pr.nom}{pr.sku ? ` (${pr.sku})` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Qté" className="w-24">
              <Input type="number" min="0" step="any" value={pieceForm.quantite}
                     onChange={(e) => setPieceForm((s) => ({ ...s, quantite: e.target.value }))} />
            </FormField>
            <label className="flex h-[var(--control-h)] items-center gap-2 text-sm">
              <Checkbox checked={pieceForm.decrement}
                        onCheckedChange={(v) => setPieceForm((s) => ({ ...s, decrement: !!v }))} />
              Décrémenter le stock
            </label>
          </div>
          <div>
            <Button type="button" variant="outline" size="sm"
                    loading={pieceBusy} disabled={!pieceForm.produit} onClick={addPiece}>
              <Plus /> Ajouter la pièce
            </Button>
          </div>
        </section>

        {/* ── Historique (chatter) ── */}
        <section className="flex flex-col gap-3">
          <h3 className="flex items-center gap-2 font-display text-base font-semibold text-foreground">
            <History className="size-4 text-muted-foreground" /> Historique
          </h3>
          <div className="flex gap-2">
            <Input placeholder="Écrire une note…" value={noteBody}
                   onChange={(e) => setNoteBody(e.target.value)}
                   onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); postNote() } }} />
            <Button type="button" variant="outline" onClick={postNote}>Noter</Button>
          </div>
          <div className="flex flex-col gap-2">
            {historique.length === 0 && <p className="text-sm text-muted-foreground">Aucune activité pour le moment.</p>}
            {historique.map((a) => (
              <div key={a.id} className="rounded-lg border border-border bg-card p-2.5 text-sm">
                {a.kind === 'note' && (
                  <span className="flex items-start gap-1.5">
                    <StickyNote className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                    <span><strong>Note :</strong> {a.body}</span>
                  </span>
                )}
                {a.kind === 'creation' && (
                  <span className="flex items-start gap-1.5">
                    <Sparkles className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" /> {a.body}
                  </span>
                )}
                {a.kind === 'modification' && (
                  <span className="flex items-start gap-1.5">
                    <Pencil className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                    <span><strong>{a.field_label} :</strong> {a.old_value} → <strong>{a.new_value}</strong></span>
                  </span>
                )}
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  — par {a.user_nom ?? '?'} · {timeAgo(a.created_at)}
                </span>
              </div>
            ))}
          </div>
        </section>

        <FormActions sticky={false}>
          {!current.annule && (
            <Button type="button" variant="destructive" className="mr-auto" onClick={() => setAnnulerOpen(true)}>
              <Trash2 /> Annuler le ticket
            </Button>
          )}
          <Button type="button" variant="outline" onClick={telechargerRapport}>
            <FileText /> Rapport d'intervention (PDF)
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
          <Button type="button" loading={saving} onClick={save}><Save /> Mettre à jour</Button>
        </FormActions>

        <AlertDialog open={annulerOpen} onOpenChange={setAnnulerOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Annuler ce ticket ?</AlertDialogTitle>
              <AlertDialogDescription>
                Le ticket sera marqué annulé (avec motif). Vous pourrez le réactiver ensuite.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="grid gap-1.5">
              <label htmlFor="motif-annulation" className="text-sm font-medium">Motif d'annulation</label>
              <Textarea id="motif-annulation" rows={2} value={motif}
                        onChange={(e) => setMotif(e.target.value)}
                        placeholder="Motif (optionnel)…" />
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel>Revenir</AlertDialogCancel>
              <AlertDialogAction onClick={annuler}>Annuler le ticket</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </SheetContent>
    </Sheet>
  )
}

export default function TicketsPage() {
  const dispatch = useDispatch()
  const { items, loading, error } = useSelector((s) => s.tickets)
  const [filters, setFilters] = useState(EMPTY_TICKET_FILTERS)
  const [selected, setSelected] = useState(null)

  const reload = () => dispatch(fetchTickets())
  useEffect(() => { reload() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const setF = (k, v) => setFilters((f) => ({ ...f, [k]: v }))

  const technicienOptions = useMemo(
    () => [...new Set(items.map((it) => it.technicien_nom).filter(Boolean))].sort(),
    [items])

  const rows = useMemo(
    () => sortTickets(filterTickets(items, filters), 'statut', 'asc'),
    [items, filters])

  const hasFilters = filters.q || filters.statut || filters.type || filters.priorite
    || filters.technicien || filters.sous_garantie || filters.ouvert !== 'ouverts'

  const columns = useMemo(() => [
    {
      id: 'reference',
      header: 'Référence',
      width: 150,
      cell: (_v, row) => (
        <span className="flex items-center gap-1.5 font-medium">
          {row.reference}
          {row.annule && <Badge tone="danger">Annulé</Badge>}
        </span>
      ),
      accessor: (r) => r.reference,
    },
    { id: 'client_nom', header: 'Client', width: 160, accessor: (r) => r.client_nom ?? '—' },
    { id: 'installation_reference', header: 'Chantier', width: 140, accessor: (r) => r.installation_reference ?? '—' },
    {
      id: 'statut',
      header: 'Statut',
      width: 130,
      searchable: false,
      cell: (_v, row) => <StatutPill statut={row.statut} />,
      exportValue: (row) => statusLabel(row.statut),
    },
    { id: 'type', header: 'Type', width: 110, accessor: (r) => r.type_display ?? r.type },
    {
      id: 'priorite',
      header: 'Priorité',
      width: 110,
      searchable: false,
      cell: (_v, row) => <PrioriteBadge value={row.priorite} />,
      exportValue: (row) => TICKET_PRIORITE_LABELS[row.priorite] ?? row.priorite,
    },
    {
      id: 'garantie',
      header: 'Garantie',
      width: 120,
      searchable: false,
      accessor: (r) => SOUS_GARANTIE_LABELS[r.sous_garantie_effectif] ?? '—',
    },
    { id: 'technicien_nom', header: 'Technicien', width: 140, accessor: (r) => r.technicien_nom ?? '—' },
  ], [])

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root flex flex-col gap-5 p-1">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight">Tickets SAV</h1>
            <p className="text-sm text-muted-foreground">
              {rows.length} ticket{rows.length > 1 ? 's' : ''}
            </p>
          </div>
          <Button variant="outline" size="sm"
                  onClick={() => importApi.exportList('tickets', rows.map((r) => r.id))
                    .then((r) => downloadXlsx(r.data, 'tickets.xlsx')).catch(() => {})}>
            <Download /> Exporter Excel
          </Button>
        </header>

        {/* ── Filtres ── */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-[220px] flex-1">
            <Input placeholder="Rechercher (référence, client, chantier, description)…"
                   value={filters.q} onChange={(e) => setF('q', e.target.value)} />
          </div>
          <Select value={filters.statut || '__all'}
                  onValueChange={(v) => setF('statut', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[130px]"><SelectValue placeholder="Tous statuts" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous statuts</SelectItem>
              {TICKET_STATUSES.map((k) => <SelectItem key={k} value={k}>{TICKET_STATUS_LABELS[k]}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.type || '__all'}
                  onValueChange={(v) => setF('type', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[120px]"><SelectValue placeholder="Tous types" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous types</SelectItem>
              {TICKET_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.priorite || '__all'}
                  onValueChange={(v) => setF('priorite', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[130px]"><SelectValue placeholder="Toutes priorités" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Toutes priorités</SelectItem>
              {TICKET_PRIORITES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.technicien || '__all'}
                  onValueChange={(v) => setF('technicien', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[140px]"><SelectValue placeholder="Tous techniciens" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous techniciens</SelectItem>
              {technicienOptions.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.sous_garantie || '__all'}
                  onValueChange={(v) => setF('sous_garantie', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[150px]"><SelectValue placeholder="Garantie (tous)" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Garantie (tous)</SelectItem>
              {SOUS_GARANTIE_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>Sous garantie : {o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={filters.ouvert} onValueChange={(v) => setF('ouvert', v)}>
            <SelectTrigger className="w-auto min-w-[170px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ouverts">Ouverts seulement</SelectItem>
              <SelectItem value="tous">Tous (incl. clôturés/annulés)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {loading ? (
          <Card className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </Card>
        ) : error ? (
          <EmptyState
            icon={AlertTriangle}
            title="Chargement impossible"
            description="Les tickets n'ont pas pu être chargés. Réessayez."
            action={<Button size="sm" variant="outline" onClick={reload}><RotateCcw /> Réessayer</Button>}
          />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={TicketIcon}
            title="Aucun ticket"
            description={hasFilters
              ? 'Aucun ticket ne correspond à vos filtres.'
              : "Aucun ticket. Ouvrez-en un depuis la fiche d'un chantier."}
            action={hasFilters
              ? <Button size="sm" variant="outline" onClick={() => setFilters(EMPTY_TICKET_FILTERS)}><RotateCcw /> Réinitialiser</Button>
              : undefined}
          />
        ) : (
          <DataTable
            data={rows}
            columns={columns}
            getRowId={(row) => row.id}
            searchable={false}
            onRowClick={(row) => setSelected(row)}
            exportName="tickets"
            emptyTitle="Aucun ticket"
            emptyDescription="Aucun ticket ne correspond à votre recherche."
          />
        )}

        {selected && (
          <TicketDetail ticket={selected} onClose={() => setSelected(null)} onSaved={reload} />
        )}
      </div>
    </TooltipProvider>
  )
}
