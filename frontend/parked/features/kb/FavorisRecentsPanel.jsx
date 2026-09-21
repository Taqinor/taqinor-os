import { useEffect, useState } from 'react'
import { Star, Clock } from 'lucide-react'
import { Card, Button, EmptyState, Spinner } from '../../ui'
import { formatDateTime } from '../../lib/format'
import kbApi from '../../api/kbApi'
import { StatutArticlePill } from './kbStatus'

/* ============================================================================
   XKB15 — « Mes favoris » + « Récemment consultés », personnels à
   l'utilisateur courant. Panneau replié par défaut (comme ArticleTree),
   ouvert à la demande depuis KbPage.
   ========================================================================== */

export default function FavorisRecentsPanel({ onSelect, onClose }) {
  const [favoris, setFavoris] = useState([])
  const [recents, setRecents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([kbApi.listFavoris(), kbApi.recents()])
      .then(([f, r]) => {
        setFavoris(Array.isArray(f.data) ? f.data : (f.data?.results ?? []))
        setRecents(Array.isArray(r.data) ? r.data : [])
      })
      .catch(() => { setFavoris([]); setRecents([]) })
      .finally(() => setLoading(false))
  }, [])

  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-semibold">Favoris &amp; récents</h2>
        <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
      </div>
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Chargement…
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <h3 className="flex items-center gap-1.5 text-sm font-medium">
              <Star className="size-4" aria-hidden="true" /> Mes favoris
            </h3>
            {favoris.length ? (
              <ul className="flex flex-col gap-1.5">
                {favoris.map((f) => (
                  <li key={f.id}>
                    <button
                      type="button"
                      onClick={() => onSelect?.({ id: f.article })}
                      className="flex w-full items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-left text-sm hover:bg-muted/60"
                    >
                      <span className="truncate">{f.article_titre || `Article #${f.article}`}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="Aucun favori" description="Étoilez un article depuis son détail." />
            )}
          </div>
          <div className="flex flex-col gap-2">
            <h3 className="flex items-center gap-1.5 text-sm font-medium">
              <Clock className="size-4" aria-hidden="true" /> Récemment consultés
            </h3>
            {recents.length ? (
              <ul className="flex flex-col gap-1.5">
                {recents.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => onSelect?.({ id: r.id })}
                      className="flex w-full items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-left text-sm hover:bg-muted/60"
                    >
                      <span className="truncate">{r.titre}</span>
                      <span className="flex items-center gap-2 shrink-0">
                        <StatutArticlePill status={r.statut} />
                        <span className="text-xs text-muted-foreground">{formatDateTime(r.lu_le)}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="Aucune consultation" description="Les articles lus récemment apparaîtront ici." />
            )}
          </div>
        </div>
      )}
    </Card>
  )
}
