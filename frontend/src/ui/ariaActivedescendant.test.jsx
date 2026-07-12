import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Combobox } from './Combobox'
import { MultiSelect } from './MultiSelect'
import { TimePicker } from './TimePicker'

/* VX128 — Comboboxes audibles : `aria-activedescendant` câblé sur l'input
   (0 occurrence avant dans tout le repo). Combobox/MultiSelect/TimePicker
   géraient un curseur visuel (`data-cursor`, flèches) mais l'input n'annonçait
   jamais l'option active à NVDA/VoiceOver — LE trou du pattern combobox
   WAI-ARIA APG. Vérifie : ouvrir, flèche bas, l'input pointe la 2ᵉ option. */

const options = [
  { value: 'a', label: 'Option A' },
  { value: 'b', label: 'Option B' },
  { value: 'c', label: 'Option C' },
]

describe('aria-activedescendant (VX128)', () => {
  it('Combobox : la flèche bas fait pointer aria-activedescendant sur la 2ᵉ option', async () => {
    render(<Combobox options={options} value={null} onChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('combobox'))
    const search = await screen.findByRole('searchbox')
    fireEvent.keyDown(search, { key: 'ArrowDown' })

    await waitFor(() => {
      const activeId = search.getAttribute('aria-activedescendant')
      expect(activeId).toBeTruthy()
      const activeOption = document.getElementById(activeId)
      expect(activeOption).toHaveTextContent('Option B')
      expect(activeOption).toHaveAttribute('role', 'option')
    })
  })

  it('MultiSelect : la flèche bas fait pointer aria-activedescendant sur la 2ᵉ option', async () => {
    render(<MultiSelect options={options} value={[]} onChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('combobox'))
    const search = await screen.findByRole('searchbox')
    fireEvent.keyDown(search, { key: 'ArrowDown' })

    await waitFor(() => {
      const activeId = search.getAttribute('aria-activedescendant')
      expect(activeId).toBeTruthy()
      expect(document.getElementById(activeId)).toHaveTextContent('Option B')
    })
  })

  it('TimePicker : la flèche bas fait pointer aria-activedescendant sur le 2ᵉ créneau', async () => {
    render(<TimePicker value="" onChange={vi.fn()} step={60} />)
    const input = screen.getByRole('combobox')
    fireEvent.focus(input)
    fireEvent.keyDown(input, { key: 'ArrowDown' }) // ouvre le listbox
    fireEvent.keyDown(input, { key: 'ArrowDown' }) // curseur -> 2ᵉ créneau

    await waitFor(() => {
      const activeId = input.getAttribute('aria-activedescendant')
      expect(activeId).toBeTruthy()
      const activeOption = document.getElementById(activeId)
      expect(activeOption).toBeTruthy()
      expect(activeOption).toHaveAttribute('role', 'option')
    })
  })
})
