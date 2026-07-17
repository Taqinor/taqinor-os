// NTUX23 — Rapport imprimable « configuration des vues actives ».
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

const listAllSavedViews = vi.fn()
const exportSavedViewsXlsx = vi.fn()
vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listAllSavedViews: (...a) => listAllSavedViews(...a),
    exportSavedViewsXlsx: (...a) => exportSavedViewsXlsx(...a),
  },
}))

const downloadBlobMock = vi.fn()
vi.mock('../../utils/downloadBlob', () => ({
  downloadBlob: (...a) => downloadBlobMock(...a),
  stampedFilename: (base, ext) => `${base}.${ext}`,
}))

vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import VuesConfigurationPage from './VuesConfigurationPage'

const VIEWS = [
  {
    id: 1, ecran: 'crm.leads', nom: 'Mes leads chauds', owner_nom: 'Amine',
    visibilite: 'PERSONNELLE', est_defaut_role: false, role_nom: null,
    updated_at: '2026-07-01T10:00:00Z',
  },
  {
    id: 2, ecran: 'ventes.devis', nom: 'Devis en retard', owner_nom: 'Reda',
    visibilite: 'EQUIPE', est_defaut_role: true, role_nom: 'Commercial',
    updated_at: '2026-07-05T10:00:00Z',
  },
]

beforeEach(() => {
  listAllSavedViews.mockReset()
  exportSavedViewsXlsx.mockReset()
  downloadBlobMock.mockReset()
})

describe('VuesConfigurationPage (NTUX23 — rapport de gouvernance des vues)', () => {
  it('liste TOUTES les vues de la company (colonnes écran/nom/propriétaire/visibilité/rôle par défaut)', async () => {
    listAllSavedViews.mockResolvedValue({ data: VIEWS })
    renderPage(<VuesConfigurationPage />)
    // DataTable duplique desktop (table) + repli carte mobile (VX43) — findAllBy*.
    expect((await screen.findAllByText('Mes leads chauds')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Devis en retard').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Amine').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Commercial').length).toBeGreaterThan(0)
  })

  it('affiche un état vide clair quand la company n\'a aucune vue', async () => {
    listAllSavedViews.mockResolvedValue({ data: [] })
    renderPage(<VuesConfigurationPage />)
    expect(await screen.findByText('Aucune vue enregistrée')).toBeInTheDocument()
  })

  it('un échec de chargement retombe sur une liste vide (jamais un plantage)', async () => {
    listAllSavedViews.mockRejectedValue(new Error('403'))
    renderPage(<VuesConfigurationPage />)
    expect(await screen.findByText('Aucune vue enregistrée')).toBeInTheDocument()
  })

  it('« Exporter (XLSX) » appelle exportSavedViewsXlsx puis déclenche le téléchargement', async () => {
    const user = userEvent.setup()
    listAllSavedViews.mockResolvedValue({ data: VIEWS })
    const blob = new Blob(['x'])
    exportSavedViewsXlsx.mockResolvedValue({ data: blob })
    renderPage(<VuesConfigurationPage />)
    await screen.findAllByText('Mes leads chauds')
    // Distinct du bouton "Exporter" intégré au DataTable (export CSV client) :
    // le rapport de gouvernance a son propre bouton XLSX serveur.
    await user.click(screen.getByRole('button', { name: /exporter \(xlsx\)/i }))
    await waitFor(() => expect(exportSavedViewsXlsx).toHaveBeenCalled())
    await waitFor(() => expect(downloadBlobMock).toHaveBeenCalledWith(blob, 'vues-sauvegardees.xlsx'))
  })
})
