import { useMemo, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import {
  Tabs, TabsList, TabsTrigger, TabsContent, Badge, Button, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import { ListShell, EcheanceCenter } from '../../ui/module'
import flotteApi from '../../api/flotteApi'
import { formatDate, formatNumber } from '../../lib/format'
import {
  EntretienStatutPill, OrStatutPill, SignalementStatutPill,
  SignalementGravitePill,
} from './statusPills'
import { PNEU_POSITIONS, PNEU_STATUTS } from './flotte'
import useFlotteResource from './useFlotteResource'
import SignalementDialog from './SignalementDialog'
import GarageDialog from './GarageDialog'
import PlanRolloutDialog from './PlanRolloutDialog'
import GarantiesFlotteTab from './GarantiesFlotteTab'

/* ============================================================================
   UX18 — Entretien (`/flotte/entretien`).
   ----------------------------------------------------------------------------
   Onglets : plans préventifs, échéances d'entretien (timeline via
   `EcheanceCenter`), garages, ordres de réparation (main-d'œuvre + pièces),
   pneumatiques, pièces. Les coûts affichés sont des coûts d'EXPLOITATION
   internes (jamais des prix client ni des prix d'achat/marge).
   ========================================================================== */

// WIR42 — Dialogue de création d'un plan d'entretien (`PlanEntretienViewSet`
// full CRUD) : avant cette dialogue, seul « Dupliquer sur… » existait — le
// tout premier plan d'un type d'actif n'avait aucun chemin de création.
function PlanEntretienDialog({ actifs = [], onClose, onSaved }) {
  const [actifFlotte, setActifFlotte] = useState('')
  const [typeEntretien, setTypeEntretien] = useState('')
  const [intervalleKm, setIntervalleKm] = useState('')
  const [intervalleJours, setIntervalleJours] = useState('')
  const [intervalleHeures, setIntervalleHeures] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(
    actifFlotte && typeEntretien.trim()
    && (intervalleKm || intervalleJours || intervalleHeures),
  )
  const dirty = Boolean(
    actifFlotte || typeEntretien || intervalleKm || intervalleJours
    || intervalleHeures || notes,
  )
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.plansEntretien.create({
        actif_flotte: Number(actifFlotte),
        type_entretien: typeEntretien.trim(),
        intervalle_km: intervalleKm === '' ? undefined : Number(intervalleKm),
        intervalle_jours: intervalleJours === '' ? undefined : Number(intervalleJours),
        intervalle_heures: intervalleHeures === '' ? undefined : Number(intervalleHeures),
        notes,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau plan d’entretien</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="plan-actif">Actif (véhicule ou engin)</Label>
            <select
              id="plan-actif"
              autoFocus
              value={actifFlotte}
              onChange={(e) => setActifFlotte(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {actifs.map((a) => (
                <option key={a.id} value={a.id}>{a.label || `#${a.id}`}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="plan-type">Type d’entretien</Label>
            <Input id="plan-type" value={typeEntretien} onChange={(e) => setTypeEntretien(e.target.value)} placeholder="Ex. : vidange" />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="plan-interv-km">Intervalle (km)</Label>
              <Input id="plan-interv-km" type="number" step="any" value={intervalleKm} onChange={(e) => setIntervalleKm(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="plan-interv-jours">Intervalle (jours)</Label>
              <Input id="plan-interv-jours" type="number" step="any" value={intervalleJours} onChange={(e) => setIntervalleJours(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="plan-interv-heures">Intervalle (heures)</Label>
              <Input id="plan-interv-heures" type="number" step="any" value={intervalleHeures} onChange={(e) => setIntervalleHeures(e.target.value)} />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">Au moins un intervalle (km / jours / heures) est requis.</p>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="plan-notes">Notes</Label>
            <Textarea id="plan-notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function PlansTab({ actifs }) {
  const { data, loading, error, reload } = useFlotteResource(flotteApi.plansEntretien.list, {})
  const [rolloutPlan, setRolloutPlan] = useState(null)
  const [showForm, setShowForm] = useState(false)

  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 200, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'type_entretien', header: 'Type', width: 180, accessor: (r) => r.type_entretien, cell: (v) => v || '—' },
    { id: 'intervalle_km', header: 'Interv. km', align: 'right', numeric: true, width: 120, accessor: (r) => r.intervalle_km, cell: (v) => (v ? `${formatNumber(v)} km` : '—') },
    { id: 'intervalle_jours', header: 'Interv. jours', align: 'right', numeric: true, width: 130, accessor: (r) => r.intervalle_jours, cell: (v) => (v ? `${v} j` : '—') },
    {
      id: 'actif_bool',
      header: 'Plan',
      width: 100,
      searchable: false,
      accessor: (r) => (r.actif ? 'Actif' : 'Inactif'),
      cell: (_v, r) => (r.actif ? <Badge tone="success">Actif</Badge> : <Badge tone="neutral">Inactif</Badge>),
    },
  ], [])

  const rowActions = (row) => [
    { id: 'rollout', label: 'Dupliquer sur…', onClick: () => setRolloutPlan(row) },
  ]

  const actions = (
    <Button onClick={() => setShowForm(true)}>Nouveau plan</Button>
  )

  return (
    <>
      <ListShell
        title="Plans d’entretien préventif"
        actions={actions}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        rowActions={rowActions}
        exportName="plans-entretien"
        emptyTitle="Aucun plan"
        emptyDescription="Aucun plan d’entretien défini."
      />
      {rolloutPlan && (
        <PlanRolloutDialog
          plan={rolloutPlan}
          actifs={actifs}
          onClose={() => setRolloutPlan(null)}
          onSaved={() => { reload(); toast.success('Plan dupliqué.') }}
        />
      )}
      {showForm && (
        <PlanEntretienDialog
          actifs={actifs}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); reload(); toast.success('Plan créé.') }}
        />
      )}
    </>
  )
}

function EcheancesTab() {
  const { data, loading, error, reload } = useFlotteResource(flotteApi.echeancesEntretien.list, { ouvertes: 'true' })
  const [generating, setGenerating] = useState(false)

  const generer = async () => {
    setGenerating(true)
    try {
      const res = await flotteApi.echeancesEntretien.generer()
      const nb = res?.data?.nb_creees ?? 0
      toast.success(nb > 0 ? `${nb} échéance(s) générée(s).` : 'Aucune nouvelle échéance due.')
      reload()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Génération impossible.')
    } finally {
      setGenerating(false)
    }
  }

  const items = useMemo(
    () => (data || []).map((e) => ({
      id: `ent-${e.id}`,
      label: `${e.type_entretien || 'Entretien'} — ${e.actif_label || ''}`.trim(),
      date: e.due_le,
      meta: e.statut_display || e.statut,
    })),
    [data],
  )
  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 200, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'type_entretien', header: 'Type', width: 180, accessor: (r) => r.type_entretien, cell: (v) => v || '—' },
    { id: 'due_le', header: 'Échéance', width: 130, accessor: (r) => r.due_le, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'due_km', header: 'Échéance km', align: 'right', numeric: true, width: 130, accessor: (r) => r.due_km, cell: (v) => (v ? `${formatNumber(v)} km` : '—') },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut, cell: (v) => <EntretienStatutPill status={v} /> },
  ], [])

  const actions = (
    <Button onClick={generer} disabled={generating}>
      {generating ? 'Génération…' : 'Générer les échéances'}
    </Button>
  )

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
      <ListShell
        title="Échéances d’entretien"
        actions={actions}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        exportName="echeances-entretien"
        emptyTitle="Aucune échéance ouverte"
        emptyDescription="Aucune échéance d’entretien à traiter."
      />
      <EcheanceCenter title="Prochains entretiens" items={items} loading={loading} max={12} />
    </div>
  )
}

function GaragesTab() {
  const [showForm, setShowForm] = useState(false)
  const { data, loading, error, reload } = useFlotteResource(flotteApi.garages.list, {})
  const columns = useMemo(() => [
    { id: 'nom', header: 'Garage', width: 200, accessor: (r) => r.nom, cell: (v) => v || '—' },
    { id: 'adresse', header: 'Adresse', width: 240, accessor: (r) => r.adresse, cell: (v) => v || '—' },
    { id: 'telephone', header: 'Téléphone', width: 150, accessor: (r) => r.telephone, cell: (v) => v || '—' },
    // XFLT26 — ICE/IF (préparation e-facturation DGI), affichés en lecture.
    { id: 'ice', header: 'ICE', width: 140, accessor: (r) => r.ice, cell: (v) => (v ? <span className="font-mono text-xs">{v}</span> : '—') },
    { id: 'identifiant_fiscal', header: 'IF', width: 120, accessor: (r) => r.identifiant_fiscal, cell: (v) => v || '—' },
    {
      id: 'actif',
      header: 'Statut',
      width: 100,
      searchable: false,
      accessor: (r) => (r.actif ? 'Actif' : 'Inactif'),
      cell: (_v, r) => (r.actif ? <Badge tone="success">Actif</Badge> : <Badge tone="neutral">Inactif</Badge>),
    },
  ], [])
  const actions = (
    <Button onClick={() => setShowForm(true)}>Nouveau garage</Button>
  )
  return (
    <>
      <ListShell
        title="Garages"
        actions={actions}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        exportName="garages"
        emptyTitle="Aucun garage"
        emptyDescription="Aucun garage référencé."
      />
      {showForm && (
        <GarageDialog
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); reload(); toast.success('Garage enregistré.') }}
        />
      )}
    </>
  )
}

