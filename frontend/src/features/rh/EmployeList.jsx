import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldAlert, UserPlus, Trash2 } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  toast, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, confirmLeaveIfDirty,
} from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { formatDate } from '../../lib/format'
import rhApi from '../../api/rhApi'
import { StatutEmploye, TYPE_CONTRAT_LABELS } from './constants.jsx'

/* ============================================================================
   UX22 — Liste des dossiers employés.
   ----------------------------------------------------------------------------
   Tableau maître (matricule, nom, poste, contrat, embauche, statut) → clic
   ouvre le dossier détaillé (`/rh/employes/:id`). WIR33 — création/édition
   manuelle du dossier (câblées sur `rhApi.createEmploye`/`updateEmploye`/
   `deleteEmploye`, jusqu'ici définis sans appelant) ; les champs sensibles
   (CNSS/CIMR/AMO/situation familiale) restent édités séparément.
   ========================================================================== */

// TypeContrat.choices côté serveur (DossierEmploye) — n'inclut PAS
// « freelance » (présent dans TYPE_CONTRAT_LABELS pour l'affichage d'autres
// écrans) : liste dédiée pour ne jamais soumettre une valeur rejetée en 400.
const TYPE_CONTRAT_OPTIONS = [
  { value: 'cdi', label: 'CDI' },
  { value: 'cdd', label: 'CDD' },
  { value: 'anapec', label: 'ANAPEC' },
  { value: 'stage', label: 'Stage' },
  { value: 'interim', label: 'Intérim' },
]

