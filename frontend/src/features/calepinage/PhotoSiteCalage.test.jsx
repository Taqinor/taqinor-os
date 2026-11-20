import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { coinsDepuisFichierMonde } from './commun/fichierCalageMonde'

/* ============================================================================
   ACAL201 — les photos se chargent par leur CHEMIN RELATIF servi (cookie
   httpOnly, même origine), préfixé de l'origine d'API quand VITE_API_URL en
   pose une.
   ACAL203 — l'écran photos : modifier / supprimer, poignées « non calées »,
   carte sur tuiles valides (zoom 19, maxNativeZoom 19), 400 de calage motivé.

   PACT13 — les photos viennent de l'exemple COMMITTÉ calepinage_photos.json.
   Leaflet est MOQUÉ (jsdom) : le double retient les options des tuiles, les
   positions et les gestionnaires de glisser. */

const photos = vi.fn()
const get = vi.fn()
const calerPhoto = vi.fn()
const modifierPhoto = vi.fn()
const supprimerPhoto = vi.fn()
const layout = vi.fn()
vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      photos: (...a) => photos(...a),
      get: (...a) => get(...a),
      calerPhoto: (...a) => calerPhoto(...a),
      modifierPhoto: (...a) => modifierPhoto(...a),
      supprimerPhoto: (...a) => supprimerPhoto(...a),
      layout: (...a) => layout(...a),
      enregistrerSectionLayout: vi.fn(),
    },
    parametres: { get: vi.fn().mockResolvedValue({ data: { imagerie: {} } }) },
  },
}))

const tileLayer = vi.fn(() => ({ addTo: () => {} }))
const carte = vi.fn()
vi.mock('leaflet', () => ({
  default: {
    map: (_el, options) => {
      carte(options)
      return Object.fromEntries(
        ['addTo', 'on'].map((nom) => [nom, function chainable() { return this }])
          .concat([['remove', () => {}], ['latLngToContainerPoint', () => ({ x: 0, y: 0 })]]),
      )
    },
    tileLayer: (...a) => tileLayer(...a),
    polygon: () => ({ addTo: () => {} }),
    marker: (pos) => {
      let [lat, lng] = Array.isArray(pos) ? pos : [pos.lat, pos.lng]
      const poignee = {
        gestionnaires: {},
        getLatLng: () => ({ lat, lng }),
        setLatLng(p) { [lat, lng] = Array.isArray(p) ? p : [p.lat, p.lng]; return poignee },
        on(evt, fn) { poignee.gestionnaires[evt] = fn; return poignee },
        addTo() { (globalThis.__marqueursCalage203 ||= []).push(poignee); return poignee },
      }
      return poignee
    },
    divIcon: () => ({}),
  },
}))
vi.mock('leaflet/dist/leaflet.css', () => ({}))

const { default: PhotoSiteCalage } = await import('./PhotoSiteCalage')

const PHOTOS = exempleContrat('calepinage', 'calepinage_photos').photos
const NON_CALEE = { ...PHOTOS[0], id: 31, calage: null, prise_le: '2026-09-18' }
const CALEE = PHOTOS[0]

const rendre = () => render(
  <MemoryRouter initialEntries={['/calepinage/9/photos']}>
    <PhotoSiteCalage calepinageId={9} />
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  globalThis.__marqueursCalage203 = []
  get.mockResolvedValue({ data: { contexte_geographique: null } })
  layout.mockResolvedValue({ data: { roof_layout: { zones: [] }, empreinte_document: 'E0' } })
})
afterEach(() => { cleanup(); vi.unstubAllEnvs() })

