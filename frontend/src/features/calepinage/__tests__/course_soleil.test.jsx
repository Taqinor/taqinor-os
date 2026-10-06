import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CAL96 — LA COURSE DU SOLEIL, PAR PAN.
   ----------------------------------------------------------------------------
   Le diagramme se lit pour le pan SÉLECTIONNÉ ; les obstructions proches (CAL94
   — obstacles de toiture à hauteur saisie CAL66 + environnement CAL67, les
   deux seules sources qui voyagent dans le document) apparaissent aux BONS
   azimuts ; aucune donnée météo n'est inventée.
   ========================================================================== */

const layout = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { layout: (...a) => layout(...a) } },
}))

const { default: CourseSoleil } = await import('../CourseSoleil')
const { azimutHauteur, obstructionsDesObstacles, centroideDuContour } = await import('../obstructionMath')

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

const rendre = (props = {}) => render(
  <MemoryRouter><CourseSoleil calepinageId={7} {...props} /></MemoryRouter>,
)

/* ── 1. La géométrie pure des obstructions ──────────────────────────────── */

describe('CAL96 — obstructionMath (moteur pur)', () => {
  it('azimutHauteur : un point plein Est donne un azimut ≈ 90°', () => {
    // ~1 km à l'est, à la même latitude.
    const pos = azimutHauteur(-7.6, 33.5, -7.6 + 0.01, 33.5, 10)
    expect(pos.azimuthDeg).toBeGreaterThan(80)
    expect(pos.azimuthDeg).toBeLessThan(100)
  })

  it('un obstacle sans hauteur saisie est écarté (il ne projette rien)', () => {
    const origine = { lng: -7.6, lat: 33.5 }
    const obstacles = [{ centerLng: -7.599, centerLat: 33.5, type: 'cheminee' }]
    expect(obstructionsDesObstacles(origine, obstacles)).toEqual([])
  })

  it('un obstacle avec hauteur saisie donne UNE obstruction, azimut/hauteur finis', () => {
    const origine = { lng: -7.6, lat: 33.5 }
    const obstacles = [{ centerLng: -7.599, centerLat: 33.5, type: 'cheminee', heightM: 1.2 }]
    const res = obstructionsDesObstacles(origine, obstacles)
    expect(res).toHaveLength(1)
    expect(Number.isFinite(res[0].azimuthDeg)).toBe(true)
    expect(Number.isFinite(res[0].elevationDeg)).toBe(true)
    expect(res[0].label).toBe('Cheminée')
  })

  it('centroideDuContour : moyenne des sommets', () => {
    const c = centroideDuContour([[0, 0], [2, 0], [2, 2], [0, 2]])
    expect(c).toEqual({ lng: 1, lat: 1 })
  })

  it('sans origine exploitable, aucune obstruction', () => {
    expect(obstructionsDesObstacles(null, [{ centerLng: 1, centerLat: 1, heightM: 2 }])).toEqual([])
  })
})

/* ── 2. L'écran ────────────────────────────────────────────────────────── */

const ZONE = {
  id: 'z1', label: 'Pan Sud',
  vertices: [[-7.601, 33.599], [-7.599, 33.599], [-7.599, 33.601], [-7.601, 33.601]],
  obstacles: [
    { id: 'o1', centerLng: -7.598, centerLat: 33.6, type: 'cheminee', heightM: 1.5 }, // à l'Est, hauteur saisie
    { id: 'o2', centerLng: -7.6005, centerLat: 33.6002, type: 'antenne' }, // sans hauteur — écarté
  ],
}

