import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// XGED12 — écran « Numériser » : capture successive de photos (caméra ou
// injection directe via le mock CameraCapture), puis upload multipart de
// toutes les photos vers `assemblerPhotos` (assemblage PDF CÔTÉ SERVEUR,
// Pillow). On mocke `gedApi` (pas d'appel réseau réel) et `CameraCapture`
// (pas de vraie caméra en test) pour vérifier que l'écran appelle le bon
// endpoint avec les bonnes photos + le bon dossier.
vi.mock('../../api/gedApi', () => ({
  default: {
    getCabinets: vi.fn(),
    getDossiers: vi.fn(),
    assemblerPhotos: vi.fn(),
    // WIR249 — GED31 (lot de fichiers) + GED32 (import CSV en masse).
    scanLot: vi.fn(),
    importMasse: vi.fn(),
  },
}))

vi.mock('../../ui/Toaster', () => ({
  Toaster: () => null,
  toast: { success: vi.fn(), error: vi.fn() },
}))

// NTMOB12 — compression réelle dépend du décodage d'image (Image/canvas),
// non fiable en jsdom (aucun vrai décodeur) : passthrough identité, hors
// périmètre de ce test (couvert par prefs.test.jsx / CameraCapture.test.jsx).
vi.mock('../../pages/preferences/prefs', () => ({
  compressPhotoForUpload: vi.fn((f) => Promise.resolve(f)),
}))

// Simule la caméra : un clic sur « Prendre la photo » remet immédiatement un
// faux fichier JPEG au parent via `onCapture` — aucune vraie caméra requise.
vi.mock('../pwa/CameraCapture.jsx', () => ({
  default: ({ onCapture }) => (
    <button type="button" onClick={() => onCapture(
      new File(['fake-jpeg-bytes'], 'photo.jpg', { type: 'image/jpeg' }))}>
      Prendre la photo (mock)
    </button>
  ),
}))

import gedApi from '../../api/gedApi'
import NumeriserPage from './NumeriserPage.jsx'

const ok = (data) => Promise.resolve({ data })

beforeEach(() => {
  vi.clearAllMocks()
  gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Chantiers' }]))
  gedApi.getDossiers.mockResolvedValue(
    ok([{ id: 10, parent: null, nom: 'Numérisations', path: '/10/' }]))
  gedApi.assemblerPhotos.mockResolvedValue(ok({ id: 99, nom: 'Chantier X' }))
  gedApi.scanLot.mockResolvedValue(ok({ documents: [{ id: 1 }, { id: 2 }], erreurs: [] }))
  gedApi.importMasse.mockResolvedValue(ok({ crees: 3, documents: [], erreurs: [] }))
  // jsdom ne fournit pas createObjectURL/revokeObjectURL — l'écran les
  // utilise pour l'aperçu miniature de chaque page capturée.
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake')
  globalThis.URL.revokeObjectURL = vi.fn()
})

describe('NumeriserPage (XGED12)', () => {
  it('capture 3 photos puis assemble-les vers le dossier choisi', async () => {
    const user = userEvent.setup()
    render(<NumeriserPage />)

    // Le dossier se peuple après le chargement des cabinets/dossiers.
    await waitFor(() => expect(gedApi.getDossiers).toHaveBeenCalled())

    const openCamera = await screen.findByRole(
      'button', { name: /prendre la première photo/i })
    await user.click(openCamera)
    await user.click(screen.getByRole('button', { name: /prendre la photo \(mock\)/i }))

    // Deuxième et troisième photo : le bouton devient "Ajouter une photo".
    await user.click(screen.getByRole('button', { name: /ajouter une photo/i }))
    await user.click(screen.getByRole('button', { name: /prendre la photo \(mock\)/i }))
    await user.click(screen.getByRole('button', { name: /ajouter une photo/i }))
    await user.click(screen.getByRole('button', { name: /prendre la photo \(mock\)/i }))

    // Choisit le dossier de destination.
    const folderSelect = screen.getByLabelText(/choisir le dossier/i)
    await user.click(folderSelect)
    await user.click(await screen.findByText('Numérisations'))

    await user.type(screen.getByLabelText(/nom du document/i), 'Chantier X')

    const submit = screen.getByRole('button', { name: /assembler en pdf et classer \(3\)/i })
    await user.click(submit)

    await waitFor(() => expect(gedApi.assemblerPhotos).toHaveBeenCalledTimes(1))
    const call = gedApi.assemblerPhotos.mock.calls[0][0]
    expect(call.folder).toBe(10)
    expect(call.photos).toHaveLength(3)
    expect(call.nom).toBe('Chantier X')
  })

  it("désactive l'assemblage tant qu'aucune photo n'est capturée", async () => {
    render(<NumeriserPage />)
    await waitFor(() => expect(gedApi.getDossiers).toHaveBeenCalled())
    const submit = screen.getByRole('button', { name: /assembler en pdf et classer \(0\)/i })
    expect(submit).toBeDisabled()
  })

  it('permet de supprimer une photo capturée avant l’envoi', async () => {
    const user = userEvent.setup()
    render(<NumeriserPage />)
    await waitFor(() => expect(gedApi.getDossiers).toHaveBeenCalled())

    await user.click(await screen.findByRole(
      'button', { name: /prendre la première photo/i }))
    await user.click(screen.getByRole('button', { name: /prendre la photo \(mock\)/i }))

    expect(screen.getByRole('button', { name: /assembler en pdf et classer \(1\)/i }))
      .toBeInTheDocument()

    await user.click(screen.getByTitle('Supprimer'))

    expect(screen.getByRole('button', { name: /assembler en pdf et classer \(0\)/i }))
      .toBeInTheDocument()
  })

  // VX42 — FAB terrain : un raccourci flottant vers la caméra, au libellé
  // DISTINCT du bouton inline (deux boutons identiques peuvent coexister à
  // l'écran ; un `getByRole` ciblé sur l'un ne doit jamais matcher l'autre).
  it('propose un FAB « Photo (caméra) » distinct du bouton inline, masqué tant que la caméra est ouverte', async () => {
    const user = userEvent.setup()
    render(<NumeriserPage />)
    await waitFor(() => expect(gedApi.getDossiers).toHaveBeenCalled())

    const fab = await screen.findByRole('button', { name: 'Photo (caméra)' })
    expect(screen.getByRole('button', { name: /prendre la première photo/i })).toBeInTheDocument()

    await user.click(fab)
    // La caméra (mock) est maintenant ouverte : le FAB comme le bouton inline
    // s'effacent au profit du flux de capture.
    expect(screen.queryByRole('button', { name: 'Photo (caméra)' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /prendre la photo \(mock\)/i })).toBeInTheDocument()
  })
})

