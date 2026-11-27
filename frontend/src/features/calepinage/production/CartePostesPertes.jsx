import { useState } from 'react'
import { Info } from 'lucide-react'
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

/* « DU SOLEIL AU RÉSEAU » de l'étape Résultats (maquette Resultats.dc.html), guidé et expert :
   « Soleil reçu par les panneaux » 100 %, les postes LISIBLES servis (`cascade.postes_lisibles`,
   ACAL695 — le serveur regroupe déjà Ombres proches / Poussière / Chaleur / Câbles et onduleur /
   Autres pertes, rien n'est regroupé ici), « Électricité produite » servie en pied, « Voir les N
   étapes » qui déplie les lignes d'ACAL444. Un poste sans valeur servie (« non compté ») est OMIS,
   jamais une barre à zéro (l'état « résultat incomplet » dit ce qui manque) ; un poste « partiel »
   dit combien d'étapes ne sont pas comptées. La longueur des barres n'est que le cumul visuel
   des pourcentages servis. `note` : la ligne « valeurs publiées » (si le serveur la justifie). */
export function DuSoleilAuReseau({ cascade, note = null }) {
  const [ouvert, setOuvert] = useState(false)
  const postes = cascade?.postes_lisibles
  const liste = (Array.isArray(postes?.postes) ? postes.postes : [])
    .filter((p) => p.statut === 'non_compte' || typeof p.perte_pct === 'number')
  if (liste.length === 0) return null
  const etapes = Array.isArray(cascade?.etapes) ? cascade.etapes : []
  const arrivee = typeof postes?.arrivee_pct === 'number' ? postes.arrivee_pct : null
  // Les barres ne cumulent que les postes COMPTÉS (un poste « non compté » ne retire rien).
  const restes = liste.map((_, i) => 100 - liste.slice(0, i + 1)
    .reduce((somme, p) => somme + (p.statut === 'non_compte' ? 0 : p.perte_pct), 0))
  return (
    <section className="cal-res-carte" data-testid="cal-resultats-pertes">
      <div className="cal-res-entete">
        <h2 className="cal-res-titre">Du soleil au réseau</h2>
        {etapes.length > 0 && (
          <button type="button" className="cal-res-lien" aria-expanded={ouvert}
            onClick={() => setOuvert((o) => !o)}>
            {ouvert ? 'Masquer les étapes' : `Voir les ${etapes.length} étapes`}
          </button>
        )}
      </div>
      <ul className="cal-res-postes">
        <li className="cal-res-poste" data-poste="soleil">
          <span>Soleil reçu par les panneaux</span>
          <div className="cal-res-piste cal-res-piste-depart" aria-hidden="true" />
          <span className="cal-res-poste-pct cal-res-poste-fort">100 %</span>
        </li>
        {liste.map((p, i) => {
          const omises = Array.isArray(p.etapes) ? p.etapes.length : 0
          if (p.statut === 'non_compte') {
            // ACAL1676 — le poste non compté est MONTRÉ : « non compté » et sa CAUSE courte servie (`cause`), aucune
            // barre, aucun 0. Sans `cause` (ancienne réponse) : « non compté » seul, jamais les motifs bruts des étapes.
            const motif = typeof p.cause === 'string' ? p.cause.trim() : ''
            return (
              <li key={p.poste} className="cal-res-poste" data-poste={p.poste} data-statut={p.statut}>
                <span>{p.libelle}</span>
                <span className="cal-res-sourdine text-xs" data-testid={`cal-res-poste-motif-${p.poste}`}>
                  {motif ? `non compté — ${motif}` : 'non compté'}
                </span>
                <span className="cal-res-poste-pct">—</span>
              </li>
            )
          }
          return (
            <li key={p.poste} className="cal-res-poste" data-poste={p.poste} data-statut={p.statut}>
              <span>
                {p.libelle}
                {p.statut === 'partiel' && omises > 0 && (
                  <span className="cal-res-sourdine block text-xs">
                    {`+ ${omises} ${omises > 1 ? 'étapes non comptées' : 'étape non comptée'}`}
                  </span>
                )}
              </span>
              {/* ACAL1832 — le restant (bleu nuit) puis CETTE perte (saumon) : deux segments d'une même piste. */}
              <div className="cal-res-piste" aria-hidden="true">
                <span style={{ width: `${Math.max(0, Math.min(100, restes[i]))}%` }} />
                <span className="cal-res-perte" style={{ width: `${Math.max(0, Math.min(100, p.perte_pct))}%` }} />
              </div>
              <span className="cal-res-poste-pct">{`− ${formatPercent(p.perte_pct, { decimals: 1 })}`}</span>
            </li>
          )
        })}
        {arrivee !== null && (
          <li className="cal-res-poste cal-res-poste-arrivee" data-poste="arrivee">
            <span>Électricité produite</span>
            <div className="cal-res-piste cal-res-piste-arrivee" aria-hidden="true">
              <span style={{ width: `${Math.max(0, Math.min(100, arrivee))}%` }} />
            </div>
            <span className="cal-res-poste-pct cal-res-poste-fort">{formatPercent(arrivee, { decimals: 1 })}</span>
          </li>
        )}
      </ul>
      {ouvert && (
        <div data-zone="etapes">
          <CascadePertesLignes lignes={construireCascadeDetaillee(etapes, cascade.total_pct ?? null, cascade.plages ?? null)} />
        </div>
      )}
      {note && (
        <div className="cal-res-info">
          <Info size={18} aria-hidden="true" style={{ flex: 'none', marginTop: 2 }} />
          <span>{note}</span>
        </div>
      )}
    </section>
  )
}
