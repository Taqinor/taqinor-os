import { useEffect, useMemo, useState } from 'react'
import {
  Megaphone, Plus, Copy, LineChart, Rocket, Pencil, Square, History,
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
   ========================================================================== */

const STATUT_TONE = { brouillon: 'neutral', active: 'success', fermee: 'warning' }

const EMPTY_FORM = {
  id: null,
  nom: '', description: '', segment: [], date_debut: '', date_fin: '',
  message_incitation: '', tag_auto: '',
}

/* WIR213 — le formulaire re-rempli depuis la campagne SERVEUR. Les champs
   absents retombent sur du vide, jamais sur la valeur d'une campagne
   précédemment ouverte : un dialogue qui garde l'état du tour d'avant écrase
   la campagne suivante avec des données qui ne sont pas les siennes. */
const formDepuisCampagne = (c) => ({
  id: c.id,
  nom: c.nom ?? '',
  description: c.description ?? '',
  segment: c.segment ?? [],
  date_debut: c.date_debut ?? '',
  date_fin: c.date_fin ?? '',
  message_incitation: c.message_incitation ?? '',
  tag_auto: c.tag_auto ?? '',
})

// Un pourcentage SERVEUR (`taux_realisation`, `taux_conversion`) est un ratio
// 0..1 : on le met en forme, on ne le recalcule pas. Absent ⇒ « — », jamais 0 %.
const pourcentage = (ratio) =>
  (Number.isFinite(ratio) ? `${Math.round(ratio * 100)} %` : '—')

// Un compteur SERVEUR absent n'est pas un zéro.
const compteur = (v) => (Number.isFinite(v) ? v : '—')

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

  // WIR213 — les tuiles du tableau de bord (NTIDE34) : agrégat SERVEUR, aucun
  // compte refait sur la liste chargée (deux écrans afficheraient deux
  // chiffres différents le jour où la liste est paginée).
  const [tableauBord, setTableauBord] = useState(null)

  // WIR213 — l'onglet « Activité » : chatter générique de la campagne
  // (NTIDE33). `entries` vient TOUJOURS du serveur — y compris après l'ajout
  // d'une note, dont la réponse est le fil rechargé.
  const [activite, setActivite] = useState(null) // { campagne, entries } | null
  const [noteBody, setNoteBody] = useState('')
  const [envoiNote, setEnvoiNote] = useState(false)

  const reload = () => Promise.all([
    innovationApi.campagnes.list(),
    innovationApi.campagnes.tableauBord(),
  ])
    .then(([c, t]) => {
      setCampagnes(c.data?.results ?? c.data ?? [])
      setTableauBord(t.data ?? null)
    })
    .catch(() => {})

  useEffect(() => {
    let active = true
    Promise.all([
      innovationApi.campagnes.list(),
      innovationApi.campagnes.segmentsDisponibles(),
      innovationApi.campagnes.tableauBord(),
    ])
      .then(([c, s, t]) => {
        if (!active) return
        setCampagnes(c.data?.results ?? c.data ?? [])
        setSegments(s.data?.results ?? [])
        setTableauBord(t.data ?? null)
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

  /* WIR213 — ÉDITION d'un brouillon. Une campagne se créait puis restait
     figée : ni le segment, ni le message d'incitation, ni les dates ne
     pouvaient être corrigés avant le lancement, alors que ce sont exactement
     les champs qu'on ajuste juste avant de partir. L'édition est réservée au
     BROUILLON : une campagne active a déjà notifié son segment, on ne réécrit
     pas son message dans le dos des destinataires (cloner sert à ça). */
  const openEdit = (campagne) => {
    setForm(formDepuisCampagne(campagne))
    setDialogOpen(true)
  }

  const setField = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    const corps = {
      nom: form.nom,
      description: form.description,
      segment: form.segment,
      cible_departement: form.segment[0] || '',
      date_debut: form.date_debut || undefined,
      date_fin: form.date_fin || undefined,
      message_incitation: form.message_incitation,
      tag_auto: form.tag_auto,
    }
    const enEdition = form.id != null
    const promesse = enEdition
      ? innovationApi.campagnes.update(form.id, corps)
      : innovationApi.campagnes.create(corps)
    promesse
      .then(() => {
        toast.success(enEdition ? 'Campagne mise à jour.' : 'Campagne créée.')
        setDialogOpen(false)
        reload()
      })
      .catch((err) => toast.error(
        err?.response?.data?.detail
        ?? (enEdition ? 'Mise à jour impossible.' : 'Création impossible.'),
      ))
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

  /* WIR213 — FERMETURE : active → fermée. Sans elle, une campagne restait
     active À VIE — son bandeau d'incitation s'affichait encore longtemps après
     la fin de l'opération, et le tableau de bord comptait des « actives » qui
     ne l'étaient plus. Même geste que le lancement : un PATCH du statut, le
     seul chemin que le sérialiseur expose. */
  const fermer = (campagne) => {
    setBusyId(campagne.id)
    innovationApi.campagnes.update(campagne.id, { statut: 'fermee' })
      .then(() => { toast.success('Campagne fermée.'); reload() })
      .catch((err) => toast.error(
        err?.response?.data?.detail ?? 'Fermeture impossible.'))
      .finally(() => setBusyId(null))
  }

  /* WIR213 — ACTIVITÉ : le chatter générique de la campagne (NTIDE33). Le
     journal AUTOMATIQUE des changements de statut y vit déjà côté serveur
     (`services.log_campagne_changes`) — il n'était simplement affiché nulle
     part, si bien qu'on ne pouvait pas savoir qui avait lancé ou fermé une
     campagne, ni quand. */
  const voirActivite = (campagne) => {
    setNoteBody('')
    setActivite({ campagne, entries: null })
    innovationApi.campagnes.historique(campagne.id)
      .then((r) => setActivite({ campagne, entries: r.data?.results ?? r.data ?? [] }))
      .catch(() => {
        toast.error('Historique indisponible.')
        setActivite(null)
      })
  }

  // La note ajoutée n'est PAS poussée dans l'état local : l'action serveur
  // renvoie le fil RECHARGÉ, et c'est lui qu'on rend. Un ajout optimiste
  // afficherait une note que le serveur pourrait avoir refusée.
  const noter = () => {
    const body = noteBody.trim()
    if (!body || !activite?.campagne) return
    setEnvoiNote(true)
    innovationApi.campagnes.noter(activite.campagne.id, body)
      .then((r) => {
        setActivite((a) => (a ? {
          ...a, entries: r.data?.results ?? r.data ?? [],
        } : a))
        setNoteBody('')
      })
      .catch((err) => toast.error(
        err?.response?.data?.body ?? err?.response?.data?.detail ?? 'Note non enregistrée.'))
      .finally(() => setEnvoiNote(false))
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
          {/* Le BROUILLON s'édite et se lance ; l'ACTIVE se ferme. Une
              campagne fermée ne garde que la lecture (rapport, activité) et
              le clonage — on ne réécrit pas une opération terminée. */}
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
            <IconButton variant="ghost" label="Fermer la campagne" disabled={busyId === r.id} onClick={() => fermer(r)}>
              <Square />
            </IconButton>
          )}
          <IconButton variant="ghost" label="Activité" onClick={() => voirActivite(r)}>
            <History />
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

      {/* ── WIR213 — Tuiles du tableau de bord (NTIDE34) ────────────────────
          Agrégat SERVEUR (`campagnes/tableau-bord/`) : rien n'est recompté sur
          la liste ci-dessous — elle est paginée, un compte local mentirait dès
          la deuxième page. */}
      {tableauBord && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4" data-campagnes-tableau-bord="">
          <Card className="p-3" data-campagnes-tuile="actives">
            <div className="text-xs text-muted-foreground">Actives</div>
            <div className="text-lg font-semibold tabular-nums">{compteur(tableauBord.actives)}</div>
          </Card>
          <Card className="p-3" data-campagnes-tuile="brouillons">
            <div className="text-xs text-muted-foreground">Brouillons</div>
            <div className="text-lg font-semibold tabular-nums">{compteur(tableauBord.brouillons)}</div>
          </Card>
          <Card className="p-3" data-campagnes-tuile="fermees">
            <div className="text-xs text-muted-foreground">Fermées</div>
            <div className="text-lg font-semibold tabular-nums">{compteur(tableauBord.fermees)}</div>
          </Card>
          <Card className="p-3" data-campagnes-tuile="taux_realisation">
            <div className="text-xs text-muted-foreground">Idées réalisées</div>
            <div className="text-lg font-semibold tabular-nums">
              {pourcentage(tableauBord.taux_realisation)}
            </div>
          </Card>
        </div>
      )}

      {tableauBord?.top_campagnes?.length > 0 && (
        <Card className="mb-4 flex flex-col gap-1.5 p-3" data-campagnes-top="">
          <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Campagnes les plus productives
          </h2>
          <ul className="flex flex-col gap-1">
            {tableauBord.top_campagnes.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="truncate">{c.nom}</span>
                <span className="tabular-nums text-muted-foreground">
                  {compteur(c.nb_idees_proposees)} idée(s)
                </span>
              </li>
            ))}
          </ul>
        </Card>
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

      {/* ── Dialogue création / édition d'un brouillon ── */}
      <ResponsiveDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        title={form.id != null ? 'Modifier la campagne (brouillon)' : 'Nouvelle campagne innovation'}
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
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Annuler</Button>
            <Button type="submit" loading={saving} disabled={!form.nom.trim()}>
              {form.id != null ? 'Enregistrer' : 'Créer (brouillon)'}
            </Button>
          </div>
        </form>
      </ResponsiveDialog>

      {/* ── WIR213 — Dialogue « Activité » : chatter de la campagne (NTIDE33) ──
          Le journal automatique des changements de statut (qui a lancé, qui a
          fermé, quand) vivait déjà côté serveur et n'était affiché nulle
          part. */}
      <ResponsiveDialog
        open={!!activite}
        onOpenChange={(o) => { if (!o) setActivite(null) }}
        title={activite ? `Activité — ${activite.campagne.nom}` : 'Activité'}
      >
        <div className="flex flex-col gap-3" data-campagne-activite={activite?.campagne?.id ?? ''}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="camp-note">Ajouter une note</Label>
            <Textarea
              id="camp-note"
              rows={2}
              value={noteBody}
              onChange={(e) => setNoteBody(e.target.value)}
              placeholder="Ce que vous voulez retrouver dans six mois."
            />
            <Button
              type="button"
              size="sm"
              className="self-end"
              loading={envoiNote}
              disabled={envoiNote || !noteBody.trim()}
              onClick={noter}
            >
              Noter
            </Button>
          </div>
          {activite?.entries == null ? (
            <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Spinner /> Chargement…
            </p>
          ) : (
            <ChatterTimeline
              entries={activite.entries}
              emptyLabel="Aucune activité sur cette campagne pour le moment."
            />
          )}
        </div>
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
