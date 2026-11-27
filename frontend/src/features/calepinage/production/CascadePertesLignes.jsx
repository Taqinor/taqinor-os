import { useState } from 'react'
import { formatNumber, formatPercent } from '../../../lib/format'
import { CHART_TOKENS } from '../../../ui/charts/chart-theme.js'
import { useModeExpert } from '../atelier/modeExpert'
import { libelleSource, texteEnergieLivree } from './DiagrammePertes.helpers'

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

const present = (v) => v !== null && v !== undefined

/* ACAL735 — étape « Fenêtre MPPT » : heures et énergie sous la tension de
   démarrage de l'onduleur, telles que servies (jamais calculées ici). Clés
   absentes ou null : aucune ligne. */
function SousDemarrage({ entree }) {
  if (!entree || typeof entree !== 'object' || !present(entree.heures_sous_demarrage)) return null
  const h = entree.heures_sous_demarrage
  const e = entree.energie_sous_demarrage_kwh
  const retiree = entree.energie_sous_demarrage_deja_retiree_kwh
  return (
    <div className="col-span-full text-sm" data-testid="acal735-sous-demarrage">
      <p>
        {`Sous la tension de démarrage de l'onduleur : ${formatNumber(h, { decimals: 0 })} ${h > 1 ? 'heures' : 'heure'}`}
        {present(e) ? `, ${formatNumber(e, { decimals: 1 })} kWh produits par les panneaux à ces heures` : ''}
        {present(retiree) && retiree !== 0
          ? ` (dont ${formatNumber(retiree, { decimals: 1 })} kWh déjà retirés par la fenêtre)` : ''}
      </p>
      <p className="text-muted-foreground">
        Information : cette énergie n'est pas retirée en plus ; la fenêtre de tension de l'onduleur décide.
      </p>
    </div>
  )
}

/* ACAL1671 / ACAL1968 — la mention SERVIE d'une entrée, telle quelle : la pose retenue de l'échauffement des modules
   (ligne de la table société prise par correspondance) ou la phrase d'une valeur SUPPOSÉE (`entree.supposee === true` :
   qualité des panneaux, LID, câbles, arrêts…). Jamais reformulée ; sans mention servie, aucune ligne. */
function MentionEntree({ ligne }) {
  const entree = ligne.entree
  if (!entree || typeof entree !== 'object' || typeof entree.mention !== 'string' || !entree.mention) return null
  if (ligne.poste === 'thermique') {
    return (
      <div className="col-span-full" data-testid="acal1671-mention-thermique">
        <dt className="text-muted-foreground">Pose retenue</dt>
        <dd className="break-words">{entree.mention}</dd>
      </div>
    )
  }
  if (entree.supposee !== true) return null
  return (
    <div className="col-span-full" data-testid="acal1968-mention-supposee">
      <dt className="text-muted-foreground">Valeur supposée</dt>
      <dd className="break-words">{entree.mention}</dd>
    </div>
  )
}

/* ACAL1948 — l'« Entrée » d'une ligne : une chaîne telle quelle ; pour l'étape `iam`, l'objet servi
   (modèle, indice du verre, antireflet, table) dit en phrase. Rien d'autre n'est déduit. */
const MODELES_IAM = { fresnel: 'Fresnel', ashrae: 'ASHRAE' }
function entreeEnPhrase(ligne) {
  const e = ligne.entree
  if (typeof e === 'string') return e || '—'
  if (ligne.poste !== 'iam' || !e || typeof e !== 'object' || !e.modele) return null
  const morceaux = [`Modèle de reflet ${MODELES_IAM[e.modele] || e.modele}`]
  if (present(e.indice_verre)) morceaux.push(`indice du verre ${formatNumber(e.indice_verre, { decimals: 3 })}`)
  if (typeof e.revetement_ar === 'boolean') morceaux.push(`revêtement antireflet : ${e.revetement_ar ? 'oui' : 'non'}`)
  if (Array.isArray(e.table_iam) && e.table_iam.length) morceaux.push('table des facteurs par angle servie')
  return `${morceaux.join(' ; ')}.`
}

function Detail({ ligne, id }) {
  const entree = entreeEnPhrase(ligne)
  const champs = [
    ['Valeur', ligne.pertePct === null || ligne.pertePct === undefined
      ? '—' : formatPercent(ligne.pertePct, { decimals: 1 })],
    ['Source', libelleSource(ligne.source)],
    ...(entree ? [['Entrée', entree]] : []),
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
      <MentionEntree ligne={ligne} />
      {ligne.poste === 'mppt' && <SousDemarrage entree={ligne.entree} />}
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
    ? texteEnergieLivree(ligne, (v) => formatNumber(v, { decimals: 0 }), (v) => formatPercent(v, { decimals: 1 }))
    : (ligne.pertePct === null || ligne.pertePct === undefined || ligne.total
      ? '' : formatPercent(ligne.pertePct, { decimals: 1 }))

  const corps = (
    <>
      <span className="min-w-0 flex-1 basis-40">
        <span className="block text-sm" title={ligne.nomClair && ligne.nomClair !== ligne.nom ? ligne.nom : undefined}>
          {ligne.nomClair || ligne.nom}
        </span>
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
      <span className={`${ligne.arrivee ? 'min-w-24' : 'w-24'} shrink-0 text-right text-xs tabular-nums`}>{perte}</span>
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
