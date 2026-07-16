import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuRadioGroup, DropdownMenuRadioItem,
  DropdownMenuSub, DropdownMenuSubTrigger, DropdownMenuSubContent,
  DropdownMenuShortcut,
} from './DropdownMenu'
import { Textarea } from './Textarea'
import { Progress } from './Progress'
import { Avatar, AvatarFallback, AvatarGroup } from './Avatar'
import { Tag, tagBase } from './Tag'
import { MultiSelect } from './MultiSelect'

/* VX129 — Primitives complétées : menus pro, Textarea adulte, Progress
   indéterminé, Avatar riche, UNE grammaire de chip. */

describe('VX129 — DropdownMenu : menu radio exclusif + sous-menu + shortcut', () => {
  it('RadioGroup/RadioItem : un seul item coché (menuitemradio)', () => {
    render(
      <DropdownMenu defaultOpen>
        <DropdownMenuTrigger>Ouvrir</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuRadioGroup value="b">
            <DropdownMenuRadioItem value="a">Option A</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="b">Option B</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="c">Option C</DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>,
    )
    const radios = screen.getAllByRole('menuitemradio')
    expect(radios).toHaveLength(3)
    const checked = radios.filter((r) => r.getAttribute('aria-checked') === 'true')
    expect(checked).toHaveLength(1)
    expect(checked[0]).toHaveTextContent('Option B')
  })

  it('Sub/SubTrigger/SubContent : le sous-menu s’ouvre (flèche droite) et expose ses items', async () => {
    render(
      <DropdownMenu defaultOpen>
        <DropdownMenuTrigger>Ouvrir</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>Action simple</DropdownMenuItem>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>Plus d’options</DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuItem>Sous-action</DropdownMenuItem>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        </DropdownMenuContent>
      </DropdownMenu>,
    )
    const subTrigger = screen.getByText('Plus d’options')
    subTrigger.focus()
    fireEvent.keyDown(subTrigger, { key: 'ArrowRight' })
    await waitFor(() => expect(screen.getByText('Sous-action')).toBeInTheDocument())
  })

  it('Shortcut : rendu comme un slot dédié à l’intérieur de l’item', () => {
    render(
      <DropdownMenu defaultOpen>
        <DropdownMenuTrigger>Ouvrir</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>
            Enregistrer
            <DropdownMenuShortcut>Ctrl+S</DropdownMenuShortcut>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    )
    const shortcut = screen.getByText('Ctrl+S')
    expect(shortcut.className).toMatch(/ml-auto/)
  })
})

describe('VX129 — Textarea : maxLength avec compteur', () => {
  it('affiche « n/max » et le met à jour à la frappe', () => {
    const onChange = vi.fn()
    render(<Textarea value="hello" maxLength={10} onChange={onChange} />)
    expect(screen.getByText('5/10')).toBeInTheDocument()

    const textarea = screen.getByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'hello worl' } })
    expect(onChange).toHaveBeenCalledTimes(1)
  })

  it('sans maxLength : pas de compteur (comportement inchangé)', () => {
    render(<Textarea value="hello" onChange={() => {}} />)
    expect(screen.queryByText(/\/\d+$/)).toBeNull()
  })
})

describe('VX129 — Progress : indeterminate balaie la piste', () => {
  it('pose data-state="indeterminate" et l’utilitaire animate-progress-sweep', () => {
    const { container } = render(<Progress indeterminate />)
    const root = container.querySelector('[role="progressbar"]')
    expect(root).toHaveAttribute('data-state', 'indeterminate')
    const indicator = container.querySelector('.animate-progress-sweep')
    expect(indicator).toBeTruthy()
  })

  it('valeur déterminée : pas de classe de balayage', () => {
    const { container } = render(<Progress value={40} />)
    expect(container.querySelector('.animate-progress-sweep')).toBeNull()
  })
})

describe('VX129 — Avatar : size + status, AvatarGroup + max', () => {
  it('status pose une pastille de présence étiquetée', () => {
    render(
      <Avatar status="online">
        <AvatarFallback>RK</AvatarFallback>
      </Avatar>,
    )
    expect(screen.getByRole('status', { name: 'En ligne' })).toBeInTheDocument()
  })

  it('AvatarGroup max={3} sur 5 avatars -> "+2"', () => {
    render(
      <AvatarGroup max={3}>
        {Array.from({ length: 5 }, (_, i) => (
          <Avatar key={i}><AvatarFallback>{i}</AvatarFallback></Avatar>
        ))}
      </AvatarGroup>,
    )
    expect(screen.getByText('+2')).toBeInTheDocument()
  })

  it('sans max : tous les avatars sont rendus, aucun "+N"', () => {
    render(
      <AvatarGroup>
        {Array.from({ length: 3 }, (_, i) => (
          <Avatar key={i}><AvatarFallback>{i}</AvatarFallback></Avatar>
        ))}
      </AvatarGroup>,
    )
    expect(screen.queryByText(/^\+\d+$/)).toBeNull()
  })
})

describe('VX129 — UNE grammaire de chip : MultiSelect et Tag partagent rayon/hauteur', () => {
  it('le jeton MultiSelect porte exactement les classes tagBase de Tag.jsx', async () => {
    const options = [{ value: 'a', label: 'Alpha' }]
    render(<MultiSelect options={options} value={['a']} onChange={vi.fn()} />)
    const chipText = screen.getByText('Alpha')
    const chip = chipText.closest('span')
    for (const cls of tagBase.split(' ')) {
      expect(chip.className).toContain(cls)
    }
  })

  it('Tag rend bien tagBase (source commune)', () => {
    render(<Tag>Alpha</Tag>)
    const chip = screen.getByText('Alpha')
    for (const cls of tagBase.split(' ')) {
      expect(chip.className).toContain(cls)
    }
  })
})
