import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR153 — Paramètres → IA : panneau de diagnostic admin-only.
   `iaApi.getSchema()` (GET /sql-agent/schema) existait déjà côté FastAPI mais
   n'avait aucun appelant frontend — ce panneau est le premier. */

const { getSchema } = vi.hoisted(() => ({
  getSchema: vi.fn(() => Promise.resolve({
    data: {
      tables: [
        { table: 'crm_client', description: 'Clients CRM' },
        { table: 'ventes_devis', description: 'Devis' },
      ],
      provider: 'groq',
      model: 'llama-3.3-70b-versatile',
      status: 'ok',
    },
  })),
}))

vi.mock('../../api/iaApi', () => ({
  default: { getSchema },
}))

import IaDiagnostic from './IaDiagnostic'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('IaDiagnostic (WIR153)', () => {
  it('affiche le provider/modèle actif et les tables autorisées', async () => {
    render(<IaDiagnostic />)

    expect(await screen.findByText('groq')).toBeInTheDocument()
    expect(screen.getByText('llama-3.3-70b-versatile')).toBeInTheDocument()
    expect(screen.getByText('crm_client')).toBeInTheDocument()
    expect(screen.getByText('ventes_devis')).toBeInTheDocument()
    expect(screen.getByText('Tables autorisées (2)')).toBeInTheDocument()
    expect(getSchema).toHaveBeenCalled()
  })

  it('affiche un état d\'erreur avec réessai quand le diagnostic échoue', async () => {
    getSchema.mockReturnValueOnce(Promise.reject(new Error('boom')))
    const user = userEvent.setup()
    render(<IaDiagnostic />)

    expect(await screen.findByText('Diagnostic indisponible')).toBeInTheDocument()

    getSchema.mockReturnValueOnce(Promise.resolve({
      data: { tables: [], provider: 'groq', model: 'llama', status: 'ok' },
    }))
    await user.click(screen.getByRole('button', { name: 'Réessayer' }))

    await waitFor(() => expect(screen.getByText('Aucune table déclarée.')).toBeInTheDocument())
    expect(getSchema).toHaveBeenCalledTimes(2)
  })
})
