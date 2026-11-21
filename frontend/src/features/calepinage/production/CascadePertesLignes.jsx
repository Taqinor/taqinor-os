import { useState } from 'react'
import { formatNumber, formatPercent } from '../../../lib/format'
import { CHART_TOKENS } from '../../../ui/charts/chart-theme.js'
import { useModeExpert } from '../atelier/modeExpert'

/* ACAL444 — la cascade de pertes en LIGNES horizontales, une par étape, dans
   l'ordre servi (`rang`). Aucun calcul : `niveau`, `base`, `valeur` viennent de
   `construireCascadeDetaillee` (énergies servies). Une étape OMISE est une
   ligne grisée « omise » + son motif servi — jamais une barre à zéro. La
   largeur suit le conteneur (pourcentages), plus aucune largeur fixe. */

const kwh = (v) => (v === null || v === undefined
  ? 'non calculée' : `${formatNumber(v, { decimals: 0 })} kWh`)

function couleur(ligne) {
  if (ligne.total) return CHART_TOKENS.primary
  if (ligne.gain) return CHART_TOKENS.success
  return CHART_TOKENS.warning
}

function Detail({ ligne, id }) {
  const champs = [
    ['Valeur', ligne.pertePct === null || ligne.pertePct === undefined
      ? '—' : formatPercent(ligne.pertePct, { decimals: 1 })],
    ['Source', ligne.source || '—'],
    ['Entrée', ligne.entree || '—'],
    ['Référence', ligne.reference || '—'],
    ['Énergie avant', kwh(ligne.kwhAvant)],
    ['Énergie après', kwh(ligne.kwhApres)],
  ]
  return (
    <dl
      className="grid grid-cols-2 gap-x-4 gap-y-1 px-2 pb-2 text-xs sm:grid-cols-3"
      data-testid={`acal444-detail-${id}`}
    >
      {champs.map(([k, v]) => (
        <div key={k}>
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="break-words">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

/* ACAL703 — la pastille « inhabituel » : TEXTE (jamais la couleur seule), valeur
   servie hors de la bande publiée, lien vers la page source. Sans entrée dans
   `cascade.plages`, aucune pastille. Niveau expert. */
function PastilleInhabituel({ plage, id }) {
  const bande = `${formatNumber(plage.min, { decimals: 1 })}–${formatNumber(plage.max, { decimals: 1 })} %`
  return (
    <span className="flex flex-wrap items-center gap-2 px-2 pb-1" data-testid={`acal703-pastille-${id}`}>
      <span
        className="rounded border border-warning/40 bg-warning/10 px-2 py-0.5 text-xs"
        title={`Hors de la plage publiée (${bande})`}
      >
        inhabituel
      </span>
      {plage.url && (
        <a
          href={plage.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex min-h-11 items-center text-xs text-primary underline"
        >
          Voir la page source
        </a>
      )}
    </span>
  )
}

function Ligne({ ligne, ouverte, onBascule, expert }) {
  const id = ligne.poste || (ligne.arrivee ? 'arrivee' : 'depart')
  const depliable = !ligne.total
  const largeur = Math.max(0, Math.min(100, ligne.niveau ?? 0))
  const debut = Math.max(0, Math.min(100, ligne.base ?? 0))
  const taille = Math.max(0, Math.min(100 - debut, ligne.valeur ?? 0))
  const perte = ligne.arrivee
    ? `${formatPercent(100 - ligne.niveau, { decimals: 1 })} (pertes totales)`
    : (ligne.pertePct === null || ligne.pertePct === undefined || ligne.total
      ? '' : formatPercent(ligne.pertePct, { decimals: 1 }))

  const corps = (
    <>
      <span className="min-w-0 flex-1 basis-40">
        <span className="block text-sm">{ligne.nom}</span>
        {ligne.omise && (
          <span className="block text-xs text-muted-foreground">
            <strong>omise</strong>
            {ligne.motif ? ` — ${ligne.motif}` : ''}
          </span>
        )}
      </span>
      {!ligne.omise && (
        <span className="relative h-3 flex-[2] basis-40 rounded bg-muted" aria-hidden="true">
          <span
            data-testid={`acal444-barre-${id}`}
            className="absolute top-0 h-3 rounded"
            style={{
              left: `${ligne.total ? 0 : debut}%`,
              width: `${ligne.total ? largeur : taille}%`,
              background: couleur(ligne),
            }}
          />
        </span>
      )}
      <span className="w-24 shrink-0 text-right text-xs tabular-nums">{perte}</span>
    </>
  )

  return (
    <li
      data-testid={`acal444-ligne-${id}`}
      data-omise={ligne.omise ? 'true' : 'false'}
      className={ligne.omise ? 'opacity-60' : ''}
    >
      {depliable ? (
        <button
          type="button"
          className="flex w-full flex-wrap items-center gap-2 px-2 py-1 text-left"
          aria-expanded={ouverte}
          onClick={onBascule}
        >
          {corps}
        </button>
      ) : (
        <div className="flex w-full flex-wrap items-center gap-2 px-2 py-1">{corps}</div>
      )}
      {expert && ligne.plage?.statut === 'inhabituel' && <PastilleInhabituel plage={ligne.plage} id={id} />}
      {depliable && ouverte && <Detail ligne={ligne} id={id} />}
    </li>
  )
}

export default function CascadePertesLignes({ lignes }) {
  const [ouvertes, setOuvertes] = useState({})
  const [expert] = useModeExpert()
  return (
    <ul className="flex w-full flex-col divide-y divide-border" data-testid="acal444-lignes">
      {lignes.map((ligne, i) => {
        const cle = ligne.poste || `${i}`
        return (
          <Ligne
            key={`${cle}-${i}`}
            ligne={ligne}
            ouverte={Boolean(ouvertes[cle])}
            expert={expert}
            onBascule={() => setOuvertes((o) => ({ ...o, [cle]: !o[cle] }))}
          />
        )
      })}
    </ul>
  )
}
