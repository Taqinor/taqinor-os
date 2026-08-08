import { useEffect, useMemo, useState } from 'react'
import { Plus, Square } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Segmented, Badge, toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Checkbox, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { formatDate } from '../../lib/format'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'
import flotteApi from '../../api/flotteApi'

/* ============================================================================
   PACT81 — Affectation véhicule & permis de conduire.
   ----------------------------------------------------------------------------
   `PermisConduire` (FG197) est la source de vérité du droit de conduire ;
   `AffectationVehicule` (FG198) lie un conducteur à un véhicule du parc sur
   une période — le serveur REFUSE (400) toute affectation sans permis valide
   via `services.controler_permis_affectation` ; ce message de refus est
   affiché TEL QUEL (jamais un filtrage/une validation côté client). Le
   véhicule référencé (`vehicule_id`) est une STRING-FK vers `flotte.Vehicule`,
   résolue ici en lecture seule via `flotteApi.vehicules.list()`.
   ========================================================================== */

const VUES = [
  { value: 'permis', label: 'Permis de conduire' },
  { value: 'affectations', label: 'Affectations véhicule' },
]

const CATEGORIE_OPTIONS = [
  { value: 'A', label: 'A — Motos' },
  { value: 'B', label: 'B — Véhicules légers' },
  { value: 'C', label: 'C — Poids lourds' },
  { value: 'D', label: 'D — Transport de personnes' },
  { value: 'EB', label: 'EB — Léger + remorque' },
  { value: 'EC', label: 'EC — Poids lourd + remorque' },
]

