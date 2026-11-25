import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* T4-X8-017 — « Assigner à » ne propose que les comptes qui peuvent OUVRIR une
   visite : la liste vient du sélecteur de collègues filtré côté serveur sur
   `visites_voir` (`apps/crm/collegues.py::filtrer_par_permission`, le prédicat
   du viewset des visites), plus de l'annuaire `/users/` entier. */

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: { get: (...a) => get(...a), post: vi.fn() } }))

import PlanifierVisitePage from './PlanifierVisitePage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PlanifierVisitePage — T4-X8-017', () => {
  it('lit les assignables filtrés sur visites_voir, jamais /users/', async () => {
    get.mockResolvedValue({ data: [{ id: 7, username: 'tech', first_name: 'Karim' }] })
    render(<MemoryRouter><PlanifierVisitePage /></MemoryRouter>)
    await waitFor(() => expect(get).toHaveBeenCalled())
    const [url, config] = get.mock.calls[0]
    expect(url).toBe('/crm/assignable-users/')
    expect(config.params).toEqual({ permission: 'visites_voir' })
    expect(get.mock.calls.map((c) => c[0])).not.toContain('/users/')
  })
})
