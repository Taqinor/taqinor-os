import { useEffect, useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, confirmLeaveIfDirty,
} from '../../ui'
import { formatDate, formatNumber } from '../../lib/format'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT88 — Grilles salariales.
   ----------------------------------------------------------------------------
   `GrilleSalariale` (XRH16) définit les bandes min/max par poste et échelon,
   gatée en LECTURE ET en ÉCRITURE par `HasPermission('salaires_voir')` côté
   serveur. L'écran ne masque JAMAIS côté client une donnée salariale : il
   tente le chargement et relaie le 403 serveur TEL QUEL si le compte
   appelant n'a pas la permission (Done= de PACT88) — jamais un filtrage
   silencieux ni un écran vide sans explication.
   ========================================================================== */

export default function GrillesSalariales() {
  const [grilles, setGrilles] = useState([])
  const [postes, setPostes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)
  const [open, setOpen] = useState(false)

  const recharger = () => {
    setLoading(true)
    setError(null)
    setReloadTick((t) => t + 1)
  }

  useEffect(() => {
    let vivant = true
    Promise.all([rhApi.getGrillesSalariales(), rhApi.getPostes()])
      .then(([g, p]) => {
        if (!vivant) return
        setGrilles(unwrapList(g))
        setPostes(unwrapList(p))
      })
      .catch((err) => {
        if (!vivant) return
        // Relais TEL QUEL du message serveur (403 salaires_voir compris) —
        // jamais un texte générique qui masquerait la vraie raison.
        const message = err?.response?.data?.detail || 'Impossible de charger les grilles salariales.'
        setError(message)
        toast.error(message)
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [reloadTick])

  const columns = useMemo(() => [
    // XRH16 — `poste_intitule` vient DÉJÀ du serveur (GrilleSalarialeSerializer) :
    // jamais recalculé par une jointure côté client.
    { id: 'poste', header: 'Poste', width: 180, accessor: (g) => g.poste_intitule || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'echelon', header: 'Échelon', width: 120, accessor: (g) => g.echelon || '', cell: (v) => v || '—' },
    { id: 'min', header: 'Salaire min (MAD)', width: 150, align: 'right', numeric: true, searchable: false, accessor: (g) => Number(g.salaire_min ?? 0), cell: (v) => formatNumber(v, { decimals: 2 }) },
    { id: 'max', header: 'Salaire max (MAD)', width: 150, align: 'right', numeric: true, searchable: false, accessor: (g) => Number(g.salaire_max ?? 0), cell: (v) => formatNumber(v, { decimals: 2 }) },
    { id: 'effet', header: "Date d'effet", width: 130, searchable: false, accessor: (g) => g.date_effet || '', cell: (v) => (v ? formatDate(v) : '—') },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Grilles salariales</h2>
      </div>

      <ListShell
        title="Bandes salariales par poste"
        columns={columns}
        rows={grilles}
        loading={loading}
        error={error}
        searchable
        exportName="grilles-salariales"
        actions={<Button onClick={() => setOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle bande</Button>}
        emptyTitle="Aucune bande"
        emptyDescription="Aucune grille salariale configurée."
      />

      {open && (
        <GrilleDialog
          postes={postes}
          onClose={() => setOpen(false)}
          onSaved={() => { setOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

function GrilleDialog({ postes, onClose, onSaved }) {
  const [poste, setPoste] = useState('')
  const [echelon, setEchelon] = useState('')
  const [salaireMin, setSalaireMin] = useState('')
  const [salaireMax, setSalaireMax] = useState('')
  const [dateEffet, setDateEffet] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(poste || echelon || salaireMin || salaireMax)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(poste && salaireMin && salaireMax && dateEffet)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createGrilleSalariale({
        poste, echelon: echelon || '',
        salaire_min: salaireMin, salaire_max: salaireMax,
        date_effet: dateEffet,
      })
      toast.success('Bande salariale créée.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.non_field_errors?.[0] || 'Création impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvelle bande salariale</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="gs-poste">Poste</Label>
              <select id="gs-poste" value={poste} onChange={(e) => setPoste(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Choisir —</option>
                {postes.map((p) => <option key={p.id} value={p.id}>{p.intitule}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="gs-echelon">Échelon (optionnel)</Label>
              <Input id="gs-echelon" value={echelon} onChange={(e) => setEchelon(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="gs-min">Salaire minimum (MAD)</Label>
              <Input id="gs-min" type="number" step="any" value={salaireMin} onChange={(e) => setSalaireMin(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="gs-max">Salaire maximum (MAD)</Label>
              <Input id="gs-max" type="number" step="any" value={salaireMax} onChange={(e) => setSalaireMax(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gs-effet">Date d’effet</Label>
            <Input id="gs-effet" type="date" value={dateEffet} onChange={(e) => setDateEffet(e.target.value)} />
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
