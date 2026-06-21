import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import BottomTabBar from './BottomTabBar'

function renderBar(onMore = () => {}) {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <BottomTabBar onMore={onMore} />
    </MemoryRouter>,
  )
}

describe('BottomTabBar — M156 polissage nav basse', () => {
  it('plafonne à 5 onglets maximum (≤ 4 liens + bouton « Plus »)', () => {
    const { container } = renderBar()
    const tabs = container.querySelectorAll('.bottom-tab')
    expect(tabs.length).toBeLessThanOrEqual(5)
  })

  it('le dernier onglet est « Plus » et ouvre le tiroir complet', async () => {
    const onMore = vi.fn()
    renderBar(onMore)
    const more = screen.getByRole('button', { name: /Plus de menus/i })
    await userEvent.click(more)
    expect(onMore).toHaveBeenCalled()
  })

  it('l’onglet actif porte aria-current="page"', () => {
    const { container } = renderBar()
    const active = container.querySelector('.bottom-tab.active')
    expect(active).toBeInTheDocument()
    expect(active).toHaveAttribute('aria-current', 'page')
  })

  it('chaque onglet a un libellé textuel (pas seulement une icône)', () => {
    const { container } = renderBar()
    container.querySelectorAll('.bottom-tab').forEach((t) => {
      expect(t.querySelector('.bottom-tab-label')).toBeInTheDocument()
    })
  })
})
