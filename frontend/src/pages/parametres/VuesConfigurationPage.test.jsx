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
const importSavedViews = vi.fn()
vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listAllSavedViews: (...a) => listAllSavedViews(...a),
    exportSavedViewsXlsx: (...a) => exportSavedViewsXlsx(...a),
    importSavedViews: (...a) => importSavedViews(...a),
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
  importSavedViews.mockReset()
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

  it("NTUX34 — « Importer des vues » envoie le fichier choisi et recharge la liste si des vues sont créées", async () => {
    const user = userEvent.setup()
    listAllSavedViews.mockResolvedValue({ data: VIEWS })
    importSavedViews.mockResolvedValue({ data: { created: [{ id: 3 }], erreurs: [] } })
    renderPage(<VuesConfigurationPage />)
    await screen.findAllByText('Mes leads chauds')

    const file = new File(['ecran,nom,configuration\ncrm.leads,Vue,{}'], 'vues.csv', { type: 'text/csv' })
    const input = document.querySelector('input[type="file"]')
    await user.upload(input, file)

    await waitFor(() => expect(importSavedViews).toHaveBeenCalledWith(file))
    // La liste est rechargée après un import réussi (2 appels : montage + après import).
    await waitFor(() => expect(listAllSavedViews).toHaveBeenCalledTimes(2))
  })

  it('NTUX34 — les lignes rejetées sont affichées avec leur numéro et leur message', async () => {
    const user = userEvent.setup()
    listAllSavedViews.mockResolvedValue({ data: VIEWS })
    importSavedViews.mockResolvedValue({
      data: { created: [], erreurs: [{ ligne: 2, message: 'JSON de configuration invalide.' }] },
    })
    renderPage(<VuesConfigurationPage />)
    await screen.findAllByText('Mes leads chauds')

    const file = new File(['ecran,nom,configuration\ncrm.leads,Vue,pas-du-json'], 'vues.csv', { type: 'text/csv' })
    const input = document.querySelector('input[type="file"]')
    await user.upload(input, file)

    expect(await screen.findByTestId('vc-import-erreurs')).toBeInTheDocument()
    expect(screen.getByText(/Ligne 2 — JSON de configuration invalide\./)).toBeInTheDocument()
    // Aucune vue créée : pas de rechargement supplémentaire (juste le montage).
    await waitFor(() => expect(listAllSavedViews).toHaveBeenCalledTimes(1))
  })
})
