import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CALX38 — TÉLÉVERSER UNE PHOTO DE SITE.
   ----------------------------------------------------------------------------
   Deux invariants du « Done » de la tâche : genre ou date absents refusent le
   dépôt AVANT tout envoi réseau, chacun pointant SON champ (jamais un refus
   générique) ; après un dépôt réussi, l'état vide disparaît et la photo
   déposée est immédiatement sélectionnable pour le calage.

   Même patron de double Leaflet que `photo_site_calage.test.jsx` (CAL53) :
   jsdom ne fournit ni tuiles ni géométrie de carte, et ce fichier ne teste
   PAS le calage lui-même — seulement le dépôt, en tête du panneau.
   ========================================================================== */

const photos = vi.fn()
const get = vi.fn()
const calerPhoto = vi.fn()
const ajouterPhoto = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      photos: (...a) => photos(...a),
      get: (...a) => get(...a),
      calerPhoto: (...a) => calerPhoto(...a),
      ajouterPhoto: (...a) => ajouterPhoto(...a),
    },
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

const { default: PhotoSiteCalage } = await import('../PhotoSiteCalage')

const PHOTO_NEUVE = {
  id: 5, genre: 'drone', legende: '', filename: 'photo.png',
  url: 'https://minio/photo-5.png', calage: null,
}

const fichierPNG = () => new File(['contenu'], 'photo.png', { type: 'image/png' })

const rendre = () => render(
  <MemoryRouter initialEntries={['/calepinage/9/photos']}>
    <PhotoSiteCalage calepinageId={9} />
  </MemoryRouter>,
)

const choisirGenre = async (libelle) => {
  fireEvent.click(screen.getByTestId('cal-photo-depot-genre'))
  fireEvent.click(await screen.findByRole('option', { name: libelle }))
}

beforeEach(() => {
  vi.clearAllMocks()
  get.mockResolvedValue({ data: { contexte_geographique: null } })
})
afterEach(() => { cleanup() })

describe('CALX38 — genre et date sont OBLIGATOIRES avant tout envoi', () => {
  it('les deux absents : refus AVANT envoi, chacun pointe SON champ', async () => {
    photos.mockResolvedValue({ data: { photos: [] } })
    rendre()
    await screen.findByTestId('cal-photo-calage-vide')

    fireEvent.change(screen.getByTestId('cal-photo-depot-fichier'),
      { target: { files: [fichierPNG()] } })

    expect(await screen.findByTestId('cal-photo-depot-erreur-genre'))
      .toHaveTextContent('obligatoire')
    expect(screen.getByTestId('cal-photo-depot-erreur-date')).toHaveTextContent('obligatoire')
    expect(ajouterPhoto).not.toHaveBeenCalled()
  })

  it('date seule absente : SEUL son champ est pointé', async () => {
    photos.mockResolvedValue({ data: { photos: [] } })
    rendre()
    await screen.findByTestId('cal-photo-calage-vide')
    await choisirGenre('Drone')

    fireEvent.change(screen.getByTestId('cal-photo-depot-fichier'),
      { target: { files: [fichierPNG()] } })

    expect(await screen.findByTestId('cal-photo-depot-erreur-date')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-photo-depot-erreur-genre')).not.toBeInTheDocument()
    expect(ajouterPhoto).not.toHaveBeenCalled()
  })
})

describe('CALX38 — un dépôt réussi', () => {
  it('l’état vide disparaît et la photo devient sélectionnable pour le calage', async () => {
    photos.mockResolvedValueOnce({ data: { photos: [] } })
    ajouterPhoto.mockResolvedValue({ data: { photo: PHOTO_NEUVE, photos: [PHOTO_NEUVE] } })
    rendre()
    await screen.findByTestId('cal-photo-calage-vide')

    await choisirGenre('Drone')
    fireEvent.change(screen.getByTestId('cal-photo-depot-date'), { target: { value: '2026-09-20' } })

    photos.mockResolvedValueOnce({ data: { photos: [PHOTO_NEUVE] } })
    fireEvent.change(screen.getByTestId('cal-photo-depot-fichier'),
      { target: { files: [fichierPNG()] } })

    await waitFor(() => expect(ajouterPhoto).toHaveBeenCalledTimes(1))
    const [idArg, corpsArg] = ajouterPhoto.mock.calls[0]
    expect(idArg).toBe(9)
    expect(corpsArg.get('genre')).toBe('drone')
    expect(corpsArg.get('prise_le')).toBe('2026-09-20')
    expect(corpsArg.get('photo')).toBeTruthy()

    await waitFor(() => expect(screen.queryByTestId('cal-photo-calage-vide')).not.toBeInTheDocument())
    expect(screen.getByTestId('cal-photo-calage-select')).toBeInTheDocument()
  })

  it('un refus SERVEUR (champ nommé) s’affiche sous le bon champ', async () => {
    photos.mockResolvedValue({ data: { photos: [] } })
    ajouterPhoto.mockRejectedValue({ response: { data: { photo: "Ce fichier n'est pas une image." } } })
    rendre()
    await screen.findByTestId('cal-photo-calage-vide')

    await choisirGenre('Oblique (aérienne)')
    fireEvent.change(screen.getByTestId('cal-photo-depot-date'), { target: { value: '2026-09-20' } })
    fireEvent.change(screen.getByTestId('cal-photo-depot-fichier'),
      { target: { files: [fichierPNG()] } })

    expect(await screen.findByTestId('cal-photo-depot-erreur-photo'))
      .toHaveTextContent("n'est pas une image")
  })
})