export default function EmployeList() {
  const navigate = useNavigate()
  const { confirmDelete } = useConfirmDialog()
  const [rows, setRows] = useState([])
  const [alertesSecurite, setAlertesSecurite] = useState([])
  const [departements, setDepartements] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)
  const [createOpen, setCreateOpen] = useState(false)

  const recharger = () => setReloadTick((t) => t + 1)

  useEffect(() => {
    let vivant = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    setLoading(true)
    setError(null)
    rhApi.getEmployes()
      .then((res) => {
        if (!vivant) return
        const data = Array.isArray(res.data) ? res.data : res.data?.results ?? []
        setRows(data)
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les employés.')
        toast.error('Impossible de charger les employés.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    // YHIRE2 — rapport de sécurité : comptes restés actifs alors que le dossier
    // est sorti (doit rester vide en fonctionnement normal).
    rhApi.getComptesActifsSortis()
      .then((res) => { if (vivant) setAlertesSecurite(unwrap(res.data)) })
      .catch(() => { /* non bloquant */ })
    // WIR33 — départements pour le sélecteur du formulaire de création.
    rhApi.getDepartements()
      .then((res) => { if (vivant) setDepartements(unwrap(res.data)) })
      .catch(() => { /* non bloquant — le champ reste optionnel */ })
    return () => { vivant = false }
  }, [reloadTick])

  const supprimer = async (e) => {
    const ok = await confirmDelete({
      title: `Supprimer le dossier de ${e.nom} ${e.prenom} ?`,
      description: 'Cette action est irréversible. Préférez la Sortie si l’employé a réellement quitté l’entreprise.',
      confirmLabel: 'Supprimer',
    })
    if (!ok) return
    try {
      await rhApi.deleteEmploye(e.id)
      toast.success('Dossier employé supprimé.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Suppression impossible.')
    }
  }

  const columns = useMemo(() => [
    {
      id: 'matricule',
      header: 'Matricule',
      width: 120,
      accessor: (e) => e.matricule || '',
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span>,
    },
    {
      id: 'nom',
      header: 'Employé',
      width: 220,
      accessor: (e) => `${e.nom || ''} ${e.prenom || ''}`.trim(),
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'poste',
      header: 'Poste',
      width: 180,
      accessor: (e) => e.poste || '',
      cell: (v) => v || '—',
    },
    {
      id: 'type_contrat',
      header: 'Contrat',
      width: 120,
      accessor: (e) => e.type_contrat_display || TYPE_CONTRAT_LABELS[e.type_contrat] || e.type_contrat || '',
      cell: (v) => v || '—',
    },
    {
      id: 'date_embauche',
      header: 'Embauche',
      width: 120,
      align: 'right',
      searchable: false,
      accessor: (e) => e.date_embauche || '',
      cell: (v) => (v ? formatDate(v) : '—'),
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 120,
      accessor: (e) => e.statut || '',
      cell: (_v, e) => <StatutEmploye status={e.statut} label={e.statut_display} />,
    },
  ], [])

  const rowActions = (e) => [
    { id: 'suppr', label: 'Supprimer', icon: Trash2, destructive: true, onClick: () => supprimer(e) },
  ]

  const actions = (
    <Button onClick={() => setCreateOpen(true)}>
      <UserPlus size={15} strokeWidth={1.75} aria-hidden="true" />
      Nouvel employé
    </Button>
  )

  return (
    <div className="page flex flex-col gap-4">
      {alertesSecurite.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div>
            <p className="font-medium">
              {alertesSecurite.length} compte(s) actif(s) alors que le dossier est sorti
            </p>
            <p className="text-xs">
              {alertesSecurite.map((a) => a.nom || a.matricule || `#${a.id}`).join(', ')}
              {' '}— à désactiver (sortie faite hors du chemin standard).
            </p>
          </div>
        </div>
      )}
      <ListShell
        title="Employés"
        actions={actions}
        columns={columns}
        rows={rows}
        loading={loading}
        error={error}
        searchable
        searchPlaceholder="Rechercher matricule, nom, poste…"
        exportName="employes"
        onRowClick={(e) => navigate(`/rh/employes/${e.id}`)}
        rowActions={rowActions}
        emptyTitle="Aucun employé"
        emptyDescription="Aucun dossier employé pour le moment."
      />
      {createOpen && (
        <CreateEmployeDialog
          departements={departements}
          onClose={() => setCreateOpen(false)}
          onSaved={(id) => { setCreateOpen(false); recharger(); if (id) navigate(`/rh/employes/${id}`) }}
        />
      )}
    </div>
  )
}

/* ── WIR33 — Création manuelle d'un dossier employé ── */
function CreateEmployeDialog({ departements, onClose, onSaved }) {
  const [matricule, setMatricule] = useState('')
  const [nom, setNom] = useState('')
  const [prenom, setPrenom] = useState('')
  const [poste, setPoste] = useState('')
  const [departement, setDepartement] = useState('')
  const [typeContrat, setTypeContrat] = useState('cdi')
  const [dateEmbauche, setDateEmbauche] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(matricule || nom || prenom || poste || departement || dateEmbauche)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const valide = Boolean(matricule.trim() && nom.trim() && prenom.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!valide) return
    setSaving(true)
    setServerError(null)
    try {
      const res = await rhApi.createEmploye({
        matricule: matricule.trim(),
        nom: nom.trim(),
        prenom: prenom.trim(),
        poste: poste || '',
        departement: departement || null,
        type_contrat: typeContrat,
        date_embauche: dateEmbauche || null,
      })
      toast.success('Dossier employé créé.')
      onSaved?.(res?.data?.id)
    } catch (err) {
      const data = err?.response?.data
      setServerError(data?.detail || data?.matricule || data?.nom
        || 'Création du dossier impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau dossier employé</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="emp-matricule">Matricule</Label>
              <Input id="emp-matricule" autoFocus value={matricule} onChange={(e) => setMatricule(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="emp-embauche">Date d’embauche</Label>
              <Input id="emp-embauche" type="date" value={dateEmbauche} onChange={(e) => setDateEmbauche(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="emp-nom">Nom</Label>
              <Input id="emp-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="emp-prenom">Prénom</Label>
              <Input id="emp-prenom" value={prenom} onChange={(e) => setPrenom(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="emp-poste">Poste</Label>
            <Input id="emp-poste" value={poste} onChange={(e) => setPoste(e.target.value)} placeholder="Ex. Technicien photovoltaïque" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="emp-departement">Département</Label>
              <select
                id="emp-departement"
                value={departement}
                onChange={(e) => setDepartement(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Aucun —</option>
                {departements.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="emp-contrat">Type de contrat</Label>
              <select
                id="emp-contrat"
                value={typeContrat}
                onChange={(e) => setTypeContrat(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {TYPE_CONTRAT_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!valide || saving}>
              {saving ? 'Création…' : 'Créer le dossier'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
