/* eslint-disable react-refresh/only-export-components --
   Les conversions de pente sont des fonctions PURES (trigonométrie, zéro
   React) : la tâche exige que les TROIS modes soient confrontés à 0,1° près
   sur un cas de test, ce qui suppose de les appeler sans monter l'écran. Même
   dérogation que `module.config.jsx` du même module. */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'

/* ============================================================================
   CAL58 — LA PENTE : en degrés, en pourcentage, OU PAR COTES.
   ----------------------------------------------------------------------------
   Constat : la pente ne s'entre aujourd'hui qu'en DEGRÉS (puces ~15/22/30/45°
   + curseur fin 5-45°, `pages/ventes/ToitureDesign.jsx`). Sur un chantier, la
   pente se lit pourtant aussi en POURCENTAGE (la convention des couvreurs et
   des plans) et se MESURE au mètre : portée et hauteur de faîtage. Trois
   chemins, une seule grandeur.

   LA VALEUR RETENUE DIT TOUJOURS D'OÙ ELLE VIENT (`source` : `degres`,
   `pourcentage`, `cotes`) — sans quoi personne ne peut savoir si la pente
   affichée a été mesurée ou estimée à l'œil.

   RÈGLE FONDATEUR — JAMAIS DE SNAP, JAMAIS DE REFUS. Aucun `min`/`max`, aucun
   `step` autre que `any`, aucun arrondi : la valeur STOCKÉE est la pente
   exacte issue de la conversion, et seul l'AFFICHAGE est arrondi au dixième.
   Une saisie hors des puces historiques (2°, 62,4°) est acceptée telle quelle.

   ZÉRO CHIFFRE INVENTÉ : une saisie absente ou inexploitable (portée nulle)
   rend `null` — jamais 0°, qui se lirait « toiture plate » alors que rien n'a
   été mesuré.
   ========================================================================== */

const DEG = 180 / Math.PI

function nombre(brut) {
  if (brut === null || brut === undefined || brut === '') return null
  const v = Number(brut)
  return Number.isFinite(v) ? v : null
}

/** CAL58 — pente en degrés, telle quelle (aucun arrondi, aucune borne). */
export function penteDepuisDegres(degres) {
  return nombre(degres)
}

/**
 * CAL58 — pente en degrés depuis un POURCENTAGE de pente (hauteur/portée).
 * 100 % = 45°, 57,735 % = 30°. Un pourcentage négatif est accepté tel quel
 * (un plan peut décrire une contre-pente) : on ne refuse pas une saisie.
 */
export function penteDepuisPourcentage(pourcentage) {
  const p = nombre(pourcentage)
  if (p === null) return null
  return Math.atan(p / 100) * DEG
}

/**
 * CAL58 — pente en degrés depuis les COTES mesurées : portée (l'horizontale)
 * et hauteur de faîtage (la verticale). Portée nulle ou absente ⇒ `null` :
 * une division par zéro ne produit pas une pente, elle produit un mensonge.
 */
export function penteDepuisCotes(porteeM, hauteurFaitageM) {
  const portee = nombre(porteeM)
  const hauteur = nombre(hauteurFaitageM)
  if (portee === null || hauteur === null || portee === 0) return null
  return Math.atan(hauteur / portee) * DEG
}

/** CAL58 — la réciproque, pour afficher la pente retenue en pourcentage. */
export function pourcentageDepuisPente(degres) {
  const d = nombre(degres)
  if (d === null) return null
  return Math.tan(d / DEG) * 100
}

/**
 * CAL58 — LA VALEUR RETENUE et SA PROVENANCE, depuis la saisie des trois
 * modes. Le mode ACTIF tranche : deux modes remplis ne se moyennent pas (une
 * moyenne serait un quatrième chiffre que personne n'a mesuré).
 */
export function penteRetenue(mode, saisie = {}) {
  if (mode === 'pourcentage') {
    const degres = penteDepuisPourcentage(saisie.pourcentage)
    return degres === null ? null : { degres, source: 'pourcentage' }
  }
  if (mode === 'cotes') {
    const degres = penteDepuisCotes(saisie.porteeM, saisie.hauteurFaitageM)
    return degres === null ? null : { degres, source: 'cotes' }
  }
  const degres = penteDepuisDegres(saisie.degres)
  return degres === null ? null : { degres, source: 'degres' }
}

const LIBELLE_SOURCE = {
  degres: 'saisie en degrés',
  pourcentage: 'convertie depuis un pourcentage de pente',
  cotes: 'mesurée aux cotes (portée et hauteur de faîtage)',
}

/** Affichage au dixième — l'AFFICHAGE seulement : la valeur reste exacte. */
function auDixieme(valeur) {
  return valeur === null || valeur === undefined ? '—' : valeur.toFixed(1)
}

function Champ({ cle, label, valeur, onChange }) {
  return (
    <label className="block" data-testid={`cal-pente-champ-${cle}`}>
      <span className="tech-label text-lune-faint">{label}</span>
      <input
        type="number"
        /* Règle fondateur : aucune borne, aucun pas — jamais de snap. */
        step="any"
        id={`cal-pente-${cle}`}
        value={valeur ?? ''}
        onChange={(e) => onChange(cle, e.target.value)}
        className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
      />
    </label>
  )
}

