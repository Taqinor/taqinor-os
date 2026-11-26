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
vi.mock('../../../api/calepinageApi', async () => (await import('../../../test/fixtures/calepinageApiMock'))
  .apiCalepinages({ photos, get, calerPhoto, ajouterPhoto }))

vi.mock('leaflet', async () => (await import('./leafletFauxMock')).leafletFauxMock())
vi.mock('leaflet/dist/leaflet.css', () => ({}))

const { default: PhotoSiteCalage } = await import('../PhotoSiteCalage')
const { anciennesEnFile, compterEnAttente, deposerOuMettreEnFile, rejouerFile, genresEnAttente } = await import('../fileEnvoiPhotos')
const { createBinaryOutboxStore } = await import('../../../lib/offlineStore')
const { store } = await import('../../../store')
const { setCredentials, logout } = await import('../../auth/store/authSlice')

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
  // Revue ACAL1949 — la file n'appartient qu'à un utilisateur CONNECTÉ : sans session, rien n'y est rejoué.
  store.dispatch(setCredentials({ user: { id: 1 } }))
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

describe('ACAL892 — photo déposée hors ligne : gardée sur l’appareil, envoyée au retour du réseau', () => {
  let enLigne
  const remplir = async () => {
    await choisirGenre('Drone')
    fireEvent.change(screen.getByTestId('cal-photo-depot-date'), { target: { value: '2026-09-20' } })
    fireEvent.change(screen.getByTestId('cal-photo-depot-fichier'), { target: { files: [fichierPNG()] } })
  }
  const retourReseau = () => { enLigne.mockReturnValue(true); window.dispatchEvent(new Event('online')) }

  beforeEach(() => {
    photos.mockResolvedValue({ data: { photos: [] } })
    enLigne = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
  })
  afterEach(async () => {
    enLigne.mockReturnValue(true)
    ajouterPhoto.mockReset()
    ajouterPhoto.mockResolvedValue({ data: { photo: PHOTO_NEUVE, photos: [PHOTO_NEUVE] } })
    await rejouerFile(9) // vide la file partagée du module entre deux cas
    enLigne.mockRestore()
  })

  it('hors ligne ⇒ photo en file, message et compte 1 ; au retour du réseau ⇒ envoi, compte 0, « Photo envoyée »', async () => {
    rendre()
    await screen.findByTestId('cal-photo-calage-vide')
    await remplir()

    const etat = await screen.findByTestId('acal892-file-attente')
    expect(etat).toHaveTextContent('Photo gardée sur cet appareil : elle partira dès le retour du réseau.')
    expect(etat).toHaveTextContent('1 photo en attente d’envoi')
    expect(ajouterPhoto).not.toHaveBeenCalled()

    ajouterPhoto.mockResolvedValue({ data: { photo: PHOTO_NEUVE, photos: [PHOTO_NEUVE] } })
    retourReseau()
    await waitFor(() => expect(ajouterPhoto).toHaveBeenCalledTimes(1))
    const [id, corps] = ajouterPhoto.mock.calls[0]
    expect(id).toBe(9)
    expect(corps.get('genre')).toBe('drone')
    expect(corps.get('prise_le')).toBe('2026-09-20')
    await waitFor(() => expect(screen.getByTestId('acal892-file-attente')).toHaveTextContent('Photo envoyée.'))
    expect(screen.getByTestId('acal892-file-attente')).not.toHaveTextContent('en attente')
    expect(await rejouerFile(9)).toMatchObject({ envoyees: 0, restantes: 0 })
  })

  it('le compte survit au rechargement de l’écran (relu dans la file)', async () => {
    rendre()
    await screen.findByTestId('cal-photo-calage-vide')
    await remplir()
    await screen.findByTestId('acal892-file-attente')
    cleanup()
    rendre()
    expect(await screen.findByTestId('acal892-file-attente')).toHaveTextContent('1 photo en attente d’envoi')
    expect(await genresEnAttente(9)).toEqual(['drone']) // T4-X8-003 — le genre gardé se relit aussi (le relevé au téléphone le montre)
  })

  it('refus serveur (400) au retour du réseau ⇒ retirée de la file, champ nommé', async () => {
    rendre()
    await screen.findByTestId('cal-photo-calage-vide')
    await remplir()
    await screen.findByTestId('acal892-file-attente')
    ajouterPhoto.mockRejectedValue({ response: { status: 400, data: { genre: 'Genre inconnu.' } } })
    retourReseau()
    await waitFor(() => expect(screen.getByTestId('acal892-file-attente')).toHaveTextContent('Photo refusée par le serveur (genre : Genre inconnu.)'))
    expect(screen.getByTestId('acal892-file-attente')).not.toHaveTextContent('en attente')
    expect(await rejouerFile(9)).toMatchObject({ restantes: 0 })
  })

  it('en ligne mais coupure pendant l’envoi (aucune réponse) ⇒ photo en file ; en ligne normal ⇒ inchangé', async () => {
    enLigne.mockReturnValue(true)
    ajouterPhoto.mockRejectedValueOnce(new Error('Network Error'))
    rendre()
    await screen.findByTestId('cal-photo-calage-vide')
    await remplir()
    expect(await screen.findByTestId('acal892-file-attente')).toHaveTextContent('Photo gardée sur cet appareil')
    expect(ajouterPhoto).toHaveBeenCalledTimes(1)
  })

  describe('revue ACAL1949 (point 4) — une photo gardée appartient à SON utilisateur', () => {
    const viderLaFile = async () => { await createBinaryOutboxStore().store.save([]) }
    afterEach(viderLaFile)
    const garderSansUtilisateur = async () => {
      store.dispatch(logout()) // la forme d'une photo gardée avant la mise à jour : aucun utilisateur noté
      expect(await deposerOuMettreEnFile(9, fichierPNG(), { genre: 'drone', prise_le: '2026-09-20' })).toEqual({ enFile: true })
      store.dispatch(setCredentials({ user: { id: 1 } }))
    }

    it('photo de A, connexion de B : ni comptée ni envoyée ; A reconnecté : envoyée', async () => {
      rendre()
      await screen.findByTestId('cal-photo-calage-vide')
      await remplir()
      await screen.findByTestId('acal892-file-attente')
      cleanup()
      store.dispatch(setCredentials({ user: { id: 2 } }))
      enLigne.mockReturnValue(true)
      expect(await compterEnAttente(9)).toBe(0)
      expect(await genresEnAttente(9)).toEqual([])
      expect(await rejouerFile(9)).toEqual({ envoyees: 0, refusees: [], restantes: 0 })
      expect(ajouterPhoto).not.toHaveBeenCalled()

      store.dispatch(setCredentials({ user: { id: 1 } }))
      ajouterPhoto.mockResolvedValue({ data: { photo: PHOTO_NEUVE, photos: [PHOTO_NEUVE] } })
      expect(await rejouerFile(9)).toEqual({ envoyees: 1, refusees: [], restantes: 0 })
      expect(ajouterPhoto).toHaveBeenCalledTimes(1)
    })

    it('photo gardée avant la règle : montrée, jamais envoyée seule ; « Envoyer sous mon compte » l’envoie', async () => {
      await garderSansUtilisateur()
      enLigne.mockReturnValue(true)
      ajouterPhoto.mockResolvedValue({ data: { photo: PHOTO_NEUVE, photos: [PHOTO_NEUVE] } })
      rendre()
      expect(await screen.findByTestId('releve-anciennes')).toHaveTextContent('1 photo gardée avant la mise à jour — à vérifier')
      expect(ajouterPhoto).not.toHaveBeenCalled()
      fireEvent.click(screen.getByTestId('releve-anciennes-envoyer'))
      await waitFor(() => expect(ajouterPhoto).toHaveBeenCalledTimes(1))
      expect(ajouterPhoto.mock.calls[0][1].get('genre')).toBe('drone')
      await waitFor(() => expect(screen.queryByTestId('releve-anciennes')).toBeNull())
    })

    it('photo gardée avant la règle : « Supprimer » la retire sans rien envoyer', async () => {
      await garderSansUtilisateur()
      enLigne.mockReturnValue(true)
      rendre()
      await screen.findByTestId('releve-anciennes')
      fireEvent.click(screen.getByTestId('releve-anciennes-supprimer'))
      await waitFor(() => expect(screen.queryByTestId('releve-anciennes')).toBeNull())
      expect(await anciennesEnFile(9)).toEqual({ releve: false, photos: 0 })
      expect(ajouterPhoto).not.toHaveBeenCalled()
    })
  })
})
