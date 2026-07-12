import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, Inbox, Trash2, UserCog, XCircle } from 'lucide-react'
import reportingApi from '../../api/reportingApi'
import automationApi from '../../api/automationApi'
import api from '../../api/axios'
import { formatMAD } from '../../lib/format'
import {
  Badge, Button, Card, DataTable, DateRangePicker, EmptyState, Form,
  FormActions, FormField, FormSection, Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem, Spinner, Tabs, TabsList, TabsTrigger, TabsContent,
  Textarea, toast,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { useConfirmDialog } from '../../ui/confirm'

/* ============================================================================
   XKB1/ZCTR7-9 — Boîte d'approbations centralisée (agrégateur cross-app).
   ----------------------------------------------------------------------------
   Écran UNIQUE listant TOUT ce qui attend l'approbation de l'utilisateur
   courant, à travers les CINQ sources exposées par
   `reporting/approbations-en-attente/` (automation/contrats/ged/
   installations/workflow) — UNFILTRÉ par défaut (contrairement à
   `WorkflowsScreen` qui n'affiche que `source=workflow`).
   Décision unitaire ou en masse (sélection multi-lignes), filtres
   source/priorité, tri urgence/ancienneté/montant. company + acting user
   toujours résolus SERVEUR (jamais posté par le client). ========================================================================== */

const SOURCE_LABELS = {
  automation: 'Automatisation',
  contrats: 'Contrats',
  ged: 'GED',
  installations: 'Installations',
  workflow: 'Workflow',
}

const SOURCES = Object.keys(SOURCE_LABELS)

const TRI_OPTIONS = [
  { value: '', label: 'Par défaut (source, id)' },
  { value: 'urgence', label: 'Urgence (en retard d’abord)' },
  { value: 'anciennete', label: 'Ancienneté (plus vieux d’abord)' },
  { value: 'montant', label: 'Montant (décroissant)' },
]

function fetchApprobations(params) {
  return reportingApi.approbationsEnAttente(params)
    .then((r) => r.data?.items ?? [])
}

/* ============================================================================
   VX103 — Onglet « Délégations » : suppléant + plage de dates, pur câblage sur
   l'API existante (`automation/approval-delegations/`, XKB3). Pendant que la
   délégation est active, le suppléant voit les items du délégant dans l'onglet
   « File » ci-dessus (déjà géré serveur par `visible_demandeur_ids_for`) — rien
   à faire ici pour ça. *(@coord NTWFL3 étend la couverture backend de cette
   même délégation au moteur WorkflowStepInstance — cette UI ne suppose pas la
   seule couverture ApprovalRequest.)* ============================================================================ */
function isDelegationActive(d) {
  const now = new Date()
  return new Date(d.date_debut) <= now && now <= new Date(d.date_fin)
}

function DelegationsTab() {
  const { confirmDelete } = useConfirmDialog()
  const [delegations, setDelegations] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [suppleant, setSuppleant] = useState('')
  const [range, setRange] = useState({ start: null, end: null })

  const load = () => {
    setLoading(true)
    return Promise.all([
      automationApi.getDelegations(),
      api.get('/users/'),
    ])
      .then(([delegRes, usersRes]) => {
        setDelegations(delegRes.data?.results ?? delegRes.data ?? [])
        setUsers(usersRes.data?.results ?? usersRes.data ?? [])
      })
      .catch(() => toast.error('Chargement des délégations impossible.'))
      .finally(() => setLoading(false))
  }

  // Chargement initial — le setState a lieu dans les callbacks async.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const create = async (e) => {
    e.preventDefault()
    if (!suppleant || !range.start || !range.end) {
      toast.error('Choisissez un suppléant et une plage de dates.')
      return
    }
    setSaving(true)
    try {
      await automationApi.createDelegation({
        suppleant: Number(suppleant),
        date_debut: range.start.toISOString(),
        date_fin: range.end.toISOString(),
      })
      toast.success('Délégation créée.')
      setSuppleant('')
      setRange({ start: null, end: null })
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail
        || err?.response?.data?.suppleant?.[0]
        || err?.response?.data?.non_field_errors?.[0]
        || 'Création impossible.')
    } finally {
      setSaving(false)
    }
  }

  const revoke = async (d) => {
    const ok = await confirmDelete({
      title: 'Révoquer cette délégation ?',
      description: `La délégation vers « ${d.suppleant_nom || d.suppleant} » sera immédiatement retirée.`,
      confirmLabel: 'Révoquer',
    })
    if (!ok) return
    try {
      await automationApi.deleteDelegation(d.id)
      toast.success('Délégation révoquée.')
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Révocation impossible.')
    }
  }

  const userLabel = (id) => users.find((u) => u.id === id)?.username || `#${id}`

  const now = new Date()
  const actives = delegations.filter((d) => isDelegationActive(d))
  const avenir = delegations.filter((d) => new Date(d.date_debut) > now)
  const passees = delegations.filter((d) => new Date(d.date_fin) < now)

  const renderRow = (d) => (
    <li
      key={d.id}
      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2.5"
    >
      <span className="flex items-center gap-2 text-sm">
        <UserCog className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span>
          <strong className="font-medium text-foreground">{d.delegant_nom || userLabel(d.delegant)}</strong>
          {' → '}
          <strong className="font-medium text-foreground">{d.suppleant_nom || userLabel(d.suppleant)}</strong>
        </span>
        {isDelegationActive(d) && <Badge tone="success">Active</Badge>}
        <span className="text-xs text-muted-foreground">
          {new Date(d.date_debut).toLocaleDateString('fr-FR')} → {new Date(d.date_fin).toLocaleDateString('fr-FR')}
        </span>
      </span>
      <Button
        size="sm" variant="ghost"
        onClick={() => revoke(d)}
        data-testid={`delegation-revoke-${d.id}`}
      >
        <Trash2 /> Révoquer
      </Button>
    </li>
  )

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-4 sm:p-5">
        <Form onSubmit={create} className="gap-4">
          <FormSection title="Nouvelle délégation" description="Pendant votre absence, votre suppléant voit et décide vos demandes en attente.">
            <FormField label="Suppléant" required htmlFor="delegation-suppleant">
              <Select value={suppleant ? String(suppleant) : undefined} onValueChange={setSuppleant}>
                <SelectTrigger id="delegation-suppleant"><SelectValue placeholder="Choisir un suppléant…" /></SelectTrigger>
                <SelectContent>
                  {users.map((u) => (
                    <SelectItem key={u.id} value={String(u.id)}>{u.username}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Période" required htmlFor="delegation-periode">
              <DateRangePicker id="delegation-periode" value={range} onChange={setRange} />
            </FormField>
          </FormSection>
          <FormActions sticky={false}>
            <Button type="submit" loading={saving}>Déléguer</Button>
          </FormActions>
        </Form>
      </Card>

      {loading ? (
        <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : delegations.length === 0 ? (
        <EmptyState
          icon={UserCog}
          title="Aucune délégation"
          description="Créez une délégation pour qu'un suppléant traite vos demandes pendant votre absence."
        />
      ) : (
        <div className="flex flex-col gap-5">
          {actives.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-foreground">Actives</h3>
              <ul className="flex flex-col gap-2">{actives.map(renderRow)}</ul>
            </div>
          )}
          {avenir.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-foreground">À venir</h3>
              <ul className="flex flex-col gap-2">{avenir.map(renderRow)}</ul>
            </div>
          )}
          {passees.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-muted-foreground">Passées</h3>
              <ul className="flex flex-col gap-2">{passees.map(renderRow)}</ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ApprobationsFileTab() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [source, setSource] = useState('')
  const [priorite, setPriorite] = useState('')
  const [trier, setTrier] = useState('')
  const [decidingKey, setDecidingKey] = useState(null)

  const params = useMemo(() => {
    const p = {}
    if (source) p.source = source
    if (priorite) p.priorite = priorite
    if (trier) p.trier = trier
    return p
  }, [source, priorite, trier])

  // Recharge manuelle (bouton, après décision) : `loading` bascule à `true`
  // AVANT l'appel réseau (hors effet, aucun souci de setState synchrone).
  const reload = () => {
    setLoading(true)
    return fetchApprobations(params)
      .then(setItems)
      .catch(() => { setItems([]); toast.error('Chargement des approbations impossible.') })
      .finally(() => setLoading(false))
  }

  // Chargement initial / à chaque changement de filtre : `loading` ne bascule
  // JAMAIS à `true` de façon synchrone dans l'effet (déjà vrai par défaut au
  // premier rendu, et remis à `true` par `reload()` pour les rechargements
  // manuels) — seul `setLoading(false)`/`setItems` sont posés dans `.then`/
  // `.catch`/`.finally`, jamais dans le corps de l'effet.
  useEffect(() => {
    let active = true
    fetchApprobations(params)
      .then((data) => { if (active) setItems(data) })
      .catch(() => { if (active) { setItems([]); toast.error('Chargement des approbations impossible.') } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [params])

  const decider = async (item, decision) => {
    const key = `${item.source}-${item.id}`
    if (decidingKey) return
    let motif = ''
    if (decision === 'refuser') {
      motif = window.prompt('Motif du refus (obligatoire) :') || ''
      if (!motif.trim()) {
        toast.error('Un motif de refus est obligatoire.')
        return
      }
    }
    setDecidingKey(key)
    try {
      await reportingApi.deciderApprobation(item.source, item.id, decision, motif)
      toast.success(decision === 'approuver' ? 'Demande approuvée.' : 'Demande refusée.')
      reload()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Action impossible.')
    } finally {
      setDecidingKey(null)
    }
  }

  // VX235(a) — `window.prompt` appliquait UN motif à N demandes HÉTÉROGÈNES
  // (« un motif menteur pour tous ») : le refus en masse ouvre désormais un
  // ResponsiveDialog listant chaque item avec son PROPRE motif (un motif
  // commun optionnel les pré-remplit tous, chacun reste modifiable ensuite).
  const [refuserMasse, setRefuserMasse] = useState(null) // { items, motifs, motifCommun, submitting } | null

  const deciderEnMasse = async (selectedRows, decision, clear) => {
    if (decision === 'refuser') {
      setRefuserMasse({
        items: selectedRows,
        motifs: Object.fromEntries(selectedRows.map((it) => [`${it.source}-${it.id}`, ''])),
        motifCommun: '',
        submitting: false,
        clear,
      })
      return
    }
    const payload = selectedRows.map((it) => ({ source: it.source, id: it.id }))
    try {
      const res = await reportingApi.deciderApprobationsEnMasse(payload, decision, '')
      const resultats = res.data?.resultats ?? []
      const ok = resultats.filter((r) => r.ok).length
      const ko = resultats.length - ok
      if (ko === 0) {
        toast.success(`${ok} demande(s) traitée(s).`)
      } else {
        toast.error(`${ok} traitée(s), ${ko} échec(s).`)
      }
      clear?.()
      reload()
    } catch {
      toast.error('Action en masse impossible.')
    }
  }

  const appliquerMotifCommun = () => {
    setRefuserMasse((s) => (s ? {
      ...s,
      motifs: Object.fromEntries(Object.keys(s.motifs).map((k) => [k, s.motifCommun])),
    } : s))
  }

  const confirmRefuserMasse = async () => {
    if (!refuserMasse) return
    const { items, motifs, clear } = refuserMasse
    const vides = items.filter((it) => !motifs[`${it.source}-${it.id}`]?.trim())
    if (vides.length > 0) {
      toast.error('Un motif est obligatoire pour chaque demande refusée.')
      return
    }
    setRefuserMasse((s) => (s ? { ...s, submitting: true } : s))
    const resultats = await Promise.all(items.map((it) => {
      const key = `${it.source}-${it.id}`
      return reportingApi.deciderApprobation(it.source, it.id, 'refuser', motifs[key].trim())
        .then(() => ({ ok: true }))
        .catch(() => ({ ok: false }))
    }))
    const ok = resultats.filter((r) => r.ok).length
    const ko = resultats.length - ok
    if (ko === 0) {
      toast.success(`${ok} demande(s) refusée(s).`)
    } else {
      toast.error(`${ok} refusée(s), ${ko} échec(s).`)
    }
    clear?.()
    setRefuserMasse(null)
    reload()
  }

  const columns = useMemo(() => [
    {
      id: 'source', header: 'Source', width: 140,
      accessor: (r) => SOURCE_LABELS[r.source] || r.source,
      cell: (v, r) => <Badge tone="neutral">{SOURCE_LABELS[r.source] || r.source}</Badge>,
    },
    {
      id: 'libelle', header: 'Demande',
      accessor: (r) => r.libelle || `#${r.id}`,
      // VX100 — clic → la pièce (lien réel fourni par le serveur, ex.
      // chantier/contrat) ; jamais de lien fabriqué côté front.
      cell: (v, r) => (r.lien ? (
        <Link to={r.lien} className="font-medium text-info hover:underline">{v}</Link>
      ) : v),
    },
    { id: 'demandeur', header: 'Demandeur', width: 160, accessor: (r) => r.demandeur || '—' },
    {
      id: 'priorite', header: 'Priorité', width: 110,
      accessor: (r) => r.priorite || '—',
      cell: (v, r) => (r.priorite ? <Badge tone="warning">{r.priorite}</Badge> : '—'),
    },
    {
      id: 'montant', header: 'Montant', width: 140, align: 'right',
      accessor: (r) => (r.montant ?? null),
      cell: (v) => (v === null || v === undefined ? '—' : formatMAD(v)),
    },
    {
      id: 'anciennete', header: 'Ancienneté', width: 140,
      accessor: (r) => r.anciennete_jours ?? 0,
      cell: (v, r) => (
        <span className="flex items-center gap-1.5">
          {r.anciennete_jours ?? 0} j ouvré(s)
          {r.en_retard && <Badge tone="danger">En retard</Badge>}
        </span>
      ),
    },
    {
      // VX218 — niveau d'escalade YEVNT9, lisible côté DEMANDEUR (jusqu'ici
      // seuls les managers voyaient la notif d'escalade ; le demandeur ne
      // savait jamais où en était sa propre demande). `None` = jamais
      // relancé (aucune fabrication) ; seule la source `automation` est
      // balayée par ce sweep aujourd'hui, les autres n'affichent rien ici.
      id: 'niveau_escalade', header: 'Relance', width: 150,
      accessor: (r) => r.niveau_escalade || '',
      cell: (v, r) => {
        if (!r.niveau_escalade) return '—'
        const label = r.niveau_escalade === 'escalade' ? 'Escaladée' : 'Relancée'
        const tone = r.niveau_escalade === 'escalade' ? 'danger' : 'warning'
        return <Badge tone={tone}>{label}</Badge>
      },
    },
    {
      id: 'actions', header: '', width: 220, align: 'right',
      accessor: () => '',
      cell: (v, r) => {
        const key = `${r.source}-${r.id}`
        return (
          <div className="flex justify-end gap-2">
            <Button
              size="sm" variant="secondary"
              disabled={decidingKey === key}
              onClick={() => decider(r, 'approuver')}
              data-testid={`approbation-approve-${key}`}
            >
              <CheckCircle2 /> Approuver
            </Button>
            <Button
              size="sm" variant="ghost"
              disabled={decidingKey === key}
              onClick={() => decider(r, 'refuser')}
              data-testid={`approbation-reject-${key}`}
            >
              <XCircle /> Refuser
            </Button>
          </div>
        )
      },
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- decider recréé par rendu
  ], [decidingKey])

  const bulkActions = (selectedRows, _selectedKeys, clear) => [
    {
      id: 'approuver-masse', label: 'Approuver la sélection', icon: CheckCircle2,
      onClick: () => deciderEnMasse(selectedRows, 'approuver', clear),
    },
    {
      id: 'refuser-masse', label: 'Refuser la sélection', icon: XCircle, destructive: true,
      onClick: () => deciderEnMasse(selectedRows, 'refuser', clear),
    },
  ]

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-muted-foreground">Source</span>
          <Select value={source || 'all'} onValueChange={(v) => setSource(v === 'all' ? '' : v)}>
            <SelectTrigger className="w-48" aria-label="Filtrer par source"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Toutes les sources</SelectItem>
              {SOURCES.map((s) => <SelectItem key={s} value={s}>{SOURCE_LABELS[s]}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-muted-foreground">Priorité</span>
          <Select value={priorite || 'all'} onValueChange={(v) => setPriorite(v === 'all' ? '' : v)}>
            <SelectTrigger className="w-40" aria-label="Filtrer par priorité"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Toutes</SelectItem>
              <SelectItem value="haute">Haute</SelectItem>
              <SelectItem value="normale">Normale</SelectItem>
              <SelectItem value="basse">Basse</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-muted-foreground">Tri</span>
          <Select value={trier || 'default'} onValueChange={(v) => setTrier(v === 'default' ? '' : v)}>
            <SelectTrigger className="w-64" aria-label="Trier"><SelectValue /></SelectTrigger>
            <SelectContent>
              {TRI_OPTIONS.map((o) => (
                <SelectItem key={o.value || 'default'} value={o.value || 'default'}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : items.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Aucune demande en attente"
          description="Rien n'attend votre décision pour le moment."
          className="my-6"
        />
      ) : (
        <DataTable
          data={items}
          columns={columns}
          getRowId={(row) => `${row.source}-${row.id}`}
          selectable
          bulkActions={bulkActions}
          searchable
          searchPlaceholder="Rechercher une demande…"
          pageSize={25}
          aria-label="Approbations en attente"
        />
      )}

      {refuserMasse && (
        <ResponsiveDialog
          open
          onOpenChange={(o) => { if (!o) setRefuserMasse(null) }}
          title={`Refuser ${refuserMasse.items.length} demande(s)`}
          description="Un motif propre à chaque demande — le motif commun ci-dessous ne fait que pré-remplir, chaque ligne reste modifiable."
          footer={(
            <>
              <Button variant="ghost" onClick={() => setRefuserMasse(null)} disabled={refuserMasse.submitting}>
                Annuler
              </Button>
              <Button variant="destructive" onClick={confirmRefuserMasse} disabled={refuserMasse.submitting}>
                {refuserMasse.submitting ? 'Refus…' : 'Confirmer le refus'}
              </Button>
            </>
          )}
        >
          <div className="flex flex-col gap-3">
            <div className="flex items-end gap-2">
              <div className="flex flex-1 flex-col gap-1">
                <span className="text-xs font-medium text-muted-foreground">Motif commun (optionnel)</span>
                <Textarea
                  value={refuserMasse.motifCommun}
                  onChange={(e) => setRefuserMasse((s) => (s ? { ...s, motifCommun: e.target.value } : s))}
                  rows={2}
                />
              </div>
              <Button type="button" variant="outline" size="sm" onClick={appliquerMotifCommun}>
                Appliquer à tous
              </Button>
            </div>
            <ul className="flex flex-col gap-3">
              {refuserMasse.items.map((it) => {
                const key = `${it.source}-${it.id}`
                return (
                  <li key={key} className="flex flex-col gap-1 border-b border-border pb-2 last:border-0">
                    <span className="text-sm font-medium">{it.libelle || `#${it.id}`}</span>
                    <Textarea
                      aria-label={`Motif du refus — ${it.libelle || `#${it.id}`}`}
                      value={refuserMasse.motifs[key] || ''}
                      onChange={(e) => setRefuserMasse((s) => (s ? {
                        ...s, motifs: { ...s.motifs, [key]: e.target.value },
                      } : s))}
                      rows={2}
                    />
                  </li>
                )
              })}
            </ul>
          </div>
        </ResponsiveDialog>
      )}
    </div>
  )
}

export default function ApprobationsPage() {
  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Approbations en attente</h1>
        <div className="page-subtitle">
          Boîte unique — automatisations, contrats, GED, réquisitions
          installations et étapes de workflow en attente de votre décision, plus
          la gestion de vos délégations d'absence.
        </div>
      </div>

      <Tabs defaultValue="file">
        <TabsList>
          <TabsTrigger value="file">File</TabsTrigger>
          <TabsTrigger value="delegations">Délégations</TabsTrigger>
        </TabsList>
        <TabsContent value="file">
          <ApprobationsFileTab />
        </TabsContent>
        <TabsContent value="delegations">
          <DelegationsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
