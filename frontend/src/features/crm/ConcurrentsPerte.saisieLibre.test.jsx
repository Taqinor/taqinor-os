import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ALEA22 — « Concurrents perdus » : formulaire `noValidate`. Un prix à 3
   décimales (« 1234.567 ») n'est plus bloqué par une bulle navigateur : la
   requête PART, et un refus serveur s'affiche SOUS le champ. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const { getLeads, getConcurrentsPerte, createConcurrentPerte } = vi.hoisted(() => ({
  getLeads: vi.fn(),
  getConcurrentsPerte: vi.fn(),
  createConcurrentPerte: vi.fn(),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getLeads: (...a) => getLeads(...a),
    getConcurrentsPerte: (...a) => getConcurrentsPerte(...a),
    createConcurrentPerte: (...a) => createConcurrentPerte(...a),
  },
}))

import ConcurrentsPerte from './ConcurrentsPerte'

beforeEach(() => {
  vi.clearAllMocks()
  getLeads.mockResolvedValue({ data: [{ id: 42, nom: 'Ahmed Alami', perdu: true }] })
  getConcurrentsPerte.mockResolvedValue({ data: [] })
})

async function ouvrirFormulaire(user) {
  render(
    <MemoryRouter><ThemeProvider><ConcurrentsPerte /></ThemeProvider></MemoryRouter>,
  )
  await user.type(screen.getByLabelText('Rechercher un lead perdu'), 'Alami')
  await user.click((await screen.findAllByText(/Ahmed Alami/))[0])
  return screen.findByLabelText('Concurrent gagnant')
}

describe('ALEA22 — Concurrents perdus : saisie libre', () => {
  it('prix à 3 décimales → requête envoyée (aucune bulle native)', async () => {
    createConcurrentPerte.mockResolvedValue({ data: { id: 1 } })
    const user = userEvent.setup()
    const nom = await ouvrirFormulaire(user)
    expect(nom.closest('form')).toHaveAttribute('novalidate')
    await user.type(nom, 'SunTech')
    await user.type(screen.getByLabelText('Prix du concurrent'), '1234.567')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(createConcurrentPerte).toHaveBeenCalledTimes(1))
    expect(createConcurrentPerte.mock.calls[0][0].concurrent_prix).toBe('1234.567')
  })

  it('refus serveur 400 → erreur sous le champ prix', async () => {
    createConcurrentPerte.mockRejectedValue({
      response: { status: 400, data: { concurrent_prix: ['Pas plus de 2 décimales.'] } },
    })
    const user = userEvent.setup()
    const nom = await ouvrirFormulaire(user)
    await user.type(nom, 'SunTech')
    await user.type(screen.getByLabelText('Prix du concurrent'), '1234.567')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Pas plus de 2 décimales.')).toBeInTheDocument()
  })

  it('concurrent vide → erreur sous le champ, aucune requête', async () => {
    const user = userEvent.setup()
    await ouvrirFormulaire(user)
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByText('Le concurrent gagnant est requis.')).toBeInTheDocument()
    expect(createConcurrentPerte).not.toHaveBeenCalled()
  })
})
