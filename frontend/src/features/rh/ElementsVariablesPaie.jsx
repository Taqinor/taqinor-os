import { useEffect, useMemo, useState } from 'react'
import { Plus, CheckCircle2, UploadCloud } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Badge, toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import { formatDate, formatNumber } from '../../lib/format'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT86 — Éléments variables de paie (bordereau externe).
   ----------------------------------------------------------------------------
   `ElementsVariablesPaie` (FG192) agrège par employé et par mois heures,
   absences, congés, primes et retenues — SEUL bordereau destiné à un
   prestataire de paie externe (le moteur interne a ses propres sélecteurs),
   cycle brouillon → validé → exporté. Les quantités/montants affichés
   viennent TELS QUELS du serveur — aucun total n'est recalculé côté client.
   ========================================================================== */

export default function ElementsVariablesPaie() {
  const [lignes, setLignes] = useState([])
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
    Promise.all([rhApi.getElementsVariablesPaie(), rhApi.getEmployes()])
      .then(([l, e]) => {
        if (!vivant) return
        setLignes(unwrapList(l))
        setEmployes(unwrapList(e))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger le bordereau.')
        toast.error('Impossible de charger le bordereau.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [reloadTick])

  const valider = async (l) => {
    try {
      await rhApi.updateElementVariablePaie(l.id, { statut: 'valide' })
      toast.success('Bordereau validé.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Validation impossible.')
    }
  }

  const marquerExporte = async (l) => {
    try {
      await rhApi.marquerExporteElementVariablePaie(l.id)
      toast.success('Bordereau marqué exporté.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Marquage impossible.')
    }
  }

  const tone = (statut) => (statut === 'exporte' ? 'success' : statut === 'valide' ? 'info' : 'neutral')

  const columns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 170, accessor: (l) => l.employe_nom || String(l.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'periode', header: 'Période', width: 90, accessor: (l) => `${l.mois}/${l.annee}`, cell: (v) => v },
    { id: 'heures_normales', header: 'H. normales', width: 100, align: 'right', numeric: true, searchable: false, accessor: (l) => Number(l.heures_normales ?? 0), cell: (v) => formatNumber(v, { decimals: 2 }) },
    { id: 'heures_supp', header: 'H. supp', width: 90, align: 'right', numeric: true, searchable: false, accessor: (l) => Number(l.heures_supp ?? 0), cell: (v) => formatNumber(v, { decimals: 2 }) },
    { id: 'primes', header: 'Primes', width: 100, align: 'right', numeric: true, searchable: false, accessor: (l) => Number(l.primes ?? 0), cell: (v) => formatNumber(v, { decimals: 2 }) },
    { id: 'retenues', header: 'Retenues', width: 100, align: 'right', numeric: true, searchable: false, accessor: (l) => Number(l.retenues ?? 0), cell: (v) => formatNumber(v, { decimals: 2 }) },
    { id: 'statut', header: 'Statut', width: 120, accessor: (l) => l.statut_display || l.statut || '', cell: (v, l) => <Badge tone={tone(l.statut)}>{v || '—'}</Badge> },
    { id: 'exporte', header: 'Exporté le', width: 130, searchable: false, accessor: (l) => l.date_export || '', cell: (v) => (v ? formatDate(v) : '—') },
  ], [])

  const rowActions = (l) => {
    if (l.statut === 'brouillon') {
      return [{ id: 'valider', label: 'Valider', icon: CheckCircle2, onClick: () => valider(l) }]
    }
    if (l.statut === 'valide') {
      return [{ id: 'exporter', label: 'Marquer exporté', icon: UploadCloud, onClick: () => marquerExporte(l) }]
    }
    return []
  }

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Éléments variables de paie</h2>
      </div>

      <ListShell
        title="Bordereau mensuel"
        columns={columns}
        rows={lignes}
        loading={loading}
        error={error}
        searchable
        exportName="elements-variables-paie"
        rowActions={rowActions}
        actions={<Button onClick={() => setOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle ligne</Button>}
        emptyTitle="Aucune ligne"
        emptyDescription="Aucun élément variable de paie saisi."
      />

      {open && (
        <LigneDialog
          employes={employes}
          onClose={() => setOpen(false)}
          onSaved={() => { setOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

function LigneDialog({ employes, onClose, onSaved }) {
  const now = new Date()
  const [employe, setEmploye] = useState('')
  const [annee, setAnnee] = useState(String(now.getFullYear()))
  const [mois, setMois] = useState(String(now.getMonth() + 1))
  const [heuresNormales, setHeuresNormales] = useState('0')
  const [heuresSupp, setHeuresSupp] = useState('0')
  const [joursAbsence, setJoursAbsence] = useState('0')
  const [joursConges, setJoursConges] = useState('0')
  const [primes, setPrimes] = useState('0')
  const [retenues, setRetenues] = useState('0')
  const [commentaire, setCommentaire] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || commentaire)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe && annee && mois)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createElementVariablePaie({
        employe, annee: Number(annee), mois: Number(mois),
        heures_normales: heuresNormales || '0',
        heures_supp: heuresSupp || '0',
        jours_absence: joursAbsence || '0',
        jours_conges: joursConges || '0',
        primes: primes || '0',
        retenues: retenues || '0',
        commentaire: commentaire || '',
      })
      toast.success('Ligne enregistrée.')
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
        <DialogHeader><DialogTitle>Nouvelle ligne du bordereau</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-1 flex flex-col gap-1.5">
              <Label htmlFor="evp-employe">Employé</Label>
              <select id="evp-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Choisir —</option>
                {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="evp-annee">Année</Label>
              <Input id="evp-annee" type="number" step="any" value={annee} onChange={(e) => setAnnee(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="evp-mois">Mois</Label>
              <Input id="evp-mois" type="number" step="any" min="1" max="12" value={mois} onChange={(e) => setMois(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="evp-hn">Heures normales</Label>
              <Input id="evp-hn" type="number" step="any" value={heuresNormales} onChange={(e) => setHeuresNormales(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="evp-hs">Heures supp</Label>
              <Input id="evp-hs" type="number" step="any" value={heuresSupp} onChange={(e) => setHeuresSupp(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="evp-ja">Jours d’absence</Label>
              <Input id="evp-ja" type="number" step="any" value={joursAbsence} onChange={(e) => setJoursAbsence(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="evp-jc">Jours de congés</Label>
              <Input id="evp-jc" type="number" step="any" value={joursConges} onChange={(e) => setJoursConges(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="evp-primes">Primes (total)</Label>
              <Input id="evp-primes" type="number" step="any" value={primes} onChange={(e) => setPrimes(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="evp-retenues">Retenues (total)</Label>
              <Input id="evp-retenues" type="number" step="any" value={retenues} onChange={(e) => setRetenues(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="evp-commentaire">Commentaire (optionnel)</Label>
            <Textarea id="evp-commentaire" value={commentaire} onChange={(e) => setCommentaire(e.target.value)} rows={2} />
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