// WIR45(a) — Dialogue « Nouvel OR » : `OrdresTab` n'offrait que « Approuver le
// devis » (seul chemin de création = conversion d'un signalement) — aucun
// chemin pour une réparation planifiée SANS signalement préalable.
function OrdreReparationDialog({ actifs = [], garages = [], onClose, onSaved }) {
  const [actifFlotte, setActifFlotte] = useState('')
  const [garage, setGarage] = useState('')
  const [description, setDescription] = useState('')
  const [dateOuverture, setDateOuverture] = useState('')
  const [coutMainOeuvre, setCoutMainOeuvre] = useState('')
  const [coutPieces, setCoutPieces] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(actifFlotte && dateOuverture)
  const dirty = Boolean(
    actifFlotte || garage || description || dateOuverture || coutMainOeuvre || coutPieces,
  )
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.ordresReparation.create({
        actif_flotte: Number(actifFlotte),
        garage: garage ? Number(garage) : null,
        description,
        date_ouverture: dateOuverture,
        cout_main_oeuvre: coutMainOeuvre === '' ? undefined : Number(coutMainOeuvre),
        cout_pieces: coutPieces === '' ? undefined : Number(coutPieces),
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvel ordre de réparation</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="or-actif">Actif (véhicule ou engin)</Label>
            <select
              id="or-actif"
              autoFocus
              value={actifFlotte}
              onChange={(e) => setActifFlotte(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {actifs.map((a) => (
                <option key={a.id} value={a.id}>{a.label || `#${a.id}`}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="or-garage">Garage (option.)</Label>
              <select
                id="or-garage"
                value={garage}
                onChange={(e) => setGarage(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Non choisi —</option>
                {garages.map((g) => (
                  <option key={g.id} value={g.id}>{g.nom}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="or-date-ouverture">Date d’ouverture</Label>
              <Input id="or-date-ouverture" type="date" value={dateOuverture} onChange={(e) => setDateOuverture(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="or-description">Description des travaux</Label>
            <Textarea id="or-description" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="or-cout-mo">Coût main-d’œuvre (MAD)</Label>
              <Input id="or-cout-mo" type="number" step="any" value={coutMainOeuvre} onChange={(e) => setCoutMainOeuvre(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="or-cout-pieces">Coût pièces (MAD)</Label>
              <Input id="or-cout-pieces" type="number" step="any" value={coutPieces} onChange={(e) => setCoutPieces(e.target.value)} />
            </div>
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function OrdresTab({ actifs }) {
  const { data, loading, error, reload } = useFlotteResource(flotteApi.ordresReparation.list, {})
  const { data: garages } = useFlotteResource(flotteApi.garages.list, {})
  const [showForm, setShowForm] = useState(false)

  const approuver = async (row) => {
    try {
      await flotteApi.ordresReparation.approuver(row.id)
      toast.success('Devis approuvé.')
      reload()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Approbation impossible.')
    }
  }

  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 180, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'garage', header: 'Garage', width: 160, accessor: (r) => r.garage_nom, cell: (v) => v || '—' },
    // ZCTR10 — type de service/entretien (référentiel éditable) ; absence = "non catégorisé".
    { id: 'type_service', header: 'Type de service', width: 160, accessor: (r) => r.type_service_libelle, cell: (v) => v || 'Non catégorisé' },
    { id: 'description', header: 'Description', width: 220, accessor: (r) => r.description, cell: (v) => v || '—' },
    { id: 'date_ouverture', header: 'Ouvert le', width: 130, accessor: (r) => r.date_ouverture, cell: (v) => (v ? formatDate(v) : '—') },
    {
      id: 'cout_total',
      header: 'Coût total',
      align: 'right',
      numeric: true,
      width: 130,
      searchable: false,
      accessor: (r) => Number(r.cout_total ?? 0),
      cell: (v) => (v ? `${formatNumber(v, { decimals: 2 })} MAD` : '—'),
    },
    {
      // XFLT14 — avertissement non bloquant : réparation sous garantie active.
      id: 'sous_garantie',
      header: 'Garantie',
      width: 110,
      searchable: false,
      accessor: (r) => (r.sous_garantie ? 'Sous garantie' : ''),
      cell: (_v, r) => (r.sous_garantie
        ? (
          <span className="inline-flex items-center gap-1 text-xs text-warning">
            <AlertTriangle className="size-3.5" aria-hidden="true" /> Sous garantie
          </span>
        )
        : <span className="text-muted-foreground">—</span>),
    },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut, cell: (v) => <OrStatutPill status={v} /> },
  ], [])

  const rowActions = (row) => (
    row.statut === 'devis_recu'
      ? [{ id: 'approuver', label: 'Approuver le devis', onClick: () => approuver(row) }]
      : []
  )

  const actions = (
    <Button onClick={() => setShowForm(true)}>Nouvel OR</Button>
  )

  return (
    <>
      <ListShell
        title="Ordres de réparation"
        subtitle="Main-d’œuvre + pièces (coûts d’exploitation internes)."
        actions={actions}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        rowActions={rowActions}
        exportName="ordres-reparation"
        emptyTitle="Aucun ordre"
        emptyDescription="Aucun ordre de réparation ouvert."
      />
      {showForm && (
        <OrdreReparationDialog
          actifs={actifs}
          garages={garages}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); reload(); toast.success('Ordre de réparation créé.') }}
        />
      )}
    </>
  )
}

function SignalementsTab({ actifs }) {
  const [showForm, setShowForm] = useState(false)
  const { data, loading, error, reload } = useFlotteResource(flotteApi.signalements.list, {})

  const convertir = async (row) => {
    try {
      await flotteApi.signalements.convertirEnOr(row.id)
      toast.success('Converti en ordre de réparation.')
      reload()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Conversion impossible.')
    }
  }

  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 170, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'description', header: 'Description', width: 260, accessor: (r) => r.description, cell: (v) => v || '—' },
    { id: 'auteur', header: 'Signalé par', width: 150, accessor: (r) => r.auteur_nom, cell: (v) => v || '—' },
    { id: 'gravite', header: 'Gravité', width: 120, accessor: (r) => r.gravite, cell: (v) => <SignalementGravitePill status={v} /> },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut, cell: (v) => <SignalementStatutPill status={v} /> },
    {
      id: 'ordre_reparation',
      header: 'OR lié',
      width: 100,
      searchable: false,
      accessor: (r) => (r.ordre_reparation ? 'Oui' : ''),
      cell: (_v, r) => (r.ordre_reparation ? <Badge tone="success">#{r.ordre_reparation}</Badge> : <span className="text-muted-foreground">—</span>),
    },
  ], [])

  const rowActions = (row) => (
    row.ordre_reparation
      ? []
      : [{ id: 'convertir', label: 'Convertir en ordre de réparation', onClick: () => convertir(row) }]
  )

  const actions = (
    <Button onClick={() => setShowForm(true)}>Signaler un problème</Button>
  )

  return (
    <>
      <ListShell
        title="Signalements"
        subtitle="Anomalies déposées par les conducteurs — convertibles en ordre de réparation."
        actions={actions}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        rowActions={rowActions}
        exportName="signalements"
        emptyTitle="Aucun signalement"
        emptyDescription="Aucune anomalie signalée."
      />
      {showForm && (
        <SignalementDialog
          actifs={actifs}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); reload(); toast.success('Signalement enregistré.') }}
        />
      )}
    </>
  )
}

// WIR45(b) — Dialogue de création d'un pneumatique (`PneumatiqueViewSet` full
// CRUD, `PneusTab` était lecture seule).
function PneumatiqueDialog({ vehicules = [], onClose, onSaved }) {
  const [vehiculeId, setVehiculeId] = useState('')
  const [position, setPosition] = useState('av_g')
  const [marque, setMarque] = useState('')
  const [dimension, setDimension] = useState('')
  const [dateMontage, setDateMontage] = useState('')
  const [kmMontage, setKmMontage] = useState('')
  const [cout, setCout] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(vehiculeId)
  const dirty = Boolean(
    vehiculeId || marque || dimension || dateMontage || kmMontage || cout || position !== 'av_g',
  )
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.pneumatiques.create({
        vehicule: Number(vehiculeId),
        position,
        marque,
        dimension,
        date_montage: dateMontage || null,
        km_montage: kmMontage === '' ? undefined : Number(kmMontage),
        cout: cout === '' ? undefined : Number(cout),
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau pneumatique</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pneu-vehicule">Véhicule</Label>
              <select
                id="pneu-vehicule"
                autoFocus
                value={vehiculeId}
                onChange={(e) => setVehiculeId(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Choisir —</option>
                {vehicules.map((v) => (
                  <option key={v.id} value={v.id}>{v.immatriculation}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pneu-position">Position</Label>
              <select
                id="pneu-position"
                value={position}
                onChange={(e) => setPosition(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {Object.entries(PNEU_POSITIONS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pneu-marque">Marque</Label>
              <Input id="pneu-marque" value={marque} onChange={(e) => setMarque(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pneu-dimension">Dimension</Label>
              <Input id="pneu-dimension" value={dimension} onChange={(e) => setDimension(e.target.value)} placeholder="Ex. : 205/55 R16" />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pneu-date-montage">Date de montage</Label>
              <Input id="pneu-date-montage" type="date" value={dateMontage} onChange={(e) => setDateMontage(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pneu-km-montage">Km au montage</Label>
              <Input id="pneu-km-montage" type="number" step="any" value={kmMontage} onChange={(e) => setKmMontage(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pneu-cout">Coût d’achat (MAD)</Label>
              <Input id="pneu-cout" type="number" step="any" value={cout} onChange={(e) => setCout(e.target.value)} />
            </div>
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function PneusTab() {
  const { data, loading, error, reload } = useFlotteResource(flotteApi.pneumatiques.list, {})
  const { data: vehicules } = useFlotteResource(flotteApi.vehicules.list, {})
  const [showForm, setShowForm] = useState(false)
  const columns = useMemo(() => [
    { id: 'vehicule', header: 'Véhicule', width: 170, accessor: (r) => r.vehicule_label, cell: (v) => v || '—' },
    { id: 'position', header: 'Position', width: 130, accessor: (r) => r.position_display || PNEU_POSITIONS[r.position] || r.position, cell: (v) => v || '—' },
    { id: 'marque', header: 'Marque', width: 140, accessor: (r) => r.marque, cell: (v) => v || '—' },
    { id: 'dimension', header: 'Dimension', width: 130, accessor: (r) => r.dimension, cell: (v) => v || '—' },
    { id: 'date_montage', header: 'Montage', width: 120, accessor: (r) => r.date_montage, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'statut', header: 'Statut', width: 110, accessor: (r) => r.statut_display || PNEU_STATUTS[r.statut] || r.statut, cell: (v) => v || '—' },
  ], [])

  const actions = (
    <Button onClick={() => setShowForm(true)}>Nouveau pneu</Button>
  )

  return (
    <>
      <ListShell
        title="Pneumatiques"
        actions={actions}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        exportName="pneumatiques"
        emptyTitle="Aucun pneu"
        emptyDescription="Aucun pneumatique enregistré."
      />
      {showForm && (
        <PneumatiqueDialog
          vehicules={vehicules}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); reload(); toast.success('Pneumatique enregistré.') }}
        />
      )}
    </>
  )
}

// WIR45(b) — Dialogue de création d'une pièce consommée (`PieceFlotteViewSet`
// full CRUD, `PiecesTab` était lecture seule). Rattachement optionnel à un
// ordre de réparation.
function PieceDialog({ vehicules = [], ordres = [], onClose, onSaved }) {
  const [vehiculeId, setVehiculeId] = useState('')
  const [ordreReparationId, setOrdreReparationId] = useState('')
  const [designation, setDesignation] = useState('')
  const [reference, setReference] = useState('')
  const [quantite, setQuantite] = useState('1')
  const [coutUnitaire, setCoutUnitaire] = useState('')
  const [datePose, setDatePose] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(vehiculeId && designation.trim())
  const dirty = Boolean(
    vehiculeId || ordreReparationId || designation || reference
    || coutUnitaire || datePose || quantite !== '1',
  )
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.pieces.create({
        vehicule: Number(vehiculeId),
        ordre_reparation: ordreReparationId ? Number(ordreReparationId) : null,
        designation: designation.trim(),
        reference,
        quantite: quantite === '' ? undefined : Number(quantite),
        cout_unitaire: coutUnitaire === '' ? undefined : Number(coutUnitaire),
        date_pose: datePose || null,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvelle pièce consommée</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="piece-vehicule">Véhicule</Label>
              <select
                id="piece-vehicule"
                autoFocus
                value={vehiculeId}
                onChange={(e) => setVehiculeId(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Choisir —</option>
                {vehicules.map((v) => (
                  <option key={v.id} value={v.id}>{v.immatriculation}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="piece-ordre">Ordre de réparation (option.)</Label>
              <select
                id="piece-ordre"
                value={ordreReparationId}
                onChange={(e) => setOrdreReparationId(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Non rattachée —</option>
                {ordres.map((o) => (
                  <option key={o.id} value={o.id}>#{o.id} — {o.actif_label || ''}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="piece-designation">Désignation</Label>
            <Input id="piece-designation" value={designation} onChange={(e) => setDesignation(e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="piece-reference">Référence</Label>
              <Input id="piece-reference" value={reference} onChange={(e) => setReference(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="piece-date-pose">Posée le</Label>
              <Input id="piece-date-pose" type="date" value={datePose} onChange={(e) => setDatePose(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="piece-quantite">Quantité</Label>
              <Input id="piece-quantite" type="number" step="any" value={quantite} onChange={(e) => setQuantite(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="piece-cout-unitaire">Coût unitaire (MAD)</Label>
              <Input id="piece-cout-unitaire" type="number" step="any" value={coutUnitaire} onChange={(e) => setCoutUnitaire(e.target.value)} />
            </div>
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function PiecesTab() {
  const { data, loading, error, reload } = useFlotteResource(flotteApi.pieces.list, {})
  const { data: vehicules } = useFlotteResource(flotteApi.vehicules.list, {})
  const { data: ordres } = useFlotteResource(flotteApi.ordresReparation.list, {})
  const [showForm, setShowForm] = useState(false)
  const columns = useMemo(() => [
    { id: 'vehicule', header: 'Véhicule', width: 170, accessor: (r) => r.vehicule_label, cell: (v) => v || '—' },
    { id: 'designation', header: 'Désignation', width: 220, accessor: (r) => r.designation, cell: (v) => v || '—' },
    { id: 'reference', header: 'Référence', width: 140, accessor: (r) => r.reference, cell: (v) => v || '—' },
    { id: 'quantite', header: 'Qté', align: 'right', numeric: true, width: 80, accessor: (r) => r.quantite, cell: (v) => (v != null ? v : '—') },
    {
      id: 'cout_total',
      header: 'Coût',
      align: 'right',
      numeric: true,
      width: 130,
      searchable: false,
      accessor: (r) => Number(r.cout_total ?? 0),
      cell: (v) => (v ? `${formatNumber(v, { decimals: 2 })} MAD` : '—'),
    },
    { id: 'date_pose', header: 'Posée le', width: 120, accessor: (r) => r.date_pose, cell: (v) => (v ? formatDate(v) : '—') },
  ], [])

  const actions = (
    <Button onClick={() => setShowForm(true)}>Nouvelle pièce</Button>
  )

  return (
    <>
      <ListShell
        title="Pièces"
        subtitle="Pièces consommées (coûts d’exploitation internes)."
        actions={actions}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        exportName="pieces"
        emptyTitle="Aucune pièce"
        emptyDescription="Aucune pièce enregistrée."
      />
      {showForm && (
        <PieceDialog
          vehicules={vehicules}
          ordres={ordres}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); reload(); toast.success('Pièce enregistrée.') }}
        />
      )}
    </>
  )
}

export default function EntretienScreen() {
  // Charge les actifs une fois pour alimenter le formulaire de signalement
  // et le rollout de plans d'entretien.
  const { data: actifs } = useFlotteResource(flotteApi.actifs.list, {})

  return (
    <div className="page flex flex-col gap-4">
      <h2 className="font-display text-xl font-semibold tracking-tight">Entretien & réparations</h2>
      <Tabs defaultValue="echeances">
        <TabsList className="flex-wrap">
          <TabsTrigger value="echeances">Échéances</TabsTrigger>
          <TabsTrigger value="plans">Plans</TabsTrigger>
          <TabsTrigger value="ordres">Ordres de réparation</TabsTrigger>
          <TabsTrigger value="signalements">Signalements</TabsTrigger>
          <TabsTrigger value="garages">Garages</TabsTrigger>
          <TabsTrigger value="pneus">Pneumatiques</TabsTrigger>
          <TabsTrigger value="pieces">Pièces</TabsTrigger>
          <TabsTrigger value="garanties">Garanties</TabsTrigger>
        </TabsList>
        <TabsContent value="echeances"><EcheancesTab /></TabsContent>
        <TabsContent value="plans"><PlansTab actifs={actifs} /></TabsContent>
        <TabsContent value="ordres"><OrdresTab actifs={actifs} /></TabsContent>
        <TabsContent value="signalements"><SignalementsTab actifs={actifs} /></TabsContent>
        <TabsContent value="garages"><GaragesTab /></TabsContent>
        <TabsContent value="pneus"><PneusTab /></TabsContent>
        <TabsContent value="pieces"><PiecesTab /></TabsContent>
        <TabsContent value="garanties"><GarantiesFlotteTab actifs={actifs} /></TabsContent>
      </Tabs>
    </div>
  )
}
