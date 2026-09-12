// NTUX12 — FavorisWidget : liste les favoris épinglés avec accès direct
// (clic navigue via ROUTE, même table que la palette ⌘K/Récents — aucune
// route dupliquée). NTUX35 — l'en-tête (export/import) reste TOUJOURS rendu,
// même sans aucun favori : l'import doit rester atteignable pour un compte
// tout juste repris (sans favori à exporter, mais tout à importer).
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

const listFavorisMock = vi.fn()
const exportFavorisCsvMock = vi.fn()
const importFavorisMock = vi.fn()
vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listFavoris: (...a) => listFavorisMock(...a),
    createFavori: vi.fn(),
    deleteFavori: vi.fn(),
    reordonnerFavori: vi.fn(),
    exportFavorisCsv: (...a) => exportFavorisCsvMock(...a),
    importFavoris: (...a) => importFavorisMock(...a),
  },
}))

const downloadBlobMock = vi.fn()
vi.mock('../../utils/downloadBlob', () => ({
  downloadBlob: (...a) => downloadBlobMock(...a),
  stampedFilename: (base, ext) => `${base}.${ext}`,
}))

const toastError = vi.fn()
const toastSuccess = vi.fn()
vi.mock('../../ui/confirm', () => ({
  toast: { success: (...a) => toastSuccess(...a), error: (...a) => toastError(...a) },
}))

import FavorisWidget from './FavorisWidget'

