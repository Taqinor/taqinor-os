import { useEffect, useMemo, useState } from 'react'
import { Plus, Play } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Badge, toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, MultiSelect, confirmLeaveIfDirty,
} from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { formatDate } from '../../lib/format'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT92 — Fermetures collectives.
   ----------------------------------------------------------------------------
   `PeriodeFermeture` (XRH14) modélise une fermeture imposée qui, à l'action
   `appliquer`, GÉNÈRE une `DemandeConge` validée par employé concerné
   (idempotent) — le serveur ne duplique jamais un second appel sur une
   fermeture déjà appliquée : on relaie ici le compte de demandes créées
   renvoyé par le serveur, jamais un compte inventé côté client.
   ========================================================================== */

export default function FermeturesCollectives() {
  const { confirm } = useConfirmDialog()
  const [fermetures, setFermetures] = useState([])
  const [typesAbsence, setTypesAbsence] = useState([])
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
    Promise.all([
      rhApi.getPeriodesFermeture(),
      rhApi.getTypesAbsence(),
      rhApi.getDepartements(),
    ])
      .then(([f, t, d]) => {
        if (!vivant) return
        setFermetures(unwrapList(f))
        setTypesAbsence(unwrapList(t))
        setDepartements(unwrapList(d))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les fermetures collectives.')
        toast.error('Impossible de charger les fermetures collectives.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [reloadTick])

  const appliquer = async (f) => {
    const ok = await confirm({
      title: 'Appliquer cette fermeture ?',
      description: `Génère une demande de congé validée par employé concerné pour « ${f.libelle} ». L'opération est idempotente.`,
      confirmLabel: 'Appliquer',
      destructive: false,
    })
    if (!ok) return
    try {
      const res = await rhApi.appliquerPeriodeFermeture(f.id)
      // XRH14 — le compte de demandes créées vient TEL QUEL de la réponse
      // serveur, jamais recalculé/inventé côté client (idempotence visible).
      toast.success(`Fermeture appliquée — ${res?.data?.demandes_creees ?? 0} demande(s) créée(s).`)
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Application impossible.')
    }
  }

  const depLabel = (ids) => {
    if (!ids || ids.length === 0) return 'Toute la société'
    return ids.map((id) => departements.find((d) => d.id === id)?.nom || `#${id}`).join(', ')
  }

  const columns = useMemo(() => [
    { id: 'libelle', header: 'Libellé', width: 200, accessor: (f) => f.libelle || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'periode', header: 'Période', width: 200, searchable: false, accessor: (f) => f.date_debut || '', cell: (_v, f) => `${formatDate(f.date_debut)} → ${formatDate(f.date_fin)}` },
    { id: 'type', header: "Type d'absence", width: 140, accessor: (f) => f.type_absence_code || String(f.type_absence || ''), cell: (v) => v || '—' },
    { id: 'departements', header: 'Départements', width: 200, searchable: false, accessor: (f) => depLabel(f.departements), cell: (v) => v },
    { id: 'appliquee', header: 'Appliquée', width: 110, accessor: (f) => (f.appliquee ? 'oui' : 'non'), cell: (_v, f) => <Badge tone={f.appliquee ? 'success' : 'neutral'}>{f.appliquee ? 'Oui' : 'Non'}</Badge> },
  ], [departements])

  const rowActions = (f) => [
    { id: 'appliquer', label: 'Appliquer', icon: Play, onClick: () => appliquer(f) },
  ]

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Fermetures collectives</h2>
      </div>

      <ListShell
        title="Fermetures"
        columns={columns}
        rows={fermetures}
        loading={loading}
        error={error}
        searchable
        exportName="fermetures-collectives"
        rowActions={rowActions}
        actions={<Button onClick={() => setOpen(true)}><Plus size={15} strokeWidth={1.75} aria-hidden="true" />Nouvelle fermeture</Button>}
        emptyTitle="Aucune fermeture"
        emptyDescription="Aucune fermeture collective configurée."
      />

      {open && (
        <FermetureDialog
          typesAbsence={typesAbsence}
          departements={departements}
          onClose={() => setOpen(false)}
          onSaved={() => { setOpen(false); recharger() }}
        />
      )}
    </div>
  )
}

function FermetureDialog({ typesAbsence, departements, onClose, onSaved }) {
  const [libelle, setLibelle] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [typeAbsence, setTypeAbsence] = useState('')
  const [deps, setDeps] = useState([])
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(libelle || dateDebut || dateFin)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const valide = Boolean(libelle.trim() && dateDebut && dateFin && typeAbsence)

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      await rhApi.createPeriodeFermeture({
        libelle: libelle.trim(), date_debut: dateDebut, date_fin: dateFin,
        type_absence: typeAbsence, departements: deps,
      })
      toast.success('Fermeture créée.')
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
        <DialogHeader><DialogTitle>Nouvelle fermeture collective</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pf-libelle">Libellé</Label>
            <Input id="pf-libelle" autoFocus value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="Ex. Fermeture annuelle" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pf-debut">Du</Label>
              <Input id="pf-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pf-fin">Au</Label>
              <Input id="pf-fin" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pf-type">Type d’absence</Label>
            <select id="pf-type" value={typeAbsence} onChange={(e) => setTypeAbsence(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              <option value="">— Choisir —</option>
              {typesAbsence.map((t) => <option key={t.id} value={t.id}>{t.libelle}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pf-departements">Départements concernés (vide = toute la société)</Label>
            <MultiSelect
              id="pf-departements"
              options={departements.map((d) => ({ value: d.id, label: d.nom }))}
              value={deps}
              onChange={setDeps}
            />
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
