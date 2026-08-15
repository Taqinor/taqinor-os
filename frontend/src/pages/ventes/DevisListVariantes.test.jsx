import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, within, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

/* WIR225 — le panneau de comparaison des variantes est alimenté par le
   SERVEUR (`getVariantes`), plus par une chaîne reconstruite depuis les seuls
   devis chargés en mémoire. Le deep-link `?variantes=<id>` l'ouvre au montage :
   quatre colonnes (référence / libellé / HT / TTC), le devis source repéré, et
   un état vide propre quand le devis n'appartient à aucun groupe. */

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }) }
})
vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listSavedViews: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    createSavedView: vi.fn(() => Promise.resolve({ data: {} })),
    updateSavedView: vi.fn(() => Promise.resolve({ data: {} })),
    deleteSavedView: vi.fn(() => Promise.resolve({})),
  },
}))
vi.mock('../../api/crmApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: { ...actual.default, getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })) },
  }
})

const getVariantesMock = vi.fn()
vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getVariantes: (...a) => getVariantesMock(...a),
      getVarianteConfig: vi.fn(() => Promise.resolve({ data: { variante_pct: '20.00' } })),
    },
  }
})

import DevisList from './DevisList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const devisBase = {
  id: 1, reference: 'DEV-2026-07-0001', client_nom: 'ACME',
  date_creation: '2026-07-01', total_ht: 10000, total_ttc: 12000,
  statut: 'brouillon', version: 1,
}

function renderList(devis) {
  const store = configureStore({
    reducer: {
      ventes: (s = { devis, loading: false, error: null }) => s,
      auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => s,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/devis?variantes=1']}>
        <ThemeProvider>
          <DevisList />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('WIR225 — comparaison des variantes servie par getVariantes', () => {
  it('le deep-link ?variantes= rend une colonne par variante, source repérée', async () => {
    getVariantesMock.mockResolvedValue({
      data: [
        {
          id: 1, reference: 'DEV-2026-07-0001', client_nom: 'ACME', version: 1,
          note: 'Standard', total_ht: '10000.00', total_ttc: '12000.00',
        },
        {
          id: 2, reference: 'DEV-2026-07-0002', client_nom: 'ACME', version: 2,
          note: 'Réduite', total_ht: '8000.00', total_ttc: '9600.00',
        },
        {
          id: 3, reference: 'DEV-2026-07-0003', client_nom: 'ACME', version: 3,
          note: 'Augmentée', total_ht: '12000.00', total_ttc: '14400.00',
        },
      ],
    })
    renderList([devisBase])

    const tableau = await screen.findByRole('table', { name: /Comparaison des variantes/ })
    // L'appel est fait avec l'id du deep-link, une seule fois (cache par id).
    expect(getVariantesMock).toHaveBeenCalledWith(1)

    // Les 3 variantes sont rendues avec des totaux DISTINCTS.
    for (const ref of ['DEV-2026-07-0001', 'DEV-2026-07-0002', 'DEV-2026-07-0003']) {
      expect(within(tableau).getByText(ref)).toBeInTheDocument()
    }
    expect(within(tableau).getByText('Réduite')).toBeInTheDocument()
    expect(within(tableau).getByText('Augmentée')).toBeInTheDocument()

    // La racine du groupe (premier élément renvoyé) porte la mention « source ».
    const ligneSource = within(tableau).getByText('DEV-2026-07-0001').closest('tr')
    expect(within(ligneSource).getByText('(source)')).toBeInTheDocument()
    const ligneAutre = within(tableau).getByText('DEV-2026-07-0002').closest('tr')
    expect(within(ligneAutre).queryByText('(source)')).toBeNull()

    // Les 4 colonnes attendues.
    for (const col of ['Référence', 'Libellé', 'Total HT', 'Total TTC']) {
      expect(within(tableau).getByText(col)).toBeInTheDocument()
    }
  })

  it('devis isolé : état vide propre, jamais de tableau ni de JSON brut', async () => {
    getVariantesMock.mockResolvedValue({ data: [] })
    renderList([devisBase])

    expect(await screen.findByText(/aucune variante à comparer/i)).toBeInTheDocument()
    expect(screen.queryByRole('table', { name: /Comparaison des variantes/ })).toBeNull()
  })

  it('403 (rôle non responsable) : dégradation silencieuse en état vide', async () => {
    getVariantesMock.mockRejectedValue({ response: { status: 403, data: { detail: 'nope' } } })
    renderList([devisBase])

    expect(await screen.findByText(/aucune variante à comparer/i)).toBeInTheDocument()
    expect(screen.queryByText(/nope/)).toBeNull()
  })
})