describe('CAL96 — l’écran', () => {
  it('sans repère GPS (pin), aucune course n’est tracée — le dit explicitement', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { activeAreaId: 'z1', zones: [ZONE] } } })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByTestId('cal-sundiagram')).toBeInTheDocument()
    expect(screen.getByText(/Latitude du site inconnue/)).toBeInTheDocument()
  })

  it('avec repère GPS, la course est tracée et les obstructions apparaissent', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          pin: { lat: 33.6, lng: -7.6 },
          activeAreaId: 'z1',
          zones: [ZONE],
        },
      },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.queryByText(/Latitude du site inconnue/)).not.toBeInTheDocument()
    // Un seul obstacle porte une hauteur saisie ⇒ UNE obstruction surimprimée.
    expect(screen.getAllByTestId('cal-sundiagram-obstruction')).toHaveLength(1)
  })

  it('aucune obstruction à hauteur saisie ⇒ le dit explicitement, rien d’inventé', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          pin: { lat: 33.6, lng: -7.6 },
          activeAreaId: 'z1',
          zones: [{ ...ZONE, obstacles: [] }],
        },
      },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.queryByTestId('cal-sundiagram-obstruction')).not.toBeInTheDocument()
    expect(screen.getByText(/Aucune obstruction proche/)).toBeInTheDocument()
  })

  it('plusieurs pans : un sélecteur change le pan affiché', async () => {
    const zoneNord = { ...ZONE, id: 'z2', label: 'Pan Nord', obstacles: [] }
    layout.mockResolvedValue({
      data: {
        roof_layout: { pin: { lat: 33.6, lng: -7.6 }, activeAreaId: 'z1', zones: [ZONE, zoneNord] },
      },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getAllByTestId('cal-sundiagram-obstruction')).toHaveLength(1)
    fireEvent.change(screen.getByLabelText('Pan'), { target: { value: 'z2' } })
    expect(screen.queryByTestId('cal-sundiagram-obstruction')).not.toBeInTheDocument()
  })

  it('sans aucun pan tracé, le dit clairement (pas de diagramme vide muet)', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { zones: [] } } })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByText(/Aucun pan tracé/)).toBeInTheDocument()
  })

  it('l’horizon lointain (CAL93) est surimprimé quand le document en porte un', async () => {
    layout.mockResolvedValue({
      data: {
        roof_layout: {
          pin: { lat: 33.6, lng: -7.6 },
          activeAreaId: 'z1',
          zones: [ZONE],
          horizonProfile: {
            source: 'saisie',
            points: [{ azimuthDeg: 90, heightDeg: 8 }, { azimuthDeg: 270, heightDeg: 5 }],
            hauteurMaxDeg: 8,
          },
        },
      },
    })
    rendre()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.queryByText(/Aucun horizon lointain saisi/)).not.toBeInTheDocument()
  })
})

/* ── 3. CALX52 / ACAL74 — la hauteur de toit : celle du bâtiment du document ── */

const MENTION_HYPOTHESE = 'hauteur de toit supposée à 6 m (2 étages × 3 m), '
  + 'non mesurée'

// Un objet d'ENVIRONNEMENT (CAL67, référencé au sol) : sa hauteur EFFECTIVE
// dépend de `roofHeightM` — contrairement à un obstacle de toiture (CAL66),
// qui est pris tel quel. C'est le cas qui rend la hauteur de toit observable.
const ZONE_AVEC_ENVIRONNEMENT = {
  ...ZONE,
  obstacles: [],
}
const ENVIRONNEMENT = [
  { label: 'Arbre voisin', kind: 'arbre', centerLng: -7.598, centerLat: 33.6, heightM: 10 },
]

const rendreAvecEnvironnement = ({ buildings, buildingId } = {}) => {
  layout.mockResolvedValue({
    data: {
      roof_layout: {
        pin: { lat: 33.6, lng: -7.6 },
        activeAreaId: 'z1',
        zones: [{ ...ZONE_AVEC_ENVIRONNEMENT, ...(buildingId ? { buildingId } : {}) }],
        environment: ENVIRONNEMENT,
        ...(buildings ? { buildings } : {}),
      },
    },
  })
  return rendre()
}

const cyDuPremierMarqueur = () => screen.getAllByTestId('cal-sundiagram-obstruction')[0]
  .querySelector('circle').getAttribute('cy')

