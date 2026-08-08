import { useEffect, useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Badge, toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Checkbox, confirmLeaveIfDirty,
} from '../../ui'
import { formatDate } from '../../lib/format'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT89 — Horaires de travail.
   ----------------------------------------------------------------------------
   `HoraireTravail` (XRH8) rend explicite l'horaire appliqué (44h standard,
   Ramadan, saisonnier, temps partiel) sur une fenêtre de dates avec retour
   automatique au standard hors fenêtre. L'état affiché (à venir/active/
   expirée) se déduit PUREMENT de l'affichage des dates déjà renvoyées par le
   serveur comparées à la date du jour — aucun redéploiement ni recalcul
   métier n'est nécessaire pour qu'une fenêtre future devienne active
   (Done= de PACT89).
   ========================================================================== */

const TYPE_OPTIONS = [
  { value: 'standard_44h', label: 'Standard 44h' },
  { value: 'ramadan', label: 'Ramadan' },
  { value: 'saisonnier', label: 'Saisonnier' },
  { value: 'temps_partiel', label: 'Temps partiel' },
]

function etatFenetre(h) {
  if (!h.date_debut && !h.date_fin) return { label: 'Permanent', tone: 'neutral' }
  const today = new Date().toISOString().slice(0, 10)
  if (h.date_debut && today < h.date_debut) return { label: 'À venir', tone: 'info' }
  if (h.date_fin && today > h.date_fin) return { label: 'Expirée', tone: 'neutral' }
  return { label: 'Active', tone: 'success' }
}

export default function HorairesTravail() {
  const [horaires, setHoraires] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)
  const [open, setOpen] = useState(false)

  const recharger = () => setReloadTick((t) => t + 1)

  useEffect(() => {
    let vivant = true
    setLoading(true)
    setError(null)
    rhApi.getHorairesTravail()
      .then((res) => { if (vivant) setHoraires(unwrapList(res)) })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les horaires de travail.')
        toast.error('Impossible de charger les horaires de travail.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [reloadTick])

  const columns = useMemo(() => [
    { id: 'nom', header: 'Nom', width: 200, accessor: (h) => h.nom || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'type', header: "Type d'horaire", width: 150, accessor: (h) => h.type_horaire_display || h.type_horaire || '', cell: (v) => v || '—' },
    { id: 'heures_semaine', header: 'H./semaine', width: 100, align: 'right', numeric: true, searchable: false, accessor: (h) => Number(h.heures_semaine ?? 0), cell: (v) => v },
    { id: 'periode', header: 'Fenêtre', width: 220, searchable: false, accessor: (h) => h.date_debut || '', cell: (_v, h) => (h.date_debut || h.date_fin ? `${h.date_debut ? formatDate(h.date_debut) : '—'} → ${h.date_fin ? formatDate(h.date_fin) : '—'}` : 'Permanent') },
    { id: 'etat', header: 'État', width: 110, accessor: (h) => etatFenetre(h).label, cell: (_v, h) => { const e = etatFenetre(h); return <Badge tone={e.tone}>{e.label}</Badge> } },
    { id: 'actif', header: 'Actif', width: 90, accessor: (h) => (h.actif ? 'oui' : 'non'), cell: (_v, h) => <Badge tone={h.actif ? 'success' : 'neutral'}>{h.actif ? 'Actif' : 'Inactif'}</Badge> },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Horaires de travail</h2>
      </div>

      <ListShell
        title="Gabarits d'horaire"
        columns={columns}
        rows={horaires}
        loading={loading}
        error={error}
        searchable
        exportName="horaires-travail"
        actions={<Button onClick={() => setOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvel horaire</Button>}
        emptyTitle="Aucun horaire"
        emptyDescription="Aucun gabarit d’horaire configuré."
      />

      {open && (
        <HoraireDialog
          onClose={() => setOpen(false)}
          onSaved={() => { setOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

function HoraireDialog({ onClose, onSaved }) {
  const [nom, setNom] = useState('')
  const [type, setType] = useState('standard_44h')
  const [heuresSemaine, setHeuresSemaine] = useState('44')
  const [heuresJour, setHeuresJour] = useState('8')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [actif, setActif] = useState(true)
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(nom || dateDebut || dateFin)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(nom.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createHoraireTravail({
        nom: nom.trim(), type_horaire: type,
        heures_semaine: heuresSemaine || '44',
        heures_jour_defaut: heuresJour || '8',
        date_debut: dateDebut || null,
        date_fin: dateFin || null,
        actif,
      })
      toast.success('Horaire créé.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.nom?.[0] || 'Création impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvel horaire de travail</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ht-nom">Nom</Label>
              <Input id="ht-nom" autoFocus value={nom} onChange={(e) => setNom(e.target.value)} placeholder="Ex. Ramadan 2026" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ht-type">Type</Label>
              <select id="ht-type" value={type} onChange={(e) => setType(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                {TYPE_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ht-hsem">Heures / semaine</Label>
              <Input id="ht-hsem" type="number" step="any" value={heuresSemaine} onChange={(e) => setHeuresSemaine(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ht-hjour">Heures / jour (défaut)</Label>
              <Input id="ht-hjour" type="number" step="any" value={heuresJour} onChange={(e) => setHeuresJour(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ht-debut">Début de validité (optionnel)</Label>
              <Input id="ht-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ht-fin">Fin de validité (optionnel)</Label>
              <Input id="ht-fin" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="ht-actif" checked={actif} onCheckedChange={setActif} />
            <Label htmlFor="ht-actif">Actif</Label>
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
