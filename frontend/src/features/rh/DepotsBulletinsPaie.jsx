import { useEffect, useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, FileUpload, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import { formatDate } from '../../lib/format'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT82 — Dépôt des bulletins de paie.
   ----------------------------------------------------------------------------
   `BulletinPaie` (FG196) stocke le PDF mensuel produit par le prestataire de
   paie externe (un fichier par employé/année/mois, MinIO via
   `records.Attachment`). Le collaborateur le consulte déjà depuis son portail
   self-service ; cet écran est le côté Administrateur/Responsable qui manquait
   pour le DÉPOSER — liste filtrable employé/année/mois, scopée société côté
   serveur (aucun filtrage client d'une donnée déjà scopée).
   ========================================================================== */

export default function DepotsBulletinsPaie() {
  const [bulletins, setBulletins] = useState([])
  const [employes, setEmployes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)
  const [open, setOpen] = useState(false)

  const recharger = () => setReloadTick((t) => t + 1)

  useEffect(() => {
    let vivant = true
    setLoading(true)
    setError(null)
    Promise.all([rhApi.getBulletinsPaie(), rhApi.getEmployes()])
      .then(([b, e]) => {
        if (!vivant) return
        setBulletins(unwrapList(b))
        setEmployes(unwrapList(e))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les bulletins de paie.')
        toast.error('Impossible de charger les bulletins de paie.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [reloadTick])

  const columns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (b) => b.employe_nom || String(b.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'periode', header: 'Période', width: 120, accessor: (b) => `${b.mois}/${b.annee}`, cell: (v) => v },
    { id: 'fichier', header: 'Fichier', width: 220, accessor: (b) => b.filename || '', cell: (v) => v || '—' },
    { id: 'depose', header: 'Déposé le', width: 130, searchable: false, accessor: (b) => b.date_creation || '', cell: (v) => (v ? formatDate(v) : '—') },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Bulletins de paie</h2>
      </div>

      <ListShell
        title="Dépôts de bulletins"
        columns={columns}
        rows={bulletins}
        loading={loading}
        error={error}
        searchable
        exportName="bulletins-paie"
        actions={<Button onClick={() => setOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Déposer un bulletin</Button>}
        emptyTitle="Aucun bulletin"
        emptyDescription="Aucun bulletin de paie déposé."
      />

      {open && (
        <DepotDialog
          employes={employes}
          onClose={() => setOpen(false)}
          onSaved={() => { setOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

function DepotDialog({ employes, onClose, onSaved }) {
  const now = new Date()
  const [employe, setEmploye] = useState('')
  const [annee, setAnnee] = useState(String(now.getFullYear()))
  const [mois, setMois] = useState(String(now.getMonth() + 1))
  const [file, setFile] = useState(null)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || file || note)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe && annee && mois && file)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.uploadBulletinPaie({ employe, file, annee, mois, note: note || '' })
      toast.success('Bulletin déposé.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.file || data?.employe || data?.non_field_errors?.[0] || 'Dépôt impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Déposer un bulletin de paie</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="bp-employe">Employé</Label>
            <select id="bp-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              <option value="">— Choisir —</option>
              {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="bp-annee">Année</Label>
              <Input id="bp-annee" type="number" step="any" value={annee} onChange={(e) => setAnnee(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="bp-mois">Mois (1–12)</Label>
              <Input id="bp-mois" type="number" step="any" min="1" max="12" value={mois} onChange={(e) => setMois(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="bp-fichier">Fichier PDF</Label>
            <FileUpload id="bp-fichier" accept="application/pdf" onFiles={(files) => setFile(files?.[0] ?? null)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="bp-note">Note (optionnel)</Label>
            <Textarea id="bp-note" value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>{saving ? 'Dépôt…' : 'Déposer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