/* WIR249 — deux entrées de MASSE jamais câblées : GED31 (scan-lot) et GED32
   (import-masse). Le rapport `erreurs` par fichier/ligne est AFFICHÉ. */
describe('NumeriserPage — WIR249 lot & import en masse', () => {
  const choisirDossier = async (user) => {
    await waitFor(() => expect(gedApi.getDossiers).toHaveBeenCalled())
    await user.click(screen.getByLabelText(/choisir le dossier/i))
    await user.click(await screen.findByText('Numérisations'))
  }

  it('GED31 — dépose un lot de fichiers en multipart (clé `files` répétée)', async () => {
    const user = userEvent.setup()
    render(<NumeriserPage />)
    await choisirDossier(user)

    await user.upload(screen.getByTestId('ged-scanlot-files'), [
      new File(['a'], 'a.pdf', { type: 'application/pdf' }),
      new File(['b'], 'b.pdf', { type: 'application/pdf' }),
    ])
    await user.click(screen.getByTestId('ged-scanlot-submit'))

    await waitFor(() => expect(gedApi.scanLot).toHaveBeenCalledTimes(1))
    const fd = gedApi.scanLot.mock.calls[0][0]
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('folder')).toBe('10')
    expect(fd.getAll('files')).toHaveLength(2)
  })

  it('GED31 — un fichier refusé est LISTÉ, jamais tu derrière un succès', async () => {
    const user = userEvent.setup()
    gedApi.scanLot.mockResolvedValue(ok({
      documents: [{ id: 1 }],
      erreurs: [{ fichier: 'virus.exe', erreur: 'Format refusé.' }],
    }))
    render(<NumeriserPage />)
    await choisirDossier(user)
    await user.upload(screen.getByTestId('ged-scanlot-files'),
      [new File(['a'], 'a.pdf', { type: 'application/pdf' })])
    await user.click(screen.getByTestId('ged-scanlot-submit'))

    const rapport = await screen.findByTestId('ged-masse-rapport')
    expect(rapport).toHaveTextContent('1 erreur(s)')
    expect(screen.getByTestId('ged-masse-erreur')).toHaveTextContent('Format refusé.')
  })

  it('GED32 — import CSV (+ ZIP optionnel) et compte des créations', async () => {
    const user = userEvent.setup()
    render(<NumeriserPage />)
    await choisirDossier(user)

    await user.upload(screen.getByTestId('ged-import-csv'),
      new File(['nom,fichier'], 'meta.csv', { type: 'text/csv' }))
    await user.upload(screen.getByTestId('ged-import-zip'),
      new File(['PK'], 'binaires.zip', { type: 'application/zip' }))
    await user.click(screen.getByTestId('ged-import-submit'))

    await waitFor(() => expect(gedApi.importMasse).toHaveBeenCalledTimes(1))
    const fd = gedApi.importMasse.mock.calls[0][0]
    expect(fd.get('folder')).toBe('10')
    expect(fd.get('csv')).toBeTruthy()
    expect(fd.get('zip')).toBeTruthy()
    expect(await screen.findByTestId('ged-masse-rapport')).toHaveTextContent('3 document(s) créé(s)')
  })

  it('les deux entrées de masse exigent un dossier de destination', async () => {
    render(<NumeriserPage />)
    await waitFor(() => expect(gedApi.getDossiers).toHaveBeenCalled())
    expect(screen.getByTestId('ged-scanlot-submit')).toBeDisabled()
    expect(screen.getByTestId('ged-import-submit')).toBeDisabled()
  })
})
