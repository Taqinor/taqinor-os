import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import { sortedHorizonPoints, horizonMaxHeightDeg, heuresMasqueesEstimation } from './horizonMath'
import SunDiagram, { COURBES_REPERE } from './SunDiagram'

/* ============================================================================
   CAL93 — L'HORIZON LOINTAIN, tracé en fond de la course du soleil, et appliqué
   à la production en poste de perte SÉPARÉ.
   ----------------------------------------------------------------------------
   Constat de la tâche : l'atelier ne connaît que l'ombrage PROCHE tracé à la
   main — une montagne à l'ouest n'existe pas pour lui. Le service CAL92
   (`apps/calepinage/services/horizon.py`) sait obtenir un profil PVGIS
   (`printhorizon`) mais N'EST PAS ENCORE exposé par une route HTTP — cet écran
   fonctionne donc pour l'instant sur le SECOND chemin explicitement autorisé
   par la tâche : « depuis l'endpoint CAL92, OU le profil saisi par
   l'utilisateur ». Un relevé terrain (jumelles + boussole, ou une carte IGN)
   bat de toute façon un modèle numérique de terrain sur un site encaissé.

   PERSISTANCE : le profil voyage dans le MÊME document que la pose (CAL18
   `roof_layout`, endpoint déjà réel — `layout`/`enregistrerLayoutCalepinage`),
   sous la clé `horizonProfile` (contrat `roof_layout_v2.schema.json`,
   `$defs/horizonProfile`). Au prochain chargement de l'atelier
   (`roof-tool-pro11.ts applyDevisHydration`), le profil est relu et son dérate
   HORAIRE est appliqué à la production — TOUJOURS un poste séparé de
   l'ombrage proche (`shadingUi.ts recomputeHorizonFactors`), jamais fondu avec
   lui.

   ZÉRO CHIFFRE INVENTÉ : moins de deux points saisis ⇒ aucun horizon n'est
   affiché ni appliqué (comportement d'aujourd'hui). La hauteur maximale et le
   compte d'heures masquées affichés ici sont TOUJOURS recalculés depuis les
   points actuels, jamais mémorisés indépendamment.
   ========================================================================== */

function nombre(brut) {
  if (brut === null || brut === undefined || brut === '') return null
  const v = Number(brut)
  return Number.isFinite(v) ? v : null
}

