import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { HelpTip } from './HelpTip'

// VX47 — Aide contextuelle intégrée : petit bouton « ? » discret + Popover,
// contenu FR concis. Ne doit JAMAIS provoquer de re-layout au clic (le
// contenu s'ouvre dans un Popover flottant, pas inline).
// VX247(d) — la bulle porte désormais un lien interne `<Link>` vers le
// lexique : rendu sous <MemoryRouter> (le composant a besoin d'un Router).

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderTip(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('HelpTip (VX47)', () => {
  it('rend un bouton « ? » avec un aria-label explicite', () => {
    renderTip(<HelpTip label="Aide — score de lead">Contenu.</HelpTip>)
    expect(screen.getByRole('button', { name: 'Aide — score de lead' })).toBeTruthy()
  })

  it('le contenu est fermé par défaut (pas de re-layout involontaire)', () => {
    renderTip(<HelpTip label="Aide">Texte explicatif concis.</HelpTip>)
    expect(screen.queryByText('Texte explicatif concis.')).toBeFalsy()
  })

  it('ouvre le Popover au clic et affiche le contenu FR', async () => {
    const user = userEvent.setup()
    renderTip(<HelpTip label="Aide — gates">Un gate bloquant empêche d'avancer.</HelpTip>)
    await user.click(screen.getByRole('button', { name: 'Aide — gates' }))
    expect(await screen.findByText("Un gate bloquant empêche d'avancer.")).toBeTruthy()
  })

  // VX247(d) — la bulle pointe vers le lexique complet au lieu de dupliquer
  // une définition détaillée dans chaque HelpTip.
  it('VX247(d) : la bulle porte un lien vers /aide/lexique', async () => {
    const user = userEvent.setup()
    renderTip(<HelpTip label="Aide — gates">Un gate bloquant empêche d'avancer.</HelpTip>)
    await user.click(screen.getByRole('button', { name: 'Aide — gates' }))
    const link = await screen.findByRole('link', { name: /lexique/i })
    expect(link).toHaveAttribute('href', '/aide/lexique')
  })
})
