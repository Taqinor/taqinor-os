// T16 — contrats de maintenance (visites préventives). Liste + vue « à venir »
// (visites dues) + génération à la demande des tickets SAV préventifs (sans
// planificateur, cohérent T7). Création (client + périodicité + début + prix +
// installation + durée), édition/désactivation inline, revenu récurrent par
// ligne, badges « À renouveler » / « Visite proche », comptes de visites
// générées et choix de la date du rapport PDF.
import { useEffect, useMemo, useState } from 'react'
import {
  Download, Cog, Plus, CalendarClock, ClipboardList, AlertTriangle, Pencil,
  Check, X,
} from 'lucide-react'
import savApi from '../../api/savApi'
import { formatMAD } from '../../lib/format'
import crmApi from '../../api/crmApi'
import installationsApi from '../../api/installationsApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import {
  TooltipProvider,
  Button,
  Badge,
  StatusPill,
  Card,
  EmptyState,
  Skeleton,
  Input,
  Checkbox,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Segmented,
  Form, FormField,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
  DataTable,
  toast,
} from '../../ui'

const PERIODES = [
  { value: 'mensuel', label: 'Mensuel' },
  { value: 'trimestriel', label: 'Trimestriel' },
  { value: 'semestriel', label: 'Semestriel' },
  { value: 'annuel', label: 'Annuel' },
]
const PERIODE_LABELS = Object.fromEntries(PERIODES.map((p) => [p.value, p.label]))
// L323 — nombre de visites par an, par périodicité (pour le revenu récurrent).
const PERIODE_PAR_AN = { mensuel: 12, trimestriel: 4, semestriel: 2, annuel: 1 }

const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}
const fmtDH = (n) => `${formatMAD(n, { decimals: 0, withSymbol: false })} DH`

// L323 — revenu récurrent équivalent mensuel d'un contrat (même maths que
// l'insight recurring_revenue : prix × visites/an ÷ 12).
function revenuMensuel(contrat) {
  const prix = Number(contrat?.prix)
  if (!Number.isFinite(prix) || prix <= 0) return null
  const parAn = PERIODE_PAR_AN[contrat.periodicite] ?? 1
  return (prix * parAn) / 12
}

// L324 — « Visite proche » : prochaine visite dans ~90 j mais pas encore due
// (calculé à la lecture, comme T7).
function visiteProche(contrat, jours = 90) {
  if (!contrat?.actif || contrat.due || !contrat.prochaine_visite) return false
  const d = new Date(`${String(contrat.prochaine_visite).slice(0, 10)}T00:00:00`)
  if (Number.isNaN(d.getTime())) return false
  const diff = Math.round((d - new Date()) / 86400000)
  return diff >= 0 && diff <= jours
}

// J144 — statut d'un contrat → { tone, label } pour StatusPill (la couleur n'est
// jamais le seul signal : le libellé reste explicite). Inactif > visite due > à jour.
function contratStatut(row) {
  if (!row?.actif) return { tone: 'neutral', label: 'Inactif' }
  if (row.due) return { tone: 'danger', label: 'Visite due' }
  return { tone: 'success', label: 'À jour' }
}

// Composant exporté (testable) : le statut d'un contrat rendu en StatusPill.
export function ContratStatutPill({ contrat }) {
  const { tone, label } = contratStatut(contrat)
  return <StatusPill tone={tone} label={label} />
}

