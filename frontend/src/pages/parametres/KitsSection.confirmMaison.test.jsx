import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor, fireEvent, within } from '@testing-library/react'

/* APAR67 — la suppression d'un kit passe par le dialogue maison (ui/confirm),
   jamais par `window.confirm`. Supprimer → dialogue rendu ; Annuler → aucune
   requête ; Confirmer → requête. */

vi.mock('../../api/outillageApi', () => ({
  default: {
    getKits: vi.fn(),
    getOutils: vi.fn(async () => ({ data: [] })),
    saveKit: vi.fn(async () => ({ data: {} })),
    deleteKit: vi.fn(async () => ({ data: {} })),
    saveKitItem: vi.fn(async () => ({ data: {} })),
    deleteKitItem: vi.fn(async () => ({ data: {} })),
  },
}))
vi.mock('../../api/installationsApi', () => ({
  default: { getTypesIntervention: vi.fn(async () => ({ data: [] })) },
}))

import outillageApi from '../../api/outillageApi'
import { ThemeProvider } from '../../design/ThemeProvider'
import { ConfirmProvider } from '../../providers/ConfirmProvider'
import KitsSection from './KitsSection'

const renderSection = async () => {
  await act(async () => {
    render(
      <ThemeProvider>
        <ConfirmProvider>
          <KitsSection />
        </ConfirmProvider>
      </ThemeProvider>,
    )
  })
}

beforeEach(() => {
  outillageApi.deleteKit.mockClear()
  outillageApi.getKits.mockResolvedValue({
    data: [{ id: 7, nom: 'Kit toiture', actif: true, ordre: 1, type_intervention: '', items: [] }],
  })
})
afterEach(() => cleanup())

describe('APAR67 KitsSection — dialogue maison', () => {
  it('Supprimer → dialogue maison rendu ; Annuler → aucune requête', async () => {
    await renderSection()
    fireEvent.click(await screen.findByLabelText('Supprimer le kit'))
    const dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText(/Supprimer le kit/)).toBeInTheDocument()
    fireEvent.click(within(dialog).getByText('Annuler'))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(outillageApi.deleteKit).not.toHaveBeenCalled()
  })

  it('Confirmer → la suppression est envoyée', async () => {
    await renderSection()
    fireEvent.click(await screen.findByLabelText('Supprimer le kit'))
    const dialog = await screen.findByRole('alertdialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Supprimer' }))
    await waitFor(() => expect(outillageApi.deleteKit).toHaveBeenCalledWith(7))
  })
})
