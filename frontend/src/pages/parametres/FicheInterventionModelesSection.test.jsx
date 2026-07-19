import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR114 (ZFSM3) — Modèles de fiche d'intervention : templates + champs. */

const TEMPLATES = [
  {
    id: 1, nom: 'Maintenance PV', type_intervention: 'maintenance', actif: true, protege: false,
    champs: [
      { id: 5, cle: 'tension_v', libelle: 'Tension mesurée', type_champ: 'mesure', unite: 'V', obligatoire: true },
    ],
  },
]

const { getFiche, saveTemplate, delTemplate, saveChamp, delChamp } = vi.hoisted(() => ({
  getFiche: vi.fn(),
  saveTemplate: vi.fn(() => Promise.resolve({ data: {} })),
  delTemplate: vi.fn(() => Promise.resolve({ data: {} })),
  saveChamp: vi.fn(() => Promise.resolve({ data: {} })),
  delChamp: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../api/installationsApi', () => ({
  default: {
    getFicheTemplates: getFiche,
    saveFicheTemplate: saveTemplate,
    deleteFicheTemplate: delTemplate,
    saveFicheChamp: saveChamp,
    deleteFicheChamp: delChamp,
  },
}))

import FicheInterventionModelesSection from './FicheInterventionModelesSection'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('FicheInterventionModelesSection (WIR114)', () => {
  it('liste les modèles avec leurs champs', async () => {
    getFiche.mockResolvedValue({ data: TEMPLATES })
    render(<FicheInterventionModelesSection />)
    const block = await screen.findByTestId('fiche-template-1')
    expect(within(block).getByText('Maintenance PV')).toBeInTheDocument()
    expect(within(block).getByText('maintenance')).toBeInTheDocument()
    expect(within(block).getByText('Tension mesurée')).toBeInTheDocument()
    expect(within(block).getByText('obligatoire')).toBeInTheDocument()
  })

  it('crée un modèle', async () => {
    getFiche.mockResolvedValue({ data: [] })
    const user = userEvent.setup()
    render(<FicheInterventionModelesSection />)
    await screen.findByPlaceholderText('Nom du modèle')
    await user.type(screen.getByPlaceholderText('Nom du modèle'), 'Recette PV')
    await user.type(screen.getByPlaceholderText("Type d'intervention"), 'recette')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(saveTemplate).toHaveBeenCalledWith(null,
      expect.objectContaining({ nom: 'Recette PV', type_intervention: 'recette', actif: true })))
  })

  it('ajoute un champ à un modèle', async () => {
    getFiche.mockResolvedValue({ data: TEMPLATES })
    const user = userEvent.setup()
    render(<FicheInterventionModelesSection />)
    const block = await screen.findByTestId('fiche-template-1')
    await user.type(within(block).getByPlaceholderText('ex. tension_v'), 'humidite')
    await user.type(within(block).getByPlaceholderText('ex. Tension mesurée'), 'Humidité')
    await user.click(within(block).getByRole('button', { name: /Champ/ }))
    await waitFor(() => expect(saveChamp).toHaveBeenCalledWith(null,
      expect.objectContaining({ template: 1, cle: 'humidite', libelle: 'Humidité', type_champ: 'texte' })))
  })
})