beforeEach(() => {
  listFavorisMock.mockReset()
  exportFavorisCsvMock.mockReset()
  importFavorisMock.mockReset()
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderWidget() {
  return render(<FavorisWidget />, { wrapper: MemoryRouter })
}

describe('FavorisWidget (NTUX12)', () => {
  it('NTUX35 — sans aucun favori, l\'en-tête reste rendu (import atteignable) mais la liste est absente', async () => {
    listFavorisMock.mockResolvedValue({ data: [] })
    renderWidget()
    expect(await screen.findByTestId('favoris-widget')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Importer des favoris' })).toBeInTheDocument()
    expect(screen.queryByRole('list')).toBeNull()
  })

  it('liste les favoris avec leur libellé résolu serveur', async () => {
    listFavorisMock.mockResolvedValue({
      data: [
        { id: 1, modele: 'installations.installation', object_id: 7, libelle: 'Chantier Nouaceur', ordre: 0 },
        { id: 2, modele: 'crm.lead', object_id: 3, libelle: 'Ali Ben', ordre: 1 },
      ],
    })
    renderWidget()
    expect(await screen.findByTestId('favoris-widget')).toBeInTheDocument()
    expect(screen.getByText('Chantier Nouaceur')).toBeInTheDocument()
    expect(screen.getByText('Ali Ben')).toBeInTheDocument()
  })

  it('cliquer un favori navigue via ROUTE[type](object_id) — accès direct', async () => {
    listFavorisMock.mockResolvedValue({
      data: [{ id: 1, modele: 'crm.lead', object_id: 3, libelle: 'Ali Ben', ordre: 0 }],
    })
    renderWidget()
    fireEvent.click(await screen.findByText('Ali Ben'))
    expect(navigateMock).toHaveBeenCalledWith('/crm/leads?lead=3')
  })

  it('modèle non câblé à ROUTE : reste affiché, jamais masqué ni cassé', async () => {
    listFavorisMock.mockResolvedValue({
      data: [{ id: 1, modele: 'sav.contrat_inconnu', object_id: 9, libelle: 'Contrat X', ordre: 0 }],
    })
    renderWidget()
    expect(await screen.findByText('Contrat X')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Contrat X'))
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('favori dont la cible a disparu (libelle=null) : libellé de repli, jamais vide', async () => {
    listFavorisMock.mockResolvedValue({
      data: [{ id: 1, modele: 'crm.lead', object_id: 3, libelle: null, ordre: 0 }],
    })
    renderWidget()
    expect(await screen.findByText('Lead')).toBeInTheDocument()
  })

  it('échec de chargement : l\'en-tête reste rendu (jamais un crash), la liste reste vide', async () => {
    listFavorisMock.mockRejectedValue(new Error('boom'))
    renderWidget()
    await waitFor(() => expect(listFavorisMock).toHaveBeenCalled())
    expect(await screen.findByTestId('favoris-widget')).toBeInTheDocument()
    expect(screen.queryByRole('list')).toBeNull()
  })

  // ── NTUX21 — glisser-déposer (poignée) ──────────────────────────────────
  it('un seul favori : aucune poignée de déplacement (rien à réordonner)', async () => {
    listFavorisMock.mockResolvedValue({
      data: [{ id: 1, modele: 'crm.lead', object_id: 3, libelle: 'Ali Ben', ordre: 0 }],
    })
    renderWidget()
    await screen.findByText('Ali Ben')
    expect(screen.queryByRole('button', { name: /^déplacer /i })).toBeNull()
  })

  it('plusieurs favoris : une poignée de déplacement accessible par favori', async () => {
    listFavorisMock.mockResolvedValue({
      data: [
        { id: 1, modele: 'crm.lead', object_id: 3, libelle: 'Ali Ben', ordre: 0 },
        { id: 2, modele: 'crm.lead', object_id: 4, libelle: 'Sara K', ordre: 1 },
      ],
    })
    renderWidget()
    await screen.findByText('Ali Ben')
    expect(screen.getByRole('button', { name: 'Déplacer Ali Ben' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Déplacer Sara K' })).toBeInTheDocument()
  })

  // ── NTUX35 — export/import CSV à la reprise de poste ────────────────────
  it('« Exporter mes favoris » désactivé sans aucun favori (rien à exporter)', async () => {
    listFavorisMock.mockResolvedValue({ data: [] })
    renderWidget()
    await screen.findByTestId('favoris-widget')
    expect(screen.getByRole('button', { name: 'Exporter mes favoris' })).toBeDisabled()
  })

  it('« Exporter mes favoris » télécharge un CSV', async () => {
    listFavorisMock.mockResolvedValue({
      data: [{ id: 1, modele: 'crm.lead', object_id: 3, libelle: 'Ali Ben', ordre: 0 }],
    })
    exportFavorisCsvMock.mockResolvedValue({ data: new Blob(['x']) })
    renderWidget()
    await screen.findByText('Ali Ben')
    fireEvent.click(screen.getByRole('button', { name: 'Exporter mes favoris' }))
    await waitFor(() => expect(exportFavorisCsvMock).toHaveBeenCalled())
    await waitFor(() => expect(downloadBlobMock).toHaveBeenCalledWith(expect.any(Blob), 'favoris.csv'))
  })

  it('« Importer des favoris » : succès rafraîchit la liste et affiche le compte importé', async () => {
    listFavorisMock.mockResolvedValue({ data: [] })
    importFavorisMock.mockResolvedValue({ data: { importes: 2, non_resolues: 0 } })
    renderWidget()
    await screen.findByTestId('favoris-widget')
    const input = document.querySelector('input[type="file"]')
    const file = new File(['x'], 'favoris.csv', { type: 'text/csv' })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(importFavorisMock).toHaveBeenCalledWith(file))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('2 favori(s) importé(s).'))
    await waitFor(() => expect(listFavorisMock).toHaveBeenCalledTimes(2)) // montage + refresh post-import
  })

  it('« Importer des favoris » : lignes non résolues rapportées, jamais silencieuses pour l\'utilisateur', async () => {
    listFavorisMock.mockResolvedValue({ data: [] })
    importFavorisMock.mockResolvedValue({ data: { importes: 1, non_resolues: 1 } })
    renderWidget()
    await screen.findByTestId('favoris-widget')
    const input = document.querySelector('input[type="file"]')
    const file = new File(['x'], 'favoris.csv', { type: 'text/csv' })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('1 ligne(s) non résolue(s), ignorée(s).'))
  })
})
