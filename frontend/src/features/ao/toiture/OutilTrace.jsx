/* AOF84 — Porte n°2 : tracé from scratch, à la SOURIS ET AU CLAVIER.
   ----------------------------------------------------------------------------
   Sur un chantier, on ne dessine pas : on saisit un relevé. Le mode clavier est
   donc le mode principal — une longueur, une direction, entrée suivante — et la
   souris n'est qu'un complément. Un rectangle de 25,62 × 51,10 se saisit
   entièrement au clavier, sans jamais viser un pixel (c'est le test).

   Directions : les flèches donnent l'orthogonal (→ +x, ← −x, ↑ +y, ↓ −y, dans
   le repère local de `repere.js`) ; pour un pan oblique, on saisit l'angle en
   degrés (0° = +x, sens trigonométrique) et on valide par Entrée. Un décrochement
   — le « L » — n'est donc qu'une suite de segments : il se trace d'un trait, sans
   jamais recoller deux rectangles.

   Deux refus fermes : l'auto-intersection (un contour qui se recoupe n'a pas
   d'aire exploitable — le calepinage y poserait des rangées dans le vide) et la
   fermeture d'un contour de moins de trois sommets. Chaque étape est annulable
   une par une. */
import { useCallback, useMemo, useRef, useState } from 'react'
import {
  aireM2,
  perimetreM,
  contourSeCroise,
  segmentsSeCroisent,
} from './repere'

// Tolérance de fermeture automatique : sous 0,50 m du point de départ, on
// considère que l'opérateur boucle le contour (relevé au mètre, pas au micron).
const TOLERANCE_FERMETURE_M = 0.5

const DIRECTIONS = {
  ArrowRight: 0,
  ArrowUp: 90,
  ArrowLeft: 180,
  ArrowDown: 270,
}

/* Le nouveau segment croise-t-il un segment DÉJÀ tracé ? (polyligne ouverte —
   `contourSeCroise` raisonne sur un contour fermé, ce n'est pas le même cas.) */
function croiseTraceOuvert(sommets, nouveau) {
  const n = sommets.length
  if (n < 3) return false
  const a = sommets[n - 1]
  for (let i = 0; i < n - 2; i += 1) {
    if (segmentsSeCroisent(a, nouveau, sommets[i], sommets[i + 1])) return true
  }
  return false
}

function arrondi(v) {
  return Math.round(v * 1000) / 1000
}

