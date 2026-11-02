import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

vi.mock('../../api/stockApi', () => ({
  default: {
    getBonCommandeFournisseur: vi.fn(),
    createReceptionFournisseur: vi.fn(),
    confirmerReceptionFournisseur: vi.fn(),
  },
}))
// `ReceptionDetail` lit le profil entreprise (useStockFlags) : lots/séries actifs.
vi.mock('../../api/parametresApi', async (importOriginal) =>
  (await import('../../test/mocksVentesEcrans.js')).parametresApiProfil(await importOriginal(), {}))
vi.mock('../../ui', async (importOriginal) => ({
  ...(await importOriginal()),
  Combobox: ({ onChange }) => <button type="button" onClick={() => onChange('5')}>choisir-bon</button>,
}))

import stockApi from '../../api/stockApi'
import { NouvelleReception, ReceptionDetail } from './ReceptionsFournisseur.jsx'
import { parseSeries } from './numerosSerie.js'

beforeEach(() => {
  vi.clearAllMocks()
  stockApi.getBonCommandeFournisseur.mockResolvedValue({
    data: { id: 5, lignes: [{ id: 11, produit_nom: 'Onduleur', quantite: 3, quantite_recue: 0 }] },
  })
  stockApi.createReceptionFournisseur.mockResolvedValue({ data: { id: 1 } })
})

async function ouvrir() {
  render(<ThemeProvider>
    <NouvelleReception bonsRecevables={[{ id: 5, reference: 'BCF-5' }]} onClose={() => {}} onSaved={() => {}} />
  </ThemeProvider>)
  fireEvent.click(screen.getByText('choisir-bon'))
  fireEvent.click(await screen.findByRole('button', { name: /N° de série \/ lot/ }))
}

describe('Réception — n° de série', () => {
  it('parseSeries découpe, rogne et dédoublonne', () => {
    expect(parseSeries(' A1,B2;\nA1\n\n C3 ')).toEqual(['A1', 'B2', 'C3'])
  })

  it('envoie numeros_serie et numero_lot dans la ligne', async () => {
    await ouvrir()
    fireEvent.change(screen.getByLabelText(/N° de série \(un par ligne, 3 attendus\)/), { target: { value: 'S1\nS2' } })
    fireEvent.change(screen.getByLabelText(/N° de lot/), { target: { value: 'LOT-9' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer en brouillon/ }))
    await waitFor(() => expect(stockApi.createReceptionFournisseur).toHaveBeenCalled())
    expect(stockApi.createReceptionFournisseur.mock.calls[0][0].lignes).toEqual([
      { ligne_commande: 11, quantite: 3, numeros_serie: ['S1', 'S2'], numero_lot: 'LOT-9' },
    ])
  })

  it('refuse plus de séries que de quantités avec une erreur sous le champ', async () => {
    await ouvrir()
    fireEvent.change(screen.getByLabelText(/N° de série \(un par ligne/), { target: { value: 'a,b,c,d' } })
    expect((await screen.findAllByRole('alert'))[0].textContent).toMatch(/4 n° de série saisis pour 3/)
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer en brouillon/ }))
    expect(stockApi.createReceptionFournisseur).not.toHaveBeenCalled()
  })
})

describe('Réception — détail enregistré (ACHT129)', () => {
  it('le détail d\'une réception affiche séries et lot', () => {
    const reception = {
      id: 9, reference: 'REC-9', statut: 'confirme',
      lignes: [
        { id: 1, produit_nom: 'Onduleur', quantite: 3, numeros_serie: ['S1', 'S2', 'S3'], numero_lot: '' },
        { id: 2, produit_nom: 'Câble', quantite: 100, numeros_serie: [], numero_lot: 'L-42' },
        { id: 3, produit_nom: 'Vis', quantite: 10, numeros_serie: [], numero_lot: '' },
      ],
    }
    render(<ThemeProvider>
      <ReceptionDetail reception={reception} onClose={() => {}} onSaved={() => {}} />
    </ThemeProvider>)
    expect(screen.getByRole('columnheader', { name: 'Séries / Lot' })).toBeTruthy()
    const ligne = (nom) => screen.getByText(nom).closest('tr')
    expect(within(ligne('Onduleur')).getByText('S1, S2, S3')).toBeTruthy()
    expect(within(ligne('Câble')).getByText('Lot L-42')).toBeTruthy()
    expect(within(ligne('Vis')).getByText('—')).toBeTruthy()
  })
})
