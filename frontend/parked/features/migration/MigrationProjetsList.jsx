import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'

import { ListShell } from '../../ui/module'
import { Button, Input, Label, toast } from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import migrationApi from '../../api/migrationApi'
import {
  SOURCES, STATUTS_PROJET, errMessage, labelSource,
} from './constants'

/* ============================================================================
   NTMIG16 — Écran « Migration » : liste des projets de migration ERP.
   ----------------------------------------------------------------------------
   Réservé Administrateur/Directeur (garde serveur IsDirecteurOuAdmin ; la
   route est gatée en plus côté module.config). Avancement = lots réconciliés
   sur total : c'est le seul chiffre qui compte, un lot n'étant « réconcilié »
   que si son rapport est conforme ou explicitement dérogé (NTMIG5).
   ========================================================================== */

const COLUMNS = [
  { id: 'nom', header: 'Projet', accessor: (r) => r.nom, sortable: true },
  {
    id: 'source',
    header: 'Source',
    accessor: (r) => labelSource(r.source),
    sortable: true,
  },
  {
    id: 'statut',
    header: 'Statut',
    accessor: (r) => STATUTS_PROJET[r.statut] || r.statut,
    sortable: true,
  },
  {
    id: 'avancement',
    header: 'Avancement',
    accessor: (r) => `${r.lots_reconcilies ?? 0} / ${r.lots_total ?? 0} lots`,
  },
]

export default function MigrationProjetsList() {
  const navigate = useNavigate()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await migrationApi.listProjets()
      const data = res?.data
      setRows(Array.isArray(data) ? data : data?.results ?? [])
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger les projets de migration.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => {
      if (alive) await load()
    })()
    return () => {
      alive = false
    }
  }, [load])

  return (
    <>
      <ListShell
        title="Migration ERP"
        subtitle="Projets de migration sortants (Odoo, Sage, Excel) — aucun lot n'est
          déclaré réussi sans rapport de réconciliation."
        actions={(
          <Button onClick={() => setShowForm(true)}>
            <Plus className="size-4" aria-hidden="true" />
            {' '}Nouveau projet de migration
          </Button>
        )}
        columns={COLUMNS}
        rows={rows}
        loading={loading}
        error={error}
        searchPlaceholder="Rechercher un projet de migration…"
        exportName="projets-migration"
        onRowClick={(p) => navigate(`/migration/projet/${p.id}`)}
        emptyTitle="Aucun projet de migration"
        emptyDescription="Créez un projet pour reprendre les données d'un ERP existant."
      />
      {showForm && (
        <NouveauProjetDialog
          onClose={() => setShowForm(false)}
          onSaved={(cree) => {
            setShowForm(false)
            toast.success('Projet de migration créé.')
            if (cree?.id) navigate(`/migration/projet/${cree.id}`)
            else load()
          }}
        />
      )}
    </>
  )
}

function NouveauProjetDialog({ onClose, onSaved }) {
  const [nom, setNom] = useState('')
  const [source, setSource] = useState('odoo')
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!nom.trim()) {
      toast.error('Le nom du projet est requis.')
      return
    }
    setSaving(true)
    try {
      const res = await migrationApi.createProjet({ nom: nom.trim(), source })
      onSaved(res?.data)
    } catch (err) {
      toast.error(errMessage(err, 'Création impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => {
        if (!o) onClose()
      }}
      title="Nouveau projet de migration"
      description="Le projet démarre en brouillon ; les lots par entité s'ajoutent ensuite."
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="mig-nom" required>Nom du projet</Label>
          <Input
            id="mig-nom"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            placeholder="Reprise Odoo — Société Cliente"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="mig-source" required>Source</Label>
          <select
            id="mig-source"
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? 'Création…' : 'Créer le projet'}
          </Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}
