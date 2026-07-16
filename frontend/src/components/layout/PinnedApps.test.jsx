import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import PinnedApps from './PinnedApps'

const PINNED_KEY = 'taqinor.sidebar.pinned'

function renderPinned(collapsed = false) {
  return render(
    <MemoryRouter>
      <PinnedApps collapsed={collapsed} />
    </MemoryRouter>,
  )
}

describe('VX10 — PinnedApps', () => {
  beforeEach(() => {
    window.localStorage.removeItem(PINNED_KEY)
  })

  it('rend rien (collapsed) même si des apps sont épinglées', () => {
    window.localStorage.setItem(PINNED_KEY, JSON.stringify(['compta']))
    const { container } = renderPinned(true)
    expect(container.firstChild).toBeNull()
  })

  it('affiche le bouton « épingler » quand rien n’est épinglé', () => {
    renderPinned(false)
    expect(screen.getByRole('button', { name: /Épingler une application/ })).toBeInTheDocument()
  })

  it('ouvre le sélecteur et épingle une app, persistée en localStorage', () => {
    renderPinned(false)
    fireEvent.click(screen.getByRole('button', { name: /Épingler une application/ }))
    const items = screen.getAllByRole('menuitemcheckbox')
    expect(items.length).toBeGreaterThan(0)
    fireEvent.click(items[0])
    const stored = JSON.parse(window.localStorage.getItem(PINNED_KEY) || '[]')
    expect(stored.length).toBe(1)
  })

  it('désépingler retire l’app de la bande et de localStorage', () => {
    // Épingle d'abord le premier module dispo pour connaître sa clé.
    renderPinned(false)
    fireEvent.click(screen.getByRole('button', { name: /Épingler une application/ }))
    const items = screen.getAllByRole('menuitemcheckbox')
    fireEvent.click(items[0])
    // Le même item est maintenant coché → un second clic désépingle.
    fireEvent.click(screen.getAllByRole('menuitemcheckbox')[0])
    const stored = JSON.parse(window.localStorage.getItem(PINNED_KEY) || '[]')
    expect(stored.length).toBe(0)
  })
})
