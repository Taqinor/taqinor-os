import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CAL53 — LES MATHS DE CALAGE, PUIS L'ÉCRAN QUI LES CONSOMME.
   ----------------------------------------------------------------------------
   La tâche exige un « test unitaire des maths de calage » : la moitié haute
   de ce fichier appelle `positionsInitiales`/`coinsDepuisMarqueurs` sans
   monter Leaflet (même dérogation fast-refresh que `PlanImporteCalage.jsx`,
   CAL63, dont ce fichier reprend le patron de test). La moitié basse tient
   les promesses de l'écran : la photo calée est visible, le calage relu
   TEL QUEL à la réouverture (jamais recalculé), et persisté par un appel
   dédié qui ne touche QUE la colonne `calage` — la bascule photo terrain
   existante n'est jamais mentionnée ni importée ici.

   Leaflet est MOQUÉ (jsdom ne fournit ni tuiles ni géométrie de carte) : le
   double retient les positions posées par `L.marker(pos, …)` et les rend via
   `getLatLng()`, exactement ce dont `coinsDepuisMarqueurs` a besoin — le test
   vérifie donc un aller-retour réel, pas une coquille vide. */

const photos = vi.fn()
const get = vi.fn()
const calerPhoto = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      photos: (...a) => photos(...a),
      get: (...a) => get(...a),
      calerPhoto: (...a) => calerPhoto(...a),
    },
    // CAL70 — `AtelierPanneaux` (monté ici pour le test d'atteignabilité)
    // porte aussi `PanneauAllees`, qui lit les réglages société au montage.
    parametres: { get: vi.fn().mockResolvedValue({ data: { degagements: {} } }) },
    moteur: { calculer: vi.fn() },
  },
}))

vi.mock('leaflet', () => {
  function fakeMarker(pos) {
    let latlng = Array.isArray(pos) ? { lat: pos[0], lng: pos[1] } : pos
    const marker = {
      addTo: () => marker,
      on: () => marker,
      getLatLng: () => latlng,
      setLatLng: (p) => { latlng = Array.isArray(p) ? { lat: p[0], lng: p[1] } : p },
    }
    return marker
  }
  function fakeMap() {
    const map = {
      addTo: () => map,
      on: () => map,
      remove: () => {},
      latLngToContainerPoint: () => ({ x: 0, y: 0 }),
    }
    return map
  }
  return {
    default: {
      map: vi.fn(() => fakeMap()),
      tileLayer: vi.fn(() => ({ addTo: () => {} })),
      polygon: vi.fn(() => ({ addTo: () => {} })),
      marker: vi.fn((pos) => fakeMarker(pos)),
      divIcon: vi.fn(() => ({})),
    },
  }
})

vi.mock('leaflet/dist/leaflet.css', () => ({}))

const {
  default: PhotoSiteCalage, positionsInitiales, coinsDepuisMarqueurs,
} = await import('../PhotoSiteCalage')

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

/* ── 1. LES MATHS, PURES ──────────────────────────────────────────────── */

describe('CAL53 — positionsInitiales : relecture EXACTE, jamais recalculée', () => {
  it('un calage déjà enregistré est rendu TEL QUEL, sans y toucher', () => {
    const coins = [[33.1, -7.1], [33.2, -7.1], [33.2, -7.2], [33.1, -7.2]]
    expect(positionsInitiales({ coins }, [33.15, -7.15])).toEqual(coins)
  })

  it('sans calage existant, un petit carré autour du centre donné', () => {
    const positions = positionsInitiales(null, [10, 20])
    expect(positions).toHaveLength(4)
    for (const [lat, lng] of positions) {
      expect(lat).toBeCloseTo(10, 2)
      expect(lng).toBeCloseTo(20, 2)
    }
  })

  it('un calage à trois coins (forme invalide) retombe sur le défaut', () => {
    const positions = positionsInitiales({ coins: [[1, 1], [2, 2]] }, [5, 5])
    expect(positions).toHaveLength(4)
    expect(positions[0][0]).toBeCloseTo(5, 2)
  })

  it('sans centre connu, replie sur le Maroc — jamais [0,0]', () => {
    const positions = positionsInitiales(null, null)
    expect(positions[0][0]).toBeCloseTo(31.7917, 2)
  })
})

describe('CAL53 — coinsDepuisMarqueurs : l’ordre de pose est préservé', () => {
  it('rend les 4 [lat, lng] dans l’ordre des marqueurs', () => {
    const marqueurs = [
      { getLatLng: () => ({ lat: 1, lng: 2 }) },
      { getLatLng: () => ({ lat: 3, lng: 4 }) },
      { getLatLng: () => ({ lat: 5, lng: 6 }) },
      { getLatLng: () => ({ lat: 7, lng: 8 }) },
    ]
    expect(coinsDepuisMarqueurs(marqueurs)).toEqual([[1, 2], [3, 4], [5, 6], [7, 8]])
  })
})

