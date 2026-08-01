/* AOF88 — Outils de saisie des obstacles : rectangle, polygone, muret/joint.
   ----------------------------------------------------------------------------
   Les 28 obstacles d'un relevé réel doivent se saisir ICI, sans passer par un
   outil externe. Trois outils suffisent parce que les treize natures se
   ramènent à deux formes : une SURFACE (édicule, cheminée, lanterneau…) et une
   entité LINÉAIRE ÉPAISSE (muret, joint de dilatation, acrotère — les joints
   d'un arc). Chaque nature garde son rendu propre (classe CSS + trait), pour
   qu'une planche se lise sans légende.

   Le repère lettré est attribué automatiquement et sans collision
   (`prochainRepere`), y compris après une suppression au milieu de la liste.

   Le HALO de dégagement est dessiné autour de l'emprise, translucide : c'est la
   surface réellement perdue, et elle change instantanément avec la provenance
   (0,30 m mesuré / 0,50 m sinon) — voir `degagementEffectif`. */
import { useCallback, useMemo, useState } from 'react'
import {
  NATURES_OBSTACLE,
  prochainRepere,
  reperesEnDouble,
  degagementEffectif,
  estLineaire,
} from './repereLettre'
import ObstacleInspecteur from './ObstacleInspecteur'

const OUTILS = [
  { cle: 'rectangle', libelle: 'Rectangle' },
  { cle: 'polygone', libelle: 'Polygone' },
  { cle: 'muret', libelle: 'Muret / joint' },
]

// Emprise par défaut d'un obstacle posé au clic (m) — retaillable ensuite.
const COTE_DEFAUT_M = 2

function nombre(v, defaut = 0) {
  const n = Number(String(v ?? '').replace(',', '.'))
  return Number.isFinite(n) ? n : defaut
}

