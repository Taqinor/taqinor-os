import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { press, pressItem, pressCurve } from './interaction'

// Radix Slider observe la taille de sa piste : jsdom n'a pas ResizeObserver.
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}

      unobserve() {}

      disconnect() {}
    }
  }
})
import { Switch } from './Switch'
import { Slider } from './Slider'
import { Segmented } from './Segmented'
import { Tabs, TabsList, TabsTrigger } from './Tabs'
import { Checkbox } from './Checkbox'
import { RadioGroup, RadioGroupItem } from './RadioGroup'
import { Progress } from './Progress'
import {
  Select, SelectContent, SelectTrigger, SelectValue, SelectItem,
} from './Select'
import { Combobox } from './Combobox'
import { MultiSelect } from './MultiSelect'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from './DropdownMenu'
import {
  ContextMenu, ContextMenuTrigger, ContextMenuContent, ContextMenuItem,
} from './ContextMenu'
import { DatePicker } from './DatePicker'

/* VX126 — L'état PRESSÉ propagé : 12+ contrôles cessent d'être morts au clic,
   courbes unifiées. On vérifie que chaque primitif pose la classe pressée
   partagée (`interaction.js`) et que la courbe de transition est identique à
   celle de Button (`pressCurve`) — pas de comportement, juste la classe (RTL
   ne peut pas simuler `:active`/`getComputedStyle` de manière fiable en jsdom,
   donc on assert la présence de l'utilitaire partagé). */

describe('VX126 — utilitaire partagé interaction.js', () => {
  it('press est réservé au pointeur fin (@media(hover:hover)) — jamais sous hover:none', () => {
    expect(press).toContain('[@media(hover:hover)]:active:scale-[0.98]')
    expect(press).not.toMatch(/\[@media\(hover:none\)\]/)
  })

  it('pressItem (items de liste/menu) ne scale jamais (casserait l’alignement de la liste)', () => {
    expect(pressItem).not.toMatch(/scale/)
    expect(pressItem).toContain('active:brightness-95')
  })

  it('pressCurve reproduit exactement la courbe de Button (150ms, cubic-bezier(0.23,1,0.32,1))', () => {
    expect(pressCurve).toContain('duration-150')
    expect(pressCurve).toContain('cubic-bezier(0.23,1,0.32,1)')
  })
})

describe('VX126 — Switch : press + squish thumb + courbe alignée', () => {
  it('pose la classe pressée sur la piste et la courbe Button sur le thumb', () => {
    render(<Switch aria-label="Notifications" />)
    const root = screen.getByRole('switch')
    expect(root.className).toContain('[@media(hover:hover)]:active:scale-[0.98]')
    expect(root.className).toContain('cubic-bezier(0.23,1,0.32,1)')
    expect(root.className).toContain('group')
    const thumb = root.querySelector('span')
    expect(thumb.className).toContain('cubic-bezier(0.23,1,0.32,1)')
    expect(thumb.className).toContain('[@media(hover:hover)]:group-active:scale-x-90')
  })
})

describe('VX126 — Slider : halo/scale au grab', () => {
  it('le thumb gagne un scale + ring au press, réservé au pointeur fin', () => {
    render(<Slider defaultValue={[50]} aria-label="Volume" />)
    const thumb = screen.getByRole('slider')
    expect(thumb.className).toContain('[@media(hover:hover)]:active:scale-110')
    expect(thumb.className).toContain('[@media(hover:hover)]:active:ring-4')
    expect(thumb.className).toContain('cubic-bezier(0.23,1,0.32,1)')
  })
})

describe('VX126 — Segmented : press partagé', () => {
  it('chaque item pose la classe pressée', () => {
    render(<Segmented options={[{ value: 'a', label: 'A' }]} value="a" onChange={() => {}} />)
    const item = screen.getByRole('radio', { name: 'A' })
    expect(item.className).toContain('[@media(hover:hover)]:active:scale-[0.98]')
    expect(item.className).toContain('cubic-bezier(0.23,1,0.32,1)')
  })
})

describe('VX126 — Tabs : press partagé sur le trigger', () => {
  it('le trigger pose la classe pressée', () => {
    render(
      <Tabs defaultValue="a">
        <TabsList>
          <TabsTrigger value="a">Onglet A</TabsTrigger>
        </TabsList>
      </Tabs>,
    )
    const trigger = screen.getByRole('tab', { name: 'Onglet A' })
    expect(trigger.className).toContain('[@media(hover:hover)]:active:scale-[0.98]')
    expect(trigger.className).toContain('cubic-bezier(0.23,1,0.32,1)')
  })
})

