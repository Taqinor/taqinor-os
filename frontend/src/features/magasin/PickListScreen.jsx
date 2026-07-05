import { useEffect, useMemo, useState } from 'react'
import {
  Card, Badge, Checkbox, Button, Segmented, EmptyState,
} from '../../ui'
import { ListShell } from '../../ui/module'
import installationsApi from '../../api/installationsApi'
import { formatDate } from '../../lib/format'
import useMagasinResource from './useMagasinResource'
import { sortPickListLignesByBin, pickListProgress } from './magasin'
import { PickListStatutPill } from './statusPills'

/* ============================================================================
   XSTK1 — Bons de prélèvement (`/magasin/prelevements`).
   ----------------------------------------------------------------------------
   Liste des bons (`PickList`, FG321) par chantier ; clic → détail avec les
   lignes ORDONNÉES PAR CASIER (`sortPickListLignesByBin`, miroir de l'ordre
   serveur) que le préparateur coche au fur et à mesure (`quantite_prelevee`).
   ========================================================================== */

const STATUT_FILTERS = [
  { value: '', label: 'Tous statuts' },
  { value: 'emis', label: 'Émis' },
  { value: 'en_cours', label: 'En cours' },
  { value: 'termine', label: 'Terminé' },
]

function PickListDetail({ pickList, onClose, onChanged }) {
  const [lignes, setLignes] = useState(sortPickListLignesByBin(pickList.lignes))
  const [busyLigneId, setBusyLigneId] = useState(null)

  useEffect(() => {
    setLignes(sortPickListLignesByBin(pickList.lignes))
  }, [pickList])

  const progress = pickListProgress(lignes)

  const toggleLigne = async (ligne) => {
    setBusyLigneId(ligne.id)
    try {
      const nextPreleve = !ligne.preleve
      const res = await installationsApi.updatePickListLigne(ligne.id, {
        preleve: nextPreleve,
        quantite_prelevee: nextPreleve ? ligne.quantite_demandee : 0,
      })
      setLignes((prev) => prev.map((l) => (l.id === ligne.id ? res.data : l)))
    } finally {
      setBusyLigneId(null)
    }
  }

  const demarrer = async () => {
    await installationsApi.demarrerPickList(pickList.id)
    onChanged?.()
  }
  const terminer = async () => {
    await installationsApi.terminerPickList(pickList.id)
    onChanged?.()
  }

  return (
    <Card className="p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-display text-base font-semibold tracking-tight">
            {pickList.reference}
          </h3>
          <p className="text-sm text-muted-foreground">
            {progress.done}/{progress.total} ligne(s) prélevée(s) ({progress.pct}%)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <PickListStatutPill status={pickList.statut} />
          {pickList.statut === 'emis' && (
            <Button size="sm" onClick={demarrer}>Démarrer</Button>
          )}
          {pickList.statut === 'en_cours' && (
            <Button size="sm" onClick={terminer}>Terminer</Button>
          )}
          <Button size="sm" variant="outline" onClick={onClose}>Fermer</Button>
        </div>
      </div>

      {lignes.length === 0 ? (
        <EmptyState title="Aucune ligne" description="Ce bon ne contient aucune ligne de prélèvement." />
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {lignes.map((ligne) => (
            <li key={ligne.id} className="flex items-center gap-3 py-2">
              <Checkbox
                checked={Boolean(ligne.preleve)}
                disabled={busyLigneId === ligne.id}
                onCheckedChange={() => toggleLigne(ligne)}
                aria-label={`Prélevé : ${ligne.designation || ligne.produit_nom || ''}`}
              />
              <span className="w-20 shrink-0 font-mono text-xs text-muted-foreground">
                {ligne.bin_code || '—'}
              </span>
              <span className="flex-1 text-sm">
                {ligne.produit_nom || ligne.designation || `Produit ${ligne.produit}`}
              </span>
              <span className="text-sm text-muted-foreground">
                {ligne.quantite_prelevee ?? 0} / {ligne.quantite_demandee ?? 0}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export default function PickListScreen() {
  const [statut, setStatut] = useState('')
  const [selected, setSelected] = useState(null)

  const params = useMemo(() => (statut ? { statut } : {}), [statut])

  const { data, loading, error, reload } = useMagasinResource(
    installationsApi.getPickLists, params, [statut],
  )

  useEffect(() => {
    if (!selected) return
    const fresh = data.find((p) => p.id === selected.id)
    if (fresh) setSelected(fresh)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  const openDetail = async (row) => {
    const res = await installationsApi.getPickList(row.id)
    setSelected(res.data)
  }

  const columns = useMemo(() => [
    { id: 'reference', header: 'Référence', width: 160, accessor: (r) => r.reference, cell: (v) => <span className="font-mono">{v}</span> },
    {
      id: 'installation',
      header: 'Chantier',
      width: 220,
      accessor: (r) => r.installation_nom || r.installation,
      cell: (v) => v || '—',
    },
    {
      id: 'lignes',
      header: 'Lignes',
      align: 'right',
      width: 90,
      accessor: (r) => (Array.isArray(r.lignes) ? r.lignes.length : 0),
      cell: (v) => <Badge tone="neutral">{v}</Badge>,
    },
    { id: 'statut', header: 'Statut', width: 120, accessor: (r) => r.statut, cell: (v) => <PickListStatutPill status={v} /> },
    { id: 'date_creation', header: 'Créé le', width: 120, accessor: (r) => r.date_creation, cell: (v) => (v ? formatDate(v) : '—') },
  ], [])

  const filters = (
    <Segmented options={STATUT_FILTERS} value={statut} onChange={setStatut} aria-label="Filtrer par statut" />
  )

  return (
    <div className="page flex flex-col gap-4">
      <ListShell
        title="Bons de prélèvement"
        subtitle="Un bon par chantier — lignes ordonnées par casier pour minimiser le parcours."
        filters={filters}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        onRowClick={openDetail}
        exportName="pick-lists"
        emptyTitle="Aucun bon"
        emptyDescription="Aucun bon de prélèvement pour ce filtre."
      />

      {selected && (
        <PickListDetail
          pickList={selected}
          onClose={() => setSelected(null)}
          onChanged={reload}
        />
      )}
    </div>
  )
}
