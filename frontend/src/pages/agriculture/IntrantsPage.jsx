import { useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import { ListShell } from '../../ui/module'
import agricultureApi from '../../api/agricultureApi'
import useAgricultureResource from '../../features/agriculture/useAgricultureResource'
import EtapeCampagneForm from '../../components/agriculture/EtapeCampagneForm'

/* ============================================================================
   NTAGR8 — Écran « Intrants » (`/agriculture/intrants`).
   ----------------------------------------------------------------------------
   Catalogue des intrants (dose/DAR) + application d'un traitement sur une
   campagne choisie, avec alerte DAR en direct (`EtapeCampagneForm`).
   ========================================================================== */

const CATEGORIE_LABEL = { semence: 'Semence', engrais: 'Engrais', phyto: 'Phytosanitaire' }

export default function IntrantsPage() {
  const { data: intrants, loading, error } = useAgricultureResource(
    agricultureApi.intrants.list, {})
  const { data: campagnes } = useAgricultureResource(agricultureApi.campagnes.list, {})
  const [campagneId, setCampagneId] = useState('')
  const [showTraitement, setShowTraitement] = useState(false)

  const campagne = useMemo(
    () => (campagnes || []).find((c) => String(c.id) === String(campagneId)) || null,
    [campagnes, campagneId],
  )

  const columns = useMemo(() => [
    {
      id: 'produit', header: 'Produit', width: 200,
      accessor: (r) => r.produit_nom, cell: (v) => v || '—',
    },
    {
      id: 'categorie', header: 'Catégorie', width: 130,
      accessor: (r) => r.categorie_display || r.categorie, cell: (v) => v || '—',
    },
    {
      id: 'dose', header: 'Dose / ha', align: 'right', numeric: true, width: 110,
      accessor: (r) => r.dose_reference_par_ha, cell: (v) => (v != null ? v : '—'),
    },
    {
      id: 'dar', header: 'DAR', align: 'right', numeric: true, width: 90,
      accessor: (r) => r.delai_avant_recolte_jours,
      cell: (v) => (v != null ? <Badge tone="warning">{v} j</Badge> : '—'),
    },
    {
      id: 'amm', header: 'N° AMM', width: 120,
      accessor: (r) => r.numero_amm, cell: (v) => v || '—',
    },
  ], [])

  const actions = (
    <div className="flex items-center gap-2">
      <select
        aria-label="Campagne"
        value={campagneId}
        onChange={(e) => setCampagneId(e.target.value)}
        className="h-9 rounded-md border border-border bg-card px-3 text-sm"
      >
        <option value="">— Choisir une campagne —</option>
        {(campagnes || []).map((c) => (
          <option key={c.id} value={c.id}>{c.culture} — #{c.id}</option>
        ))}
      </select>
      <Button onClick={() => setShowTraitement(true)} disabled={!campagne}>
        <Plus /> Ajouter un traitement
      </Button>
    </div>
  )

  return (
    <div className="page flex flex-col gap-4">
      <ListShell
        title="Intrants"
        subtitle="Catalogue agronomique (semences, engrais, phytosanitaires) lié au stock."
        actions={actions}
        columns={columns}
        rows={intrants}
        loading={loading}
        error={error}
        exportName="intrants"
        emptyTitle="Aucun intrant"
        emptyDescription="Aucun intrant agricole enregistré pour l’instant."
      >
        {!campagne && (
          <p className="text-xs text-muted-foreground">
            Choisissez une campagne pour appliquer un traitement.
          </p>
        )}
      </ListShell>

      {showTraitement && campagne && (
        <EtapeCampagneForm
          campagne={campagne}
          intrants={(intrants || []).filter((i) => i.categorie === 'phyto')}
          onClose={() => setShowTraitement(false)}
          onSaved={() => {
            setShowTraitement(false)
            toast.success('Traitement enregistré.')
          }}
        />
      )}
    </div>
  )
}