describe('CALX52 — l’hypothèse de hauteur de toit, quand le document n’a pas de hauteur', () => {
  it('la mention est présente au montage, avec le lien pour saisir la hauteur dans l’atelier', async () => {
    await rendreAvecEnvironnement()
    await screen.findByTestId('cal-course-soleil')

    expect(screen.getByTestId('cal-course-soleil-hauteur-toit-provenance'))
      .toHaveTextContent(MENTION_HYPOTHESE)
    expect(screen.getByTestId('cal-course-soleil-hauteur-toit-valeur'))
      .toHaveTextContent('6 m')
    expect(screen.getByRole('link', { name: 'Saisir la hauteur dans l’atelier (Bâtiment)' }))
      .toHaveAttribute('href', '/calepinage/7')
  })

  it('aucune obstruction proche n’est tracée sans que la hauteur employée soit lisible', async () => {
    await rendreAvecEnvironnement()
    await screen.findByTestId('cal-course-soleil')

    const marqueurs = screen.getAllByTestId('cal-sundiagram-obstruction')
    expect(marqueurs.length).toBeGreaterThan(0)
    const lignes = screen.getAllByTestId(/^cal-course-soleil-obstruction-hauteur-/)
    expect(lignes).toHaveLength(marqueurs.length)
    for (const ligne of lignes) {
      expect(ligne).toHaveTextContent(MENTION_HYPOTHESE)
    }
  })

  it('la saisie locale « hauteur de toit » n’existe plus (état d’écran perdu au rechargement)', async () => {
    await rendreAvecEnvironnement()
    await screen.findByTestId('cal-course-soleil')
    expect(screen.queryByTestId('cal-course-soleil-hauteur-toit-champ')).not.toBeInTheDocument()
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument()
  })

  it('un bâtiment SANS hauteur (null) ou un pan sans bâtiment : l’hypothèse reste', async () => {
    await rendreAvecEnvironnement({ buildings: [{ id: 'b1', hauteurM: null, source: null }], buildingId: 'b1' })
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByTestId('cal-course-soleil-hauteur-toit-provenance'))
      .toHaveTextContent(MENTION_HYPOTHESE)
    cleanup()
    await rendreAvecEnvironnement({ buildings: [{ id: 'b1', hauteurM: 9, source: 'saisie' }] })
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByTestId('cal-course-soleil-hauteur-toit-provenance'))
      .toHaveTextContent(MENTION_HYPOTHESE)
  })

  it('la hauteur d’un AUTRE bâtiment ne s’applique pas au pan', async () => {
    await rendreAvecEnvironnement({
      buildings: [{ id: 'autre', hauteurM: 9, source: 'saisie' }], buildingId: 'b1',
    })
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByTestId('cal-course-soleil-hauteur-toit-valeur')).toHaveTextContent('6 m')
  })
})

describe('ACAL74 — la hauteur du bâtiment du pan, lue dans le document', () => {
  it('buildings[{hauteurM:9}] + zones[].buildingId → obstruction calculée à 9 m, provenance affichée', async () => {
    await rendreAvecEnvironnement()
    await screen.findByTestId('cal-course-soleil')
    const cyHypothese = cyDuPremierMarqueur()
    cleanup()

    await rendreAvecEnvironnement({
      buildings: [{ id: 'b1', label: 'Villa', hauteurM: 9, source: 'saisie' }], buildingId: 'b1',
    })
    await screen.findByTestId('cal-course-soleil')

    expect(screen.getByTestId('cal-course-soleil-hauteur-toit-valeur')).toHaveTextContent('9 m')
    expect(screen.getByTestId('cal-course-soleil-hauteur-toit-provenance'))
      .toHaveTextContent('hauteur du bâtiment : 9 m (saisie atelier)')
    expect(screen.queryByRole('link', { name: /Saisir la hauteur/ })).not.toBeInTheDocument()
    // L'objet d'environnement (10 m) est ramené au plan du champ : 10 − 9 = 1 m au lieu
    // de 10 − 6 = 4 m — le marqueur change de hauteur angulaire, par la MÊME formule.
    expect(cyDuPremierMarqueur()).not.toBe(cyHypothese)
    for (const ligne of screen.getAllByTestId(/^cal-course-soleil-obstruction-hauteur-/)) {
      expect(ligne).toHaveTextContent('hauteur du bâtiment : 9 m (saisie atelier)')
    }
  })

  it('une source libre (« lue sur le permis ») est affichée telle quelle', async () => {
    await rendreAvecEnvironnement({
      buildings: [{ id: 'b1', hauteurM: 7.5, source: 'lue sur le permis' }], buildingId: 'b1',
    })
    await screen.findByTestId('cal-course-soleil')
    expect(screen.getByTestId('cal-course-soleil-hauteur-toit-provenance'))
      .toHaveTextContent('hauteur du bâtiment : 7.5 m (lue sur le permis)')
  })

  it('lecture du document en échec : l’erreur est dite, aucune hauteur n’est inventée', async () => {
    layout.mockRejectedValue(new Error('500'))
    rendre()
    expect(await screen.findByRole('alert')).toHaveTextContent('Impossible de charger la conception')
    expect(screen.queryByTestId('cal-course-soleil-hauteur-toit-valeur')).not.toBeInTheDocument()
  })
})

describe('CAL96 — l’écran est ATTEIGNABLE', () => {
  it('le module déclare la route `/calepinage/:id/course-soleil` avec ses rôles', async () => {
    const { default: config } = await import('../module.config.jsx')
    const route = config.routes.find((r) => r.path === '/calepinage/:id/course-soleil')
    expect(route, 'route course-soleil absente du module').toBeTruthy()
    expect(Array.isArray(route.roles) && route.roles.length > 0).toBe(true)
  })
})
