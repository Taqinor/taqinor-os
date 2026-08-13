import { useEffect, useMemo, useState } from 'react'
import { Megaphone, Plus, Copy, LineChart, Rocket } from 'lucide-react'
import innovationApi from '../../api/innovationApi'
import {
  Badge, Button, Card, DataTable, EmptyState, IconButton,
  Input, Label, MultiSelect,
  Spinner, Textarea, toast,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatDate } from '../../lib/format'

/* ============================================================================
   WIR150 — Écran « Campagnes » du module Innovation (NTIDE25+).
   ----------------------------------------------------------------------------
   `CampagneInnovationViewSet` (CRUD + incitation/rapport/cloner/tableau-bord/
   segments/historique/noter) n'avait aucun consommateur : seul `.incitation()`
   était appelé (bandeau du formulaire « Proposer une idée »), et
   `CampagnesInnovationSettings.jsx` ne fait que basculer le toggle global —
   aucune campagne réelle n'était créable. Créer/lister/consulter le rapport/
   cloner depuis cet écran. Réservé au palier Directeur/Admin (IdeasSeeAll,
   même gate que le tableau de bord d'idées).
   ========================================================================== */

const STATUT_TONE = { brouillon: 'neutral', active: 'success', fermee: 'warning' }

const EMPTY_FORM = {
  nom: '', description: '', segment: [], date_debut: '', date_fin: '',
  message_incitation: '', tag_auto: '',
}