export default function VehiculesPermis() {
  const { confirm } = useConfirmDialog()
  const [vue, setVue] = useState('permis')
  const [permis, setPermis] = useState([])
  const [affectations, setAffectations] = useState([])
  const [employes, setEmployes] = useState([])
  const [vehicules, setVehicules] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)
  const [permisOpen, setPermisOpen] = useState(false)
  const [affectationOpen, setAffectationOpen] = useState(false)

  const recharger = () => {
    setLoading(true)
    setError(null)
    setReloadTick((t) => t + 1)
  }

  useEffect(() => {
    let vivant = true
    Promise.all([
      rhApi.getPermisConduire(),
      rhApi.getAffectationsVehicule(),
      rhApi.getEmployes(),
      flotteApi.vehicules.list(),
    ])
      .then(([p, a, e, v]) => {
        if (!vivant) return
        setPermis(unwrapList(p))
        setAffectations(unwrapList(a))
        setEmployes(unwrapList(e))
        setVehicules(unwrapList(v))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les permis et affectations.')
        toast.error('Impossible de charger les permis et affectations.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadTick])

  const vehiculeLabel = useMemo(() => {
    const map = new Map()
    vehicules.forEach((v) => map.set(String(v.id), `${v.immatriculation || '—'} — ${v.marque || ''} ${v.modele || ''}`.trim()))
    return map
  }, [vehicules])

  const terminer = async (a) => {
    const ok = await confirm({
      title: 'Terminer cette affectation ?',
      description: 'Le véhicule redevient disponible pour une nouvelle affectation.',
      confirmLabel: 'Terminer',
      destructive: false,
    })
    if (!ok) return
    try {
      await rhApi.terminerAffectationVehicule(a.id)
      toast.success('Affectation clôturée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Clôture impossible.')
    }
  }

  const permisColumns = useMemo(() => [
    { id: 'employe', header: 'Conducteur', width: 180, accessor: (p) => p.employe_nom || String(p.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'categorie', header: 'Catégorie', width: 160, accessor: (p) => p.categorie_display || p.categorie || '', cell: (v) => v || '—' },
    { id: 'numero', header: 'Numéro', width: 140, accessor: (p) => p.numero || '', cell: (v) => v || '—' },
    { id: 'expiration', header: 'Expiration', width: 130, searchable: false, accessor: (p) => p.date_expiration || '', cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'valide', header: 'État', width: 100, accessor: (p) => (p.valide ? 'valide' : 'expire'), cell: (_v, p) => <Badge tone={p.valide ? 'success' : 'danger'}>{p.valide ? 'Valide' : 'Expiré'}</Badge> },
  ], [])

  const affectationColumns = useMemo(() => [
    { id: 'employe', header: 'Conducteur', width: 180, accessor: (a) => a.employe_nom || String(a.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'vehicule', header: 'Véhicule', width: 200, accessor: (a) => vehiculeLabel.get(String(a.vehicule_id)) || `#${a.vehicule_id}`, cell: (v) => v || '—' },
    { id: 'periode', header: 'Période', width: 200, searchable: false, accessor: (a) => a.date_debut || '', cell: (_v, a) => `${formatDate(a.date_debut)} → ${a.date_fin ? formatDate(a.date_fin) : 'en cours'}` },
    { id: 'statut', header: 'Statut', width: 120, accessor: (a) => a.statut_display || a.statut || '', cell: (v) => v || '—' },
    { id: 'permis_verifie', header: 'Permis vérifié', width: 130, accessor: (a) => (a.permis_verifie ? 'oui' : 'non'), cell: (_v, a) => <Badge tone={a.permis_verifie ? 'success' : 'neutral'}>{a.permis_verifie ? 'Oui' : 'Non'}</Badge> },
  ], [vehiculeLabel])

  const affectationActions = (a) => (a.statut === 'active'
    ? [{ id: 'terminer', label: 'Terminer', icon: Square, onClick: () => terminer(a) }]
    : [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Véhicules & permis</h2>
      </div>

      <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue véhicules & permis" />

      {vue === 'permis' ? (
        <ListShell
          title="Permis de conduire"
          columns={permisColumns}
          rows={permis}
          loading={loading}
          error={error}
          searchable
          exportName="permis-conduire"
          actions={<Button onClick={() => setPermisOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouveau permis</Button>}
          emptyTitle="Aucun permis"
          emptyDescription="Aucun permis de conduire enregistré."
        />
      ) : (
        <ListShell
          title="Affectations véhicule"
          columns={affectationColumns}
          rows={affectations}
          loading={loading}
          error={error}
          searchable
          exportName="affectations-vehicule"
          rowActions={affectationActions}
          actions={<Button onClick={() => setAffectationOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle affectation</Button>}
          emptyTitle="Aucune affectation"
          emptyDescription="Aucune affectation véhicule enregistrée."
        />
      )}

      {permisOpen && (
        <PermisDialog
          employes={employes}
          onClose={() => setPermisOpen(false)}
          onSaved={() => { setPermisOpen(false); recharger() }}
        />
      )}
      {affectationOpen && (
        <AffectationDialog
          employes={employes}
          vehicules={vehicules}
          onClose={() => setAffectationOpen(false)}
          onSaved={() => { setAffectationOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

function PermisDialog({ employes, onClose, onSaved }) {
  const [employe, setEmploye] = useState('')
  const [categorie, setCategorie] = useState('B')
  const [numero, setNumero] = useState('')
  const [dateDelivrance, setDateDelivrance] = useState('')
  const [dateExpiration, setDateExpiration] = useState('')
  const [habilitation, setHabilitation] = useState(false)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || numero || dateDelivrance || dateExpiration || note)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createPermisConduire({
        employe, categorie, numero: numero || '',
        date_delivrance: dateDelivrance || null,
        date_expiration: dateExpiration || null,
        habilitation_conduite: habilitation,
        note: note || '',
      })
      toast.success('Permis enregistré.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.non_field_errors?.[0] || 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouveau permis de conduire</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pc-employe">Conducteur</Label>
              <select id="pc-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Choisir —</option>
                {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pc-categorie">Catégorie</Label>
              <select id="pc-categorie" value={categorie} onChange={(e) => setCategorie(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                {CATEGORIE_OPTIONS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pc-numero">Numéro de permis</Label>
            <Input id="pc-numero" value={numero} onChange={(e) => setNumero(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pc-delivrance">Date de délivrance</Label>
              <Input id="pc-delivrance" type="date" value={dateDelivrance} onChange={(e) => setDateDelivrance(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pc-expiration">Date d’expiration</Label>
              <Input id="pc-expiration" type="date" value={dateExpiration} onChange={(e) => setDateExpiration(e.target.value)} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="pc-habilitation" checked={habilitation} onCheckedChange={setHabilitation} />
            <Label htmlFor="pc-habilitation">Habilitation interne à conduire</Label>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pc-note">Note (optionnel)</Label>
            <Textarea id="pc-note" value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function AffectationDialog({ employes, vehicules, onClose, onSaved }) {
  const [employe, setEmploye] = useState('')
  const [vehiculeId, setVehiculeId] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || vehiculeId || dateDebut || dateFin || note)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe && vehiculeId && dateDebut)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createAffectationVehicule({
        employe, vehicule_id: vehiculeId,
        date_debut: dateDebut, date_fin: dateFin || null,
        note: note || '',
      })
      toast.success('Affectation créée.')
      onSaved?.()
    } catch (err) {
      // FG198 — le refus serveur (permis absent/expiré) est affiché TEL QUEL,
      // jamais un filtrage/une validation côté client (Done= de PACT81).
      const data = err?.response?.data
      setServerError(data?.employe?.[0] || data?.detail || data?.non_field_errors?.[0] || 'Affectation impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvelle affectation véhicule</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="av-employe">Conducteur</Label>
              <select id="av-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Choisir —</option>
                {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="av-vehicule">Véhicule</Label>
              <select id="av-vehicule" value={vehiculeId} onChange={(e) => setVehiculeId(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Choisir —</option>
                {vehicules.map((v) => <option key={v.id} value={v.id}>{v.immatriculation} — {v.marque} {v.modele}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="av-debut">Date de début</Label>
              <Input id="av-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="av-fin">Date de fin (optionnel)</Label>
              <Input id="av-fin" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="av-note">Note (optionnel)</Label>
            <Textarea id="av-note" value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
