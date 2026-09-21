import { useEffect, useMemo, useState } from 'react'
import { HardHat } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Card, Stat, Label, Input, toast } from '../../ui'
import { formatDate } from '../../lib/format'
import rhApi from '../../api/rhApi'

/* ============================================================================
   AUDV20 — Présents chantier (effectif d'un chantier un jour donné).
   ----------------------------------------------------------------------------
   `selectors.effectif_present_le` (FG170) comptait déjà les employés
   RÉELLEMENT présents sur un chantier un jour donné — brique de facturation
   main-d'œuvre et de preuve en litige — mais aucun écran ne l'appelait.
   Cet écran est son consommateur : on choisit un chantier (`installation_id`)
   et un jour, le serveur renvoie l'effectif ET la liste des lignes retenues
   (ABSENT exclus), pour qu'un nombre facturé soit toujours accompagné de QUI
   il compte. Lecture gatée `rh_voir` côté serveur (jamais IsAnyRole).
   ========================================================================== */

const aujourdHui = () => new Date().toISOString().slice(0, 10)

export default function PresentsChantier() {
  const [installationId, setInstallationId] = useState('')
  const [jour, setJour] = useState(aujourdHui)
  // Un SEUL état pour la réponse : la remise à zéro avant chaque résolution
  // tient alors en une instruction (voir la dérogation ciblée ci-dessous).
  const [etat, setEtat] = useState({ data: null, loading: false, error: null })
  const { data, loading, error } = etat

  useEffect(() => {
    const id = String(installationId).trim()
    let vivant = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialise avant résolution (changement de chantier ou de jour)
    setEtat({ data: null, loading: Boolean(id), error: null })
    if (!id) return undefined
    rhApi.getEffectifChantier({ installation_id: id, date: jour })
      .then((res) => {
        if (vivant) setEtat({ data: res.data, loading: false, error: null })
      })
      .catch(() => {
        if (!vivant) return
        setEtat({
          data: null,
          loading: false,
          error: 'Impossible de charger l’effectif du chantier.',
        })
        toast.error('Impossible de charger l’effectif du chantier.')
      })
    return () => { vivant = false }
  }, [installationId, jour])

  const columns = useMemo(() => [
    {
      id: 'employe',
      header: 'Employé',
      width: 220,
      accessor: (p) => p.employe_nom || String(p.employe || ''),
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 140,
      accessor: (p) => p.statut_display || p.statut || '',
      cell: (v) => v || '—',
    },
    {
      id: 'emarge',
      header: 'Émargé',
      width: 110,
      searchable: false,
      accessor: (p) => (p.emarge ? 'Oui' : 'Non'),
      cell: (v) => v,
    },
    {
      id: 'date',
      header: 'Jour',
      width: 130,
      searchable: false,
      accessor: (p) => p.date || '',
      cell: (v) => formatDate(v),
    },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Présents chantier</h2>
      </div>

      <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-end">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="pc-installation">Chantier (ID installation)</Label>
          <Input
            id="pc-installation"
            inputMode="numeric"
            value={installationId}
            onChange={(e) => setInstallationId(e.target.value)}
            placeholder="Ex. 42"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="pc-date">Jour</Label>
          <Input
            id="pc-date"
            type="date"
            value={jour}
            onChange={(e) => setJour(e.target.value)}
          />
        </div>
        <div className="sm:ml-auto">
          <Stat
            label="Effectif présent"
            value={data ? String(data.effectif ?? 0) : '—'}
            hint={data ? `le ${formatDate(data.date)}` : 'Choisir un chantier'}
            icon={HardHat}
          />
        </div>
      </Card>

      <ListShell
        title="Employés comptés"
        subtitle="Lignes de présence retenues (absents exclus)"
        columns={columns}
        rows={data?.presents ?? []}
        loading={loading}
        error={error}
        searchable
        exportName="presents-chantier"
        emptyTitle="Aucun présent"
        emptyDescription="Aucun employé n’est compté présent sur ce chantier ce jour-là."
      />
    </div>
  )
}
