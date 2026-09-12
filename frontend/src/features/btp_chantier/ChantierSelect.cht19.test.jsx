import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CHT19 — Les écrans satellites acceptent `?chantier=`.
   ----------------------------------------------------------------------------
   `ChantierSelect` (partagé par les 7 écrans btp_chantier, SuiviProjetChantier
   et NotesDeFraisPage/CHT16) lit `?chantier=<id>` au montage et pré-sélectionne
   — UNE SEULE FOIS, sans jamais écraser une valeur déjà présente (fournie par
   le parent, ou déjà choisie par l'utilisateur).
   ========================================================================== */

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({
      data: [{ id: 88, reference: 'CH-0088', client_nom: 'Villa Zenith', site_ville: 'Agadir' }],
    }),
  },
}))

import ChantierSelect from './ChantierSelect'

afterEach(() => cleanup())

describe('ChantierSelect — pré-sélection par URL (CHT19)', () => {
  it('pré-sélectionne le chantier depuis ?chantier=<id> au montage', async () => {
    const onChange = vi.fn()
    render(
      <MemoryRouter initialEntries={['/reserves?chantier=88']}>
        <ChantierSelect value={null} onChange={onChange} />
      </MemoryRouter>,
    )
    await screen.findByLabelText('Chantier')
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('88'))
  })

  it("n'écrase jamais une valeur déjà présente", async () => {
    const onChange = vi.fn()
    render(
      <MemoryRouter initialEntries={['/reserves?chantier=88']}>
        <ChantierSelect value={42} onChange={onChange} />
      </MemoryRouter>,
    )
    await screen.findByLabelText('Chantier')
    expect(onChange).not.toHaveBeenCalled()
  })

  it('ne fait rien sans paramètre ?chantier= dans l\'URL', async () => {
    const onChange = vi.fn()
    render(
      <MemoryRouter initialEntries={['/reserves']}>
        <ChantierSelect value={null} onChange={onChange} />
      </MemoryRouter>,
    )
    await screen.findByLabelText('Chantier')
    expect(onChange).not.toHaveBeenCalled()
  })
})
