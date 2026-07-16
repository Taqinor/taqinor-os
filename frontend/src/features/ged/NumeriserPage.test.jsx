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
  },
}))

vi.mock('../../ui/Toaster', () => ({
  Toaster: () => null,
  toast: { success: vi.fn(), error: vi.fn() },
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