describe('ACAL201 — l’image se charge par l’URL relative servie', () => {
  it('charge l’image par l’URL relative préfixée et redessine au load', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.exemple.test')
    photos.mockResolvedValue({ data: { photos: [CALEE] } })
    const { container } = rendre()
    await screen.findByTestId('cal-photo-calage-carte')

    const image = container.querySelector('img[hidden]')
    expect(CALEE.url.startsWith('/api/django/calepinage/')).toBe(true)
    expect(image.getAttribute('src')).toBe(`https://api.exemple.test${CALEE.url}`)
    // Une origine d'API distincte : le cookie de session part avec l'image.
    expect(image.getAttribute('crossorigin')).toBe('use-credentials')
    // onLoad déclenche le redessin sans erreur.
    expect(() => fireEvent.load(image)).not.toThrow()
  })

  it('même origine (VITE_API_URL vide) : le chemin relatif tel quel', async () => {
    photos.mockResolvedValue({ data: { photos: [CALEE] } })
    const { container } = rendre()
    await screen.findByTestId('cal-photo-calage-carte')
    expect(container.querySelector('img[hidden]').getAttribute('src')).toBe(CALEE.url)
  })
})

describe('ACAL203 — calage, modification, suppression, carte', () => {
  it('Enregistrer le calage est désactivé tant que les poignées n’ont pas bougé', async () => {
    photos.mockResolvedValue({ data: { photos: [NON_CALEE] } })
    rendre()
    await screen.findByTestId('cal-photo-calage-carte')
    const bouton = screen.getByTestId('cal-photo-calage-enregistrer')
    expect(bouton).toBeDisabled()

    act(() => { globalThis.__marqueursCalage203.at(-1).gestionnaires.dragend() })
    expect(bouton).not.toBeDisabled()
  })

  it('une photo déjà calée s’enregistre sans geste (calage existant)', async () => {
    photos.mockResolvedValue({ data: { photos: [CALEE] } })
    rendre()
    await screen.findByTestId('cal-photo-calage-carte')
    expect(screen.getByTestId('cal-photo-calage-enregistrer')).not.toBeDisabled()
  })

  it('un calage refusé 400 affiche le motif sous Calage', async () => {
    photos.mockResolvedValue({ data: { photos: [NON_CALEE] } })
    calerPhoto.mockRejectedValue({
      response: { status: 400, data: { calage: 'Les quatre coins sont confondus.' } },
    })
    rendre()
    await screen.findByTestId('cal-photo-calage-carte')
    act(() => { globalThis.__marqueursCalage203.at(-1).gestionnaires.dragend() })
    fireEvent.click(screen.getByTestId('cal-photo-calage-enregistrer'))
    expect(await screen.findByTestId('cal-photo-calage-erreur'))
      .toHaveTextContent('Calage : Les quatre coins sont confondus.')
  })

  it('modifie la date de prise de vue', async () => {
    photos.mockResolvedValue({ data: { photos: [CALEE] } })
    modifierPhoto.mockResolvedValue({ data: { photo: CALEE, photos: [CALEE] } })
    rendre()
    await screen.findByTestId('cal-photo-calage-carte')

    fireEvent.click(screen.getByTestId('cal-photo-modifier'))
    fireEvent.change(await screen.findByTestId('cal-photo-edition-date'),
      { target: { value: '2026-09-20' } })
    fireEvent.click(screen.getByTestId('cal-photo-edition-enregistrer'))

    await waitFor(() => expect(modifierPhoto).toHaveBeenCalledTimes(1))
    expect(modifierPhoto).toHaveBeenCalledWith(9, CALEE.id, {
      genre: CALEE.genre, prise_le: '2026-09-20', legende: CALEE.legende,
    })
    expect(await screen.findByTestId('cal-photo-calage-message'))
      .toHaveTextContent('Photo modifiée.')
  })

  it('supprime la photo après confirmation', async () => {
    photos.mockResolvedValue({ data: { photos: [CALEE] } })
    supprimerPhoto.mockResolvedValue({ data: { photos: [] } })
    rendre()
    await screen.findByTestId('cal-photo-calage-carte')

    fireEvent.click(screen.getByTestId('cal-photo-supprimer'))
    expect(supprimerPhoto).not.toHaveBeenCalled() // pas de suppression sans confirmation
    photos.mockResolvedValue({ data: { photos: [] } })
    fireEvent.click(screen.getByTestId('cal-photo-supprimer-confirmer'))

    await waitFor(() => expect(supprimerPhoto).toHaveBeenCalledWith(9, CALEE.id))
    expect(await screen.findByTestId('cal-photo-calage-vide')).toBeInTheDocument()
  })

  it('un retrait refusé (409 verrou) affiche le motif', async () => {
    // ACON13 — calepinage au devis accepté : le motif SERVEUR (`photos[0]`) est dit.
    photos.mockResolvedValue({ data: { photos: [CALEE] } })
    supprimerPhoto.mockRejectedValue({ response: { status: 409, data: {
      photos: ['Devis accepté : révisez-le (nouvelle version).'] } } })
    rendre()
    await screen.findByTestId('cal-photo-calage-carte')

    fireEvent.click(screen.getByTestId('cal-photo-supprimer'))
    fireEvent.click(screen.getByTestId('cal-photo-supprimer-confirmer'))

    expect(await screen.findByTestId('cal-photo-calage-message'))
      .toHaveTextContent('Devis accepté : révisez-le')
  })

  it('la carte utilise maxNativeZoom 19 et démarre au zoom 19', async () => {
    photos.mockResolvedValue({ data: { photos: [CALEE] } })
    rendre()
    await screen.findByTestId('cal-photo-calage-carte')

    expect(carte.mock.calls[0][0].zoom).toBe(19)
    const options = tileLayer.mock.calls[0][1]
    expect(options.maxNativeZoom).toBe(19)
  })
})

