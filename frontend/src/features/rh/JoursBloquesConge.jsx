import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, MultiSelect, confirmLeaveIfDirty,
} from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { formatDate } from '../../lib/format'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT90 — Jours bloqués (congés).
   ----------------------------------------------------------------------------
   `JourBloqueConge` (ZRH4, « Mandatory / Stress Days » Odoo) interdit la
   SOUMISSION d'une `DemandeConge` chevauchant une période bloquée (haute
   saison de pose, inventaire…), forçable via `?forcer=1` par un Responsable
   à la soumission — ce refus/forçage vit dans l'écran Congés existant qui
   soumet la demande ; cet écran gère le CATALOGUE des périodes bloquées
   lui-même (créer/lister/supprimer), scopé société côté serveur.
   ========================================================================== */

export default function JoursBloquesConge() {
  const { confirmDelete } = useConfirmDialog()
  const [jours, setJours] = useState([])
  const [departements, setDepartements] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)
  const [open, setOpen] = useState(false)

  const recharger = () => setReloadTick((t) => t + 1)

  useEffect(() => {
    let vivant = true
    setLoading(true)
    setError(null)
    Promise.all([rhApi.getJoursBloquesConge(), rhApi.getDepartements()])
      .then(([j, d]) => {
        if (!vivant) return
        setJours(unwrapList(j))
        setDepartements(unwrapList(d))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les jours bloqués.')
        toast.error('Impossible de charger les jours bloqués.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [reloadTick])

  const supprimer = async (j) => {
    const ok = await confirmDelete({
      title: 'Supprimer ce blocage ?',
      description: `« ${j.libelle} » ne sera plus contrôlé à la soumission.`,
      confirmLabel: 'Supprimer',
    })
    if (!ok) return
    try {
      await rhApi.deleteJourBloqueConge(j.id)
      toast.success('Blocage supprimé.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Suppression impossible.')
    }
  }

  const depLabel = (ids) => {
    if (!ids || ids.length === 0) return 'Toute la société'
    return ids.map((id) => departements.find((d) => d.id === id)?.nom || `#${id}`).join(', ')
  }

  const columns = useMemo(() => [
    { id: 'libelle', header: 'Libellé', width: 200, accessor: (j) => j.libelle || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'periode', header: 'Période', width: 200, searchable: false, accessor: (j) => j.date_debut || '', cell: (_v, j) => `${formatDate(j.date_debut)} → ${formatDate(j.date_fin)}` },
    { id: 'departements', header: 'Départements', width: 220, searchable: false, accessor: (j) => depLabel(j.departements), cell: (v) => v },
    { id: 'motif', header: 'Motif', width: 200, accessor: (j) => j.motif || '', cell: (v) => v || '—' },
  ], [departements])

  const rowActions = (j) => [
    { id: 'suppr', label: 'Supprimer', icon: Trash2, destructive: true, onClick: () => supprimer(j) },
  ]

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Jours bloqués (congés)</h2>
      </div>

      <ListShell
        title="Périodes bloquées"
        columns={columns}
        rows={jours}
        loading={loading}
        error={error}
        searchable
        exportName="jours-bloques-conge"
        rowActions={rowActions}
        actions={<Button onClick={() => setOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouveau blocage</Button>}
        emptyTitle="Aucun blocage"
        emptyDescription="Aucune période bloquée configurée."
      />

      {open && (
        <JourBloqueDialog
          departements={departements}
          onClose={() => setOpen(false)}
          onSaved={() => { setOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

function JourBloqueDialog({ departements, onClose, onSaved }) {
  const [libelle, setLibelle] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [deps, setDeps] = useState([])
  const [motif, setMotif] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(libelle || dateDebut || dateFin || motif)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(libelle.trim() && dateDebut && dateFin)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createJourBloqueConge({
        libelle: libelle.trim(), date_debut: dateDebut, date_fin: dateFin,
        departements: deps, motif: motif || '',
      })
      toast.success('Période bloquée créée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.date_fin || data?.detail || data?.non_field_errors?.[0] || 'Création impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvelle période bloquée</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="jb-libelle">Libellé</Label>
            <Input id="jb-libelle" autoFocus value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="Ex. Haute saison pose" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="jb-debut">Du</Label>
              <Input id="jb-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="jb-fin">Au</Label>
              <Input id="jb-fin" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="jb-departements">Départements concernés (vide = toute la société)</Label>
            <MultiSelect
              id="jb-departements"
              options={departements.map((d) => ({ value: d.id, label: d.nom }))}
              value={deps}
              onChange={setDeps}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="jb-motif">Motif (optionnel)</Label>
            <Input id="jb-motif" value={motif} onChange={(e) => setMotif(e.target.value)} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
