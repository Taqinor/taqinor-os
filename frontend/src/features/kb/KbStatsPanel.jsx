import { useEffect, useState } from 'react'
import { BarChart3 } from 'lucide-react'
import { Card, Button, EmptyState, Spinner } from '../../ui'
import kbApi from '../../api/kbApi'

/* ============================================================================
   XKB16 — Statistiques de la base : top/moins consultés + lacunes de
   connaissance (termes cherchés jamais servis). Lecture seule, responsable/
   admin uniquement (gaté par l'appelant, KbPage).
   ========================================================================== */

function Liste({ titre, items, vide, renderValeur }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-medium">{titre}</h3>
      {items.length ? (
        <ul className="flex flex-col gap-1">
          {items.map((it, i) => (
            <li key={it.id ?? it.terme_norm ?? i} className="flex items-center justify-between gap-3 rounded border border-border px-2.5 py-1.5 text-sm">
              <span className="truncate">{it.titre ?? it.terme_norm}</span>
              <span className="text-xs text-muted-foreground shrink-0">{renderValeur(it)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{vide}</p>
      )}
    </div>
  )
}

export default function KbStatsPanel({ onClose }) {
  const [top, setTop] = useState([])
  const [moins, setMoins] = useState([])
  const [lacunes, setLacunes] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      kbApi.rapportTopConsultes(),
      kbApi.rapportMoinsConsultes(),
      kbApi.rapportLacunesConnaissance(),
    ])
      .then(([t, m, l]) => {
        setTop(Array.isArray(t.data) ? t.data : [])
        setMoins(Array.isArray(m.data) ? m.data : [])
        setLacunes(Array.isArray(l.data) ? l.data : [])
      })
      .catch(() => { setTop([]); setMoins([]); setLacunes([]) })
      .finally(() => setLoading(false))
  }, [])

  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-display text-lg font-semibold">
          <BarChart3 className="size-5" aria-hidden="true" /> Statistiques de la base
        </h2>
        <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
      </div>
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Chargement…
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          <Liste
            titre="Les plus consultés" items={top}
            vide="Aucune consultation enregistrée."
            renderValeur={(it) => `${it.vues} vue(s)`}
          />
          <Liste
            titre="Les moins consultés" items={moins}
            vide="Aucune consultation enregistrée."
            renderValeur={(it) => `${it.vues} vue(s)`}
          />
          <Liste
            titre="Lacunes de connaissance" items={lacunes}
            vide="Aucune recherche sans résultat."
            renderValeur={(it) => `${it.occurrences}×`}
          />
        </div>
      )}
      {!loading && !top.length && !moins.length && !lacunes.length && (
        <EmptyState title="Pas encore de données" description="Les statistiques apparaîtront après les premières consultations et recherches." />
      )}
    </Card>
  )
}