export default function OutilsObstacles({
  obstaclesInitiaux = [],
  metresParPixel = 0.05,
  onChange,
}) {
  const [obstacles, setObstacles] = useState(obstaclesInitiaux)
  const [outil, setOutil] = useState('rectangle')
  const [brouillon, setBrouillon] = useState([]) // sommets en cours (polygone/muret)
  const [selection, setSelection] = useState(null)

  const publier = useCallback(
    (suivants) => {
      setObstacles(suivants)
      onChange?.(suivants)
    },
    [onChange],
  )

  const creer = useCallback(
    (forme) => {
      const repere = prochainRepere(obstacles)
      const obstacle = {
        id: `obs-${repere}-${Date.now()}`,
        repere,
        nature: forme.type === 'lineaire' ? 'muret' : 'edicule',
        provenance: 'mesure',
        degagementM: null,
        epaisseurM: forme.type === 'lineaire' ? 0.2 : null,
        verrouille: false,
        ...forme,
      }
      publier([...obstacles, obstacle])
      setSelection(obstacle.id)
      return obstacle
    },
    [obstacles, publier],
  )

  const cliquerSurface = useCallback(
    (e) => {
      const boite = e.currentTarget.getBoundingClientRect()
      const point = {
        x: (e.clientX - boite.left) * metresParPixel,
        y: (e.clientY - boite.top) * metresParPixel,
      }
      if (outil === 'rectangle') {
        creer({
          type: 'surface',
          sommets: [
            { x: point.x, y: point.y },
            { x: point.x + COTE_DEFAUT_M, y: point.y },
            { x: point.x + COTE_DEFAUT_M, y: point.y + COTE_DEFAUT_M },
            { x: point.x, y: point.y + COTE_DEFAUT_M },
          ],
        })
        return
      }
      setBrouillon((prec) => {
        const suivant = [...prec, point]
        if (outil === 'muret' && suivant.length === 2) {
          creer({ type: 'lineaire', sommets: suivant })
          return []
        }
        return suivant
      })
    },
    [outil, metresParPixel, creer],
  )

  const terminerPolygone = useCallback(() => {
    if (brouillon.length < 3) return
    creer({ type: 'surface', sommets: brouillon })
    setBrouillon([])
  }, [brouillon, creer])

  const majObstacle = useCallback(
    (patch) => {
      publier(obstacles.map((o) => (o.id === patch.id ? { ...o, ...patch } : o)))
    },
    [obstacles, publier],
  )

  const dupliquer = useCallback(
    (id) => {
      const source = obstacles.find((o) => o.id === id)
      if (!source) return
      const repere = prochainRepere(obstacles)
      const copie = {
        ...source,
        id: `obs-${repere}-${Date.now()}`,
        repere,
        verrouille: false,
        sommets: source.sommets.map((s) => ({ x: s.x + COTE_DEFAUT_M, y: s.y })),
      }
      publier([...obstacles, copie])
      setSelection(copie.id)
    },
    [obstacles, publier],
  )

  const supprimer = useCallback(
    (id) => {
      publier(obstacles.filter((o) => o.id !== id))
      setSelection((s) => (s === id ? null : s))
    },
    [obstacles, publier],
  )

  /* Alignement : on cale l'obstacle sélectionné sur l'axe du voisin le plus
     proche — le geste réel d'un relevé (une file d'édicules alignés). */
  const aligner = useCallback(
    (axe) => {
      const cible = obstacles.find((o) => o.id === selection)
      if (!cible || cible.verrouille) return
      const autres = obstacles.filter((o) => o.id !== cible.id)
      if (autres.length === 0) return
      const valeurDe = (o) => Math.min(...o.sommets.map((s) => s[axe]))
      const ref = autres.reduce((meilleur, o) =>
        Math.abs(valeurDe(o) - valeurDe(cible)) < Math.abs(valeurDe(meilleur) - valeurDe(cible))
          ? o
          : meilleur,
      )
      const delta = valeurDe(ref) - valeurDe(cible)
      majObstacle({
        ...cible,
        sommets: cible.sommets.map((s) => ({ ...s, [axe]: s[axe] + delta })),
      })
    },
    [obstacles, selection, majObstacle],
  )

  const doublons = useMemo(() => reperesEnDouble(obstacles), [obstacles])
  const selectionne = obstacles.find((o) => o.id === selection) ?? null

  return (
    <section className="ao-obstacles" data-ao-outils-obstacles={obstacles.length}>
      <div className="ao-obstacles-barre" role="group" aria-label="Outils de saisie">
        {OUTILS.map((o) => (
          <button
            key={o.cle}
            type="button"
            aria-pressed={outil === o.cle}
            onClick={() => {
              setOutil(o.cle)
              setBrouillon([])
            }}
            data-ao-outil={o.cle}
          >
            {o.libelle}
          </button>
        ))}
        {outil === 'polygone' && (
          <button type="button" onClick={terminerPolygone} data-ao-outil-terminer>
            Terminer le polygone ({brouillon.length} points)
          </button>
        )}
        <button type="button" onClick={() => aligner('x')} disabled={!selectionne}>
          Aligner en X
        </button>
        <button type="button" onClick={() => aligner('y')} disabled={!selectionne}>
          Aligner en Y
        </button>
        <button type="button" onClick={() => dupliquer(selection)} disabled={!selectionne}>
          Dupliquer
        </button>
        <button type="button" onClick={() => supprimer(selection)} disabled={!selectionne}>
          Supprimer
        </button>
      </div>

      {doublons.length > 0 && (
        <p role="alert" data-ao-obstacles-doublons>
          Anomalie&nbsp;: repère(s) en double — {doublons.join(', ')}.
        </p>
      )}

      <svg
        className="ao-obstacles-planche"
        viewBox="0 0 60 60"
        role="application"
        aria-label="Planche des obstacles — cliquez pour poser"
        onClick={cliquerSurface}
        data-ao-obstacles-planche
      >
        {obstacles.map((o) => {
          const { valeur: d, surcharge } = degagementEffectif(o)
          const points = (o.sommets || []).map((s) => `${s.x},${s.y}`).join(' ')
          const lineaire = estLineaire(o.nature) || o.type === 'lineaire'
          const epaisseur = nombre(o.epaisseurM, 0.2)
          return (
            <g
              key={o.id}
              data-ao-obstacle={o.repere}
              data-ao-obstacle-nature={o.nature}
              data-ao-obstacle-surcharge={surcharge ? 'oui' : 'non'}
              className={`ao-obstacle ao-obstacle-${o.nature}${o.id === selection ? ' est-selectionne' : ''}`}
              onClick={(e) => {
                e.stopPropagation()
                setSelection(o.id)
              }}
            >
              {/* HALO de dégagement : la surface réellement perdue autour de
                  l'emprise. Translucide, dessiné SOUS l'emprise. */}
              {lineaire ? (
                <polyline
                  points={points}
                  className="ao-obstacle-halo"
                  fill="none"
                  strokeWidth={epaisseur + 2 * d}
                  strokeLinecap="round"
                  data-ao-obstacle-halo={d}
                />
              ) : (
                <polygon
                  points={points}
                  className="ao-obstacle-halo"
                  strokeWidth={2 * d}
                  strokeLinejoin="round"
                  data-ao-obstacle-halo={d}
                />
              )}

              {/* Emprise. Le rendu diffère par forme : une entité linéaire est
                  un trait épais, une surface un polygone plein. */}
              {lineaire ? (
                <polyline
                  points={points}
                  className="ao-obstacle-emprise"
                  fill="none"
                  strokeWidth={epaisseur}
                  strokeLinecap="round"
                />
              ) : (
                <polygon points={points} className="ao-obstacle-emprise" />
              )}

              <text
                x={(o.sommets?.[0]?.x ?? 0) + 0.3}
                y={(o.sommets?.[0]?.y ?? 0) - 0.3}
                fontSize="1.2"
                className="ao-obstacle-repere"
              >
                {o.repere}
              </text>
            </g>
          )
        })}

        {/* Brouillon en cours de saisie (polygone / muret). */}
        {brouillon.length > 0 && (
          <polyline
            points={brouillon.map((p) => `${p.x},${p.y}`).join(' ')}
            className="ao-obstacle-brouillon"
            fill="none"
            data-ao-obstacle-brouillon={brouillon.length}
          />
        )}
      </svg>

      <ObstacleInspecteur obstacle={selectionne} onChange={majObstacle} />

      <p className="ao-hint">
        {obstacles.length} obstacle{obstacles.length > 1 ? 's' : ''} —{' '}
        {NATURES_OBSTACLE.length} natures disponibles. Le dégagement suit la provenance&nbsp;:
        0,30 m si l&apos;emprise est mesurée, 0,50 m sinon.
      </p>
    </section>
  )
}
