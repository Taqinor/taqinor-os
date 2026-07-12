import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

// WR2b — la liste des factures ne doit toucher aucun réseau pendant le test :
// on neutralise le thunk de chargement (le composant le dispatche au montage).
vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchFactures: () => ({ type: 'ventes/fetchFactures/noop' }),
  }
})

// WR2b — espionne lienPaiementFacture / dgiExportFacture / dgiConformiteFacture
// / bulkFactures (le pouvoir de la liste factures complétant WR2).
vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      lienPaiementFacture: vi.fn(() => Promise.resolve({
        data: { pay_url: 'https://pay.example/tok123', montant: '5000.00', token: 'tok123' },
      })),
      dgiExportFacture: vi.fn(() => Promise.resolve({
        data: new Blob(['<xml/>'], { type: 'application/xml' }),
      })),
      dgiConformiteFacture: vi.fn(() => Promise.resolve({ data: { conforme: true, problemes: [] } })),
      bulkFactures: vi.fn(() => Promise.resolve({
        data: { 1: { ok: true, detail: 'Émise.' } },
      })),
    },
  }
})

vi.mock('../../api/parametresApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getProfile: vi.fn(() => Promise.resolve({ data: { dgi_export_actif: false } })),
    },
  }
})

import FactureList from './FactureList'
import ventesApi from '../../api/ventesApi'
import parametresApi from '../../api/parametresApi'
// ARC53 — FactureList rend son tableau via le moteur `ui/datatable` (useDensity),
// qui EXIGE un <ThemeProvider> dans l'arbre (présent en prod via <Layout>). Ajout
// de wrapper de HARNAIS uniquement — aucune assertion n'est modifiée.
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

function makeStore({ factures = [], loading = false, error = null, role = 'admin' } = {}) {
  return configureStore({
    reducer: {
      ventes: (state = { factures, loading, error }) => state,
      auth: (state = { role }) => state,
    },
  })
}

function renderList(opts) {
  const store = makeStore(opts)
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/factures']}>
        <ThemeProvider>
          <FactureList />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

const baseFacture = {
  id: 1, reference: 'FAC-2026-07-0001', client_nom: 'ACME', statut: 'emise',
  date_emission: '2026-07-01', date_echeance: '2026-08-01',
  total_ttc: 5000, montant_paye: 0, montant_du: 5000,
}

describe('FactureList — WR2b : « Payer en ligne »', () => {
  it('crée le lien de paiement et le copie au presse-papier', async () => {
    const writeText = vi.fn(() => Promise.resolve())
    Object.assign(navigator, { clipboard: { writeText } })
    renderList({ factures: [{ ...baseFacture }] })
    const row = screen.getByText('FAC-2026-07-0001').closest('tr')
    fireEvent.click(within(row).getByRole('button', { name: /Payer en ligne/ }))
    await waitFor(() => {
      expect(ventesApi.lienPaiementFacture).toHaveBeenCalledWith(1)
    })
    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith('https://pay.example/tok123')
    })
  })

  it('n\'affiche pas le bouton quand la facture est déjà soldée', () => {
    renderList({
      factures: [{ ...baseFacture, id: 2, reference: 'FAC-SOLDEE', montant_du: 0 }],
    })
    const row = screen.getByText('FAC-SOLDEE').closest('tr')
    expect(within(row).queryByRole('button', { name: /Payer en ligne/ })).toBeNull()
  })
})

