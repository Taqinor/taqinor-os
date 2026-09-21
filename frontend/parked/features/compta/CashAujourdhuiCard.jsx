// NTTRE17 — Carte compacte « Cash aujourd'hui » du tableau de bord.
//
// Composant AUTONOME (même patron qu'`ApprobationsAttentionCard`) : il rend
// `null` tant que rien n'est chargé, en cas d'erreur, ou si l'utilisateur n'a
// pas accès aux états de trésorerie (403) — jamais de carte vide.
//
// UNE SEULE requête, vers `etats/position-tresorerie/` (FG122, endpoint
// existant) : le bloc `cash_du_jour` qu'elle publie porte déjà le solde
// consolidé multi-comptes arrêté au jour J, le delta vs la veille et les 3
// prochaines échéances (effets + campagnes de règlement). Aucun autre appel
// n'est émis par cette carte.
import { useEffect, useState } from 'react'
import { Wallet } from 'lucide-react'
import comptaApi from '../../api/comptaApi'
import { Stat } from '../../ui'
import { formatMAD, formatDate } from '../../lib/format'

export default function CashAujourdhuiCard() {
  const [cash, setCash] = useState(null)

  useEffect(() => {
    let vivant = true
    comptaApi.etats.positionTresorerie()
      .then((res) => { if (vivant) setCash(res.data?.cash_du_jour ?? null) })
      .catch(() => { if (vivant) setCash(null) })
    return () => { vivant = false }
  }, [])

  if (!cash) return null

  const delta = Number(cash.delta_veille) || 0
  const echeances = cash.prochaines_echeances || []

  return (
    <Stat
      label="Cash aujourd'hui"
      value={formatMAD(cash.total)}
      icon={Wallet}
      hint="Solde consolidé de tous les comptes"
      delta={{
        value: formatMAD(delta),
        direction: delta > 0 ? 'up' : delta < 0 ? 'down' : undefined,
      }}
      data-testid="cash-aujourdhui-card"
    >
      <div className="mt-3 border-t pt-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Prochaines échéances
        </span>
        {!echeances.length ? (
          <p className="mt-1 text-xs text-muted-foreground">
            Aucune échéance à venir.
          </p>
        ) : (
          <ul className="mt-1 flex flex-col gap-1">
            {echeances.map((e) => (
              <li
                key={`${e.source}-${e.id}`}
                className="flex items-center justify-between gap-2 text-xs"
              >
                <span className="truncate text-muted-foreground">
                  {formatDate(e.date)} — {e.libelle}
                </span>
                <span className="shrink-0 tabular-nums">
                  {formatMAD(e.montant)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Stat>
  )
}
