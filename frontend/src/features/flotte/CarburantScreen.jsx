import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import {
  Tabs, TabsList, TabsTrigger, TabsContent, Badge, Button, Spinner, EmptyState,
  toast, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, confirmLeaveIfDirty,
} from '../../ui'
import { ListShell } from '../../ui/module'
import flotteApi from '../../api/flotteApi'
import { formatDate, formatDateTime, formatNumber } from '../../lib/format'
import { SinistreStatutPill, InfractionStatutPill } from './statusPills'
import { SINISTRE_TYPES, INFRACTION_TYPES, TELEMATIQUE_SOURCES } from './flotte'
import useFlotteResource from './useFlotteResource'
import PleinDialog from './PleinDialog'

/* ============================================================================
   UX20 — Carburant & télématique (`/flotte/carburant`).
   ----------------------------------------------------------------------------
   Onglets : pleins de carburant, cartes carburant (anomalies), sinistres,
   infractions (PV en attente), relevés / trajets télématiques, trajets
   chantier. Coûts = coûts d'exploitation internes (jamais prix client / achat).
   ========================================================================== */

function PleinsTab() {
  const [showForm, setShowForm] = useState(false)
  const { data, loading, error, reload } = useFlotteResource(flotteApi.pleins.list, {})
  const { data: vehicules } = useFlotteResource(flotteApi.vehicules.list, {})
  const columns = useMemo(() => [
    { id: 'vehicule', header: 'Véhicule', width: 160, accessor: (r) => r.vehicule_label, cell: (v) => v || '—' },
    { id: 'date_plein', header: 'Date', width: 120, accessor: (r) => r.date_plein, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'kilometrage', header: 'Km', align: 'right', numeric: true, width: 110, searchable: false, accessor: (r) => r.kilometrage, cell: (v) => (v != null ? formatNumber(v) : '—') },
    { id: 'quantite', header: 'Quantité', align: 'right', numeric: true, width: 120, searchable: false, accessor: (r) => r.quantite, cell: (v, r) => (v != null ? `${formatNumber(v, { decimals: 2 })} ${r.unite === 'kwh' ? 'kWh' : 'L'}` : '—') },
    { id: 'prix_total', header: 'Coût', align: 'right', numeric: true, width: 120, searchable: false, accessor: (r) => Number(r.prix_total ?? 0), cell: (v) => (v ? `${formatNumber(v, { decimals: 2 })} MAD` : '—') },
    { id: 'station', header: 'Station', width: 150, accessor: (r) => r.station, cell: (v) => v || '—' },
  ], [])
  const actions = (
    <Button onClick={() => setShowForm(true)}>Nouveau plein</Button>
  )
  return (
    <>
      <ListShell title="Pleins de carburant" actions={actions} columns={columns} rows={data} loading={loading} error={error}
        exportName="pleins" searchable searchPlaceholder="Rechercher station…"
        emptyTitle="Aucun plein" emptyDescription="Aucun plein enregistré." />
      {showForm && (
        <PleinDialog
          vehicules={vehicules}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); reload(); toast.success('Plein enregistré.') }}
        />
      )}
    </>
  )
}

