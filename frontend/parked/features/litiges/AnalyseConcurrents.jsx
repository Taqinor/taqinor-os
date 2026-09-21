import { useEffect, useState } from 'react'
import { Card, Badge, EmptyState, Spinner } from '../../ui'
import { formatMAD } from '../../lib/format'
import litigesApi from '../../api/litigesApi'

/* ============================================================================
   UX44 — Analyse concurrents sur deals perdus (LITIGE5).
   ----------------------------------------------------------------------------
   Intelligence concurrentielle : qui nous bat, à quel prix moyen, et sur quels
   motifs, agrégée sur les litiges portant un concurrent gagnant saisi. Lecture
   seule (``analyse-concurrents``). Aucun coût/marge — que du prix concurrent.
   ========================================================================== */

export default function AnalyseConcurrents() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    litigesApi.analyseConcurrents()
      .then((res) => setData(res.data))
      .catch(() => setError('Analyse indisponible.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement de l’analyse…
      </div>
    )
  }
  if (error) {
    return <EmptyState title="Analyse indisponible" description={error} />
  }

  const parConcurrent = data?.par_concurrent ?? []
  const parMotif = data?.par_motif ?? []
  const total = data?.total_litiges_avec_concurrent ?? 0

  if (!total) {
    return (
      <EmptyState
        title="Aucun deal perdu documenté"
        description="Renseignez un concurrent gagnant sur une réclamation pour alimenter l’analyse."
      />
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-muted-foreground">
        {total} litige(s) portent un concurrent gagnant saisi.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-4 sm:p-5">
          <h3 className="mb-3 font-display text-base font-semibold tracking-tight">
            Par concurrent
          </h3>
          {parConcurrent.length ? (
            <ul className="flex flex-col gap-2">
              {parConcurrent.map((c) => (
                <li
                  key={c.concurrent}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm"
                >
                  <span className="flex items-center gap-2">
                    <span className="font-medium">{c.concurrent}</span>
                    <Badge tone="info">{c.nombre}</Badge>
                  </span>
                  <span className="text-muted-foreground">
                    {c.prix_moyen != null
                      ? `${formatMAD(c.prix_moyen, { withSymbol: false })} ${c.devise || 'MAD'} (moy.)`
                      : 'Prix inconnu'}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Aucun concurrent saisi.</p>
          )}
        </Card>

        <Card className="p-4 sm:p-5">
          <h3 className="mb-3 font-display text-base font-semibold tracking-tight">
            Par motif de perte
          </h3>
          {parMotif.length ? (
            <ul className="flex flex-col gap-2">
              {parMotif.map((m) => (
                <li
                  key={m.motif}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm"
                >
                  <span className="font-medium">{m.motif}</span>
                  <Badge tone="neutral">{m.nombre}</Badge>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Aucun motif saisi.</p>
          )}
        </Card>
      </div>
    </div>
  )
}
