import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* WIR64 — écran admin des formulaires d'intake : liste + création. */

const list = vi.fn(() => Promise.resolve({ data: [
  { id: 1, nom: 'Pompage agricole', slug: 'pompage-agricole', tag_prefill: 'pompage', type_installation: 'agricole', actif: true },
] }))
const create = vi.fn(() => Promise.resolve({ data: { id: 2 } }))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (r) => (Array.isArray(r.data) ? r.data : (r.data?.results ?? [])),
    formulairesIntake: {
      list: (...a) => list(...a),
      create: (...a) => create(...a),
      lienPublic: (slug) => `/api/django/marketing/intake/${slug}/`,
    },
  },
}))

import FormulairesIntakeList from './FormulairesIntakeList'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('FormulairesIntakeList (WIR64)', () => {
  it('liste les formulaires existants avec leur lien public', async () => {
    render(<FormulairesIntakeList />)
    expect(await screen.findByText('Pompage agricole')).toBeInTheDocument()
    expect(screen.getByText('/api/django/marketing/intake/pompage-agricole/')).toBeInTheDocument()
  })

  it('crée un formulaire via l\'API', async () => {
    render(<FormulairesIntakeList />)
    await screen.findByText('Pompage agricole')
    fireEvent.change(screen.getByTestId('intake-nom'), { target: { value: 'Régularisation 82-21' } })
    fireEvent.change(screen.getByTestId('intake-slug'), { target: { value: 'regul-82-21' } })
    fireEvent.change(screen.getByTestId('intake-tag'), { target: { value: 'regul' } })
    fireEvent.click(screen.getByTestId('intake-creer'))

    await waitFor(() => expect(create).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Régularisation 82-21', slug: 'regul-82-21', tag_prefill: 'regul' }),
    ))
  })
})
