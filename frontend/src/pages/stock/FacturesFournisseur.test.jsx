import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   WIR192 — rapprochement 3 voies (XPUR10) : une facture en exception était
   invisible et inrésolvable depuis l'écran. Badge `statut_controle` + file
   « En exception », action « Résoudre l'exception » (Responsable/Admin).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getFacturesFournisseur: vi.fn(() => Promise.resolve({
      data: [
        { id: 1, reference: 'FF-1', fournisseur_nom: 'JA Solar', statut: 'a_payer', statut_controle: 'normale', montant_ttc: '1000', solde_du: '1000' },
        {
          id: 2, reference: 'FF-2', fournisseur_nom: 'Sunrak', statut: 'a_payer',
          statut_controle: 'exception', motif_ecart: 'Écart de 500 MAD vs BCF-2',
          montant_ttc: '2000', solde_du: '2000',
        },
      ],
    })),
    getFacturesEnException: vi.fn(() => Promise.resolve({
      data: [{
        id: 2, reference: 'FF-2', fournisseur_nom: 'Sunrak', statut: 'a_payer',
        statut_controle: 'exception', motif_ecart: 'Écart de 500 MAD vs BCF-2',
        montant_ttc: '2000', solde_du: '2000',
      }],
    })),
    resoudreExceptionFacture: vi.fn(() => Promise.resolve({
      data: {
        id: 2, reference: 'FF-2', statut: 'a_payer', statut_controle: 'resolue',
        montant_ttc: '2000', total_paye: '0', solde_du: '2000', paiements: [],
      },
    })),
    getFactureFournisseur: vi.fn((id) => Promise.resolve({
      data: {
        id, reference: `FF-${id}`, statut: 'a_payer', statut_controle: 'exception',
        motif_ecart: 'Écart de 500 MAD vs BCF-2',
        montant_ttc: '2000', total_paye: '0', solde_du: '2000', paiements: [],
      },
    })),
    getFournisseurs: vi.fn(() => Promise.resolve({ data: [] })),
    getBonsCommandeFournisseur: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

import stockApi from '../../api/stockApi'
import FacturesFournisseur, { FactureDetail } from './FacturesFournisseur.jsx'

function makeStore({ role = 'admin' } = {}) {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: { user: { id: 1 }, role, role_nom: role, permissions: [], isAuthenticated: true, loading: false },
    },
  })
}

function renderPage(store = makeStore()) {
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><FacturesFournisseur /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('FacturesFournisseur — badge et file « En exception » (WIR192)', () => {
  it('affiche le badge « En exception » sur la ligne concernée, infobulle = motif_ecart', async () => {
    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Factures fournisseur' })
    const badge = within(grid).getByText('En exception')
    expect(badge.closest('[title]')).toHaveAttribute('title', 'Écart de 500 MAD vs BCF-2')
  })

  it('le bouton « En exception » charge la file dédiée', async () => {
    renderPage()
    await screen.findByRole('grid', { name: 'Factures fournisseur' })

    // Le repli « cartes mobiles » du DataTable rend chaque ligne cliquable en
    // `role="button"` : la carte FF-2 porte le badge « En exception » dans son
    // nom accessible. On vise donc le bouton de filtre par son nom EXACT.
    await userEvent.click(screen.getByRole('button', { name: 'En exception' }))
    await waitFor(() => expect(stockApi.getFacturesEnException).toHaveBeenCalled())
    const grid = await screen.findByRole('grid', { name: 'Factures fournisseur' })
    expect(within(grid).getByText('FF-2')).toBeInTheDocument()
    expect(within(grid).queryByText('FF-1')).toBeNull()
  })
})

describe('FactureDetail — résoudre une exception (WIR192)', () => {
  const factureException = {
    id: 2, reference: 'FF-2', statut: 'a_payer', statut_controle: 'exception',
    motif_ecart: 'Écart de 500 MAD vs BCF-2',
    fournisseur_nom: 'Sunrak', montant_ttc: '2000', total_paye: '0', solde_du: '2000',
    paiements: [],
  }

  it('affiche le motif de l\'écart et le bouton « Résoudre l\'exception » (Responsable/Admin)', () => {
    // `canResoudre` est un PROP simple (jamais un hook Redux) : ce composant
    // se monte sans Provider, comme dans wr4ReceptionFacture.test.jsx.
    render(<ThemeProvider>
      <FactureDetail facture={factureException} canResoudre onClose={() => {}} onSaved={() => {}} />
    </ThemeProvider>)
    expect(screen.getByText('Écart de 500 MAD vs BCF-2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Résoudre l'exception/ })).toBeInTheDocument()
  })

  it('sans le droit (canResoudre=false), aucun bouton de résolution n\'apparaît', () => {
    render(<ThemeProvider>
      <FactureDetail facture={factureException} canResoudre={false} onClose={() => {}} onSaved={() => {}} />
    </ThemeProvider>)
    expect(screen.queryByRole('button', { name: /Résoudre l'exception/ })).toBeNull()
  })

  it('confirmer la résolution appelle resoudreExceptionFacture et sort la facture de la file', async () => {
    const onSaved = vi.fn()
    render(<ThemeProvider>
      <FactureDetail facture={factureException} canResoudre onClose={() => {}} onSaved={onSaved} />
    </ThemeProvider>)

    await userEvent.click(screen.getByRole('button', { name: /Résoudre l'exception/ }))
    await userEvent.type(screen.getByPlaceholderText('Commentaire de résolution (optionnel)'), 'Vérifié avec le fournisseur')
    await userEvent.click(screen.getByRole('button', { name: 'Confirmer la résolution' }))

    await waitFor(() => expect(stockApi.resoudreExceptionFacture).toHaveBeenCalledWith(
      2, { commentaire: 'Vérifié avec le fournisseur' },
    ))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    // La facture résolue ne montre plus le bandeau/bouton d'exception.
    expect(screen.queryByRole('button', { name: /Résoudre l'exception/ })).toBeNull()
  })
})
