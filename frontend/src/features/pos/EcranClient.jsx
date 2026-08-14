import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import posApi from '../../api/posApi'
import { formatMAD } from '../../lib/format'
import { EmptyState } from '../../ui'

// NTRET31 — Écran client (customer-facing display), route /pos/ecran-client/
// :session_id. LECTURE SEULE — aucune action n'est jamais exposée ici, le
// panier reflète celui poussé par l'écran caisse (CaisseScreen) via un
// polling léger (re-fetch, pas de WebSocket). Pensé pour un second moniteur
// ou une tablette tournée vers le client, sans login séparé.
const POLL_INTERVAL_MS = 2000

export default function EcranClient() {
  const { session_id: sessionId } = useParams()
  const [panier, setPanier] = useState(null)
  const [erreur, setErreur] = useState(false)

  useEffect(() => {
    if (!sessionId) return undefined
    let annule = false

    const rafraichir = () => {
      posApi.getPanierCourant(sessionId)
        .then((r) => {
          if (annule) return
          setPanier(r?.data?.panier || null)
          setErreur(false)
        })
        .catch(() => { if (!annule) setErreur(true) })
    }

    rafraichir()
    const timer = setInterval(rafraichir, POLL_INTERVAL_MS)
    return () => { annule = true; clearInterval(timer) }
  }, [sessionId])

  const lignes = panier?.lignes || []
  const total = panier?.total

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background p-8" data-testid="ecran-client">
      {erreur && (
        <div className="text-sm text-muted-foreground">Connexion à la caisse en attente…</div>
      )}
      {!erreur && lignes.length === 0 && (
        <EmptyState title="Panier vide" description="En attente d’un article…" />
      )}
      {lignes.length > 0 && (
        <div className="w-full max-w-2xl">
          <ul className="flex flex-col gap-3" data-testid="ecran-client-lignes">
            {lignes.map((l, i) => (
              <li key={i} className="flex items-center justify-between text-2xl">
                <span>{l.nom} × {l.quantite}</span>
                <span className="tabular-nums">
                  {formatMAD((l.prix_ttc || 0) * (l.quantite || 0), { withSymbol: false })} DH
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-8 flex items-center justify-between border-t border-border pt-4 text-4xl font-semibold">
            <span>Total</span>
            <span className="tabular-nums" data-testid="ecran-client-total">
              {formatMAD(total || 0, { withSymbol: false })} DH
            </span>
          </div>
          {panier?.rendu > 0 && (
            <div className="mt-4 text-right text-2xl text-muted-foreground">
              Monnaie rendue : {formatMAD(panier.rendu, { withSymbol: false })} DH
            </div>
          )}
        </div>
      )}
    </div>
  )
}
