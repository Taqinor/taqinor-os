import { useEffect, useMemo, useState } from 'react'
import {
  Megaphone, Plus, Copy, LineChart, Rocket, Pencil, Lock, MessageSquare,
} from 'lucide-react'
import innovationApi from '../../api/innovationApi'
import {
  Badge, Button, Card, DataTable, EmptyState, IconButton,
  Input, Label, MultiSelect,
  Spinner, Textarea, toast,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import ChatterTimeline from '../../components/ChatterTimeline'
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

   WIR213 — une campagne restait structurellement INERTE : ni fermeture, ni
   édition d'un brouillon, ni tableau de bord (`campagnes.tableauBord`), ni
   chatter (`campagnes.historique`/`noter`) — quatre appels serveur sans aucun
   consommateur. Un brouillon mal saisi ne pouvait donc plus être corrigé, et
   une campagne active ne pouvait jamais être close. Les quatre sont câblés
   ici ; le statut passe par le PATCH `statut` (c'est cette transition que le
   serveur intercepte pour notifier le segment, NTIDE31), et la note publiée
   est RELUE du serveur (la réponse de `noter` est la timeline complète).
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
  // WIR213 — édition d'un brouillon (null = création), tableau de bord et
  // panneau d'activité (chatter) d'une campagne.
  const [editing, setEditing] = useState(null)
  const [bord, setBord] = useState(null)
  const [activite, setActivite] = useState(null) // { campagne, entrees } | null
  const [note, setNote] = useState('')
  const [notant, setNotant] = useState(false)

  const [rapport, setRapport] = useState(null) // { campagne, data } | null
  const [loadingRapport, setLoadingRapport] = useState(false)
  const [busyId, setBusyId] = useState(null)

  // WIR213 — le tableau de bord est rechargé avec la liste : les tuiles
  // (actives / brouillons / fermées / taux de réalisation) doivent suivre
  // chaque transition de statut.
  const reload = () => Promise.all([
    innovationApi.campagnes.list(),
    innovationApi.campagnes.tableauBord().catch(() => ({ data: null })),
  ]).then(([r, b]) => {
    setCampagnes(r.data?.results ?? r.data ?? [])
    setBord(b.data ?? null)
  }).catch(() => setCampagnes([]))

  useEffect(() => {
    let active = true
    Promise.all([
      innovationApi.campagnes.list(),
      innovationApi.campagnes.segmentsDisponibles(),
      innovationApi.campagnes.tableauBord().catch(() => ({ data: null })),
    ])
      .then(([c, s, b]) => {
        if (!active) return
        setCampagnes(c.data?.results ?? c.data ?? [])
        setSegments(s.data?.results ?? [])
        setBord(b?.data ?? null)
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
    setEditing(null)
    setForm(EMPTY_FORM)
    setDialogOpen(true)
  }

  // WIR213 — édition d'un BROUILLON : une campagne mal saisie ne pouvait plus
  // être corrigée (aucun écran n'appelait `campagnes.update` hors lancement).
  const openEdit = (campagne) => {
    setEditing(campagne)
    setForm({
      nom: campagne.nom ?? '',
      description: campagne.description ?? '',
      segment: campagne.segment ?? [],
      date_debut: campagne.date_debut ?? '',
      date_fin: campagne.date_fin ?? '',
      message_incitation: campagne.message_incitation ?? '',
      tag_auto: campagne.tag_auto ?? '',
    })
    setDialogOpen(true)
  }

  const setField = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    // `statut` n'est JAMAIS envoyé ici : il appartient aux transitions
    // (lancer/fermer), qui sont les seules à notifier le segment côté serveur.
    const payload = {
      nom: form.nom,
      description: form.description,
      segment: form.segment,
      cible_departement: form.segment[0] || '',
      date_debut: form.date_debut || undefined,
      date_fin: form.date_fin || undefined,
      message_incitation: form.message_incitation,
      tag_auto: form.tag_auto,
    }
    const requete = editing
      ? innovationApi.campagnes.update(editing.id, payload)
      : innovationApi.campagnes.create(payload)
    requete
      .then(() => {
        toast.success(editing ? 'Campagne mise à jour.' : 'Campagne créée.')
        setDialogOpen(false)
        setEditing(null)
        reload()
      })
      .catch((err) => toast.error(
        err?.response?.data?.detail
        ?? (editing ? 'Mise à jour impossible.' : 'Création impossible.')))
      .finally(() => setSaving(false))
  }

  // WIR213 — panneau « Activité » : historique serveur + composeur de note.
  // `noter` renvoie la timeline COMPLÈTE : on la relit telle quelle, jamais
  // d'ajout optimiste (auteur et horodatage sont posés côté serveur).
  const ouvrirActivite = (campagne) => {
    setActivite({ campagne, entrees: null })
    setNote('')
    innovationApi.campagnes.historique(campagne.id)
      .then((r) => setActivite({ campagne, entrees: r.data?.results ?? r.data ?? [] }))
      .catch(() => { toast.error('Historique indisponible.'); setActivite(null) })
  }

  const publierNote = (e) => {
    e.preventDefault()
    if (!note.trim() || !activite) return
    setNotant(true)
    innovationApi.campagnes.noter(activite.campagne.id, note.trim())
      .then((r) => {
        setNote('')
        setActivite((a) => (a
          ? { ...a, entrees: r.data?.results ?? r.data ?? [] }
          : a))
        toast.success('Note ajoutée.')
      })
      .catch((err) => toast.error(
        err?.response?.data?.body ?? 'Ajout de la note impossible.'))
      .finally(() => setNotant(false))
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

  // WIR213 — fermeture : active → fermée. Symétrique du lancement (même PATCH
  // de statut), sans quoi une campagne restait active pour toujours.
  const fermer = (campagne) => {
    setBusyId(campagne.id)
    innovationApi.campagnes.update(campagne.id, { statut: 'fermee' })
      .then(() => { toast.success('Campagne fermée.'); reload() })
      .catch(() => toast.error('Fermeture impossible.'))
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
      id: 'actions', header: '', width: 240, align: 'right',
      accessor: () => '',
      cell: (v, r) => (
        <span className="flex items-center justify-end gap-1">
          {r.statut === 'brouillon' && (
            <IconButton variant="ghost" label="Modifier" disabled={busyId === r.id} onClick={() => openEdit(r)}>
              <Pencil />
            </IconButton>
          )}
          {r.statut === 'brouillon' && (
            <IconButton variant="ghost" label="Lancer" disabled={busyId === r.id} onClick={() => lancer(r)}>
              <Rocket />
            </IconButton>
          )}
          {r.statut === 'active' && (
            <IconButton variant="ghost" label="Fermer" disabled={busyId === r.id} onClick={() => fermer(r)}>
              <Lock />
            </IconButton>
          )}
          <IconButton variant="ghost" label="Activité" onClick={() => ouvrirActivite(r)}>
            <MessageSquare />
          </IconButton>
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

      {/* WIR213 — tuiles du tableau de bord serveur (`campagnes/tableau-bord/`,
          NTIDE34) : l'endpoint existait sans aucun consommateur. Les valeurs
          viennent TELLES QUELLES du serveur — rien n'est recalculé ici. */}
      {bord && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ['Actives', bord.actives],
            ['Brouillons', bord.brouillons],
            ['Fermées', bord.fermees],
          ].map(([libelle, valeur]) => (
            <Card key={libelle} className="p-3">
              <div className="text-xs text-muted-foreground">{libelle}</div>
              <div className="text-lg font-semibold tabular-nums">{valeur ?? 0}</div>
            </Card>
          ))}
          <Card className="p-3">
            <div className="text-xs text-muted-foreground">Taux de réalisation</div>
            <div className="text-lg font-semibold tabular-nums">
              {Math.round((bord.taux_realisation ?? 0) * 100)}%
            </div>
          </Card>
        </div>
      )}

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
      <ResponsiveDialog
        open={dialogOpen}
        onOpenChange={(o) => { setDialogOpen(o); if (!o) setEditing(null) }}
        title={editing ? `Modifier — ${editing.nom}` : 'Nouvelle campagne innovation'}
      >
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
            <Button type="button" variant="outline" onClick={() => { setDialogOpen(false); setEditing(null) }}>Annuler</Button>
            <Button type="submit" loading={saving} disabled={!form.nom.trim()}>
              {editing ? 'Enregistrer' : 'Créer (brouillon)'}
            </Button>
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

      {/* ── WIR213 — Activité (chatter) d'une campagne ── */}
      <ResponsiveDialog
        open={!!activite}
        onOpenChange={(o) => { if (!o) setActivite(null) }}
        title={activite ? `Activité — ${activite.campagne.nom}` : 'Activité'}
      >
        <div className="flex flex-col gap-3">
          <form onSubmit={publierNote} className="flex flex-col gap-2">
            <Label htmlFor="camp-note">Ajouter une note</Label>
            <Textarea id="camp-note" rows={2} value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder="Note libre — visible dans le journal de la campagne" />
            <div className="flex justify-end">
              <Button type="submit" size="sm" loading={notant} disabled={!note.trim()}>
                Publier la note
              </Button>
            </div>
          </form>
          {activite?.entrees === null ? (
            <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Spinner /> Chargement…
            </p>
          ) : (
            <ChatterTimeline
              entries={(activite?.entrees ?? []).map((a) => ({
                ...a, user_nom: a.user_username,
              }))}
              emptyLabel="Aucune activité sur cette campagne."
            />
          )}
        </div>
      </ResponsiveDialog>
    </div>
  )
}
