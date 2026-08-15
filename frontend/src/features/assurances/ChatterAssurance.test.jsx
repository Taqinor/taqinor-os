import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR262 — Assurances : chatter sinistre invisible et note de police
   impossible. ChatterAssurance est le composeur PARTAGÉ (getHistorique/noter
   en props) utilisé identiquement par PoliceDetail (noterPolice) et le détail
   sinistre de SinistresPage (noterSinistre). Bouton « Publier » inactif tant
   que la note est vide. */

import ChatterAssurance from './ChatterAssurance'

describe('ChatterAssurance (WIR262)', () => {
  it('affiche la transition de statut au fil et le bouton Publier reste inactif à vide', async () => {
    const getHistorique = vi.fn(() => Promise.resolve({
      data: [{
        id: 1, kind: 'modification', field: 'statut', field_label: 'Statut',
        old_value: 'declare', new_value: 'en_expertise', created_at: '2026-08-01T10:00:00Z',
      }],
    }))
    const noter = vi.fn()

    render(<ChatterAssurance getHistorique={getHistorique} noter={noter} subjectId={9} />)

    expect(await screen.findByText(/en_expertise/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Publier' })).toBeDisabled()
  })

  it('publie une note (noter appelé avec subjectId + texte) et elle apparaît en tête', async () => {
    const getHistorique = vi.fn()
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({
        data: [{ id: 2, kind: 'note', body: 'Expert missionné', created_at: '2026-08-02T10:00:00Z' }],
      })
    const noter = vi.fn(() => Promise.resolve({ data: {} }))
    const user = userEvent.setup()

    render(<ChatterAssurance getHistorique={getHistorique} noter={noter} subjectId={9} />)
    await screen.findByText('Aucune activité.')

    await user.type(screen.getByLabelText('Nouvelle note'), 'Expert missionné')
    await user.click(screen.getByRole('button', { name: 'Publier' }))

    await waitFor(() => expect(noter).toHaveBeenCalledWith(9, 'Expert missionné'))
    expect(await screen.findByText('Expert missionné')).toBeInTheDocument()
  })
})
