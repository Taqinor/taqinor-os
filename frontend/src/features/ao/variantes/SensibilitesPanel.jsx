import { useMemo } from 'react'
import { AlertTriangle, TrendingDown } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { Card, EmptyState, Skeleton } from '../../../ui'
import { StatutControle } from '../statusAo'
import { formatNumber } from '../../../lib/format'

/* ============================================================================
   AOF103 — Panneau « Sensibilités » : le plancher, et la phrase GÉNÉRÉE.
   ----------------------------------------------------------------------------
   Les variantes défavorables (100 % portrait, 100 % paysage, dégagement
   maximal partout, allées 1,00 / 1,20 / 1,90, cotes douteuses au pire,
   segments raccourcis) sont recalculées par LE MÊME MOTEUR côté serveur
   (`GET /ao/calepinages/:id/sensibilites/`, AOF11). Ce panneau ne connaît
   AUCUN de ces scénarios : leurs libellés, leurs comptes et leur verdict
   `tenu` viennent tous du payload — un scénario ajouté côté serveur apparaît
   ici sans toucher au front, et aucun libellé de scénario n'est écrit dans ce
   fichier (gardé par le contrat de source de `SensibilitesPanel.test.jsx`).

   ── LA PHRASE EST GÉNÉRÉE, JAMAIS RÉDIGÉE ─────────────────────────────────
   `construirePhrase()` COMPOSE le verdict à partir des données :
     • tous les scénarios tenus  → « Engagement tenu partout … »
     • au moins un scénario non tenu → « Engagement tenu sauf : » + les
       libellés SERVEUR des scénarios fautifs, énumérés depuis le payload ;
     • au moins un scénario non évalué → le verdict est déclaré INCOMPLET
       (jamais un « tenu partout » optimiste fondé sur un trou de données).
   Il n'existe donc AUCUNE phrase de verdict pré-écrite couvrant un cas
   particulier : la seule chose figée est la charpente de la phrase.

   ── LE PLANCHER ───────────────────────────────────────────────────────────
   `plancher` est renvoyé par le serveur (`{ cle, compte_modules }`). À défaut,
   le front SÉLECTIONNE la ligne au plus petit compte — une sélection parmi des
   valeurs serveur, jamais une arithmétique de calepinage — et le signale.
   ========================================================================== */

const NON_EVALUE = 'non_evalue'

// État d'une ligne : lecture du verdict SERVEUR, jamais une comparaison locale.
function etatLigne(ligne) {
  if (typeof ligne.tenu !== 'boolean') return NON_EVALUE
  return ligne.tenu ? 'ok' : 'bloquant'
}

// Charpente de la phrase — les libellés énumérés viennent TOUS du payload.
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function construirePhrase({ lignes = [], engagementModules = null } = {}) {
  if (!lignes.length) return ''
  const nonEvaluees = lignes.filter((l) => etatLigne(l) === NON_EVALUE)
  const fautives = lignes.filter((l) => etatLigne(l) === 'bloquant')

  const suffixeEngagement = engagementModules != null
    ? ` (engagement : ${formatNumber(engagementModules, { decimals: 0 })} modules)`
    : ''

  if (nonEvaluees.length) {
    return `Verdict incomplet : ${formatNumber(nonEvaluees.length, { decimals: 0 })} scénario(s) non évalué(s)`
      + ` — ${nonEvaluees.map((l) => l.libelle).join(', ')}.`
  }
  if (!fautives.length) {
    return `Engagement tenu partout${suffixeEngagement} — `
      + `${formatNumber(lignes.length, { decimals: 0 })} scénario(s) défavorable(s) testé(s).`
  }
  return `Engagement tenu sauf : ${fautives.map((l) => l.libelle).join(', ')}${suffixeEngagement}.`
}

// Ligne-plancher : celle désignée par le serveur, sinon le plus petit compte.
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function lignePlancher(lignes = [], plancher = null) {
  if (!lignes.length) return null
  if (plancher?.cle) {
    const trouvee = lignes.find((l) => l.cle === plancher.cle)
    if (trouvee) return { ligne: trouvee, deduit: false }
  }
  const mini = lignes.reduce(
    (acc, l) => (acc == null || (l.compte_modules ?? Infinity) < (acc.compte_modules ?? Infinity) ? l : acc),
    null,
  )
  return mini ? { ligne: mini, deduit: true } : null
}

