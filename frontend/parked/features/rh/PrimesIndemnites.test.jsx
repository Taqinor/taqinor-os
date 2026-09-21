import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import PrimesIndemnites from './PrimesIndemnites.jsx'

/* PACT93 — Primes & indemnités. Le montant pré-rempli depuis le type reste
   MODIFIABLE, et le statut affiché vient du serveur, jamais dérivé côté
   client. */

vi.mock('../../api/rhApi', () => ({
  default: {
    getPrimesAttribuees: vi.fn(() => Promise.resolve({ data: [] })),
    getTypesPrime: vi.fn(() => Promise.resolve({
      data: [{ id: 5, code: 'PANIER', libelle: 'Panier repas', nature: 'indemnite', montant_defaut: 30, imposable: false, actif: true }],
    })),
    getEmployes: vi.fn(() => Promise.resolve({ data: [{ id: 9, nom: 'Bennani', prenom: 'Youssef' }] })),
    createPrimeAttribuee: vi.fn(),
    createTypePrime: vi.fn(),
    validerPrimeAttribuee: vi.fn(),
    updatePrimeAttribuee: vi.fn(),
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <PrimesIndemnites />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('PrimesIndemnites (PACT93)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('pré-remplit le montant depuis le type choisi, mais le laisse modifiable', async () => {
    rhApi.createPrimeAttribuee.mockResolvedValueOnce({ data: { id: 1 } })
    renderScreen()
    await screen.findAllByText('Primes & indemnités')

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouvelle attribution/ }))[0])
    fireEvent.change(screen.getByLabelText('Employé'), { target: { value: '9' } })
    fireEvent.change(screen.getByLabelText('Type de prime'), { target: { value: '5' } })
    expect(screen.getByLabelText('Montant (MAD)')).toHaveValue(30)

    fireEvent.change(screen.getByLabelText('Montant (MAD)'), { target: { value: '45' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Attribuer' })[0])

    await waitFor(() => expect(rhApi.createPrimeAttribuee).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '9', type_prime: '5', montant: '45' }),
    ))
  })

  it('crée un type de prime via rhApi.createTypePrime (onglet catalogue)', async () => {
    rhApi.createTypePrime.mockResolvedValueOnce({ data: { id: 6 } })
    renderScreen()
    await screen.findAllByText('Primes & indemnités')

    fireEvent.click(screen.getByRole('radio', { name: 'Catalogue de types' }))
    fireEvent.click((await screen.findAllByRole('button', { name: /Nouveau type/ }))[0])
    fireEvent.change(screen.getByLabelText('Code'), { target: { value: 'TRANSPORT' } })
    fireEvent.change(screen.getByLabelText('Libellé'), { target: { value: 'Indemnité transport' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Créer' })[0])

    await waitFor(() => expect(rhApi.createTypePrime).toHaveBeenCalledWith(
      expect.objectContaining({ code: 'TRANSPORT', libelle: 'Indemnité transport' }),
    ))
  })
})