/* ── 2. L'ÉCRAN : sélection, drapage, persistance, relecture ───────────── */

const PHOTO_NON_CALEE = {
  id: 1, genre: 'drone', legende: 'Vol du matin', filename: 'vol.png',
  url: 'https://minio/photo-1.png', calage: null,
}
const PHOTO_CALEE = {
  id: 2, genre: 'oblique', legende: '', filename: 'oblique.png',
  url: 'https://minio/photo-2.png',
  calage: { coins: [[33.1, -7.1], [33.2, -7.1], [33.2, -7.2], [33.1, -7.2]] },
}

const rendre = () => render(
  <MemoryRouter initialEntries={['/calepinage/9/photos']}>
    <PhotoSiteCalage calepinageId={9} />
  </MemoryRouter>,
)

describe('CAL53 — l’écran affiche, cale et persiste', () => {
  it('sans aucune photo de site, le DIT au lieu d’une carte vide', async () => {
    photos.mockResolvedValue({ data: { photos: [] } })
    get.mockResolvedValue({ data: { contexte_geographique: null } })
    rendre()
    expect(await screen.findByTestId('cal-photo-calage-vide')).toBeInTheDocument()
  })

  it('choisit la première photo par défaut et affiche la carte', async () => {
    photos.mockResolvedValue({ data: { photos: [PHOTO_NON_CALEE, PHOTO_CALEE] } })
    get.mockResolvedValue({
      data: { contexte_geographique: { pin: { lat: 33.15, lng: -7.15 }, outline: null } },
    })
    rendre()
    expect(await screen.findByTestId('cal-photo-calage-carte')).toBeInTheDocument()
    expect(screen.getByTestId('cal-photo-calage-enregistrer')).toBeInTheDocument()
    // La photo déjà calée propose de plus l'effacement — la première (non
    // calée) ne le propose pas.
    expect(screen.queryByTestId('cal-photo-calage-effacer')).toBeNull()
  })

  it('enregistre le calage courant, EXACTEMENT les 4 coins posés', async () => {
    photos.mockResolvedValue({ data: { photos: [PHOTO_NON_CALEE] } })
    get.mockResolvedValue({ data: { contexte_geographique: null } })
    calerPhoto.mockResolvedValue({ data: {} })
    rendre()
    await screen.findByTestId('cal-photo-calage-carte')

    fireEvent.click(screen.getByTestId('cal-photo-calage-enregistrer'))
    await waitFor(() => expect(calerPhoto).toHaveBeenCalledTimes(1))
    const [calepinageId, photoId, coins] = calerPhoto.mock.calls[0]
    expect(calepinageId).toBe(9)
    expect(photoId).toBe(1)
    expect(coins).toHaveLength(4)
    expect(await screen.findByTestId('cal-photo-calage-message'))
      .toHaveTextContent('Calage enregistré')
  })

  it('efface le calage d’une photo déjà calée — coins envoyés à null', async () => {
    photos.mockResolvedValue({ data: { photos: [PHOTO_CALEE] } })
    get.mockResolvedValue({ data: { contexte_geographique: null } })
    calerPhoto.mockResolvedValue({ data: {} })
    rendre()
    await screen.findByTestId('cal-photo-calage-carte')

    fireEvent.click(screen.getByTestId('cal-photo-calage-effacer'))
    await waitFor(() => expect(calerPhoto).toHaveBeenCalledTimes(1))
    const [, , coins] = calerPhoto.mock.calls[0]
    expect(coins).toBeNull()
    expect(await screen.findByTestId('cal-photo-calage-message'))
      .toHaveTextContent('Calage effacé')
  })
})

describe('CAL53 — l’écran est ATTEIGNABLE', () => {
  it('le module déclare la route `/calepinage/:id/photos` avec ses rôles', async () => {
    const { default: config } = await import('../module.config.jsx')
    const route = config.routes.find((r) => r.path === '/calepinage/:id/photos')
    expect(route, 'route de calage des photos absente du module').toBeTruthy()
    expect(Array.isArray(route.roles) && route.roles.length > 0).toBe(true)
  })

  it('l’atelier propose un lien vers l’écran (CAL37)', async () => {
    const { default: AtelierPanneaux } = await import('../AtelierPanneaux')
    render(
      <MemoryRouter>
        <AtelierPanneaux calepinageId={9} contexte={{}} builderApi={{}} />
      </MemoryRouter>,
    )
    expect(await screen.findByTestId('cal-lien-photos-calage'))
      .toHaveAttribute('href', '/calepinage/9/photos')
  })
})