export function SensibilitesPanel({ calepinageId }) {
  const { data, loading, error } = useResource(
    () => aoApi.calepinages.sensibilites(calepinageId), calepinageId,
    { select: (res) => res.data, errorMessage: 'Impossible de charger les sensibilités.' },
  )

  const lignes = useMemo(() => data?.lignes ?? [], [data])
  const engagementModules = data?.engagement_modules ?? null
  const plancher = useMemo(() => lignePlancher(lignes, data?.plancher), [lignes, data])
  const phrase = useMemo(
    () => construirePhrase({ lignes, engagementModules }),
    [lignes, engagementModules],
  )

  if (loading) {
    return <Card className="p-4"><Skeleton className="h-5 w-1/2" /><Skeleton className="mt-3 h-32 w-full" /></Card>
  }
  if (error) {
    return <EmptyState icon={AlertTriangle} title="Impossible de charger les sensibilités" description={error} />
  }
  if (!lignes.length) {
    return (
      <EmptyState
        icon={TrendingDown}
        title="Aucune sensibilité calculée"
        description="Lancez le calepinage : les variantes défavorables sont recalculées par le même moteur, côté serveur."
      />
    )
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div>
        <h2 className="font-display text-lg font-semibold tracking-tight">Sensibilités</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Variantes défavorables recalculées par le même moteur — le plancher est ce que l’on peut promettre.
        </p>
      </div>

      {/* Phrase GÉNÉRÉE (annoncée aux lecteurs d'écran après chaque recalcul). */}
      <p
        aria-live="polite"
        className="rounded-md border border-border bg-muted/30 px-3 py-2 text-sm font-medium"
      >
        {phrase}
      </p>

      {/* Tablette : le tableau défile HORIZONTALEMENT dans son propre conteneur,
          la page ne défile jamais latéralement (règle de mise en page du dépôt). */}
      <div className="-mx-1 overflow-x-auto px-1">
        <table className="w-full min-w-[34rem] border-collapse text-sm">
          <caption className="sr-only">
            Scénarios défavorables, compte de modules obtenu et verdict vis-à-vis de l’engagement.
          </caption>
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th scope="col" className="py-2 pr-3 font-medium">Scénario</th>
              <th scope="col" className="py-2 pr-3 text-right font-medium">Modules</th>
              <th scope="col" className="py-2 pr-3 text-right font-medium">Puissance</th>
              <th scope="col" className="py-2 pr-3 text-right font-medium">Écart / engagement</th>
              <th scope="col" className="py-2 font-medium">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {lignes.map((l) => {
              const estPlancher = plancher?.ligne === l
              return (
                <tr
                  key={l.cle}
                  className={`border-b border-border/60 ${estPlancher ? 'bg-warning/10 font-medium' : ''}`}
                >
                  <th scope="row" className="py-2 pr-3 text-left font-normal">
                    {l.libelle}
                    {estPlancher && (
                      <span className="ml-2 rounded bg-warning/20 px-1.5 py-0.5 text-[11px] font-semibold uppercase text-warning">
                        Plancher
                      </span>
                    )}
                  </th>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {formatNumber(l.compte_modules, { decimals: 0 })}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {l.puissance_kwc != null ? `${formatNumber(l.puissance_kwc, { decimals: 2 })} kWc` : '—'}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {l.ecart_engagement_modules != null
                      ? formatNumber(l.ecart_engagement_modules, { decimals: 0 })
                      : '—'}
                  </td>
                  <td className="py-2">
                    <StatutControle
                      status={etatLigne(l) === NON_EVALUE ? 'avertissement' : etatLigne(l)}
                      label={etatLigne(l) === NON_EVALUE ? 'Non évalué' : undefined}
                      data-ao-etat={etatLigne(l)}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {plancher?.deduit && (
        <p className="text-xs text-muted-foreground">
          Plancher déduit de la liste (le serveur ne l’a pas désigné).
        </p>
      )}
    </Card>
  )
}

export default SensibilitesPanel
