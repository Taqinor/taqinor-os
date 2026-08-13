import { useEffect, useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Segmented, toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import { formatDate } from '../../lib/format'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT91 — Parcours (timeline) des employés.
   ----------------------------------------------------------------------------
   `LigneParcours`/`TypeLigneParcours` (ZRH15, models.py:5934-5960) forment la
   timeline chronologique d'un employé, déjà affichée en lecture seule dans
   l'annuaire self-service — cet écran édite le CATALOGUE de types et les
   LIGNES elles-mêmes. Un type ajouté au catalogue est immédiatement
   sélectionnable pour une nouvelle ligne (les deux listes partagent le même
   état rechargé), sans redéploiement.
   ========================================================================== */

const VUES = [
  { value: 'lignes', label: 'Lignes de parcours' },
  { value: 'types', label: 'Catalogue de types' },
]

export default function ParcoursEmploye() {
  const [vue, setVue] = useState('lignes')
  const [types, setTypes] = useState([])
  const [lignes, setLignes] = useState([])
  const [employes, setEmployes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)
  const [typeOpen, setTypeOpen] = useState(false)
  const [ligneOpen, setLigneOpen] = useState(false)

  const recharger = () => {
    setLoading(true)
    setError(null)
    setReloadTick((t) => t + 1)
  }

  useEffect(() => {
    let vivant = true
    Promise.all([
      rhApi.getTypesLigneParcours(),
      rhApi.getLignesParcours(),
      rhApi.getEmployes(),
    ])
      .then(([t, l, e]) => {
        if (!vivant) return
        setTypes(unwrapList(t))
        setLignes(unwrapList(l))
        setEmployes(unwrapList(e))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger le parcours des employés.')
        toast.error('Impossible de charger le parcours des employés.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [reloadTick])

  const ligneColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 170, accessor: (l) => employes.find((e) => e.id === l.employe) ? `${employes.find((e) => e.id === l.employe).nom} ${employes.find((e) => e.id === l.employe).prenom}` : String(l.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'type', header: 'Type', width: 150, accessor: (l) => l.type_libelle || '', cell: (v) => v || '—' },
    { id: 'intitule', header: 'Intitulé', width: 200, accessor: (l) => l.intitule || '', cell: (v) => v || '—' },
    { id: 'organisme', header: 'Organisme', width: 160, accessor: (l) => l.organisme || '', cell: (v) => v || '—' },
    { id: 'periode', header: 'Période', width: 200, searchable: false, accessor: (l) => l.date_debut || '', cell: (_v, l) => `${l.date_debut ? formatDate(l.date_debut) : '—'} → ${l.date_fin ? formatDate(l.date_fin) : '—'}` },
  ], [employes])

  const typeColumns = useMemo(() => [
    { id: 'libelle', header: 'Libellé', width: 240, accessor: (t) => t.libelle || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'ordre', header: 'Ordre', width: 100, align: 'right', numeric: true, searchable: false, accessor: (t) => t.ordre ?? 0, cell: (v) => v },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Parcours des employés</h2>
      </div>

      <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue parcours" />

      {vue === 'lignes' ? (
        <ListShell
          title="Lignes de parcours"
          columns={ligneColumns}
          rows={lignes}
          loading={loading}
          error={error}
          searchable
          exportName="lignes-parcours"
          actions={<Button onClick={() => setLigneOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle ligne</Button>}
          emptyTitle="Aucune ligne"
          emptyDescription="Aucune ligne de parcours enregistrée."
        />
      ) : (
        <ListShell
          title="Catalogue de types"
          columns={typeColumns}
          rows={types}
          loading={loading}
          error={error}
          searchable
          exportName="types-ligne-parcours"
          actions={<Button onClick={() => setTypeOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouveau type</Button>}
          emptyTitle="Aucun type"
          emptyDescription="Aucun type de ligne de parcours configuré."
        />
      )}

      {typeOpen && (
        <TypeDialog
          onClose={() => setTypeOpen(false)}
          onSaved={() => { setTypeOpen(false); recharger() }}
        />
      )}
      {ligneOpen && (
        <LigneDialog
          employes={employes}
          types={types}
          onClose={() => setLigneOpen(false)}
          onSaved={() => { setLigneOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

function TypeDialog({ onClose, onSaved }) {
  const [libelle, setLibelle] = useState('')
  const [ordre, setOrdre] = useState('0')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(libelle)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(libelle.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createTypeLigneParcours({ libelle: libelle.trim(), ordre: Number(ordre) || 0 })
      toast.success('Type créé.')
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.libelle?.[0] || 'Création impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouveau type de ligne de parcours</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tlp-libelle">Libellé</Label>
            <Input id="tlp-libelle" autoFocus value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="Ex. Expérience" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tlp-ordre">Ordre</Label>
            <Input id="tlp-ordre" type="number" step="any" value={ordre} onChange={(e) => setOrdre(e.target.value)} />
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

function LigneDialog({ employes, types, onClose, onSaved }) {
  const [employe, setEmploye] = useState('')
  const [type, setType] = useState('')
  const [intitule, setIntitule] = useState('')
  const [organisme, setOrganisme] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(employe || intitule || organisme)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(employe && type && intitule.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createLigneParcours({
        employe, type, intitule: intitule.trim(),
        organisme: organisme || '',
        date_debut: dateDebut || null, date_fin: dateFin || null,
        description: description || '',
      })
      toast.success('Ligne de parcours créée.')
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
        <DialogHeader><DialogTitle>Nouvelle ligne de parcours</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lp-employe">Employé</Label>
              <select id="lp-employe" value={employe} onChange={(e) => setEmploye(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Choisir —</option>
                {employes.map((e) => <option key={e.id} value={e.id}>{e.nom} {e.prenom}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lp-type">Type</Label>
              <select id="lp-type" value={type} onChange={(e) => setType(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm">
                <option value="">— Choisir —</option>
                {types.map((t) => <option key={t.id} value={t.id}>{t.libelle}</option>)}
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lp-intitule">Intitulé</Label>
            <Input id="lp-intitule" value={intitule} onChange={(e) => setIntitule(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lp-organisme">Organisme/employeur (optionnel)</Label>
            <Input id="lp-organisme" value={organisme} onChange={(e) => setOrganisme(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lp-debut">Date de début</Label>
              <Input id="lp-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lp-fin">Date de fin</Label>
              <Input id="lp-fin" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lp-description">Description (optionnel)</Label>
            <Textarea id="lp-description" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
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
