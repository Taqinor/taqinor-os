import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HelpTip } from './HelpTip'

// VX47 — Aide contextuelle intégrée : petit bouton « ? » discret + Popover,
// contenu FR concis. Ne doit JAMAIS provoquer de re-layout au clic (le
// contenu s'ouvre dans un Popover flottant, pas inline).

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

describe('HelpTip (VX47)', () => {
  it('rend un bouton « ? » avec un aria-label explicite', () => {
    render(<HelpTip label="Aide — score de lead">Contenu.</HelpTip>)
    expect(screen.getByRole('button', { name: 'Aide — score de lead' })).toBeTruthy()
  })

  it('le contenu est fermé par défaut (pas de re-layout involontaire)', () => {
    render(<HelpTip label="Aide">Texte explicatif concis.</HelpTip>)
    expect(screen.queryByText('Texte explicatif concis.')).toBeFalsy()
  })

  it('ouvre le Popover au clic et affiche le contenu FR', async () => {
    const user = userEvent.setup()
    render(<HelpTip label="Aide — gates">Un gate bloquant empêche d'avancer.</HelpTip>)
    await user.click(screen.getByRole('button', { name: 'Aide — gates' }))
    expect(await screen.findByText("Un gate bloquant empêche d'avancer.")).toBeTruthy()
  })
})
