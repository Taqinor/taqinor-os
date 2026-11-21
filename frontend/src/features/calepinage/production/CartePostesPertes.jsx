import { useState } from 'react'
import { formatPercent } from '../../../lib/format'
import { CHART_TOKENS } from '../../../ui/charts/chart-theme.js'
import { useModeExpert } from '../atelier/modeExpert'
import CascadePertesLignes from './CascadePertesLignes'
import { construireCascadeDetaillee } from './DiagrammePertes.helpers'

/* ACAL696 — « Du soleil au réseau » : cinq postes en barres lus dans
   `cascade.postes_lisibles` (ACAL695), « Soleil reçu » en tête, « Électricité
   produite » en pied, et « Voir les N étapes » qui déplie les lignes d'ACAL444.
   AUCUN calcul : valeurs et statuts sont ceux du serveur. Un poste « non
   compté » ne dessine JAMAIS une barre à zéro : il dit « non compté » et son
   motif. Niveau expert (étape Résultats) ; rien d'ajouté au premier écran. */

function Poste({ poste }) {
  const nonCompte = poste.statut === 'non_compte'
  const omises = Array.isArray(poste.etapes) ? poste.etapes : []
  const motifs = omises.map((e) => e.motif_omission).filter(Boolean)
  const largeur = Math.max(0, Math.min(100, Number(poste.perte_pct) || 0))
  return (
    <li className="flex flex-col gap-1 py-1" data-testid={`acal696-poste-${poste.poste}`}
      data-statut={poste.statut}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 basis-40 text-sm">{poste.libelle}</span>
        {!nonCompte && (
          <span className="relative h-3 flex-[2] basis-40 rounded bg-muted" aria-hidden="true">
            <span
              data-testid={`acal696-barre-${poste.poste}`}
              className="absolute left-0 top-0 h-3 rounded"
              style={{ width: `${largeur}%`, background: CHART_TOKENS.warning }}
            />
          </span>
        )}
        <span className="w-24 shrink-0 text-right text-sm tabular-nums">
          {nonCompte ? 'non compté' : `− ${formatPercent(poste.perte_pct, { decimals: 1 })}`}
        </span>
      </div>
      {nonCompte && motifs.length > 0 && (
        <p className="text-xs text-muted-foreground" data-testid={`acal696-motif-${poste.poste}`}>
          {motifs.join(' ')}
        </p>
      )}
      {poste.statut === 'partiel' && omises.length > 0 && (
        <p className="text-xs text-muted-foreground" data-testid={`acal696-partiel-${poste.poste}`}>
          + {omises.length} {omises.length > 1 ? 'étapes non comptées' : 'étape non comptée'}
        </p>
      )}
    </li>
  )
}

export default function CartePostesPertes({ cascade }) {
  const [expert] = useModeExpert()
  const [ouvert, setOuvert] = useState(false)
  if (!expert) return null
  const postes = cascade?.postes_lisibles
  const liste = Array.isArray(postes?.postes) ? postes.postes : []
  if (liste.length === 0) {
    if (!postes?.motif_absence) return null
    return (
      <p className="text-sm text-muted-foreground" data-testid="acal696-absente">
        {postes.motif_absence}
      </p>
    )
  }
  const etapes = Array.isArray(cascade?.etapes) ? cascade.etapes : []
  return (
    <section className="rounded-md border border-border/60 p-3" data-testid="acal696-carte">
      <h3 className="text-sm font-medium">Du soleil au réseau</h3>
      <p className="mt-2 flex justify-between text-sm" data-testid="acal696-soleil">
        <span>Soleil reçu par les panneaux</span>
        <span className="tabular-nums">100 %</span>
      </p>
      <ul className="divide-y divide-border">
        {liste.map((poste) => <Poste key={poste.poste} poste={poste} />)}
      </ul>
      <p className="mt-2 flex justify-between text-sm font-medium" data-testid="acal696-arrivee">
        <span>Électricité produite</span>
        <span className="tabular-nums">
          {postes.arrivee_pct === null || postes.arrivee_pct === undefined
            ? 'non calculée' : formatPercent(postes.arrivee_pct, { decimals: 1 })}
        </span>
      </p>
      {etapes.length > 0 && (
        <>
          <button
            type="button"
            className="mt-2 min-h-11 text-sm underline"
            aria-expanded={ouvert}
            onClick={() => setOuvert((o) => !o)}
            data-testid="acal696-voir-etapes"
          >
            {ouvert ? 'Masquer les étapes' : `Voir les ${etapes.length} étapes`}
          </button>
          {ouvert && (
            <div data-testid="acal696-etapes">
              <CascadePertesLignes lignes={construireCascadeDetaillee(etapes, cascade.total_pct ?? null, cascade.plages ?? null)} />
            </div>
          )}
        </>
      )}
    </section>
  )
}
