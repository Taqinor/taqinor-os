import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Inbox, XCircle } from 'lucide-react'
import reportingApi from '../../api/reportingApi'
import {
  Badge, Button, DataTable, EmptyState, Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem, Spinner, toast,
} from '../../ui'

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

export default function ApprobationsPage() {
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

  const deciderEnMasse = async (selectedRows, decision, clear) => {
    let motif = ''
    if (decision === 'refuser') {
      motif = window.prompt('Motif du refus (obligatoire, appliqué à toute la sélection) :') || ''
      if (!motif.trim()) {
        toast.error('Un motif de refus est obligatoire.')
        return
      }
    }
    const payload = selectedRows.map((it) => ({ source: it.source, id: it.id }))
    try {
      const res = await reportingApi.deciderApprobationsEnMasse(payload, decision, motif)
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

  const columns = useMemo(() => [
    {
      id: 'source', header: 'Source', width: 140,
      accessor: (r) => SOURCE_LABELS[r.source] || r.source,
      cell: (v, r) => <Badge tone="neutral">{SOURCE_LABELS[r.source] || r.source}</Badge>,
    },
    { id: 'libelle', header: 'Demande', accessor: (r) => r.libelle || `#${r.id}` },
    { id: 'demandeur', header: 'Demandeur', width: 160, accessor: (r) => r.demandeur || '—' },
    {
      id: 'priorite', header: 'Priorité', width: 110,
      accessor: (r) => r.priorite || '—',
      cell: (v, r) => (r.priorite ? <Badge tone="warning">{r.priorite}</Badge> : '—'),
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
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Approbations en attente</h1>
        <div className="page-subtitle">
          Boîte unique — automatisations, contrats, GED, réquisitions
          installations et étapes de workflow en attente de votre décision.
        </div>
      </div>

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
    </div>
  )
}
