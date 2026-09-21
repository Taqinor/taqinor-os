import { useEffect, useMemo, useState } from 'react'
import { Users } from 'lucide-react'
import { ListShell } from '../../ui/module'
import {
  Card, Stat, Label, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import rhApi from '../../api/rhApi'

/* ============================================================================
   NTFSM26 — Vue équipe & compétences par zone géographique (dispatch).
   ----------------------------------------------------------------------------
   Pour affecter vite une intervention dans une région, il faut voir d'un coup
   QUI est dans la zone, ce qu'il sait faire (compétences FG172) et ce qu'il a
   le droit de faire (habilitations FG173, seuls les titres VALIDES sont
   servis par le serveur — un titre périmé ne donne aucun droit sur chantier).

   La liste des zones vient du serveur (`employes/zones-intervention/`) : ce
   sont EXACTEMENT les zones déclarées sur les dossiers, jamais une liste de
   villes inventée. Un technicien sans zone déclarée n'apparaît dans aucun
   filtre par zone — le supposer disponible partout serait une donnée inventée.
   ========================================================================== */

// Radix Select interdit la chaîne vide comme valeur d'item : « toutes les
// zones » porte donc un jeton dédié, traduit en « pas de filtre » à l'appel.
const TOUTES = '__toutes__'

export default function EquipePage() {
  const [zone, setZone] = useState(TOUTES)
  const [zones, setZones] = useState([])
  const [etat, setEtat] = useState({ rows: [], loading: true, error: null })
  const { rows, loading, error } = etat

  useEffect(() => {
    let vivant = true
    rhApi.getZonesIntervention()
      .then((res) => {
        if (vivant) setZones(Array.isArray(res.data) ? res.data : [])
      })
      .catch(() => {
        // Le filtre dégrade proprement : sans la liste, « Toutes les zones »
        // reste utilisable.
        if (vivant) setZones([])
      })
    return () => { vivant = false }
  }, [])

  useEffect(() => {
    let vivant = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- remet la liste en chargement avant chaque résolution (changement de zone)
    setEtat({ rows: [], loading: true, error: null })
    const filtre = zone === TOUTES ? undefined : { zone }
    rhApi.getEquipeTerrain(filtre)
      .then((res) => {
        if (!vivant) return
        setEtat({
          rows: Array.isArray(res.data) ? res.data : [],
          loading: false,
          error: null,
        })
      })
      .catch(() => {
        if (!vivant) return
        setEtat({
          rows: [],
          loading: false,
          error: 'Impossible de charger l’équipe terrain.',
        })
        toast.error('Impossible de charger l’équipe terrain.')
      })
    return () => { vivant = false }
  }, [zone])

  const columns = useMemo(() => [
    {
      id: 'technicien',
      header: 'Technicien',
      width: 200,
      accessor: (t) => `${t.nom || ''} ${t.prenom || ''}`.trim(),
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'poste',
      header: 'Poste',
      width: 170,
      accessor: (t) => t.poste || '',
      cell: (v) => v || '—',
    },
    {
      id: 'zone',
      header: 'Zone d’intervention',
      width: 170,
      accessor: (t) => t.zone_intervention || '',
      cell: (v) => v || (
        <span className="text-muted-foreground">Non déclarée</span>
      ),
    },
    {
      id: 'competences',
      header: 'Compétences',
      width: 260,
      accessor: (t) => (t.competences || [])
        .map((c) => `${c.libelle} (${c.niveau_display})`).join(', '),
      cell: (v) => v || '—',
    },
    {
      id: 'habilitations',
      header: 'Habilitations valides',
      width: 240,
      accessor: (t) => (t.habilitations || [])
        .map((h) => h.libelle).join(', '),
      cell: (v) => v || '—',
    },
    {
      id: 'telephone',
      header: 'Téléphone',
      width: 140,
      searchable: false,
      accessor: (t) => t.telephone || '',
      cell: (v) => v || '—',
    },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Équipe terrain</h2>
      </div>

      <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-end">
        <div className="flex w-full flex-col gap-1.5 sm:w-[260px]">
          <Label>Zone d’intervention</Label>
          <Select value={zone} onValueChange={setZone}>
            <SelectTrigger aria-label="Zone d’intervention">
              <SelectValue placeholder="Toutes les zones" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TOUTES}>Toutes les zones</SelectItem>
              {zones.map((z) => (
                <SelectItem key={z} value={z}>{z}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="sm:ml-auto">
          <Stat
            label="Techniciens"
            value={String(rows.length)}
            hint={zone === TOUTES ? 'toutes zones' : `zone ${zone}`}
            icon={Users}
          />
        </div>
      </Card>

      <ListShell
        title="Techniciens disponibles"
        subtitle="Compétences et habilitations valides, par zone"
        columns={columns}
        rows={rows}
        loading={loading}
        error={error}
        searchable
        exportName="equipe-terrain"
        emptyTitle="Aucun technicien"
        emptyDescription="Aucun technicien actif ne couvre cette zone."
      />
    </div>
  )
}
