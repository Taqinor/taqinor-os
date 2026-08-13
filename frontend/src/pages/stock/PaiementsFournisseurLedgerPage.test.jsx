import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* PACT51 — Registre consolidé des paiements fournisseur + relevé RAS-TVA.
   Les trois trous réels que la ressource autonome exposait sans appelant :
   l'export Simpl-TVA, la vue trésorerie tous fournisseurs confondus, et le
   pourcentage d'escompte que le chemin d'écran actuel perdait. */

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: { get, post } }))

const { downloadBlob, filenameFromResponse } = vi.hoisted(() => ({
  downloadBlob: vi.fn(),
  filenameFromResponse: vi.fn(() => 'releve-ras-tva.xlsx'),
}))
vi.mock('../../api/importApi', () => ({ downloadBlob, filenameFromResponse }))

import PaiementsFournisseurLedgerPage from './PaiementsFournisseurLedgerPage'

const PAIEMENTS = [
  {
    id: 1, facture: 9, facture_reference: 'FF-2026-08-0001', montant: '12000.00',
    date_paiement: '2026-08-03', mode: 'virement', mode_display: 'Virement',
    montant_ras_tva: '1500.00', taux_ras: '75.00', montant_net_paye: '10500.00',
  },
  {
    id: 2, facture: 10, facture_reference: 'FF-2026-07-0004', montant: '4000.00',
    date_paiement: '2026-07-20', mode: 'cheque', mode_display: 'Chèque',
    montant_ras_tva: '0.00', taux_ras: '0.00', montant_net_paye: '4000.00',
  },
]
const FACTURES = [
  { id: 9, reference: 'FF-2026-08-0001', fournisseur_nom: 'SunRak', solde_du: '3000.00' },
]

function mockGets(paiements = PAIEMENTS) {
  get.mockImplementation((url) => {
    if (url === '/stock/paiements-fournisseur/') return Promise.resolve({ data: paiements })
    if (url === '/stock/factures-fournisseur/') return Promise.resolve({ data: FACTURES })
    if (url === '/stock/paiements-fournisseur/ras-tva/export/') {
      return Promise.resolve({ data: new Blob(['x']), headers: {} })
    }
    return Promise.reject(new Error(`URL inattendue : ${url}`))
  })
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

function afficher(role = 'admin') {
  const store = configureStore({ reducer: { auth: (state = { role }) => state } })
  return render(
    <Provider store={store}><PaiementsFournisseurLedgerPage /></Provider>,
  )
}

describe('PaiementsFournisseurLedgerPage (PACT51)', () => {
  it('consolide les paiements de TOUS les fournisseurs avec RAS-TVA et net décaissé', async () => {
    mockGets()
    afficher()

    const table = await screen.findByTestId('table-paiements')
    // Deux factures différentes dans un seul registre — la vue trésorerie qui
    // manquait (jusqu'ici visible facture par facture uniquement).
    expect(within(table).getByText('FF-2026-08-0001')).toBeInTheDocument()
    expect(within(table).getByText('FF-2026-07-0004')).toBeInTheDocument()

    const ligne = screen.getByTestId('paiement-1')
    expect(within(ligne).getByText(/1 500,00 MAD \(75.00 %\)/)).toBeInTheDocument()
    expect(within(ligne).getByText('10 500,00 MAD')).toBeInTheDocument()

    const totaux = screen.getByTestId('ledger-totaux')
    expect(totaux).toHaveTextContent('16 000,00 MAD')  // brut
    expect(totaux).toHaveTextContent('1 500,00 MAD')   // RAS-TVA
    expect(totaux).toHaveTextContent('14 500,00 MAD')  // net
  })

  it('exporte le relevé RAS-TVA sur la période choisie (Simpl-TVA)', async () => {
    const user = userEvent.setup()
    mockGets()
    afficher()
    await screen.findByTestId('table-paiements')

    fireEvent.change(screen.getByLabelText('Du'), { target: { value: '2026-08-01' } })
    fireEvent.change(screen.getByLabelText('Au'), { target: { value: '2026-08-31' } })
    await user.click(screen.getByRole('button', { name: /Exporter le relevé RAS-TVA/ }))

    await waitFor(() => expect(get).toHaveBeenCalledWith(
      '/stock/paiements-fournisseur/ras-tva/export/',
      { params: { date_debut: '2026-08-01', date_fin: '2026-08-31' }, responseType: 'blob' },
    ))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalled())
  })

  it("affiche le pourcentage d'escompte renvoyé à la saisie du règlement", async () => {
    const user = userEvent.setup()
    mockGets()
    post.mockResolvedValue({ data: { id: 7, escompte_disponible_pct: '2.50' } })
    afficher()
    await screen.findByTestId('table-paiements')

    await user.click(screen.getByRole('combobox', { name: 'Facture fournisseur' }))
    await user.click(await screen.findByRole('option', { name: /FF-2026-08-0001/ }))
    await user.type(screen.getByLabelText('Montant du règlement'), '3000')
    await user.click(screen.getByRole('button', { name: /Enregistrer le règlement/ }))

    // La saisie passe par la ressource AUTONOME : c'est la seule qui renvoie
    // le flag d'escompte (le chemin imbriqué renvoie la facture et le perd).
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/stock/paiements-fournisseur/',
      { facture: 9, montant: 3000, date_paiement: null, mode: 'virement' },
    ))
    const banniere = await screen.findByTestId('escompte-banner')
    expect(banniere).toHaveTextContent('2.50 %')
    // `company` n'est jamais envoyée : imposée côté serveur.
    expect(Object.keys(post.mock.calls[0][1])).not.toContain('company')
  })

  it('filtre le registre sur la période affichée', async () => {
    mockGets()
    afficher()
    await screen.findByTestId('paiement-2')

    fireEvent.change(screen.getByLabelText('Du'), { target: { value: '2026-08-01' } })

    await waitFor(() => expect(screen.queryByTestId('paiement-2')).toBeNull())
    expect(screen.getByTestId('paiement-1')).toBeInTheDocument()
  })

  it("un rôle simple lit le registre sans pouvoir saisir de règlement", async () => {
    mockGets()
    afficher('normal')

    await screen.findByTestId('table-paiements')
    expect(screen.queryByRole('button', { name: /Enregistrer le règlement/ })).toBeNull()
  })

  it('affiche une erreur de chargement sans planter', async () => {
    get.mockImplementation((url) => {
      if (url === '/stock/paiements-fournisseur/') return Promise.reject(new Error('boom'))
      return Promise.resolve({ data: [] })
    })
    afficher()
    expect(await screen.findByText('Impossible de charger les paiements'))
      .toBeInTheDocument()
  })
})
