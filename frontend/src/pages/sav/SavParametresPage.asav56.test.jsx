import { describe, it, expect, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// ASAV56 — réglages SLA honnêtes : libellé selon D-ASAV-5 (Q2 a), éditeur du
// SLA par priorité et des horaires ouvrés. Faux serveur qui applique
// POST /sav/sla-settings/ (upsert du singleton) et le relit.

const serveur = vi.hoisted(() => ({ reglages: {
  sla_response_days: 1, sla_resolution_days: 7, sla_par_priorite: null,
  sla_breach_enabled: false, sla_heures_ouvrees_actif: false, horaires_ouvres: null,
}, posts: [] }))

vi.mock('../../api/savApi', () => ({
  default: new Proxy({}, { get: () => () => Promise.resolve({ data: [] }) }),
}))
vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn((url) => Promise.resolve({
      data: url === '/sav/sla-settings/' ? { ...serveur.reglages } : [] })),
    post: vi.fn((url, corps) => {
      serveur.posts.push(corps)
      serveur.reglages = { ...serveur.reglages, ...corps }
      return Promise.resolve({ data: { ...serveur.reglages } })
    }),
  },
}))

import SavParametresPage from './SavParametresPage'

const monter = () => render(<MemoryRouter><ThemeProvider><SavParametresPage /></ThemeProvider></MemoryRouter>)
const ouvrirSla = async (user) => {
  await user.click(screen.getByRole('tab', { name: 'SLA / Automatisation' }))
  await screen.findByText(/SLA par priorité/)
}

describe('SavParametresPage — ASAV56 réglages SLA', () => {
  it('libellé D-ASAV-5, SLA par priorité et horaires enregistrés puis relus', async () => {
    const user = userEvent.setup()
    monter()
    await ouvrirSla(user)
    expect(screen.getByText(/le SLA reste toujours calculé et affiché/)).toBeInTheDocument()

    await user.click(screen.getByRole('switch', { name: 'Décompter le SLA en heures ouvrées' }))
    fireEvent.change(screen.getByLabelText('Urgente — résolution (jours)'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Urgente — résolution (heures ouvrées)'), { target: { value: '4' } })
    fireEvent.change(screen.getByLabelText('Haute — résolution (jours)'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText('Fin des horaires ouvrés'), { target: { value: '17:00' } })
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(serveur.posts).toHaveLength(1))
    expect(serveur.reglages.sla_par_priorite).toEqual({
      urgente: { resolution: 1, resolution_heures: 4 }, haute: { resolution: 3 } })
    expect(serveur.reglages.sla_heures_ouvrees_actif).toBe(true)
    expect(serveur.reglages.horaires_ouvres).toMatchObject({ fin: '17:00', debut: '08:00' })

    // Recharger la page : valeurs relues du serveur.
    cleanup()
    monter()
    await ouvrirSla(user)
    expect(screen.getByLabelText('Urgente — résolution (jours)')).toHaveValue(1)
    expect(screen.getByLabelText('Haute — résolution (jours)')).toHaveValue(3)
    expect(screen.getByLabelText('Fin des horaires ouvrés')).toHaveValue('17:00')
  }, 90000)

  it('le champ heures ouvrées n\'est proposé qu\'avec l\'interrupteur', async () => {
    const user = userEvent.setup()
    serveur.reglages.sla_heures_ouvrees_actif = false
    monter()
    await ouvrirSla(user)
    expect(screen.queryByLabelText('Urgente — résolution (heures ouvrées)')).toBeNull()
    expect(screen.getByLabelText('Début des horaires ouvrés')).toBeInTheDocument()
  }, 60000)
})
