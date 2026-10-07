import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* ACAL203 — « même fond de carte » : le calage de la photo de toit de la
   visite pose le fond par le MÊME module (`lib/calage/fondCarte.js`) que le
   calage de photo de site du calepinage : zoom 19, tuiles au zoom natif 19
   (aucune tuile en 400), jamais le zoom 20 d'avant. */

const getVisite = vi.fn()
vi.mock('../../api/visitesApi', () => ({
  default: {
    getVisite: (...a) => getVisite(...a),
    assemblerPhotosVisite: vi.fn(),
  },
}))

const tileLayer = vi.fn(() => ({ addTo: () => {} }))
const carte = vi.fn()
vi.mock('leaflet', () => {
  const marker = () => {
    const m = { addTo: () => m, on: () => m, getLatLng: () => ({ lat: 0, lng: 0 }) }
    return m
  }
  const fakeMap = (options) => {
    carte(options)
    const map = { on: () => map, remove: () => {}, latLngToContainerPoint: () => ({ x: 0, y: 0 }) }
    return map
  }
  return {
    default: {
      map: vi.fn((_el, options) => fakeMap(options)),
      tileLayer: (...a) => tileLayer(...a),
      marker: vi.fn(marker),
      divIcon: vi.fn(() => ({})),
    },
  }
})
vi.mock('leaflet/dist/leaflet.css', () => ({}))

const { default: CalageToitPage } = await import('./CalageToitPage')
const { tuileDeFond } = await import('../../lib/calage/fondCarte')

beforeEach(() => {
  vi.clearAllMocks()
  getVisite.mockResolvedValue({
    data: {
      id: 5,
      client_panel: { gps_lat: 33.57, gps_lng: -7.59 },
      photo_toit: { assemblage_etat: 'aucun' },
      checklist: [],
    },
  })
})
afterEach(() => { cleanup() })

describe('ACAL203 — CalageToitPage : même fond de carte', () => {
  it('même fond de carte : zoom 19 et tuiles au zoom natif 19', async () => {
    render(
      <MemoryRouter initialEntries={['/visites/5/calage']}>
        <Routes><Route path="/visites/:id/calage" element={<CalageToitPage />} /></Routes>
      </MemoryRouter>,
    )
    await waitFor(() => expect(carte).toHaveBeenCalled())

    expect(carte.mock.calls[0][0].zoom).toBe(19)
    const options = tileLayer.mock.calls[0][1]
    expect(options.maxNativeZoom).toBe(19)
  })
})

describe('ACAL203 — fondCarte : la tuile du fournisseur de la société', () => {
  it('sans réglage : OSM, comportement d’aujourd’hui', () => {
    expect(tuileDeFond({}).url).toContain('tile.openstreetmap.org')
    expect(tuileDeFond(null).url).toContain('tile.openstreetmap.org')
  })

  it('IGN réglé AVEC sa mention saisie : la tuile IGN, mention affichée telle quelle', () => {
    const tuile = tuileDeFond({
      fournisseur_imagerie: 'ign_bd_ortho', attribution: '© IGN — BD ORTHO®',
    })
    expect(tuile.url).toContain('ORTHOIMAGERY.ORTHOPHOTOS')
    expect(tuile.attribution).toBe('© IGN — BD ORTHO®')
  })

  it('IGN sans mention saisie : jamais affiché sans elle — repli OSM', () => {
    expect(tuileDeFond({ fournisseur_imagerie: 'ign_bd_ortho', attribution: null }).url)
      .toContain('tile.openstreetmap.org')
  })

  it('fournisseur à clé (MapTiler) : OSM, aucune clé inventée', () => {
    expect(tuileDeFond({ fournisseur_imagerie: 'maptiler' }).url)
      .toContain('tile.openstreetmap.org')
  })
})
