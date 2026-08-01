import { useMemo } from 'react'
import { Card } from '../../../ui'
import { formatNumber } from '../../../lib/format'

/* ============================================================================
   AOF105 (2/2) — Comparaison A/B : SUPERPOSITION de deux calepinages.
   ----------------------------------------------------------------------------
   Superpose le plan de la version A (référence, en gris) et celui de la
   version B (courante), en SURLIGNANT les différences rangée par rangée :
   rangée ajoutée, rangée retirée, rangée modifiée (position ou nombre de
   tables), rangée inchangée. Le delta de compte est affiché en tête.

   `diffRangees()` est la logique testée (« test du calcul de différence de
   rangées », Done d'AOF105) : appariement par `cle` — l'identifiant de rangée
   que le serveur porte déjà — et JAMAIS par l'ordre du tableau, qui change dès
   qu'une rangée est insérée au milieu (l'ordre ferait alors apparaître toutes
   les rangées suivantes comme « modifiées », un faux récit de diff).

   Le delta de compte est une SOUSTRACTION D'AFFICHAGE entre deux comptes
   SERVEUR — jamais un calepinage recalculé côté front (règle du groupe).
   ========================================================================== */

// Champs comparés d'une rangée. `tables` = nombre de tables posées sur la
// rangée ; `y`/`x0`/`x1` = sa position en mètres, telle que rendue par le
// serveur.
const CHAMPS_RANGEE = ['y', 'x0', 'x1', 'tables']

// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function diffRangees(rangeesA = [], rangeesB = []) {
  const parCleA = new Map(rangeesA.map((r) => [r.cle, r]))
  const parCleB = new Map(rangeesB.map((r) => [r.cle, r]))

  const ajoutees = rangeesB.filter((r) => !parCleA.has(r.cle))
  const retirees = rangeesA.filter((r) => !parCleB.has(r.cle))

  const modifiees = []
  const inchangees = []
  for (const avant of rangeesA) {
    const apres = parCleB.get(avant.cle)
    if (!apres) continue
    const champs = CHAMPS_RANGEE.filter((c) => avant[c] !== apres[c])
    if (champs.length) modifiees.push({ cle: avant.cle, avant, apres, champs })
    else inchangees.push(apres)
  }
  return { ajoutees, retirees, modifiees, inchangees }
}

// Delta de compte : soustraction d'AFFICHAGE entre deux comptes serveur.
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function deltaCompte(planA, planB) {
  const a = planA?.compte_modules
  const b = planB?.compte_modules
  if (typeof a !== 'number' || typeof b !== 'number') return null
  return b - a
}

// Cadre englobant les DEUX plans (pour que la superposition soit à l'échelle).
function cadre(rangees) {
  if (!rangees.length) return { x0: 0, x1: 10, y0: 0, y1: 10 }
  return {
    x0: Math.min(...rangees.map((r) => r.x0 ?? 0)),
    x1: Math.max(...rangees.map((r) => r.x1 ?? 0)),
    y0: Math.min(...rangees.map((r) => r.y ?? 0)),
    y1: Math.max(...rangees.map((r) => r.y ?? 0)),
  }
}

const COULEURS = {
  ajoutee: 'var(--success)',
  retiree: 'var(--destructive)',
  modifiee: 'var(--warning)',
  inchangee: 'var(--muted-foreground)',
}

const LIBELLES = {
  ajoutee: 'Rangée ajoutée',
  retiree: 'Rangée retirée',
  modifiee: 'Rangée modifiée',
  inchangee: 'Rangée inchangée',
}