describe('FactureList — WR2b : Export DGI + badge conformité (gated par dgi_export_actif)', () => {
  it('masque le bouton Export DGI et le badge conformité quand le flag société est OFF', async () => {
    const user = userEvent.setup()
    renderList({ factures: [{ ...baseFacture }] })
    await waitFor(() => expect(parametresApi.getProfile).toHaveBeenCalled())
    const row = screen.getByText('FAC-2026-07-0001').closest('tr')
    expect(within(row).queryByText(/Conformité DGI/)).toBeNull()
    await user.click(within(row).getByRole('button', { name: 'Actions' }))
    expect(screen.queryByText(/Export DGI/)).toBeNull()
  })

  it('affiche le badge conformité et l\'action Export DGI quand le flag société est ON', async () => {
    const user = userEvent.setup()
    parametresApi.getProfile.mockResolvedValueOnce({ data: { dgi_export_actif: true } })
    renderList({ factures: [{ ...baseFacture }] })
    const row = await screen.findByText('FAC-2026-07-0001').then(el => el.closest('tr'))
    await waitFor(() => {
      expect(within(row).getByText(/Conformité DGI/)).toBeVisible()
    })
    await user.click(within(row).getByRole('button', { name: 'Actions' }))
    const exportItem = await screen.findByRole('menuitem', { name: /Export DGI/ })
    await user.click(exportItem)
    await waitFor(() => {
      expect(ventesApi.dgiExportFacture).toHaveBeenCalledWith(1)
    })
  })

  it('le clic sur le badge conformité appelle le contrôle DGI (aucun statut modifié)', async () => {
    parametresApi.getProfile.mockResolvedValueOnce({ data: { dgi_export_actif: true } })
    renderList({ factures: [{ ...baseFacture }] })
    const row = await screen.findByText('FAC-2026-07-0001').then(el => el.closest('tr'))
    const badge = await waitFor(() => within(row).getByText(/Conformité DGI/))
    fireEvent.click(badge)
    await waitFor(() => {
      expect(ventesApi.dgiConformiteFacture).toHaveBeenCalledWith(1)
    })
  })
})

describe('FactureList — WR2b : barre d\'actions en masse (bulkFactures)', () => {
  beforeEach(() => { ventesApi.bulkFactures.mockClear() })

  it('sélectionne une facture puis lance « Émettre » en masse via bulkFactures', async () => {
    renderList({
      factures: [
        { ...baseFacture, id: 1, reference: 'FAC-BULK-1', statut: 'brouillon' },
        { ...baseFacture, id: 2, reference: 'FAC-BULK-2', statut: 'brouillon' },
      ],
    })
    const row1 = screen.getByText('FAC-BULK-1').closest('tr')
    fireEvent.click(within(row1).getByRole('checkbox', { name: /Sélectionner la facture FAC-BULK-1/ }))

    const bulkBar = screen.getByRole('region', { name: 'Actions factures en masse' })
    expect(within(bulkBar).getByText('1')).toBeVisible()
    fireEvent.click(within(bulkBar).getByRole('button', { name: 'Émettre' }))

    await waitFor(() => {
      expect(ventesApi.bulkFactures).toHaveBeenCalledWith('emettre', [1])
    })
  })

  it('tout sélectionner coche toutes les lignes filtrées', () => {
    renderList({
      factures: [
        { ...baseFacture, id: 1, reference: 'FAC-ALL-1' },
        { ...baseFacture, id: 2, reference: 'FAC-ALL-2' },
      ],
    })
    fireEvent.click(screen.getByRole('checkbox', { name: 'Tout sélectionner' }))
    const bulkBar = screen.getByRole('region', { name: 'Actions factures en masse' })
    expect(within(bulkBar).getByText('2')).toBeVisible()
  })
})

describe('FactureList — ZFAC9 : bascule Liste/Kanban', () => {
  it('la vue Liste (tableau) est affichée par défaut', () => {
    renderList({ factures: [{ ...baseFacture }] })
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.queryByTestId('facture-kanban-board')).not.toBeInTheDocument()
  })

  it('basculer sur Kanban masque le tableau et regroupe par colonne (même onglet/dérivation)', async () => {
    const user = userEvent.setup()
    renderList({
      factures: [
        { ...baseFacture, id: 1, reference: 'FAC-K-1', statut: 'brouillon' },
        { ...baseFacture, id: 2, reference: 'FAC-K-2', statut: 'payee', montant_du: 0 },
      ],
    })
    await user.click(screen.getByRole('button', { name: /Kanban/ }))
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByTestId('facture-kanban-board')).toBeInTheDocument()
    expect(screen.getByTestId('fkb-count-brouillon')).toHaveTextContent('1')
    expect(screen.getByTestId('fkb-count-payee')).toHaveTextContent('1')
    expect(screen.getByText('FAC-K-1')).toBeInTheDocument()
    expect(screen.getByText('FAC-K-2')).toBeInTheDocument()
  })

  it('revenir sur Liste réaffiche le tableau', async () => {
    const user = userEvent.setup()
    renderList({ factures: [{ ...baseFacture }] })
    await user.click(screen.getByRole('button', { name: /Kanban/ }))
    await user.click(screen.getByRole('button', { name: /^Liste/ }))
    expect(screen.getByRole('table')).toBeInTheDocument()
  })
})