const MODES = [
  ['degres', 'En degrés'],
  ['pourcentage', 'En pourcentage'],
  ['cotes', 'Aux cotes'],
]

export default function SaisiePente({
  calepinageId: idPropose, onChange = null, persister = true,
}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [mode, setMode] = useState('degres')
  const [saisie, setSaisie] = useState({
    degres: '', pourcentage: '', porteeM: '', hauteurFaitageM: '',
  })
  const [layout, setLayout] = useState(null)
  const [message, setMessage] = useState(null)

  // RELECTURE : la pente déjà enregistrée dans le document de conception.
  useEffect(() => {
    if (!calepinageId || !persister) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.layout(calepinageId))
      .then((res) => {
        if (annule) return
        const document = res?.data?.roof_layout ?? null
        setLayout(document)
        if (document?.penteDeg === null || document?.penteDeg === undefined) return
        setMode(document.penteSource ?? 'degres')
        setSaisie((s) => ({ ...s, degres: String(document.penteDeg) }))
      })
      .catch(() => { if (!annule) setLayout(null) })
    return () => { annule = true }
  }, [calepinageId, persister])

  const majChamp = (cle, brut) => {
    const suivante = { ...saisie, [cle]: brut }
    setSaisie(suivante)
    if (onChange) onChange(penteRetenue(mode, suivante))
  }

  const changerMode = (suivant) => {
    setMode(suivant)
    if (onChange) onChange(penteRetenue(suivant, saisie))
  }

  const retenue = penteRetenue(mode, saisie)

  const enregistrer = () => {
    if (!retenue) {
      setMessage('Aucune pente n’est encore mesurée : rien n’est enregistré, '
        + 'et surtout pas un 0° qui se lirait « toiture plate ».')
      return
    }
    const document = {
      ...(layout ?? {}),
      // La valeur EXACTE, jamais l'arrondi d'affichage.
      penteDeg: retenue.degres,
      penteSource: retenue.source,
    }
    Promise.resolve(calepinageApi.calepinages.enregistrerLayout(calepinageId, document))
      .then(() => {
        setLayout(document)
        setMessage('Pente enregistrée dans la conception.')
      })
      .catch(() => setMessage('La pente n’a pas pu être enregistrée.'))
  }

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-pente">
      <p className="tech-label rule-brass text-brass-300">Pente de la toiture</p>

      <div className="mt-3 flex flex-wrap gap-2" role="radiogroup"
        aria-label="Mode de saisie de la pente">
        {MODES.map(([cle, label]) => (
          <button
            key={cle}
            type="button"
            role="radio"
            aria-checked={mode === cle}
            data-testid={`cal-pente-mode-${cle}`}
            onClick={() => changerMode(cle)}
            className={`rounded px-3 py-1 text-sm ${mode === cle
              ? 'bg-brass-500/20 text-brass-200' : 'text-lune-soft'}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {mode === 'degres' && (
          <Champ cle="degres" label="Pente (°)" valeur={saisie.degres}
            onChange={majChamp} />
        )}
        {mode === 'pourcentage' && (
          <Champ cle="pourcentage" label="Pente (%)" valeur={saisie.pourcentage}
            onChange={majChamp} />
        )}
        {mode === 'cotes' && (
          <>
            <Champ cle="porteeM" label="Portée (m)" valeur={saisie.porteeM}
              onChange={majChamp} />
            <Champ cle="hauteurFaitageM" label="Hauteur de faîtage (m)"
              valeur={saisie.hauteurFaitageM} onChange={majChamp} />
          </>
        )}
      </div>

      {/* LA VALEUR RETENUE ET SA PROVENANCE, toujours affichées ensemble. */}
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
        <div data-testid="cal-pente-valeur">
          <dd className="fig text-lg text-white">
            {retenue ? `${auDixieme(retenue.degres)} °` : '—'}
          </dd>
          <dt className="tech-label text-lune-faint">Pente retenue</dt>
        </div>
        <div data-testid="cal-pente-source">
          <dd className="text-sm text-white">
            {retenue ? LIBELLE_SOURCE[retenue.source] : 'aucune pente mesurée'}
          </dd>
          <dt className="tech-label text-lune-faint">D’où elle vient</dt>
        </div>
        <div data-testid="cal-pente-equivalent">
          <dd className="fig text-lg text-white">
            {retenue ? `${auDixieme(pourcentageDepuisPente(retenue.degres))} %` : '—'}
          </dd>
          <dt className="tech-label text-lune-faint">Soit, en pourcentage</dt>
        </div>
      </dl>

      {persister && (
        <button type="button" onClick={enregistrer}
          data-testid="cal-pente-enregistrer"
          className="mt-4 rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200">
          Enregistrer la pente
        </button>
      )}
      {message && (
        <p className="mt-3 text-sm text-lune-soft" role="status"
          data-testid="cal-pente-message">{message}</p>
      )}
    </div>
  )
}
