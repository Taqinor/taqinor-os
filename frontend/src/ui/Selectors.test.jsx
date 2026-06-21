import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Select, SelectContent, SelectTrigger, SelectValue, SelectItem } from './Select'
import { Combobox } from './Combobox'
import { MultiSelect } from './MultiSelect'

/* G126 — États de chargement / erreur des sélecteurs. */
describe('G126 — Select : état de chargement', () => {
  it('affiche un spinner/squelette pendant un chargement asynchrone', () => {
    render(
      <Select defaultOpen>
        <SelectTrigger aria-label="Statut">
          <SelectValue placeholder="Choisir" />
        </SelectTrigger>
        <SelectContent loading loadingText="Chargement…">
          <SelectItem value="a">A</SelectItem>
        </SelectContent>
      </Select>,
    )
    // L'état chargement est annoncé (role status) et l'item n'est pas rendu.
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getAllByText('Chargement…').length).toBeGreaterThan(0)
    expect(screen.queryByText('A')).not.toBeInTheDocument()
  })

  it('rend les options quand loading=false', () => {
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
    expect(screen.getByText('Option A')).toBeInTheDocument()
  })
})

describe('G126 — Combobox : ligne d’erreur explicite', () => {
  it('affiche une erreur (role alert) au lieu d’un silence « Aucun résultat »', async () => {
    const onSearch = () => Promise.reject(new Error('Réseau indisponible'))
    render(<Combobox onSearch={onSearch} value={null} />)
    await userEvent.click(screen.getByRole('combobox'))
    await waitFor(() => {
      const alert = screen.getByRole('alert')
      expect(alert).toHaveTextContent('Réseau indisponible')
    })
    expect(screen.queryByText('Aucun résultat')).not.toBeInTheDocument()
  })
})

describe('G126 — MultiSelect : ligne d’erreur explicite', () => {
  it('affiche une erreur (role alert) en cas d’échec de recherche', async () => {
    const onSearch = () => Promise.reject(new Error('Réseau indisponible'))
    render(<MultiSelect onSearch={onSearch} value={[]} />)
    await userEvent.click(screen.getByRole('combobox'))
    await waitFor(() => {
      const alert = screen.getByRole('alert')
      expect(alert).toHaveTextContent('Réseau indisponible')
    })
    expect(screen.queryByText('Aucun résultat')).not.toBeInTheDocument()
  })
})
