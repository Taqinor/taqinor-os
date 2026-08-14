import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeftRight, Download, RefreshCw } from 'lucide-react'
import scmApi from '../../api/scmApi'
import { Button, DataTable, EmptyState, Skeleton } from '../../ui'
import { StateBlock } from '../../components/StateBlock'

/* ============================================================================
   NTSCM20/41 — Suggestions de transfert inter-sites (anticipatif) : croise le
   stock disponible par dépôt avec la prévision de demande par segment pour
   proposer un transfert d'un dépôt en surstock projeté vers un dépôt en
   rupture projetée — AVANT qu'un seuil déjà franchi ne déclenche (FG326).
   Écran INTERNE (Responsable/Admin), lecture seule + export .xlsx (NTSCM41).
   ========================================================================== */

export default function TransfertsSuggeresPage() {
  const [lignes, setLignes] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [exportBusy, setExportBusy] = useState(false)

  const charger = useCallback(() => {
    setLoading(true)
    setLoadError(null)
    return scmApi.suggestionsTransfert()
      .then((r) => setLignes(r.data ?? []))
      .catch((e) => setLoadError(
        e?.response?.status === 403
          ? 'Réservé aux responsables et administrateurs.'
          : (e?.response?.data?.detail ?? "Les suggestions de transfert n'ont pas pu être chargées.")))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { Promise.resolve().then(charger) }, [charger])

  const exporter = async () => {
    setExportBusy(true)
    try {
      const res = await scmApi.exportSuggestionsTransfert()
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'suggestions-transfert.xlsx'
      a.click()
      window.URL.revokeObjectURL(url)
    } finally {
      setExportBusy(false)
    }
  }

  const columns = useMemo(() => [
    { id: 'produit_nom', header: 'Produit', accessor: (r) => r.produit_nom },
    {
      id: 'emplacement_source_nom', header: 'Dépôt source',
      accessor: (r) => r.emplacement_source_nom,
    },
    {
      id: 'emplacement_destination_nom', header: 'Dépôt destination',
      accessor: (r) => r.emplacement_destination_nom,
    },
    {
      id: 'quantite_suggeree', header: 'Quantité suggérée', align: 'right', width: 150,
      accessor: (r) => Number(r.quantite_suggeree) || 0,
      cell: (v, r) => <span className="font-semibold tabular-nums">{r.quantite_suggeree}</span>,
    },
  ], [])

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>Suggestions de transfert inter-sites</h2>
        <p className="text-sm text-muted-foreground">
          Transferts suggérés entre dépôts secondaires, pilotés par l&apos;écart
          offre/demande PROJETÉ (anticipatif) plutôt qu&apos;un seuil déjà
          franchi.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" size="sm" onClick={charger}>
          <RefreshCw /> Actualiser
        </Button>
        <Button
          type="button" variant="outline" size="sm" loading={exportBusy}
          onClick={exporter} disabled={lignes.length === 0}
          title="Exporte les suggestions de transfert (produit, dépôts, quantité, justification) au format .xlsx."
        >
          <Download /> Exporter
        </Button>
      </div>

      {loading ? (
        <Skeleton className="h-64 w-full" />
      ) : loadError ? (
        <StateBlock error={loadError} onRetry={charger} />
      ) : lignes.length === 0 ? (
        <EmptyState
          icon={ArrowLeftRight}
          title="Aucun transfert suggéré"
          description="Aucun surplus/déficit projeté détecté entre dépôts secondaires pour le moment."
        />
      ) : (
        <DataTable
          data={lignes}
          columns={columns}
          getRowId={(r, i) => `${r.produit_id}-${r.emplacement_source_id}-${r.emplacement_destination_id}-${i}`}
          pageSize={25}
          aria-label="Suggestions de transfert inter-sites"
        />
      )}
    </div>
  )
}
