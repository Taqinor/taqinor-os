// QJR546 — appliquer un modèle passe TOUJOURS par l'écran : le panneau rend le
// preset ENTIER au parent (lignes, remise, TVA, marché), en création comme en
// édition, et n'appelle jamais d'endpoint d'application (apply-preset supprimé).
//
// Run : npx vitest run src/pages/ventes/DevisPresetPanel.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../api/ventesApi', () => ({
  default: {
    getPresets: vi.fn(),
    savePreset: vi.fn(),
    deletePreset: vi.fn(),
  },
}))

import ventesApi from '../../api/ventesApi'
import DevisPresetPanel from './DevisPresetPanel'

const PRESET = {
  id: 5, nom: 'Standard 6 kWc', mode_installation: 'industriel',
  taux_tva: '10.00', remise_globale: '3.00',
  lignes_snapshot: [
    { produit_id: 101, designation: 'Panneau', quantite: '8', prix_unitaire: '1000',
      remise: '0', taux_tva: '10' },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.getPresets.mockResolvedValue({ data: [PRESET] })
})

async function ouvrirEtAppliquer(props) {
  const onApplied = vi.fn()
  render(<DevisPresetPanel {...props} onApplied={onApplied} />)
  await userEvent.click(screen.getByRole('button', { name: /Modèles de devis/ }))
  await userEvent.click(await screen.findByRole('button', { name: 'Appliquer' }))
  return onApplied
}

describe('QJR546 — le modèle s’applique à l’écran', () => {
  it('en édition (devisId=42) : jamais d’endpoint, onApplied reçoit le preset complet', async () => {
    const onApplied = await ouvrirEtAppliquer({ devisId: 42 })
    await waitFor(() => expect(onApplied).toHaveBeenCalledTimes(1))
    expect(onApplied).toHaveBeenCalledWith(PRESET)
    expect(ventesApi).not.toHaveProperty('applyPreset')
    expect(ventesApi.savePreset).not.toHaveBeenCalled()
    expect(await screen.findByText(/Modèle "Standard 6 kWc" appliqué/)).toBeTruthy()
  })

  it('en création (sans devisId) : même geste, même preset complet', async () => {
    const onApplied = await ouvrirEtAppliquer({})
    await waitFor(() => expect(onApplied).toHaveBeenCalledWith(PRESET))
  })

  it('un modèle sans ligne n’appelle pas le parent et le dit', async () => {
    ventesApi.getPresets.mockResolvedValue({ data: [{ ...PRESET, lignes_snapshot: [] }] })
    const onApplied = await ouvrirEtAppliquer({ devisId: 42 })
    expect(await screen.findByText(/aucune ligne/)).toBeTruthy()
    expect(onApplied).not.toHaveBeenCalled()
  })
})
