import { useEffect, useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Badge, toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import { formatDate } from '../../lib/format'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT87 — Entretiens de sortie.
   ----------------------------------------------------------------------------
   `EntretienSortie` (XRH25) capture, un par employé sorti, un questionnaire
   structuré (motif principal, JSON libre, recommanderait) distinct du simple
   `motif_sortie` déjà saisi à l'offboarding. Un seul entretien par employé
   (`OneToOneField`) — un second essai est refusé par la CONTRAINTE D'UNICITÉ
   du serveur, jamais par une validation front (Done= de PACT87).
   ========================================================================== */

const MOTIF_OPTIONS = [
  { value: '', label: '— Non précisé —' },
  { value: 'salaire', label: 'Salaire' },
  { value: 'management', label: 'Management' },
  { value: 'conditions', label: 'Conditions de travail' },
  { value: 'distance', label: 'Distance / trajet' },
  { value: 'opportunite', label: 'Opportunité ailleurs' },
  { value: 'sante', label: 'Santé' },
  { value: 'autre', label: 'Autre' },
]

export default function EntretiensSortie() {
  const [entretiens, setEntretiens] = useState([])
  const [employes, setEmployes] = useState([])
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
    Promise.all([rhApi.getEntretiensSortie(), rhApi.getEmployes()])
      .then(([e, emp]) => {
        if (!vivant) return
        setEntretiens(unwrapList(e))
        setEmployes(unwrapList(emp))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les entretiens de sortie.')
        toast.error('Impossible de charger les entretiens de sortie.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [reloadTick])

  const columns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (e) => e.employe_nom || String(e.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'date', header: "Date de l'entretien", width: 140, searchable: false, accessor: (e) => e.date || '', cell: (v) => (v ? formatDate(v) : '—') },
    { id: 'motif', header: 'Motif principal', width: 160, accessor: (e) => e.motif_principal_display || e.motif_principal || '', cell: (v) => v || '—' },
    { id: 'recommanderait', header: 'Recommanderait', width: 130, accessor: (e) => (e.recommanderait == null ? '' : e.recommanderait ? 'oui' : 'non'), cell: (_v, e) => (e.recommanderait == null ? <span className="text-muted-foreground">—</span> : <Badge tone={e.recommanderait ? 'success' : 'danger'}>{e.recommanderait ? 'Oui' : 'Non'}</Badge>) },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Entretiens de sortie</h2>
      </div>

      <ListShell
        title="Entretiens"
        columns={columns}
        rows={entretiens}
        loading={loading}
        error={error}
        searchable
        exportName="entretiens-sortie"
        actions={<Button onClick={() => setOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvel entretien</Button>}
        emptyTitle="Aucun entretien"
        emptyDescription="Aucun entretien de sortie enregistré."
      />

      {open && (
        <EntretienDialog
          employes={employes}
          onClose={() => setOpen(false)}
          onSaved={() => { setOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

function EntretienDialog({ employes, onClose, onSaved }) {
  const [employe, setEmploye] = useState('')
  const [date, setDate] = useState('')
  const [motif, setMotif] = useState('')
  const [recommanderait, setRecommanderait] = useState('')
  const [commentaire, setCommentaire] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || date || commentaire)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createEntretienSortie({
        employe, date: date || null,
        motif_principal: motif || '',
        recommanderait: recommanderait === '' ? null : recommanderait === 'oui',
        commentaire: commentaire || '',
      })
      toast.success('Entretien de sortie enregistré.')
      onSaved?.()
    } catch (err) {
      // XRH25 — un second entretien pour le même employé est refusé par la
      // contrainte d'unicité SERVEUR ; le message est affiché tel quel.
      const data = err?.response?.data
      setServerError(data?.employe?.[0] || data?.detail || data?.non_field_errors?.[0] || 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvel entretien de sortie</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="es-employe">Employé</Label>
              <select id="es-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Choisir —</option>
                {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="es-date">Date de l’entretien</Label>
              <Input id="es-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="es-motif">Motif principal</Label>
            <select id="es-motif" value={motif} onChange={(e) => setMotif(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              {MOTIF_OPTIONS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="es-recommanderait">Recommanderait l’entreprise</Label>
            <select id="es-recommanderait" value={recommanderait} onChange={(e) => setRecommanderait(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              <option value="">— Non répondu —</option>
              <option value="oui">Oui</option>
              <option value="non">Non</option>
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="es-commentaire">Commentaire (optionnel)</Label>
            <Textarea id="es-commentaire" value={commentaire} onChange={(e) => setCommentaire(e.target.value)} rows={3} />
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