export function DiffPlan({ versionA, versionB }) {
  const rangeesA = useMemo(() => versionA?.plan?.rangees ?? [], [versionA])
  const rangeesB = useMemo(() => versionB?.plan?.rangees ?? [], [versionB])
  const diff = useMemo(() => diffRangees(rangeesA, rangeesB), [rangeesA, rangeesB])
  const delta = deltaCompte(versionA?.plan, versionB?.plan)

  const bbox = useMemo(() => cadre([...rangeesA, ...rangeesB]), [rangeesA, rangeesB])
  const largeur = Math.max(bbox.x1 - bbox.x0, 1)
  const hauteur = Math.max(bbox.y1 - bbox.y0, 1)
  const pad = Math.max(largeur, hauteur) * 0.05

  // Chaque rangée du dessin, avec sa nature de différence.
  const dessin = useMemo(() => [
    ...diff.inchangees.map((r) => ({ r, nature: 'inchangee' })),
    ...diff.retirees.map((r) => ({ r, nature: 'retiree' })),
    ...diff.modifiees.map((m) => ({ r: m.apres, nature: 'modifiee' })),
    ...diff.ajoutees.map((r) => ({ r, nature: 'ajoutee' })),
  ], [diff])

  if (!rangeesA.length && !rangeesB.length) {
    return (
      <Card className="p-4 text-sm text-muted-foreground">
        Aucun plan à superposer : les deux versions sélectionnées n’ont pas de rangées.
      </Card>
    )
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-medium">
          {`Superposition ${versionA?.libelle ?? 'A'} → ${versionB?.libelle ?? 'B'}`}
        </h3>
        <p className="text-sm font-medium tabular-nums" aria-live="polite">
          {delta == null
            ? 'Delta de compte indisponible'
            : `Delta de compte : ${delta > 0 ? '+' : ''}${formatNumber(delta, { decimals: 0 })} module(s)`}
        </p>
      </div>

      {/* Légende — la couleur n'est jamais le seul signal (chaque nature est
          aussi comptée en toutes lettres juste dessous). */}
      <ul className="flex flex-wrap gap-3 text-xs">
        {Object.entries(LIBELLES).map(([nature, libelle]) => (
          <li key={nature} className="flex items-center gap-1.5">
            <span className="size-2 rounded-full" style={{ background: COULEURS[nature] }} aria-hidden="true" />
            {`${libelle} : ${formatNumber(
              nature === 'modifiee' ? diff.modifiees.length
                : nature === 'ajoutee' ? diff.ajoutees.length
                  : nature === 'retiree' ? diff.retirees.length : diff.inchangees.length,
              { decimals: 0 },
            )}`}
          </li>
        ))}
      </ul>

      <div className="-mx-1 overflow-x-auto px-1">
        {/* Pas de `data-ao-canvas` ici : ce hook appartient au canvas de
            l'atelier (AOF73/84/92) et n'admet qu'UN repère par écran — le
            réutiliser ferait matcher deux éléments dès que la superposition
            est ouverte à côté de l'atelier. Le nom accessible du dessin suffit
            comme cible e2e stable. */}
        <svg
          viewBox={`${bbox.x0 - pad} ${bbox.y0 - pad} ${largeur + pad * 2} ${hauteur + pad * 2}`}
          className="h-64 w-full"
          role="img"
          aria-label={`Superposition des deux versions : ${diff.ajoutees.length} rangée(s) ajoutée(s), `
            + `${diff.retirees.length} retirée(s), ${diff.modifiees.length} modifiée(s).`}
        >
          {dessin.map(({ r, nature }) => (
            <g key={`${nature}-${r.cle}`} data-nature={nature}>
              <line
                x1={r.x0} x2={r.x1} y1={r.y} y2={r.y}
                style={{ stroke: COULEURS[nature] }}
                strokeWidth={Math.max(hauteur * 0.02, 0.08)}
                strokeDasharray={nature === 'retiree' ? '0.6 0.4' : undefined}
                opacity={nature === 'inchangee' ? 0.35 : 1}
              />
            </g>
          ))}
        </svg>
      </div>

      {/* Détail textuel des modifications — la superposition seule ne dit pas
          CE QUI a bougé sur une rangée déplacée de quelques centimètres. */}
      {diff.modifiees.length > 0 && (
        <ul className="flex flex-col gap-1 text-sm">
          {diff.modifiees.map((m) => (
            <li key={m.cle} className="text-muted-foreground">
              {`Rangée ${m.cle} — ${m.champs.join(', ')} : `}
              {m.champs.map((c) => `${c} ${formatNumber(m.avant[c], { decimals: 2 })} → ${formatNumber(m.apres[c], { decimals: 2 })}`).join(' ; ')}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export default DiffPlan
