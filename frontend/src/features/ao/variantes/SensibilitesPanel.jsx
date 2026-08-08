import { useMemo } from 'react'
import { AlertTriangle, TrendingDown } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { Card, EmptyState, Skeleton } from '../../../ui'
import { StatutControle } from '../statusAo'
import { formatNumber } from '../../../lib/format'

/* ============================================================================
   AOF103 — Panneau « Sensibilités » : le plancher, et la phrase SERVEUR.
   ----------------------------------------------------------------------------
   RÉPARATION 07/08/2026 (PACT172) — BUG RÉEL trouvé en branchant ce panneau :
   il appelait `aoApi.calepinages.sensibilites(calepinageId)`, un endpoint
   NON CONSTRUIT (`aoApi.js` le documentait déjà comme tel). Le vrai endpoint
   est PORTÉ PAR LA VARIANTE — `aoApi.calepinage.variantes.sensibilites
   (varianteId)`, POST `/ao/calepinage/variantes/<id>/sensibilites/`
   (`CalepinageVarianteViewSet.sensibilites`, `calepinage_service.
   calculer_sensibilites`) — et sa réponse n'a JAMAIS eu la forme que ce
   composant lisait : `lignes`/`plancher` n'existent pas côté serveur, qui
   rend `{reference_modules, plancher_modules, engagement_modules, verdict,
   non_applicables, sensibilites}`. Brancher sans corriger l'appel ET la
   lecture aurait produit un refus serveur permanent (l'ancien endpoint) puis,
   une fois l'URL seule corrigée, un tableau vide silencieux (l'ancienne forme
   ne matchant plus rien) — les deux sont pires qu'un panneau non monté.

   Les variantes défavorables (100 % portrait, 100 % paysage, dégagement
   maximal partout, allées 1,00 / 1,20 / 1,90, cotes douteuses au pire,
   segments raccourcis) sont recalculées par LE MÊME MOTEUR côté serveur.
   Ce panneau ne connaît AUCUN de ces scénarios : leurs libellés (déjà
   « … — impact chiffré de +N module(s) », `core/calepinage/sensibilites.py`)
   et leur verdict `tenu` viennent tous du payload — un scénario ajouté côté
   serveur apparaît ici sans toucher au front, et aucun libellé de scénario
   n'est écrit dans ce fichier (gardé par le contrat de source de
   `SensibilitesPanel.test.jsx`).

   ── LA PHRASE EST SERVEUR, JAMAIS COMPOSÉE ICI ────────────────────────────
   `resultat.verdict()` (`core/calepinage/sensibilites.py`) rend déjà la
   phrase complète, GÉNÉRÉE à partir des nombres — ce panneau se contente de
   l'AFFICHER (`data.verdict`), il ne la reconstruit plus d'aucune façon.

   ── LE PLANCHER ───────────────────────────────────────────────────────────
   `plancher_modules` est un NOMBRE publié par le serveur (le pire compte
   obtenu, référence comprise) — jamais recalculé ici. La/les ligne(s) qui
   l'atteignent sont repérées par égalité de `modules`, une comparaison
   d'AFFICHAGE entre deux nombres serveur, pas une arithmétique de calepinage.
   ========================================================================== */

const NON_EVALUE = 'non_evalue'

// État d'une ligne : lecture du verdict SERVEUR, jamais une comparaison locale.
function etatLigne(ligne) {
  if (typeof ligne.tenu !== 'boolean') return NON_EVALUE
  return ligne.tenu ? 'ok' : 'bloquant'
}

// Lignes du tableau : la RÉFÉRENCE (calcul retenu, `reference_modules`) suivie
// de chaque sensibilité défavorable rejouée par le serveur (`sensibilites`).
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function lignesSensibilites({ referenceModules = null, engagementModules = null, sensibilites = [] } = {}) {
  if (referenceModules == null) return []
  const tenuReference = engagementModules == null ? null : referenceModules >= engagementModules
  return [
    {
      cle: 'reference', libelle: 'Référence (calcul retenu)', modules: referenceModules,
      delta: 0, tenu: tenuReference, reference: true,
    },
    ...sensibilites.map((s) => ({
      cle: s.code, libelle: s.libelle, modules: s.modules, delta: s.delta, tenu: s.tenu,
    })),
  ]
}

// Ligne(s) au PLANCHER publié par le serveur (`plancher_modules`) — une
// SÉLECTION parmi des valeurs serveur, jamais un recalcul.
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function lignesPlancher(lignes = [], plancherModules = null) {
  if (plancherModules == null) return []
  return lignes.filter((l) => l.modules === plancherModules)
}

export function SensibilitesPanel({ varianteId }) {
  const { data, loading, error } = useResource(
    () => aoApi.calepinage.variantes.sensibilites(varianteId), varianteId,
    { select: (res) => res.data, errorMessage: 'Impossible de charger les sensibilités.' },
  )

  const lignes = useMemo(() => lignesSensibilites({
    referenceModules: data?.reference_modules ?? null,
    engagementModules: data?.engagement_modules ?? null,
    sensibilites: data?.sensibilites ?? [],
  }), [data])
  const planchers = useMemo(
    () => lignesPlancher(lignes, data?.plancher_modules ?? null), [lignes, data],
  )
  const clesPlancher = useMemo(() => new Set(planchers.map((l) => l.cle)), [planchers])
  const nonApplicables = data?.non_applicables ?? []

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

      {/* Verdict GÉNÉRÉ PAR LE SERVEUR (`resultat.verdict()`) — jamais rédigé ici. */}
      <p
        aria-live="polite"
        className="rounded-md border border-border bg-muted/30 px-3 py-2 text-sm font-medium"
      >
        {data.verdict}
      </p>

      {/* Tablette : le tableau défile HORIZONTALEMENT dans son propre conteneur,
          la page ne défile jamais latéralement (règle de mise en page du dépôt). */}
      <div className="-mx-1 overflow-x-auto px-1">
        <table className="w-full min-w-[34rem] border-collapse text-sm">
          <caption className="sr-only">
            Référence et scénarios défavorables, compte de modules obtenu et verdict vis-à-vis de l’engagement.
          </caption>
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th scope="col" className="py-2 pr-3 font-medium">Scénario</th>
              <th scope="col" className="py-2 pr-3 text-right font-medium">Modules</th>
              <th scope="col" className="py-2 pr-3 text-right font-medium">Delta vs référence</th>
              <th scope="col" className="py-2 font-medium">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {lignes.map((l) => {
              const estPlancher = clesPlancher.has(l.cle)
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
                    {formatNumber(l.modules, { decimals: 0 })}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {l.reference ? '—' : `${l.delta > 0 ? '+' : ''}${formatNumber(l.delta, { decimals: 0 })}`}
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

      {/* Scénarios non applicables à ce relevé — phrases COMPLÈTES, déjà
          rédigées par le serveur (`batterie()`), jamais recomposées ici. */}
      {nonApplicables.length > 0 && (
        <ul className="flex flex-col gap-0.5 text-xs text-muted-foreground">
          {nonApplicables.map((motif) => <li key={motif}>{motif}</li>)}
        </ul>
      )}
    </Card>
  )
}

export default SensibilitesPanel