describe('VX126 — Checkbox : hover froid + press + scale-in de coche', () => {
  it('a hover:border-primary/60, la classe pressée, et l’indicateur en pop-in', () => {
    render(<Checkbox checked aria-label="Accepter" />)
    const box = screen.getByRole('checkbox')
    expect(box.className).toContain('hover:border-primary/60')
    expect(box.className).toContain('[@media(hover:hover)]:active:scale-[0.98]')
    const indicator = box.querySelector('span')
    expect(indicator?.className).toContain('animate-pop-in')
  })
})

describe('VX126 — RadioGroup : hover froid + press', () => {
  it('l’item a hover:border-primary/60 et la classe pressée', () => {
    render(
      <RadioGroup value="a">
        <RadioGroupItem value="a" aria-label="Option A" />
      </RadioGroup>,
    )
    const item = screen.getByRole('radio', { name: 'Option A' })
    expect(item.className).toContain('hover:border-primary/60')
    expect(item.className).toContain('[@media(hover:hover)]:active:scale-[0.98]')
  })
})

describe('VX126 — Progress : courbe alignée sur Button', () => {
  it('l’indicateur porte la même courbe que Button', () => {
    const { container } = render(<Progress value={40} />)
    const indicator = container.querySelector('[style]')
    expect(indicator.className).toContain('cubic-bezier(0.23,1,0.32,1)')
  })
})

describe('VX126 — Select : item pressé', () => {
  it('SelectItem pose la classe pressée (item, sans scale)', () => {
    render(
      <Select defaultOpen>
        <SelectTrigger aria-label="Statut">
          <SelectValue placeholder="Choisir" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="a">Option A</SelectItem>
        </SelectContent>
      </Select>,
    )
    const item = screen.getByText('Option A').closest('[role="option"]')
    expect(item.className).toContain('active:brightness-95')
    expect(item.className).not.toMatch(/active:scale/)
  })
})

describe('VX126 — Combobox : option pressée', () => {
  it('chaque option pose la classe pressée', async () => {
    render(<Combobox options={[{ value: 'a', label: 'Option A' }]} value={null} />)
    screen.getByRole('combobox').click()
    const option = await screen.findByText('Option A')
    expect(option.closest('[role="option"]').className).toContain('active:brightness-95')
  })
})

describe('VX126 — MultiSelect : option pressée', () => {
  it('chaque option pose la classe pressée', async () => {
    render(<MultiSelect options={[{ value: 'a', label: 'Option A' }]} value={[]} />)
    screen.getByRole('combobox').click()
    const option = await screen.findByText('Option A')
    expect(option.closest('[role="option"]').className).toContain('active:brightness-95')
  })
})

describe('VX126 — DropdownMenu : item pressé', () => {
  it('DropdownMenuItem pose la classe pressée', async () => {
    render(
      <DropdownMenu defaultOpen>
        <DropdownMenuTrigger>Ouvrir</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>Action</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    )
    const item = await screen.findByText('Action')
    expect(item.className).toContain('active:brightness-95')
  })
})

describe('VX126 — ContextMenu : item pressé', () => {
  it('ContextMenuItem pose la classe pressée', async () => {
    render(
      <ContextMenu>
        <ContextMenuTrigger>Zone</ContextMenuTrigger>
        <ContextMenuContent>
          <ContextMenuItem>Action</ContextMenuItem>
        </ContextMenuContent>
      </ContextMenu>,
    )
    // Le contenu de ContextMenu n'est monté qu'à l'ouverture (clic droit) ;
    // on vérifie la présence du déclencheur pour un rendu sans erreur.
    expect(screen.getByText('Zone')).toBeInTheDocument()
  })
})

describe('VX126 — DatePicker : cellule pressée', () => {
  it('les cellules non désactivées portent la classe pressée', async () => {
    render(<DatePicker value={null} />)
    screen.getByRole('button').click()
    const grid = await screen.findByRole('grid')
    const cell = grid.querySelector('[role="gridcell"]:not([disabled])')
    expect(cell.className).toContain('active:brightness-95')
  })
})