export function Component() {
  const [rows, setRows] = useState([])
  const [clients, setClients] = useState([])
  const [installations, setInstallations] = useState([])
  const [preventifs, setPreventifs] = useState([]) // L327 — tickets préventifs
  const [vue, setVue] = useState('tous') // 'tous' | 'dus' | 'renouveler'
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false) // L329 — vide vs erreur
  const [form, setForm] = useState({
    client: '', periodicite: 'annuel', date_debut: '', date_renouvellement: '',
    prix: '', installation: '', duree_mois: '',
  })
  const [formError, setFormError] = useState(null) // L326
  const [edit, setEdit] = useState(null) // L320 — { id, periodicite, prix, actif }
  // L675 — choix de la date du rapport PDF : { row, date }.
  const [pdfDialog, setPdfDialog] = useState(null)

  const dueOnly = vue === 'dus'

  const load = () => {
    setLoading(true)
    setLoadError(false)
    return savApi.getContrats(dueOnly ? { due: 1 } : {})
      .then((r) => setRows(r.data.results ?? r.data))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { load() }, [dueOnly])
  useEffect(() => {
    crmApi.getClients().then((r) => setClients(r.data.results ?? r.data)).catch(() => {})
    installationsApi.getInstallations()
      .then((r) => setInstallations(r.data.results ?? r.data ?? [])).catch(() => {})
    // L327 — tickets préventifs pour compter les visites générées par contrat.
    savApi.getTickets({ type: 'preventif', ouvert: 'tous' })
      .then((r) => setPreventifs(r.data.results ?? r.data ?? [])).catch(() => {})
  }, [])

  // L327 — compte de tickets préventifs par client (et installation si fixée).
  const preventifCount = (contrat) => (preventifs ?? []).filter((t) => {
    if (String(t.client) !== String(contrat.client)) return false
    if (contrat.installation
        && String(t.installation ?? '') !== String(contrat.installation)) return false
    return true
  }).length

  // L322 — vue « À renouveler » via renouvellement_du déjà sérialisé.
  const visibleRows = useMemo(() => {
    if (vue === 'renouveler') return rows.filter((r) => r.renouvellement_du)
    return rows
  }, [rows, vue])

  const create = async () => {
    // L326 — validation FR claire au lieu d'un no-op silencieux.
    if (!form.client || !form.date_debut) {
      setFormError('Client et date de début requis.')
      return
    }
    setFormError(null)
    try {
      const payload = {
        client: form.client,
        periodicite: form.periodicite,
        date_debut: form.date_debut,
      }
      if (form.date_renouvellement) payload.date_renouvellement = form.date_renouvellement
      if (form.prix !== '') payload.prix = form.prix
      if (form.installation) payload.installation = form.installation
      if (form.duree_mois !== '') payload.duree_mois = form.duree_mois
      await savApi.saveContrat(null, payload)
      setForm({
        client: '', periodicite: 'annuel', date_debut: '', date_renouvellement: '',
        prix: '', installation: '', duree_mois: '',
      })
      toast.success('Contrat ajouté')
      load()
    } catch (e) {
      setFormError(e?.response?.data?.detail ?? 'Création impossible.')
    }
  }

  // L320 — édition/désactivation inline (saveContrat(id, …) + actif).
  const startEdit = (row) => setEdit({
    id: row.id, periodicite: row.periodicite, prix: row.prix ?? '', actif: row.actif,
  })
  const saveEdit = async () => {
    try {
      await savApi.saveContrat(edit.id, {
        periodicite: edit.periodicite,
        prix: edit.prix === '' ? null : edit.prix,
        actif: edit.actif,
      })
      setEdit(null)
      toast.success('Contrat mis à jour')
      load()
    } catch { toast.error('Mise à jour impossible.') }
  }
  const toggleActif = async (row) => {
    try {
      await savApi.saveContrat(row.id, { actif: !row.actif })
      load()
    } catch { toast.error('Bascule impossible.') }
  }

  // L675 — ouvre le choix de date avant téléchargement (défaut derniere_visite).
  const openRapport = (row) => setPdfDialog({
    row,
    date: (row.derniere_visite || row.prochaine_visite || '').slice(0, 10),
  })
  const rapport = async () => {
    if (!pdfDialog) return
    const { row, date } = pdfDialog
    try {
      const res = await savApi.maintenanceRapportPdf(row.id, date || undefined)
      openPdfBlob(res.data, `maintenance-contrat-${row.id}.pdf`)
      setPdfDialog(null)
    } catch { toast.error('Rapport indisponible.') }
  }
  const generer = async () => {
    try {
      const { data } = await savApi.genererVisitesDues()
      // L328 — confirmer le compte généré et recharger sans race.
      toast.success(`${data.tickets_generes} ticket(s) de maintenance généré(s).`)
      await load()
      savApi.getTickets({ type: 'preventif', ouvert: 'tous' })
        .then((r) => setPreventifs(r.data.results ?? r.data ?? [])).catch(() => {})
    } catch { toast.error('Génération impossible.') }
  }

  const columns = [
    { id: 'client_nom', header: 'Client', width: 180, accessor: (r) => r.client_nom },
    {
      id: 'periodicite', header: 'Périodicité', width: 130,
      // L325 — libellé FR (Annuel/Mensuel/…) via la map PERIODES.
      cell: (_v, row) => (edit?.id === row.id ? (
        <Select value={edit.periodicite}
                onValueChange={(v) => setEdit((e) => ({ ...e, periodicite: v }))}>
          <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
          <SelectContent>
            {PERIODES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
          </SelectContent>
        </Select>
      ) : (PERIODE_LABELS[row.periodicite] ?? row.periodicite)),
      exportValue: (row) => PERIODE_LABELS[row.periodicite] ?? row.periodicite,
    },
    {
      id: 'prix', header: 'Prix', width: 110,
      cell: (_v, row) => (edit?.id === row.id ? (
        <Input type="number" step="any" className="h-8" value={edit.prix}
               onChange={(e) => setEdit((s) => ({ ...s, prix: e.target.value }))} />
      ) : (row.prix != null ? fmtDH(row.prix) : '—')),
      exportValue: (row) => (row.prix != null ? row.prix : ''),
    },
    {
      // L323 — revenu récurrent équivalent mensuel.
      id: 'recurrent', header: 'Récurrent', width: 130, searchable: false,
      cell: (_v, row) => {
        const rev = revenuMensuel(row)
        return rev ? `≈ ${fmtDH(rev)}/mois` : '—'
      },
      exportValue: (row) => { const r = revenuMensuel(row); return r ? Math.round(r) : '' },
    },
    { id: 'date_debut', header: 'Début', width: 120, accessor: (r) => formatDateFR(r.date_debut) },
    {
      id: 'prochaine_visite', header: 'Prochaine visite', width: 160,
      cell: (_v, row) => (
        <span className="flex items-center gap-1.5">
          {formatDateFR(row.prochaine_visite)}
          {/* L324 — badge « Visite proche » distinct de déjà dû. */}
          {visiteProche(row) && <Badge tone="warning">Visite proche</Badge>}
        </span>
      ),
      exportValue: (row) => formatDateFR(row.prochaine_visite),
    },
    {
      // L327 — nombre de visites (tickets préventifs) générées.
      id: 'visites', header: 'Visites', width: 110, searchable: false,
      cell: (_v, row) => {
        const n = preventifCount(row)
        return n ? `${n} visite(s)` : '—'
      },
      exportValue: (row) => preventifCount(row),
    },
    {
      id: 'date_renouvellement', header: 'Renouvellement', width: 160,
      cell: (_v, row) => (
        <span className="flex items-center gap-1.5">
          {formatDateFR(row.date_renouvellement)}
          {row.renouvellement_du && <Badge tone="warning">à renouveler</Badge>}
        </span>
      ),
      exportValue: (row) => formatDateFR(row.date_renouvellement),
    },
    {
      // L330 — date de création + notes (sérialisés, désormais affichés).
      id: 'infos', header: 'Créé le / Notes', width: 180, searchable: false,
      cell: (_v, row) => (
        <span className="flex flex-col text-xs text-muted-foreground">
          <span>Créé le {formatDateFR(row.date_creation)}</span>
          {row.notes && <span className="truncate" title={row.notes}>{row.notes}</span>}
        </span>
      ),
      exportValue: (row) => `${formatDateFR(row.date_creation)} ${row.notes ?? ''}`.trim(),
    },
    {
      id: 'statut', header: 'Statut', width: 130, searchable: false,
      cell: (_v, row) => <ContratStatutPill contrat={row} />,
      exportValue: (row) => contratStatut(row).label,
    },
    {
      id: 'actions', header: '', width: 270, sortable: false, searchable: false, hideable: false,
      cell: (_v, row) => (edit?.id === row.id ? (
        <span className="flex items-center gap-2 text-sm">
          <label className="flex items-center gap-1.5">
            <Checkbox checked={edit.actif}
                      onCheckedChange={(v) => setEdit((e) => ({ ...e, actif: !!v }))} />
            Actif
          </label>
          <Button variant="outline" size="sm" onClick={saveEdit}><Check /> Enregistrer</Button>
          <Button variant="ghost" size="sm" onClick={() => setEdit(null)}><X /></Button>
        </span>
      ) : (
        <span className="flex items-center gap-1.5">
          <Button variant="outline" size="sm" onClick={() => openRapport(row)}>
            <Download /> Rapport PDF
          </Button>
          <Button variant="ghost" size="sm" onClick={() => startEdit(row)} title="Éditer">
            <Pencil />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => toggleActif(row)}
                  title={row.actif ? 'Désactiver' : 'Activer'}>
            {row.actif ? 'Désactiver' : 'Activer'}
          </Button>
        </span>
      )),
    },
  ]

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root mx-auto flex max-w-6xl flex-col gap-5 p-1">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight">Contrats de maintenance</h1>
            <p className="text-sm text-muted-foreground">
              Visites préventives — {visibleRows.length} contrat{visibleRows.length > 1 ? 's' : ''}
            </p>
          </div>
          {/* MB5 — segmenté (3 options) + bouton : sur mobile ils passent sur
              deux lignes plutôt que déborder horizontalement. */}
          <div className="flex flex-wrap items-center gap-2">
            <Segmented
              size="sm"
              className="flex-wrap"
              value={vue}
              onChange={setVue}
              options={[
                { value: 'tous', label: 'Tous' },
                { value: 'dus', label: 'À venir (dus)' },
                { value: 'renouveler', label: 'À renouveler' },
              ]}
            />
            <Button variant="outline" size="sm" onClick={generer}>
              <Cog /> Générer les visites dues
            </Button>
          </div>
        </header>

        {/* ── Création ── */}
        <Card className="p-4">
          <Form onSubmit={(e) => { e.preventDefault(); create() }}
                className="grid items-end gap-3 sm:grid-cols-[2fr_1fr_1fr_1fr] lg:grid-cols-[2fr_1fr_1fr_1fr_1fr_1fr_auto]">
            <FormField label="Client">
              <Select value={form.client ? String(form.client) : '__none'}
                      onValueChange={(v) => setForm((f) => ({ ...f, client: v === '__none' ? '' : v }))}>
                <SelectTrigger><SelectValue placeholder="— Client —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Client —</SelectItem>
                  {clients.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>{c.nom} {c.prenom || ''}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Périodicité">
              <Select value={form.periodicite}
                      onValueChange={(v) => setForm((f) => ({ ...f, periodicite: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PERIODES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Début">
              <Input type="date" value={form.date_debut}
                     onChange={(e) => setForm((f) => ({ ...f, date_debut: e.target.value }))} />
            </FormField>
            <FormField label="Renouvellement" hint="optionnel">
              <Input type="date" value={form.date_renouvellement}
                     onChange={(e) => setForm((f) => ({ ...f, date_renouvellement: e.target.value }))} />
            </FormField>
            {/* L321 — prix, installation et durée exposés à la création. */}
            <FormField label="Prix (DH)" hint="optionnel">
              <Input type="number" step="any" value={form.prix}
                     onChange={(e) => setForm((f) => ({ ...f, prix: e.target.value }))} />
            </FormField>
            <FormField label="Durée (mois)" hint="optionnel">
              <Input type="number" step="any" value={form.duree_mois}
                     onChange={(e) => setForm((f) => ({ ...f, duree_mois: e.target.value }))} />
            </FormField>
            <Button type="submit"><Plus /> Ajouter</Button>
            <FormField label="Chantier (optionnel)" className="sm:col-span-2 lg:col-span-2">
              <Select value={form.installation ? String(form.installation) : '__none'}
                      onValueChange={(v) => setForm((f) => ({ ...f, installation: v === '__none' ? '' : v }))}>
                <SelectTrigger><SelectValue placeholder="— Aucun chantier —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Aucun chantier —</SelectItem>
                  {installations.map((i) => (
                    <SelectItem key={i.id} value={String(i.id)}>
                      {i.reference ?? `Chantier ${i.id}`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
          </Form>
          {formError && (
            <div role="alert"
                 className="mt-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">
              <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
              {formError}
            </div>
          )}
        </Card>

        {loading ? (
          // L329 — état de chargement explicite.
          <Card className="space-y-2 p-4">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </Card>
        ) : loadError ? (
          // L329 — distinction vide vs erreur de chargement.
          <EmptyState
            icon={AlertTriangle}
            title="Chargement impossible"
            description="Les contrats n'ont pas pu être chargés. Réessayez."
            action={<Button size="sm" variant="outline" onClick={load}>Réessayer</Button>}
          />
        ) : visibleRows.length === 0 ? (
          <EmptyState
            icon={vue === 'tous' ? ClipboardList : CalendarClock}
            title={vue === 'dus' ? 'Aucune visite due'
              : vue === 'renouveler' ? 'Aucun contrat à renouveler' : 'Aucun contrat'}
            description={vue === 'dus'
              ? 'Aucun contrat n’a de visite due pour le moment.'
              : vue === 'renouveler'
                ? 'Aucun contrat n’atteint sa date de renouvellement.'
                : 'Ajoutez un contrat de maintenance ci-dessus pour planifier les visites préventives.'}
          />
        ) : (
          <DataTable
            data={visibleRows}
            columns={columns}
            getRowId={(row) => row.id}
            searchable={false}
            exportName="contrats-maintenance"
            emptyTitle="Aucun contrat"
          />
        )}

        {/* L675 — choix de la date de visite avant téléchargement du rapport. */}
        <Dialog open={!!pdfDialog} onOpenChange={(o) => { if (!o) setPdfDialog(null) }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Rapport de maintenance</DialogTitle>
              <DialogDescription>
                Choisissez la date de visite figurant sur le rapport
                (par défaut, la dernière visite générée).
              </DialogDescription>
            </DialogHeader>
            <FormField label="Date de visite">
              <Input type="date" value={pdfDialog?.date ?? ''}
                     onChange={(e) => setPdfDialog((d) => ({ ...d, date: e.target.value }))} />
            </FormField>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setPdfDialog(null)}>Annuler</Button>
              <Button onClick={rapport}><Download /> Télécharger</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  )
}