// WIR6/FLOTTE14 — carte « Anomalies » : le détecteur serveur
// (`CarteCarburantViewSet.anomalies`) tournait dans le vide, sans consommateur
// frontend — une fraude détectée n'était jamais montrée à personne.
function AnomaliesCard() {
  const [state, setState] = useState({ loading: true, error: null, data: null })

  const load = useCallback(() => {
    let cancelled = false
    setState({ loading: true, error: null, data: null })
    flotteApi.cartes.anomalies()
      .then((res) => { if (!cancelled) setState({ loading: false, error: null, data: res?.data || null }) })
      .catch((err) => {
        if (!cancelled) setState({ loading: false, error: err?.response?.data?.detail || 'Détection indisponible.', data: null })
      })
    return () => { cancelled = true }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  if (state.loading) {
    return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner className="size-4" /> Détection en cours…</div>
  }
  if (state.error) {
    return <EmptyState title="Indisponible" description={state.error} />
  }
  const anomalies = state.data?.anomalies || []
  if (anomalies.length === 0) {
    return (
      <div className="rounded-md border border-border p-3 text-sm text-muted-foreground">
        Aucune anomalie détectée sur le carnet de carburant ({state.data?.nb_pleins ?? 0} plein(s) analysé(s)).
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-2 rounded-md border border-warning/40 p-3">
      <p className="flex items-center gap-1.5 text-sm font-medium text-warning">
        <AlertTriangle className="size-4" aria-hidden="true" />
        {anomalies.length} anomalie(s) détectée(s)
      </p>
      <ul className="flex flex-col gap-2">
        {anomalies.map((a, i) => (
          <li key={`${a.plein_id}-${a.type}-${i}`} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
            <span>{a.message}</span>
            <span className="text-xs text-muted-foreground">
              {a.date_plein ? formatDate(a.date_plein) : '—'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// WIR43 — Création/édition d'une carte carburant : `CartesTab` était lecture
// seule malgré un backend full CRUD. `carte` fourni = édition (PATCH),
// absent = création (POST).
function CarteCarburantDialog({ carte, vehicules = [], conducteurs = [], onClose, onSaved }) {
  const [numero, setNumero] = useState(carte?.numero || '')
  const [vehiculeId, setVehiculeId] = useState(carte?.vehicule ? String(carte.vehicule) : '')
  const [conducteurId, setConducteurId] = useState(carte?.conducteur ? String(carte.conducteur) : '')
  const [plafond, setPlafond] = useState(carte?.plafond != null ? String(carte.plafond) : '')
  const [notes, setNotes] = useState(carte?.notes || '')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(numero.trim())
  const dirty = carte
    ? Boolean(
      numero !== (carte.numero || '') || vehiculeId !== (carte.vehicule ? String(carte.vehicule) : '')
      || conducteurId !== (carte.conducteur ? String(carte.conducteur) : '')
      || plafond !== (carte.plafond != null ? String(carte.plafond) : '') || notes !== (carte.notes || ''),
    )
    : Boolean(numero || vehiculeId || conducteurId || plafond || notes)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    const payload = {
      numero: numero.trim(),
      vehicule: vehiculeId ? Number(vehiculeId) : null,
      conducteur: conducteurId ? Number(conducteurId) : null,
      plafond: plafond === '' ? undefined : Number(plafond),
      notes,
    }
    try {
      if (carte) {
        await flotteApi.cartes.update(carte.id, payload)
      } else {
        await flotteApi.cartes.create(payload)
      }
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.plafond
        || data?.detail
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
          <DialogTitle>{carte ? 'Modifier la carte carburant' : 'Nouvelle carte carburant'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="carte-numero">N° carte</Label>
            <Input id="carte-numero" autoFocus value={numero} onChange={(e) => setNumero(e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="carte-vehicule">Véhicule (option.)</Label>
              <select
                id="carte-vehicule"
                value={vehiculeId}
                onChange={(e) => setVehiculeId(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Non rattaché —</option>
                {vehicules.map((v) => (
                  <option key={v.id} value={v.id}>{v.immatriculation}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="carte-conducteur">Conducteur (option.)</Label>
              <select
                id="carte-conducteur"
                value={conducteurId}
                onChange={(e) => setConducteurId(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Non rattaché —</option>
                {conducteurs.map((c) => (
                  <option key={c.id} value={c.id}>{c.nom}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="carte-plafond">Plafond (MAD, option.)</Label>
            <Input id="carte-plafond" type="number" step="any" value={plafond} onChange={(e) => setPlafond(e.target.value)} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="carte-notes">Notes</Label>
            <Input id="carte-notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : carte ? 'Enregistrer' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function CartesTab() {
  const { data, loading, error, reload } = useFlotteResource(flotteApi.cartes.list, {})
  const { data: vehicules } = useFlotteResource(flotteApi.vehicules.list, {})
  const { data: conducteurs } = useFlotteResource(flotteApi.conducteurs.list, {})
  const [editing, setEditing] = useState(null) // carte en édition, ou {} pour création
  const columns = useMemo(() => [
    { id: 'numero', header: 'N° carte', width: 160, accessor: (r) => r.numero, cell: (v) => (v ? <span className="font-mono text-xs">{v}</span> : '—') },
    { id: 'vehicule', header: 'Véhicule', width: 160, accessor: (r) => r.vehicule_label, cell: (v) => v || '—' },
    { id: 'plafond', header: 'Plafond', align: 'right', numeric: true, width: 130, searchable: false, accessor: (r) => Number(r.plafond ?? 0), cell: (v) => (v ? `${formatNumber(v, { decimals: 0 })} MAD` : '—') },
    {
      id: 'actif',
      header: 'Statut',
      width: 100,
      searchable: false,
      accessor: (r) => (r.actif ? 'Active' : 'Inactive'),
      cell: (_v, r) => (r.actif ? <Badge tone="success">Active</Badge> : <Badge tone="neutral">Inactive</Badge>),
    },
  ], [])

  const actions = (
    <Button onClick={() => setEditing({})}>Nouvelle carte</Button>
  )
  const rowActions = (row) => [
    { id: 'modifier', label: 'Modifier', onClick: () => setEditing(row) },
  ]

  return (
    <div className="flex flex-col gap-4">
      <AnomaliesCard />
      <ListShell title="Cartes carburant" actions={actions} rowActions={rowActions} columns={columns} rows={data} loading={loading} error={error}
        exportName="cartes-carburant" emptyTitle="Aucune carte" emptyDescription="Aucune carte carburant enregistrée." />
      {editing && (
        <CarteCarburantDialog
          carte={editing.id ? editing : null}
          vehicules={vehicules}
          conducteurs={conducteurs}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); reload(); toast.success(editing.id ? 'Carte modifiée.' : 'Carte créée.') }}
        />
      )}
    </div>
  )
}

function SinistresTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.sinistres.list, {})
  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 160, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'date_sinistre', header: 'Date', width: 120, accessor: (r) => r.date_sinistre, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'type', header: 'Type', width: 160, accessor: (r) => r.type_sinistre_display || SINISTRE_TYPES[r.type_sinistre] || r.type_sinistre, cell: (v) => v || '—' },
    { id: 'lieu', header: 'Lieu', width: 160, accessor: (r) => r.lieu, cell: (v) => v || '—' },
    { id: 'montant_estime', header: 'Montant estimé', align: 'right', numeric: true, width: 150, searchable: false, accessor: (r) => Number(r.montant_estime ?? 0), cell: (v) => (v ? `${formatNumber(v, { decimals: 0 })} MAD` : '—') },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut, cell: (v) => <SinistreStatutPill status={v} /> },
  ], [])
  return (
    <ListShell title="Sinistres" columns={columns} rows={data} loading={loading} error={error}
      exportName="sinistres" emptyTitle="Aucun sinistre" emptyDescription="Aucun sinistre déclaré." />
  )
}

function InfractionsTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.infractions.list, {})
  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 160, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'conducteur', header: 'Conducteur', width: 150, accessor: (r) => r.conducteur_nom, cell: (v) => v || '—' },
    { id: 'date_infraction', header: 'Date', width: 120, accessor: (r) => r.date_infraction, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'type', header: 'Type', width: 150, accessor: (r) => r.type_infraction_display || INFRACTION_TYPES[r.type_infraction] || r.type_infraction, cell: (v) => v || '—' },
    { id: 'reference_pv', header: 'Réf. PV', width: 130, accessor: (r) => r.reference_pv, cell: (v) => v || '—' },
    { id: 'montant_amende', header: 'Amende', align: 'right', numeric: true, width: 120, searchable: false, accessor: (r) => Number(r.montant_amende ?? 0), cell: (v) => (v ? `${formatNumber(v, { decimals: 0 })} MAD` : '—') },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut, cell: (v) => <InfractionStatutPill status={v} /> },
  ], [])
  return (
    <ListShell title="Infractions (PV)" subtitle="PV en attente de règlement ou contestés."
      columns={columns} rows={data} loading={loading} error={error}
      exportName="infractions" emptyTitle="Aucune infraction" emptyDescription="Aucune infraction enregistrée." />
  )
}

function TelematiqueTab() {
  const { data: releves, loading: lr, error: er } = useFlotteResource(flotteApi.relevesTelematiques.list, {})
  const { data: trajets, loading: lt, error: et } = useFlotteResource(flotteApi.trajetsTelematiques.list, {})

  const relevesCols = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 160, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'horodatage', header: 'Horodatage', width: 170, accessor: (r) => r.horodatage, cell: (v) => (v ? formatDateTime(v) : '—') },
    { id: 'odometre', header: 'Odomètre', align: 'right', numeric: true, width: 120, searchable: false, accessor: (r) => r.odometre, cell: (v) => (v != null ? `${formatNumber(v)} km` : '—') },
    { id: 'source', header: 'Source', width: 150, accessor: (r) => r.source_display || TELEMATIQUE_SOURCES[r.source] || r.source, cell: (v) => v || '—' },
    {
      // XFLT25 — codes défaut moteur (DTC) remontés par le relevé télématique.
      id: 'codes_defaut',
      header: 'Codes défaut (DTC)',
      width: 180,
      searchable: false,
      accessor: (r) => (Array.isArray(r.codes_defaut) ? r.codes_defaut.join(', ') : ''),
      cell: (v) => (v ? <span className="font-mono text-xs text-warning">{v}</span> : <span className="text-muted-foreground">—</span>),
    },
  ], [])
  const trajetsCols = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 160, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'debut', header: 'Début', width: 170, accessor: (r) => r.debut, cell: (v) => (v ? formatDateTime(v) : '—') },
    { id: 'fin', header: 'Fin', width: 170, accessor: (r) => r.fin, cell: (v) => (v ? formatDateTime(v) : '—') },
    { id: 'distance_km', header: 'Distance', align: 'right', numeric: true, width: 120, searchable: false, accessor: (r) => r.distance_km, cell: (v) => (v != null ? `${formatNumber(v, { decimals: 1 })} km` : '—') },
    { id: 'vitesse', header: 'Vit. moy.', align: 'right', numeric: true, width: 120, searchable: false, accessor: (r) => r.vitesse_moyenne_kmh, cell: (v) => (v != null ? `${formatNumber(v)} km/h` : '—') },
  ], [])
  return (
    <div className="flex flex-col gap-6">
      <ListShell title="Relevés télématiques" columns={relevesCols} rows={releves} loading={lr} error={er}
        exportName="releves-telematiques" emptyTitle="Aucun relevé" emptyDescription="Aucun relevé télématique." />
      <ListShell title="Trajets télématiques" columns={trajetsCols} rows={trajets} loading={lt} error={et}
        exportName="trajets-telematiques" emptyTitle="Aucun trajet" emptyDescription="Aucun trajet reconstruit." />
    </div>
  )
}

function TrajetsChantierTab() {
  const { data, loading, error } = useFlotteResource(flotteApi.trajetsChantier.list, {})
  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 160, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'date_trajet', header: 'Date', width: 120, accessor: (r) => r.date_trajet, cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'motif', header: 'Motif', width: 220, accessor: (r) => r.motif, cell: (v) => v || '—' },
    { id: 'distance_km', header: 'Distance', align: 'right', numeric: true, width: 120, searchable: false, accessor: (r) => r.distance_km, cell: (v) => (v != null ? `${formatNumber(v, { decimals: 1 })} km` : '—') },
  ], [])
  return (
    <ListShell title="Trajets chantier" columns={columns} rows={data} loading={loading} error={error}
      exportName="trajets-chantier" emptyTitle="Aucun trajet" emptyDescription="Aucun trajet chantier enregistré." />
  )
}

export default function CarburantScreen() {
  return (
    <div className="page flex flex-col gap-4">
      <h2 className="font-display text-xl font-semibold tracking-tight">Carburant, sinistres & télématique</h2>
      <Tabs defaultValue="pleins">
        <TabsList className="flex-wrap">
          <TabsTrigger value="pleins">Carburant</TabsTrigger>
          <TabsTrigger value="cartes">Cartes</TabsTrigger>
          <TabsTrigger value="sinistres">Sinistres</TabsTrigger>
          <TabsTrigger value="infractions">Infractions</TabsTrigger>
          <TabsTrigger value="telematique">Télématique</TabsTrigger>
          <TabsTrigger value="chantier">Trajets chantier</TabsTrigger>
        </TabsList>
        <TabsContent value="pleins"><PleinsTab /></TabsContent>
        <TabsContent value="cartes"><CartesTab /></TabsContent>
        <TabsContent value="sinistres"><SinistresTab /></TabsContent>
        <TabsContent value="infractions"><InfractionsTab /></TabsContent>
        <TabsContent value="telematique"><TelematiqueTab /></TabsContent>
        <TabsContent value="chantier"><TrajetsChantierTab /></TabsContent>
      </Tabs>
    </div>
  )
}
