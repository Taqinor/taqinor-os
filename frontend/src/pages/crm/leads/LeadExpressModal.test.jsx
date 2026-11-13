import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* AERR104 — le refus 400 du serveur à la création d'un lead express se range
   SOUS son champ ; la boîte reste ouverte avec la saisie (aucun bandeau
   générique « Erreur lors de la création du lead. »). */

vi.mock('../../../api/crmApi', () => ({
  default: {
    createLead: vi.fn(),
    checkDuplicates: vi.fn(() => Promise.resolve({ data: {} })),
    getCanaux: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    scanCarteVisite: vi.fn(),
  },
}))

import crmApi from '../../../api/crmApi'
import LeadExpressModal from './LeadExpressModal'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('LeadExpressModal — AERR104', () => {
  it('400 email : message sous E-mail, boîte ouverte', async () => {
    crmApi.createLead.mockRejectedValueOnce({
      response: { status: 400, data: { email: ['Saisissez une adresse e-mail valide.'] } },
    })
    const onClose = vi.fn()
    render(<LeadExpressModal onClose={onClose} onSaved={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText('Nom du prospect'), { target: { value: 'Test' } })
    fireEvent.change(screen.getByPlaceholderText('contact@exemple.com'), { target: { value: 'abc@' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer le lead/ }))

    expect(await screen.findByText('Saisissez une adresse e-mail valide.')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('contact@exemple.com')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.queryByText('Erreur lors de la création du lead.')).not.toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByPlaceholderText('Nom du prospect')).toHaveValue('Test')

    // Corriger l'e-mail efface le message.
    fireEvent.change(screen.getByPlaceholderText('contact@exemple.com'), { target: { value: 'abc@x.ma' } })
    await waitFor(() => expect(screen.queryByText('Saisissez une adresse e-mail valide.')).not.toBeInTheDocument())
  })

  it('un refus sans champ garde le message générique', async () => {
    crmApi.createLead.mockRejectedValueOnce({ response: { status: 500, data: {} } })
    render(<LeadExpressModal onClose={vi.fn()} onSaved={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText('Nom du prospect'), { target: { value: 'Test' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer le lead/ }))
    expect(await screen.findByText('Erreur lors de la création du lead.')).toBeInTheDocument()
  })
})
