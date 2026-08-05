import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('./entitesApi', () => ({
  default: {
    mesEntites: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

import entitesApi from './entitesApi'
import EntiteSwitcher from './EntiteSwitcher'
import { CLE_ENTITE_ACTIVE, lireEntiteActive } from '../../lib/entiteActive'

const DEUX_ENTITES = [
  { id: 7, code: 'FA', nom: 'Filiale A' },
  { id: 9, code: 'FB', nom: 'Filiale B' },
]

describe('EntiteSwitcher (NTADM26)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.removeItem(CLE_ENTITE_ACTIVE)
  })

  it("ne s'affiche pas avec une seule entité accessible", async () => {
    entitesApi.mesEntites.mockResolvedValueOnce({
      data: [{ id: 7, code: 'FA', nom: 'Filiale A' }],
    })
    const { container } = render(<EntiteSwitcher />)
    await waitFor(() => expect(entitesApi.mesEntites).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it("s'affiche à partir de deux entités, « Toutes » par défaut", async () => {
    entitesApi.mesEntites.mockResolvedValueOnce({ data: DEUX_ENTITES })
    render(<EntiteSwitcher />)
    const select = await screen.findByLabelText("Changer d'entité affichée")
    expect(select.value).toBe('')
    expect(screen.getByText('Filiale A')).toBeInTheDocument()
    expect(screen.getByText('Filiale B')).toBeInTheDocument()
  })

  it('mémorise l\'entité choisie', async () => {
    entitesApi.mesEntites.mockResolvedValueOnce({ data: DEUX_ENTITES })
    render(<EntiteSwitcher />)
    const select = await screen.findByLabelText("Changer d'entité affichée")
    fireEvent.change(select, { target: { value: '9' } })
    await waitFor(() => expect(lireEntiteActive()).toBe(9))
    expect(select.value).toBe('9')
  })

  it('revient à « Toutes les entités »', async () => {
    entitesApi.mesEntites.mockResolvedValueOnce({ data: DEUX_ENTITES })
    render(<EntiteSwitcher />)
    const select = await screen.findByLabelText("Changer d'entité affichée")
    fireEvent.change(select, { target: { value: '9' } })
    await waitFor(() => expect(lireEntiteActive()).toBe(9))
    fireEvent.change(select, { target: { value: '' } })
    await waitFor(() => expect(lireEntiteActive()).toBeNull())
  })

  it('reste silencieux quand le référentiel est inaccessible', async () => {
    entitesApi.mesEntites.mockRejectedValueOnce(new Error('403'))
    const { container } = render(<EntiteSwitcher />)
    await waitFor(() => expect(entitesApi.mesEntites).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
