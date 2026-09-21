/* AOF80 — Écran de calibration deux points : OBLIGATOIRE et BLOQUANT.
   ----------------------------------------------------------------------------
   Tant que la calibration n'est pas acquise, la barre d'état affiche « échelle
   inconnue » et les outils de tracé/cotation sont désactivés — c'est
   `calibration.js` qui tranche (`peutTracer`/`peutCoter`), jamais cet écran.

   Le recalibrage ne perd JAMAIS le tracé : quand une calibration existe déjà et
   qu'une nouvelle est validée, l'écran PROPOSE explicitement le ré-échelonnage
   des sommets — deux boutons, aucune application silencieuse. */
import { useCallback, useState } from 'react'
import {
  calibrer,
  estCalibree,
  libelleEchelle,
  verifierVraisemblance,
  peutTracer,
  peutCoter,
} from './calibration'

export default function Calibration({
  calibration,
  onCalibration,
  onReechelonner,
  aUnTrace = false,
}) {
  const [p1, setP1] = useState(null)
  const [p2, setP2] = useState(null)
  const [distance, setDistance] = useState('')
  const [motif, setMotif] = useState('')
  const [alerte, setAlerte] = useState(null)
  const [enAttenteRescale, setEnAttenteRescale] = useState(null)

  const cliquerPlan = useCallback(
    (e) => {
      const hote = e.currentTarget.getBoundingClientRect()
      const point = { x: e.clientX - hote.left, y: e.clientY - hote.top }
      if (!p1 || (p1 && p2)) {
        setP1(point)
        setP2(null)
      } else {
        setP2(point)
      }
      setMotif('')
    },
    [p1, p2],
  )

  const valider = useCallback(() => {
    const candidate = calibrer({ p1, p2, distanceReelleM: distance })
    if (!candidate.valide) {
      setMotif(candidate.motif)
      setAlerte(null)
      return
    }
    setMotif('')
    setAlerte(verifierVraisemblance(candidate))
    if (estCalibree(calibration) && aUnTrace) {
      // Recalibrage sur un tracé existant : on demande AVANT de toucher quoi
      // que ce soit.
      setEnAttenteRescale({ ancienne: calibration, nouvelle: candidate })
      return
    }
    onCalibration?.(candidate)
  }, [p1, p2, distance, calibration, aUnTrace, onCalibration])

  const repondreRescale = useCallback(
    (reechelonnerLeTrace) => {
      const { ancienne, nouvelle } = enAttenteRescale
      onCalibration?.(nouvelle)
      if (reechelonnerLeTrace) onReechelonner?.(ancienne, nouvelle)
      setEnAttenteRescale(null)
    },
    [enAttenteRescale, onCalibration, onReechelonner],
  )

  const calibree = estCalibree(calibration)

  return (
    <section className="ao-calibration" data-ao-calibration>
      <header className="ao-calibration-etat" data-ao-echelle>
        <strong>{libelleEchelle(calibration)}</strong>
        {!calibree && (
          <span className="ao-calibration-bloque">
            Tracé et cotation désactivés tant que le plan n&apos;est pas calibré.
          </span>
        )}
      </header>

      <ol className="ao-calibration-etapes">
        <li>
          Cliquez deux points dont vous connaissez la distance réelle (le plus long possible).
        </li>
        <li>Saisissez cette distance en mètres.</li>
        <li>Validez : l&apos;échelle du plan est fixée.</li>
      </ol>

      {/* Surface de saisie des deux points. Le fond de calque est rendu
          au-dessous par UnderlayPdf/UnderlayImage ; cette couche ne capte que
          les deux clics. */}
      <div
        className="ao-calibration-surface"
        role="application"
        aria-label="Surface de calibration : cliquez deux points"
        onClick={cliquerPlan}
        data-ao-calibration-surface
      >
        {p1 && <span className="ao-calibration-point" style={{ left: p1.x, top: p1.y }} />}
        {p2 && <span className="ao-calibration-point" style={{ left: p2.x, top: p2.y }} />}
      </div>

      <label className="ao-champ" htmlFor="ao-calibration-distance">
        <span>Distance réelle (m)</span>
        <input
          id="ao-calibration-distance"
          className="form-control"
          type="number"
          step="any"
          value={distance}
          onChange={(e) => setDistance(e.target.value)}
        />
      </label>

      <button type="button" onClick={valider} data-ao-calibration-valider>
        Valider l&apos;échelle
      </button>

      {motif && (
        <p role="alert" className="ao-calibration-motif" data-ao-calibration-motif>
          {motif}
        </p>
      )}

      {alerte && alerte.niveau === 'alerte' && (
        <p role="alert" className="ao-calibration-alerte" data-ao-calibration-alerte>
          ⚠ {alerte.message}
        </p>
      )}

      {enAttenteRescale && (
        <div className="ao-calibration-rescale" role="group" aria-label="Ré-échelonner le tracé ?">
          <p>
            Le plan était déjà calibré. Voulez-vous ré-échelonner le tracé existant avec la
            nouvelle échelle&nbsp;? Rien n&apos;est modifié sans votre réponse.
          </p>
          <button type="button" onClick={() => repondreRescale(true)}>
            Ré-échelonner le tracé
          </button>
          <button type="button" onClick={() => repondreRescale(false)}>
            Garder le tracé tel quel
          </button>
        </div>
      )}

      <p className="ao-calibration-gardes">
        Tracé&nbsp;: {peutTracer(calibration) ? 'actif' : 'désactivé'} — Cotation&nbsp;:{' '}
        {peutCoter(calibration) ? 'active' : 'désactivée'}
      </p>
    </section>
  )
}