export default function HorizonPanel({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [layout, setLayout] = useState(null)
  const [points, setPoints] = useState([])
  const [source, setSource] = useState('saisie')
  const [latitudeDeg, setLatitudeDeg] = useState(null)
  const [saisie, setSaisie] = useState({ azimut: '', hauteur: '' })
  const [message, setMessage] = useState(null)
  const [chargement, setChargement] = useState(!!calepinageId)

  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.layout(calepinageId))
      .then((res) => {
        if (annule) return
        const document = res?.data?.roof_layout ?? null
        setLayout(document)
        setLatitudeDeg(nombre(document?.pin?.lat))
        const profil = document?.horizonProfile
        if (profil && Array.isArray(profil.points)) {
          setPoints(sortedHorizonPoints(profil.points))
          setSource(profil.source === 'pvgis' ? 'pvgis' : 'saisie')
        }
      })
      .catch(() => { if (!annule) setLayout(null) })
      .finally(() => { if (!annule) setChargement(false) })
    return () => { annule = true }
  }, [calepinageId])

  const hauteurMaxDeg = horizonMaxHeightDeg(points)
  const heuresMasquees = typeof latitudeDeg === 'number' ? heuresMasqueesEstimation(latitudeDeg, points) : 0
  const exploitable = sortedHorizonPoints(points).length >= 2

  function ajouterPoint() {
    const az = nombre(saisie.azimut)
    const h = nombre(saisie.hauteur)
    if (az === null || h === null) {
      setMessage('Azimut et hauteur doivent être des nombres — rien n’a été ajouté.')
      return
    }
    setPoints((prev) => sortedHorizonPoints([...prev, { azimuthDeg: az, heightDeg: h }]))
    setSaisie({ azimut: '', hauteur: '' })
    setSource('saisie') // toute saisie manuelle bascule la source (jamais mélangée à `pvgis`)
    setMessage(null)
  }

  function retirerPoint(index) {
    setPoints((prev) => sortedHorizonPoints(prev).filter((_, i) => i !== index))
  }

  function enregistrer() {
    const propres = sortedHorizonPoints(points)
    const document = { ...(layout ?? {}) }
    if (propres.length >= 2) {
      document.horizonProfile = { source, points: propres, hauteurMaxDeg: horizonMaxHeightDeg(propres) }
    } else {
      delete document.horizonProfile
    }
    Promise.resolve(calepinageApi.calepinages.enregistrerLayoutCalepinage(calepinageId, document))
      .then(() => {
        setLayout(document)
        setMessage(
          propres.length >= 2
            ? 'Profil d’horizon enregistré — appliqué à la production au prochain calcul de l’atelier.'
            : 'Profil retiré (moins de deux points) — aucun horizon n’est appliqué.',
        )
      })
      .catch(() => setMessage('Le profil d’horizon n’a pas pu être enregistré.'))
  }

  if (chargement) {
    return <div className="cine-card mt-6 p-6" data-testid="cal-horizon-loading">Chargement…</div>
  }

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-horizon">
      <p className="tech-label rule-brass text-brass-300">Horizon lointain</p>
      <p className="mt-1 text-sm text-lune-faint">
        Le relief à distance (montagne, crête, immeuble éloigné) qui masque le soleil aux
        heures rasantes — un poste de perte SÉPARÉ de l’ombrage proche tracé sur le toit.
        Saisissez au moins deux points (azimut, hauteur angulaire) pour l’activer ; sans
        eux, rien ne change.
      </p>

      <div className="mt-4">
        <SunDiagram
          latitudeDeg={latitudeDeg}
          horizonPoints={points}
          ariaLabel="Course du soleil et horizon lointain, par azimut"
          testId="cal-horizon-diagramme"
        />
        <div className="mt-1 flex flex-wrap gap-3 text-xs text-lune-faint">
          {COURBES_REPERE.map((c) => (
            <span key={c.jour} className="inline-flex items-center gap-1">
              <span aria-hidden="true" style={{ display: 'inline-block', width: 10, height: 2, background: c.couleur }} />
              {c.label}
            </span>
          ))}
          <span className="inline-flex items-center gap-1">
            <span aria-hidden="true" style={{ display: 'inline-block', width: 10, height: 10, background: 'rgba(90,60,30,0.55)' }} />
            Horizon saisi
          </span>
        </div>
        {latitudeDeg === null && (
          <p className="mt-1 text-xs text-amber-300">
            Latitude du site inconnue (aucun repère posé) — la course du soleil n’est pas tracée.
          </p>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="tech-label text-lune-faint">Hauteur maximale</span>
          <div className="fig text-white" data-testid="cal-horizon-hauteur-max">
            {hauteurMaxDeg === null ? '—' : `${hauteurMaxDeg.toFixed(1)}°`}
          </div>
        </div>
        <div>
          <span className="tech-label text-lune-faint">Heures masquées (estimation, 3 jours de repère)</span>
          <div className="fig text-white" data-testid="cal-horizon-heures-masquees">
            {exploitable ? heuresMasquees : '—'}
          </div>
        </div>
      </div>

      <div className="mt-4">
        <p className="tech-label text-lune-faint">Points du profil (azimut °, hauteur °)</p>
        <ul className="mt-2 flex flex-col gap-1" data-testid="cal-horizon-points">
          {sortedHorizonPoints(points).map((p, i) => (
            <li key={`${p.azimuthDeg}-${i}`} className="flex items-center gap-2 text-sm">
              <span className="fig">{p.azimuthDeg.toFixed(0)}°</span>
              <span className="fig">{p.heightDeg.toFixed(1)}°</span>
              <button
                type="button"
                onClick={() => retirerPoint(i)}
                className="text-xs text-red-300 underline"
                aria-label={`Retirer le point à ${p.azimuthDeg.toFixed(0)}°`}
              >
                Retirer
              </button>
            </li>
          ))}
          {!points.length && <li className="text-sm text-lune-faint">Aucun point saisi.</li>}
        </ul>

        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="block" data-testid="cal-horizon-champ-azimut">
            <span className="tech-label text-lune-faint">Azimut (°, 0=Nord)</span>
            <input
              type="number"
              step="any"
              value={saisie.azimut}
              onChange={(e) => setSaisie((s) => ({ ...s, azimut: e.target.value }))}
              className="mt-1 w-28 rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
            />
          </label>
          <label className="block" data-testid="cal-horizon-champ-hauteur">
            <span className="tech-label text-lune-faint">Hauteur angulaire (°)</span>
            <input
              type="number"
              step="any"
              value={saisie.hauteur}
              onChange={(e) => setSaisie((s) => ({ ...s, hauteur: e.target.value }))}
              className="mt-1 w-28 rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
            />
          </label>
          <button
            type="button"
            onClick={ajouterPoint}
            className="rounded border border-white/20 px-3 py-1.5 text-sm font-semibold text-white hover:bg-white/10"
          >
            Ajouter le point
          </button>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={enregistrer}
          className="rounded border border-brass-400/60 px-4 py-2 text-sm font-semibold text-brass-200 hover:bg-brass-400/10"
        >
          Enregistrer le profil
        </button>
        {message && <p className="text-sm text-lune-faint" role="status">{message}</p>}
      </div>
    </div>
  )
}
