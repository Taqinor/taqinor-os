import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import gestionProjetApi from '../../../api/gestionProjetApi'
import ProjetFormDialog from './ProjetFormDialog'

/* XPRJ27 — Volet marchés publics FACULTATIF : replié par défaut (aucun champ
   obligatoire), révélé au clic, les valeurs saisies sont envoyées au serveur
   sans jamais forcer le statut. */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    createProjet: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    updateProjet: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ProjetFormDialog — XPRJ27 marché public', () => {
  it('le volet marché public est replié par défaut', () => {
    render(<ProjetFormDialog onClose={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.queryByLabelText('N° de marché')).not.toBeInTheDocument()
  })

  it('révèle le volet et envoie les champs marché public à la création', async () => {
    const user = userEvent.setup()
    render(<ProjetFormDialog onClose={vi.fn()} onSaved={vi.fn()} />)
    await user.type(screen.getByLabelText('Nom'), 'Villa Fès')
    await user.click(screen.getByRole('button', { name: /Marché public/ }))
    await user.type(screen.getByLabelText('N° de marché'), 'MP-2026-042')
    await user.type(screen.getByLabelText('Montant du marché (MAD)'), '500000')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(gestionProjetApi.createProjet).toHaveBeenCalledWith(
      expect.objectContaining({ numero_marche: 'MP-2026-042', montant_marche: '500000' }),
    ))
  })
})