export default function OutilTrace({ onChange, actif = true }) {
  const [sommets, setSommets] = useState([{ x: 0, y: 0 }])
  const [ferme, setFerme] = useState(false)
  const [longueur, setLongueur] = useState('')
  const [angle, setAngle] = useState('')
  const [erreur, setErreur] = useState('')
  const longueurRef = useRef(null)

  const publier = useCallback(
    (nouveauxSommets, estFerme) => {
      setSommets(nouveauxSommets)
      setFerme(estFerme)
      onChange?.({ sommets_m: nouveauxSommets, ferme: estFerme })
    },
    [onChange],
  )

  const ajouterSegment = useCallback(
    (angleDeg) => {
      if (!actif) return
      if (ferme) {
        setErreur('Le contour est fermé. Annulez la fermeture pour continuer à tracer.')
        return
      }
      const l = Number(String(longueur).replace(',', '.'))
      if (!Number.isFinite(l) || l <= 0) {
        setErreur('Saisissez d’abord une longueur en mètres (nombre positif).')
        return
      }
      const a = (angleDeg * Math.PI) / 180
      const dernier = sommets[sommets.length - 1]
      const candidat = {
        x: arrondi(dernier.x + l * Math.cos(a)),
        y: arrondi(dernier.y + l * Math.sin(a)),
      }

      // Fermeture automatique : le nouveau point retombe sur le départ.
      const depart = sommets[0]
      const distanceDepart = Math.hypot(candidat.x - depart.x, candidat.y - depart.y)
      if (sommets.length >= 3 && distanceDepart <= TOLERANCE_FERMETURE_M) {
        if (contourSeCroise(sommets)) {
          setErreur('Contour refusé : le tracé se recoupe. Corrigez avant de fermer.')
          return
        }
        setErreur('')
        setLongueur('')
        publier(sommets, true)
        return
      }

      if (croiseTraceOuvert(sommets, candidat)) {
        setErreur('Segment refusé : il croiserait le tracé existant (auto-intersection).')
        return
      }

      setErreur('')
      setLongueur('')
      publier([...sommets, candidat], false)
    },
    [actif, ferme, longueur, sommets, publier],
  )

  /* Annulation PAR ÉTAPE : une fermeture s'annule d'abord (le contour redevient
     ouvert), puis chaque sommet un par un. Jamais un « tout effacer » déguisé. */
  const annuler = useCallback(() => {
    setErreur('')
    if (ferme) {
      publier(sommets, false)
      return
    }
    if (sommets.length <= 1) return
    publier(sommets.slice(0, -1), false)
  }, [ferme, sommets, publier])

  const surTouche = useCallback(
    (e) => {
      if (DIRECTIONS[e.key] !== undefined) {
        e.preventDefault()
        ajouterSegment(DIRECTIONS[e.key])
        return
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        const a = Number(String(angle).replace(',', '.'))
        if (!Number.isFinite(a)) {
          setErreur('Saisissez un angle en degrés, ou utilisez les flèches pour l’orthogonal.')
          return
        }
        ajouterSegment(a)
        return
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault()
        annuler()
      }
    },
    [ajouterSegment, angle, annuler],
  )

  const fermerContour = useCallback(() => {
    if (sommets.length < 3) {
      setErreur('Il faut au moins trois sommets pour fermer un contour.')
      return
    }
    if (contourSeCroise(sommets)) {
      setErreur('Contour refusé : le tracé se recoupe. Corrigez avant de fermer.')
      return
    }
    setErreur('')
    publier(sommets, true)
  }, [sommets, publier])

  const supprimerSommet = useCallback(
    (index) => {
      if (sommets.length <= 2) {
        setErreur('Un contour ne peut pas descendre sous deux sommets.')
        return
      }
      const restants = sommets.filter((_, i) => i !== index)
      if (ferme && contourSeCroise(restants)) {
        setErreur('Suppression refusée : le contour se recouperait.')
        return
      }
      setErreur('')
      publier(restants, ferme)
    },
    [sommets, ferme, publier],
  )

  const insererSommet = useCallback(
    (index) => {
      const a = sommets[index]
      const b = sommets[(index + 1) % sommets.length]
      if (!a || !b) return
      const milieu = { x: arrondi((a.x + b.x) / 2), y: arrondi((a.y + b.y) / 2) }
      const restants = [...sommets.slice(0, index + 1), milieu, ...sommets.slice(index + 1)]
      setErreur('')
      publier(restants, ferme)
    },
    [sommets, ferme, publier],
  )

  const aire = useMemo(() => (ferme ? aireM2(sommets) : 0), [ferme, sommets])
  const perimetre = useMemo(() => (ferme ? perimetreM(sommets) : 0), [ferme, sommets])

  return (
    <section className="ao-trace" data-ao-outil-trace>
      <h3>Tracer la toiture</h3>
      <p className="ao-hint">
        Saisissez une longueur, puis une direction&nbsp;: flèches pour
        l&apos;orthogonal, ou un angle en degrés validé par Entrée. Un décrochement se trace
        d&apos;un seul tenant, segment après segment.
      </p>

      <div className="ao-trace-saisie">
        <label className="ao-champ" htmlFor="ao-trace-longueur">
          <span>Longueur (m)</span>
          <input
            id="ao-trace-longueur"
            ref={longueurRef}
            className="form-control"
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={longueur}
            onChange={(e) => setLongueur(e.target.value)}
            onKeyDown={surTouche}
          />
        </label>

        <label className="ao-champ" htmlFor="ao-trace-angle">
          <span>Angle (°)</span>
          <input
            id="ao-trace-angle"
            className="form-control"
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={angle}
            onChange={(e) => setAngle(e.target.value)}
            onKeyDown={surTouche}
          />
        </label>

        <div className="ao-trace-directions">
          {Object.entries(DIRECTIONS).map(([touche, deg]) => (
            <button
              key={touche}
              type="button"
              onClick={() => ajouterSegment(deg)}
              data-ao-trace-direction={deg}
            >
              {touche === 'ArrowRight' && '→'}
              {touche === 'ArrowUp' && '↑'}
              {touche === 'ArrowLeft' && '←'}
              {touche === 'ArrowDown' && '↓'}
            </button>
          ))}
        </div>
      </div>

      <div className="ao-trace-actions">
        <button type="button" onClick={fermerContour} data-ao-trace-fermer>
          Fermer le contour
        </button>
        <button type="button" onClick={annuler} data-ao-trace-annuler>
          Annuler la dernière étape
        </button>
      </div>

      {erreur && (
        <p role="alert" className="ao-trace-erreur" data-ao-trace-erreur>
          {erreur}
        </p>
      )}

      <p data-ao-trace-etat>
        {sommets.length} sommet{sommets.length > 1 ? 's' : ''} — contour{' '}
        {ferme ? 'fermé' : 'ouvert'}
        {ferme && ` — ${aire.toFixed(2)} m² — périmètre ${perimetre.toFixed(2)} m`}
      </p>

      <ol className="ao-trace-sommets" data-ao-trace-sommets={sommets.length}>
        {sommets.map((s, i) => (
          <li key={`${s.x}:${s.y}:${i}`}>
            <span>
              S{i + 1} — x {s.x.toFixed(2)} m, y {s.y.toFixed(2)} m
            </span>
            <button type="button" onClick={() => insererSommet(i)}>
              Insérer après S{i + 1}
            </button>
            <button type="button" onClick={() => supprimerSommet(i)}>
              Supprimer S{i + 1}
            </button>
          </li>
        ))}
      </ol>
    </section>
  )
}