// ACAL424 — l'orthophoto se cale depuis son fichier « monde » (degrés WGS84).
describe('ACAL424 — fichier de calage monde (.jgw/.pgw/.wld)', () => {
  // 0,001° par pixel, haut-gauche (lng -7,10 ; lat 33,60), lignes dans l'ordre A D B E C F.
  const JGW = ['0.001', '0', '0', '-0.001', '-7.10', '33.60'].join('\n')

  it('fichier .jgw en degrés : 4 coins NO, NE, SE, SO (lat, lng) ; mètres refusé', () => {
    const { coins } = coinsDepuisFichierMonde(JGW, 100, 50)
    expect(coins[0][0]).toBeCloseTo(33.6005, 6) // NO : lat
    expect(coins[0][1]).toBeCloseTo(-7.1005, 6) // NO : lng
    expect(coins[1][1]).toBeCloseTo(-7.1005 + 0.1, 6) // NE : lng
    expect(coins[2][0]).toBeCloseTo(33.6005 - 0.05, 6) // SE : lat
    expect(coins[3][1]).toBeCloseTo(-7.1005, 6) // SO : lng
    const metres = ['0.5', '0', '0', '-0.5', '300000', '3700000'].join('\n')
    expect(coinsDepuisFichierMonde(metres, 100, 50).erreur).toMatch(/WGS84/)
    expect(coinsDepuisFichierMonde('1\n2\n3\n', 100, 50).erreur).toMatch(/6 nombres/)
    expect(coinsDepuisFichierMonde(JGW, 0, 0).erreur).toMatch(/Dimensions/)
  })

  it('le fichier remplit les poignées ; rien n’est enregistré avant le clic', async () => {
    photos.mockResolvedValue({ data: { photos: [NON_CALEE] } })
    const { container } = rendre()
    await screen.findByTestId('cal-photo-calage-carte')
    const image = container.querySelector('img[hidden]')
    Object.defineProperty(image, 'naturalWidth', { value: 100 })
    Object.defineProperty(image, 'naturalHeight', { value: 50 })
    const fichier = new File([JGW], 'ortho.jgw', { type: 'text/plain' })
    Object.defineProperty(fichier, 'text', { value: () => Promise.resolve(JGW) })
    fireEvent.change(screen.getByTestId('cal-photo-calage-monde'), { target: { files: [fichier] } })

    await waitFor(() => expect(screen.getByTestId('cal-photo-calage-enregistrer')).not.toBeDisabled())
    expect(calerPhoto).not.toHaveBeenCalled()
    const poignees = globalThis.__marqueursCalage203.slice(-4)
    expect(poignees[0].getLatLng().lat).toBeCloseTo(33.6005, 6)
    expect(poignees[1].getLatLng().lng).toBeCloseTo(-7.0005, 6)
  })
})