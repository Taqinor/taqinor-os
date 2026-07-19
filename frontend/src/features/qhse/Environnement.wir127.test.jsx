import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR127 — les 10 onglets d'Environnement étaient lecture seule alors que le
   backend supporte toute la création. On vérifie que chaque onglet expose au
   minimum une création, et que le chemin de création d'un déchet (loi 28-00,
   prioritaire) fonctionne de bout en bout. Réseau mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (typeof Element.prototype.hasPointerCapture === 'undefined') {
    Element.prototype.hasPointerCapture = () => false
  }
  if (typeof Element.prototype.scrollIntoView === 'undefined') {
    Element.prototype.scrollIntoView = () => {}
  }
})

const { empty, dechetCreate } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  dechetCreate: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
}))

vi.mock('../../api/qhseApi', () => ({
  default: {
    dechets: { list: empty, create: (...a) => dechetCreate(...a) },
    bordereauxDechets: { list: empty, create: vi.fn() },
    recyclageModules: { list: empty, create: vi.fn() },
    conformitesEnvironnementales: { list: empty, create: vi.fn() },
    bilansCarbone: { list: empty, create: vi.fn() },
    indicateursEsg: { list: empty, create: vi.fn() },
    aspectsEnvironnementaux: { list: empty, create: vi.fn() },
    relevesConsommation: { list: empty, create: vi.fn() },
    demandesChangement: { list: empty, create: vi.fn() },
    veillesReglementaires: { list: empty, create: vi.fn() },
  },
}))

// CoutNonQualiteCard (onglet Changement) lit une permission — non touché ici.
vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

import Environnement from './Environnement'

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

beforeEach(() => { vi.clearAllMocks() })

describe('Environnement — création par onglet (WIR127)', () => {
  it('l\'onglet Déchets propose de créer un déchet et un BSD', async () => {
    withProviders(<Environnement />)
    await waitFor(() => expect(screen.getByRole('button', { name: /Nouveau déchet/ })).toBeTruthy())
    expect(screen.getByRole('button', { name: /Nouveau BSD/ })).toBeTruthy()
  })

  it('crée un déchet de bout en bout (loi 28-00)', async () => {
    const user = userEvent.setup()
    withProviders(<Environnement />)

    await user.click(await screen.findByRole('button', { name: /Nouveau déchet/ }))
    await waitFor(() => expect(screen.getAllByText('Nouveau déchet').length).toBeGreaterThan(1))

    fireEvent.change(screen.getByLabelText('Libellé'), { target: { value: 'Chutes de câble' } })
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(dechetCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        libelle: 'Chutes de câble',
        categorie: 'non_dangereux',
        mode_traitement: 'recyclage',
        unite: 'kg',
      }),
    ))
  })

  it('l\'onglet Bilan carbone propose de créer un bilan', async () => {
    const user = userEvent.setup()
    withProviders(<Environnement />)
    await user.click(screen.getByRole('tab', { name: 'Bilan carbone' }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Nouveau bilan/ })).toBeTruthy())
  })

  it('l\'onglet Aspects propose de créer un aspect et un relevé', async () => {
    const user = userEvent.setup()
    withProviders(<Environnement />)
    await user.click(screen.getByRole('tab', { name: 'Aspects environnementaux' }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Nouvel aspect/ })).toBeTruthy())
    expect(screen.getByRole('button', { name: /Nouveau relevé/ })).toBeTruthy()
  })
})