describe('FactureList — VX142(a) : toolbar « Exporter » unique, plus de window.prompt', () => {
  it('le menu « Exporter » regroupe Exporter Excel / Journal comptable / Export comptable / Audit numérotation', async () => {
    const user = userEvent.setup()
    const promptSpy = vi.spyOn(window, 'prompt')
    renderList({ factures: [{ ...baseFacture }] })
    await user.click(screen.getByRole('button', { name: /^Exporter$/ }))
    expect(screen.getByRole('menuitem', { name: /Exporter Excel/ })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: /Journal comptable/ })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: /Export comptable/ })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: /Audit numérotation/ })).toBeVisible()
    expect(promptSpy).not.toHaveBeenCalled()
  })

  it('« Journal comptable… » ouvre un Dialog mois/trimestre, jamais window.prompt', async () => {
    const user = userEvent.setup()
    const promptSpy = vi.spyOn(window, 'prompt')
    renderList({ factures: [{ ...baseFacture }] })
    await user.click(screen.getByRole('button', { name: /^Exporter$/ }))
    await user.click(screen.getByRole('menuitem', { name: /Journal comptable/ }))
    expect(screen.getByRole('heading', { name: 'Journal comptable' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Mois' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Trimestre' })).toBeVisible()
    expect(promptSpy).not.toHaveBeenCalled()
  })

  it('« Export comptable… » ouvre un Dialog à deux champs date, jamais window.prompt', async () => {
    const user = userEvent.setup()
    const promptSpy = vi.spyOn(window, 'prompt')
    renderList({ factures: [{ ...baseFacture }] })
    await user.click(screen.getByRole('button', { name: /^Exporter$/ }))
    await user.click(screen.getByRole('menuitem', { name: /Export comptable/ }))
    expect(screen.getByRole('heading', { name: 'Export comptable' })).toBeVisible()
    expect(screen.getByLabelText('Date de début')).toBeVisible()
    expect(screen.getByLabelText('Date de fin')).toBeVisible()
    expect(promptSpy).not.toHaveBeenCalled()
  })
})

describe('FactureList — VX142(b) : nextBestAction en position 1, style distinct', () => {
  it('une facture brouillon montre « Émettre » recommandé en PREMIER bouton de la rangée', () => {
    renderList({
      factures: [{ ...baseFacture, id: 2, reference: 'FAC-NBA-1', statut: 'brouillon', montant_du: 0 }],
    })
    const row = screen.getByText('FAC-NBA-1').closest('tr')
    const actionsCell = row.cells[row.cells.length - 1]
    const buttons = within(actionsCell).getAllByRole('button')
    expect(buttons[0]).toHaveAccessibleName(/Émettre/)
    expect(buttons[0]).toHaveAttribute('title', 'Action recommandée')
    // Une seule occurrence du bouton Émettre (pas de doublon plus loin dans la rangée).
    expect(within(actionsCell).getAllByRole('button', { name: /Émettre/ })).toHaveLength(1)
  })

  it('une facture émise partiellement payée montre « Encaisser » recommandé en PREMIER, sans doublon', () => {
    renderList({
      factures: [{
        ...baseFacture, id: 3, reference: 'FAC-NBA-2', statut: 'emise',
        date_echeance: '2099-01-01', montant_paye: 1000, montant_du: 4000,
      }],
    })
    const row = screen.getByText('FAC-NBA-2').closest('tr')
    const actionsCell = row.cells[row.cells.length - 1]
    const buttons = within(actionsCell).getAllByRole('button')
    expect(buttons[0]).toHaveAccessibleName(/Encaisser/)
    // « Enregistrer paiement » (position historique) ne réapparaît pas à côté.
    expect(within(actionsCell).queryByRole('button', { name: /Enregistrer paiement/ })).toBeNull()
  })
})