export default function CampagnesInnovationPage() {
  const [campagnes, setCampagnes] = useState([])
  const [segments, setSegments] = useState([])
  const [loading, setLoading] = useState(true)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  const [rapport, setRapport] = useState(null) // { campagne, data } | null
  const [loadingRapport, setLoadingRapport] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const reload = () => innovationApi.campagnes.list()
    .then((r) => setCampagnes(r.data?.results ?? r.data ?? []))
    .catch(() => setCampagnes([]))

  useEffect(() => {
    let active = true
    Promise.all([
      innovationApi.campagnes.list(),
      innovationApi.campagnes.segmentsDisponibles(),
    ])
      .then(([c, s]) => {
        if (!active) return
        setCampagnes(c.data?.results ?? c.data ?? [])
        setSegments(s.data?.results ?? [])
      })
      .catch(() => {})
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const segmentOptions = useMemo(
    () => segments.map((s) => ({ value: s, label: s })),
    [segments],
  )

  const openCreate = () => {
    setForm(EMPTY_FORM)
    setDialogOpen(true)
  }

  const setField = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    innovationApi.campagnes.create({
      nom: form.nom,
      description: form.description,
      segment: form.segment,
      cible_departement: form.segment[0] || '',
      date_debut: form.date_debut || undefined,
      date_fin: form.date_fin || undefined,
      message_incitation: form.message_incitation,
      tag_auto: form.tag_auto,
    })
      .then(() => {
        toast.success('Campagne créée.')
        setDialogOpen(false)
        reload()
      })
      .catch((err) => toast.error(err?.response?.data?.detail ?? 'Création impossible.'))
      .finally(() => setSaving(false))
  }

  const voirRapport = (campagne) => {
    setRapport({ campagne, data: null })
    setLoadingRapport(true)
    innovationApi.campagnes.rapport(campagne.id)
      .then((r) => setRapport({ campagne, data: r.data }))
      .catch(() => { toast.error('Rapport indisponible.'); setRapport(null) })
      .finally(() => setLoadingRapport(false))
  }

  // NTIDE62 — lancement : brouillon → active. C'est CETTE transition (et elle
  // seule) qui notifie le segment ciblé côté serveur (NTIDE31,
  // `CampagneInnovationViewSet.perform_update`) et qui fait apparaître le
  // bandeau d'incitation sur « Proposer une idée » (NTIDE27) : le PATCH direct
  // du statut est donc l'unique geste nécessaire, aucune route dédiée.
  const lancer = (campagne) => {
    setBusyId(campagne.id)
    innovationApi.campagnes.update(campagne.id, { statut: 'active' })
      .then(() => { toast.success('Campagne lancée.'); reload() })
      .catch(() => toast.error('Lancement impossible.'))
      .finally(() => setBusyId(null))
  }

  const cloner = (campagne) => {
    setBusyId(campagne.id)
    innovationApi.campagnes.cloner(campagne.id)
      .then(() => { toast.success('Campagne clonée (brouillon).'); reload() })
      .catch(() => toast.error('Clonage impossible.'))
      .finally(() => setBusyId(null))
  }

  const columns = useMemo(() => [
    { id: 'nom', header: 'Nom', accessor: (r) => r.nom },
    {
      id: 'statut', header: 'Statut', width: 110,
      accessor: (r) => r.statut,
      cell: (v, r) => <Badge tone={STATUT_TONE[v] ?? 'neutral'}>{r.statut_display || v}</Badge>,
    },
    {
      id: 'segment', header: 'Segment', width: 220,
      accessor: (r) => (r.segment || []).join(', '),
    },
    {
      id: 'dates', header: 'Période', width: 200,
      accessor: (r) => `${r.date_debut ?? ''}${r.date_fin ?? ''}`,
      cell: (v, r) => (r.date_debut || r.date_fin
        ? `${r.date_debut ? formatDate(r.date_debut) : '…'} → ${r.date_fin ? formatDate(r.date_fin) : '…'}`
        : '—'),
    },
    {
      id: 'actions', header: '', width: 160, align: 'right',
      accessor: () => '',
      cell: (v, r) => (
        <span className="flex items-center justify-end gap-1">
          {r.statut === 'brouillon' && (
            <IconButton variant="ghost" label="Lancer" disabled={busyId === r.id} onClick={() => lancer(r)}>
              <Rocket />
            </IconButton>
          )}
          <IconButton variant="ghost" label="Rapport" onClick={() => voirRapport(r)}>
            <LineChart />
          </IconButton>
          <IconButton variant="ghost" label="Cloner" disabled={busyId === r.id} onClick={() => cloner(r)}>
            <Copy />
          </IconButton>
        </span>
      ),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- lancer/voirRapport/cloner recréés à chaque rendu
  ], [busyId])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title inline-flex items-center gap-2">
          <Megaphone className="size-5" aria-hidden="true" />
          Campagnes innovation
        </h1>
        <div className="page-subtitle">
          Incitez un segment ciblé à proposer des idées ; suivez la conversion et le taux de réponse.
        </div>
      </div>

      <div className="mb-4 flex justify-end">
        <Button onClick={openCreate}><Plus /> Nouvelle campagne</Button>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : campagnes.length === 0 ? (
        <EmptyState
          title="Aucune campagne"
          description="Créez une campagne pour inciter un segment ciblé à proposer des idées."
          className="my-6"
        />
      ) : (
        <DataTable
          data={campagnes}
          columns={columns}
          getRowId={(row) => row.id}
          searchable={false}
          pageSize={25}
          aria-label="Campagnes innovation"
        />
      )}

      {/* ── Dialogue création ── */}
      <ResponsiveDialog open={dialogOpen} onOpenChange={setDialogOpen} title="Nouvelle campagne innovation">
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <div>
            <Label htmlFor="camp-nom">Nom</Label>
            <Input id="camp-nom" value={form.nom} onChange={setField('nom')} />
          </div>
          <div>
            <Label htmlFor="camp-desc">Description</Label>
            <Textarea id="camp-desc" rows={2} value={form.description} onChange={setField('description')} />
          </div>
          <div>
            <Label htmlFor="camp-segment">Segment ciblé</Label>
            <MultiSelect
              id="camp-segment"
              options={segmentOptions}
              value={form.segment}
              onChange={(v) => setForm((f) => ({ ...f, segment: v }))}
              placeholder="Rôles / départements ciblés…"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="camp-debut">Date de début</Label>
              <Input id="camp-debut" type="date" value={form.date_debut} onChange={setField('date_debut')} />
            </div>
            <div>
              <Label htmlFor="camp-fin">Date de fin</Label>
              <Input id="camp-fin" type="date" value={form.date_fin} onChange={setField('date_fin')} />
            </div>
          </div>
          <div>
            <Label htmlFor="camp-message">Message d'incitation</Label>
            <Textarea id="camp-message" rows={2} value={form.message_incitation} onChange={setField('message_incitation')} placeholder="Affiché aux utilisateurs ciblés sur « Proposer une idée »." />
          </div>
          <div>
            <Label htmlFor="camp-tag">Tag automatique</Label>
            <Input id="camp-tag" value={form.tag_auto} onChange={setField('tag_auto')} placeholder="Optionnel" />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Annuler</Button>
            <Button type="submit" loading={saving} disabled={!form.nom.trim()}>Créer (brouillon)</Button>
          </div>
        </form>
      </ResponsiveDialog>

      {/* ── Dialogue rapport ── */}
      <ResponsiveDialog
        open={!!rapport}
        onOpenChange={(o) => { if (!o) setRapport(null) }}
        title={rapport ? `Rapport — ${rapport.campagne.nom}` : 'Rapport'}
      >
        {loadingRapport || !rapport?.data ? (
          <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
        ) : (
          <Card className="flex flex-col gap-3 p-4">
            <div className="grid grid-cols-3 gap-3 text-center">
              <div>
                <div className="text-xs text-muted-foreground">Ciblés</div>
                <div className="text-lg font-semibold tabular-nums">{rapport.data.nb_utilisateurs_cibles}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Idées proposées</div>
                <div className="text-lg font-semibold tabular-nums">{rapport.data.nb_idees_proposees}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Conversion</div>
                <div className="text-lg font-semibold tabular-nums">
                  {Math.round((rapport.data.taux_conversion ?? 0) * 100)}%
                </div>
              </div>
            </div>
            {rapport.data.top_idees?.length > 0 && (
              <ul className="flex flex-col gap-1.5">
                {rapport.data.top_idees.map((i) => (
                  <li key={i.id} className="flex items-center justify-between gap-2 text-sm">
                    <span className="truncate">{i.titre}</span>
                    <span className="tabular-nums text-muted-foreground">{i.votes_count} vote(s)</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}
      </ResponsiveDialog>
    </div>
  )
}
