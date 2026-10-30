import { useEffect, useState } from 'react'
import reportingApi from '../../api/reportingApi'
import { formatMAD, formatNumber, formatPercent, toNumber } from '../../lib/format'
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Progress, Skeleton, Stat } from '../../ui'

/* ============================================================================
   AANA45 / D-AANA-036-BRANCHER (C-AANA-036) — bloc « Achats → paiement » du
   tableau de bord /reporting. `GET /reporting/p2p/kpi/` existait côté serveur
   (NTP2P46) sans aucun écran : le fondateur (30/10/2026) a tranché « brancher ».

   Contrat partagé : `apps/reporting/contract_samples/kpi_p2p.json`. L'écran
   n'affiche QUE ce que le serveur sert : une valeur `null` (aucune donnée pour
   la calculer) est OMISE — jamais un 0 ou un « — » inventé en son nom. Sans
   aucune valeur servie, l'état vide le dit.
   ========================================================================== */

const dh = (v) => formatMAD(v, { decimals: 0 }).replace(' MAD', ' DH')

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
  'septembre', 'octobre', 'novembre', 'décembre',
]

function libelleBudget(budget) {
  if (budget.periodicite === 'mensuelle' && MOIS[budget.mois - 1]) {
    return `Budget achats · ${MOIS[budget.mois - 1]} ${budget.annee}`
  }
  return `Budget achats · ${budget.annee}`
}

function tonePourTaux(taux) {
  if (taux >= 100) return 'danger'
  if (taux >= 80) return 'warning'
  return 'success'
}

export default function KpiP2pCard() {
  const [data, setData] = useState(null)
  const [etat, setEtat] = useState('chargement') // chargement | ok | erreur

  const [tentative, setTentative] = useState(0)

  useEffect(() => {
    let vivant = true
    reportingApi.kpiP2p()
      .then((res) => {
        if (!vivant) return
        setData(res?.data ?? {})
        setEtat('ok')
      })
      .catch(() => { if (vivant) setEtat('erreur') })
    return () => { vivant = false }
  }, [tentative])

  const reessayer = () => {
    setEtat('chargement')
    setTentative((n) => n + 1)
  }

  const budgets = Array.isArray(data?.budgets_departement) ? data.budgets_departement : []
  const delai = toNumber(data?.delai_demande_bcf_jours)
  const conformite = toNumber(data?.conformite_fournisseur_moyenne)
  const conversion = toNumber(data?.taux_conversion_pct)
  const vide = delai === null && conformite === null && conversion === null && budgets.length === 0

  return (
    <Card className="mb-4" data-testid="kpi-p2p-card">
      <CardHeader>
        <CardTitle>Achats → paiement</CardTitle>
        {etat === 'ok' && data?.debut && data?.fin && (
          <CardDescription>{`Période du ${data.debut} au ${data.fin}`}</CardDescription>
        )}
      </CardHeader>
      <CardContent>
        {etat === 'chargement' && (
          <div className="grid gap-4 sm:grid-cols-3" data-testid="kpi-p2p-chargement">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        )}

        {etat === 'erreur' && (
          <div className="flex flex-wrap items-center gap-3" role="alert">
            <p className="text-sm text-muted-foreground">
              Impossible de charger les indicateurs achats.
            </p>
            <Button variant="outline" size="sm" onClick={reessayer}>Réessayer</Button>
          </div>
        )}

        {etat === 'ok' && vide && (
          <p className="text-sm text-muted-foreground" data-testid="kpi-p2p-vide">
            Aucune donnée d’achats exploitable pour le moment.
          </p>
        )}

        {etat === 'ok' && !vide && (
          <div className="flex flex-col gap-4">
            {(delai !== null || conformite !== null || conversion !== null) && (
              <div className="grid gap-4 sm:grid-cols-3">
                {delai !== null && (
                  <Stat
                    label="Délai demande → bon de commande"
                    value={`${formatNumber(delai, { decimals: 1 })} j`}
                  />
                )}
                {conformite !== null && (
                  <Stat
                    label="Conformité fournisseurs (score moyen)"
                    value={formatNumber(conformite, { decimals: 1 })}
                  />
                )}
                {conversion !== null && (
                  <Stat
                    label="Demandes d’achat commandées"
                    value={formatPercent(conversion, { decimals: 1 })}
                    hint="Parmi les demandes décidées"
                  />
                )}
              </div>
            )}

            {budgets.map((b) => {
              const taux = toNumber(b.taux_consommation_pct)
              return (
                <div key={b.budget_id} data-testid={`kpi-p2p-budget-${b.budget_id}`}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="font-medium">{libelleBudget(b)}</span>
                    {taux !== null && (
                      <span className="num text-muted-foreground">
                        {formatPercent(taux, { decimals: 1 })} consommé
                      </span>
                    )}
                  </div>
                  {taux !== null && <Progress value={taux} tone={tonePourTaux(taux)} />}
                  <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                    <div><dt className="text-xs text-muted-foreground">Alloué</dt><dd className="num">{dh(b.montant_alloue)}</dd></div>
                    <div><dt className="text-xs text-muted-foreground">Engagé</dt><dd className="num">{dh(b.engage)}</dd></div>
                    <div><dt className="text-xs text-muted-foreground">Réalisé</dt><dd className="num">{dh(b.realise)}</dd></div>
                    <div><dt className="text-xs text-muted-foreground">Restant</dt><dd className="num">{dh(b.restant)}</dd></div>
                  </dl>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
