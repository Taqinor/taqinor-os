import { useMemo, useState } from 'react'
import { MapPin, Package } from 'lucide-react'
import { Card, Badge, Segmented, EmptyState, Skeleton } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import installationsApi from '../../api/installationsApi'
import useMagasinResource from './useMagasinResource'
import { buildBinTree, countBinsInTree } from './magasin'

/* ============================================================================
   XSTK1 — Arborescence des casiers (`/magasin/casiers`).
   ----------------------------------------------------------------------------
   Liste les casiers (`BinLocation`, FG319) regroupés emplacement → zone →
   allée → casier. Chaque casier affiche les produits qui lui sont affectés
   (`BinAffectation`, quantité INDICATIVE — jamais le prix d'achat, jamais
   présent dans ce serializer). Bascule « actifs / y compris archivés ».
   ========================================================================== */

const ARCHIVE_FILTERS = [
  { value: '0', label: 'Casiers actifs' },
  { value: '', label: 'Tous (y compris archivés)' },
]

export default function BinTreeScreen() {
  const [archived, setArchived] = useState('0')

  const params = useMemo(
    () => (archived ? { archived } : {}),
    [archived],
  )

  const { data, loading, error } = useMagasinResource(
    installationsApi.getBinLocations, params, [archived],
  )

  const tree = useMemo(
    () => buildBinTree(data, { includeArchived: archived === '' }),
    [data, archived],
  )
  const total = useMemo(() => countBinsInTree(tree), [tree])

  return (
    <div className="page flex flex-col gap-4">
      <PageHeader
        title="Casiers de rangement"
        subtitle="Arborescence des emplacements — zone / allée / casier."
        filters={(
          <Segmented
            options={ARCHIVE_FILTERS}
            value={archived}
            onChange={setArchived}
            aria-label="Filtrer par archivage"
          />
        )}
      />

      {error && (
        <EmptyState
          title="Impossible de charger les casiers"
          description={error}
        />
      )}

      {loading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((unused, i) => (
            <Card key={i} className="p-4"><Skeleton className="h-6 w-1/3" /></Card>
          ))}
        </div>
      )}

      {!loading && !error && tree.length === 0 && (
        <EmptyState
          icon={MapPin}
          title="Aucun casier"
          description="Aucun casier de rangement n'est configuré pour cette société."
        />
      )}

      {!loading && !error && tree.length > 0 && (
        <>
          <p className="text-sm text-muted-foreground">{total} casier(s) au total.</p>
          <div className="flex flex-col gap-4">
            {tree.map((emp) => (
              <Card key={emp.id} className="p-4 sm:p-5">
                <h3 className="mb-3 flex items-center gap-2 font-display text-base font-semibold tracking-tight">
                  <MapPin size={16} strokeWidth={1.75} aria-hidden="true" />
                  {emp.label}
                </h3>
                <div className="flex flex-col gap-3">
                  {emp.zones.map((zone) => (
                    <div key={zone.id} className="rounded-lg border border-border p-3">
                      <p className="mb-2 text-sm font-medium text-muted-foreground">
                        Zone {zone.label}
                      </p>
                      <div className="flex flex-col gap-2">
                        {zone.allees.map((allee) => (
                          <div key={allee.id} className="pl-2">
                            <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                              Allée {allee.label}
                            </p>
                            <div className="flex flex-wrap gap-2">
                              {allee.bins.map((bin) => (
                                <div
                                  key={bin.id}
                                  className="rounded-md border border-border bg-card px-3 py-2 text-sm"
                                >
                                  <div className="flex items-center gap-2">
                                    <span className="font-mono font-medium">{bin.code}</span>
                                    {bin.archived && <Badge tone="neutral">Archivé</Badge>}
                                  </div>
                                  {Array.isArray(bin.affectations) && bin.affectations.length > 0 && (
                                    <ul className="mt-1 flex flex-col gap-0.5 text-xs text-muted-foreground">
                                      {bin.affectations.map((aff) => (
                                        <li key={aff.id} className="flex items-center gap-1">
                                          <Package size={12} strokeWidth={1.75} aria-hidden="true" />
                                          {aff.produit_nom || `Produit ${aff.produit}`} × {aff.quantite}
                                        </li>
                                      ))}
                                    </ul>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
