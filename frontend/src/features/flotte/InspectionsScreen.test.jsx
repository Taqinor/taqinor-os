import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XFLT13 — écran Inspections : exécution d'une check-list DVIR paramétrable.
   Décocher un item bascule son résultat en échec ; la création envoie les
   résultats alignés par libellé au serveur. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const inspectionsCreate = vi.fn(() => Promise.resolve({ data: { id: 1 } }))

vi.mock('../../api/flotteApi', () => ({
  default: {
    actifs: { list: () => Promise.resolve({ data: [{ id: 1, label: '12345-A-6' }] }) },
    modelesInspection: { list: () => Promise.resolve({
      data: [{ id: 3, nom: 'Pré-départ', items: [{ libelle: 'Freins', bloquant: true }, { libelle: 'Pneus', bloquant: false }] }],
    }) },
    inspections: { list: () => Promise.resolve({ data: [] }), create: (...args) => inspectionsCreate(...args) },
  },
}))

import InspectionsScreen from './InspectionsScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('InspectionsScreen (XFLT13)', () => {
  it('exécute la check-list choisie et envoie un item en échec', async () => {
    const user = userEvent.setup()
    withProviders(<InspectionsScreen />)

    await user.click(screen.getByRole('button', { name: 'Nouvelle inspection' }))
    await user.selectOptions(screen.getByLabelText('Véhicule / engin'), '1')
    await user.selectOptions(screen.getByLabelText('Modèle de check-list'), '3')

    await waitFor(() => expect(screen.getByText('Freins *')).toBeInTheDocument())
    await user.click(screen.getByRole('checkbox', { name: /Freins/ }))
    await user.type(screen.getByLabelText('Nom du signataire (e-signature)'), 'Karim')
    await user.click(screen.getByRole('button', { name: 'Valider l’inspection' }))

    await waitFor(() => expect(inspectionsCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        actif_flotte: 1,
        modele_inspection: 3,
        signature_nom: 'Karim',
        resultats: expect.arrayContaining([
          expect.objectContaining({ libelle: 'Freins', resultat: 'fail' }),
          expect.objectContaining({ libelle: 'Pneus', resultat: 'pass' }),
        ]),
      }),
    ))
  })
})
