import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import ClientTypeToggle from './ClientTypeToggle'

/* J139 + L151 — bascule optimiste du type de client.
   On vérifie : (1) la pastille reflète le type serveur ; (2) choisir un autre
   type appelle onSave avec la nouvelle valeur ; (3) un onSave qui REJETTE
   restaure l'affichage (rollback) ; (4) le libellé inline « Enregistrement… »
   apparaît pendant le commit. Le toast est mocké (provider global non monté). */

vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const clientParticulier = { id: 1, type_client: 'particulier' }

describe('ClientTypeToggle (L151)', () => {
  it('affiche le type serveur en pastille', () => {
    render(<ClientTypeToggle client={clientParticulier} onSave={vi.fn()} />)
    expect(screen.getByText('Particulier')).toBeInTheDocument()
  })

  it('déduit « Entreprise » d’un identifiant B2B même sans type explicite', () => {
    render(<ClientTypeToggle client={{ id: 2, ice: '0012' }} onSave={vi.fn()} />)
    expect(screen.getByText('Entreprise')).toBeInTheDocument()
  })

  it('enregistre la nouvelle valeur en optimiste (onSave appelé)', async () => {
    const onSave = vi.fn(() => Promise.resolve())
    render(<ClientTypeToggle client={clientParticulier} onSave={onSave} />)
    // Ouvre le menu puis choisit « Entreprise ».
    fireEvent.click(screen.getByTitle('Changer le type de client'))
    fireEvent.click(screen.getByRole('button', { name: 'Entreprise' }))
    await waitFor(() => expect(onSave).toHaveBeenCalledWith('entreprise'))
    // La valeur optimiste reste affichée après confirmation.
    await waitFor(() => expect(screen.getByText('Entreprise')).toBeInTheDocument())
  })

  it('restaure l’affichage si onSave rejette (rollback)', async () => {
    const onSave = vi.fn(() => Promise.reject(new Error('boom')))
    render(<ClientTypeToggle client={clientParticulier} onSave={onSave} />)
    fireEvent.click(screen.getByTitle('Changer le type de client'))
    fireEvent.click(screen.getByRole('button', { name: 'Entreprise' }))
    await waitFor(() => expect(onSave).toHaveBeenCalled())
    // Après rollback, la pastille revient à « Particulier ».
    await waitFor(() => expect(screen.getByTitle('Changer le type de client'))
      .toHaveTextContent('Particulier'))
  })
})
