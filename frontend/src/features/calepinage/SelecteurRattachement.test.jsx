import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../api/crmApi', () => ({
  default: { getLeads: vi.fn(), searchClients: vi.fn() },
}))

import crmApi from '../../api/crmApi'
import SelecteurRattachement from './SelecteurRattachement'

beforeEach(() => { vi.clearAllMocks() })

describe('SelecteurRattachement (ACAL181)', () => {
  it('cherche les leads au SERVEUR et rend l’id choisi', async () => {
    crmApi.getLeads.mockResolvedValue({ data: { results: [
      { id: 5, nom: 'Alami', prenom: 'Sara', ville: 'Rabat' },
    ] } })
    const onChange = vi.fn()
    render(<SelecteurRattachement genre="lead" onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox'))
    await userEvent.click(await screen.findByText('Alami Sara'))
    await waitFor(() => expect(onChange).toHaveBeenCalled())
    expect(crmApi.getLeads).toHaveBeenCalled()
    expect(onChange.mock.calls[0][0]).toBe('5')
  })

  it('cherche les clients par searchClients et affiche le libellé courant', async () => {
    crmApi.searchClients.mockResolvedValue({ data: { results: [
      { id: 9, nom: 'Atlas', adresse: 'Casablanca' },
    ] } })
    const onChange = vi.fn()
    render(<SelecteurRattachement genre="client" valeur={3} libelle="Client actuel"
      onChange={onChange} />)
    expect(screen.getByRole('combobox')).toHaveTextContent('Client actuel')
    await userEvent.click(screen.getByRole('combobox'))
    await userEvent.click(await screen.findByText('Atlas'))
    await waitFor(() => expect(onChange).toHaveBeenCalled())
    expect(crmApi.searchClients).toHaveBeenCalled()
    expect(onChange.mock.calls[0][0]).toBe('9')
  })
})
