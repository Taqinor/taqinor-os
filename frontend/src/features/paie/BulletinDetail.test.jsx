import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR39 — le cycle de vie du bulletin (rectification, marquer payé,
   simulation what-if) était construit et testé côté backend
   (paieApi.rectifierBulletin/marquerPayeBulletin/simulationBulletin) sans
   AUCUN déclencheur dans BulletinDetail.jsx. On couvre les 3 chemins.
   Radix Select ne s'ouvre pas de façon fiable sous jsdom — pattern établi
   (pages/ventes/ListesPrixPage.test.jsx) : <select> natif à la place. */
vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children }) => (
      <select role="combobox" value={value}
        onChange={(e) => onValueChange(e.target.value)}>
        <option value="" />
        {children}
      </select>
    ),
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})

const BULLETIN = {
  id: 77, periode: 5, profil: 12, statut: 'valide', paye: false,
  personnes_a_charge: 1, brut: '8000.00', lignes: [],
}

vi.mock('../../api/paieApi', () => ({
  default: {
    getBulletin: vi.fn(() => Promise.resolve({ data: BULLETIN })),
    marquerPayeBulletin: vi.fn(() => Promise.resolve({ data: {} })),
    rectifierBulletin: vi.fn(() => Promise.resolve({
      data: { id: 88, net_a_payer: '7200.00' },
    })),
    simulationBulletin: vi.fn(() => Promise.resolve({
      data: { net_a_payer: 7100, ir: 320 },
    })),
    getPeriodes: vi.fn(() => Promise.resolve({
      data: [
        { id: 5, libelle: 'Juin 2026', mois: 6, annee: 2026 },
        { id: 6, libelle: 'Juillet 2026', mois: 7, annee: 2026 },
      ],
    })),
  },
}))

import paieApi from '../../api/paieApi'
import BulletinDetail from './BulletinDetail.jsx'

function renderAt(id = '77') {
  return render(
    <MemoryRouter initialEntries={[`/paie/bulletins/${id}`]}>
      <ThemeProvider>
        <Routes>
          <Route path="/paie/bulletins/:id" element={<BulletinDetail />} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('BulletinDetail — cycle de vie du bulletin (WIR39)', () => {
  beforeEach(() => {
    paieApi.getBulletin.mockClear()
    paieApi.getBulletin.mockResolvedValue({ data: BULLETIN })
    paieApi.marquerPayeBulletin.mockClear()
    paieApi.rectifierBulletin.mockClear()
    paieApi.simulationBulletin.mockClear()
  })

  it('marquer payé appelle marquerPayeBulletin et recharge le bulletin', async () => {
    renderAt()
    await userEvent.click(await screen.findByRole('button', { name: /Marquer payé/i }))
    await waitFor(() => expect(paieApi.marquerPayeBulletin).toHaveBeenCalledWith('77'))
  })

  it('rectifier crée un bulletin rectificatif sur une période cible différente',
    async () => {
      renderAt()
      await userEvent.click(await screen.findByRole('button', { name: /Rectifier/i }))

      const dialog = await screen.findByRole('dialog')
      const [natureSelect, periodeSelect] = within(dialog).getAllByRole('combobox')
      // La période d'origine (5) n'est jamais proposée comme cible.
      expect(within(dialog).queryByText('Juin 2026')).not.toBeInTheDocument()
      await userEvent.selectOptions(periodeSelect, '6')
      await userEvent.selectOptions(natureSelect, 'rectificatif')

      await userEvent.click(within(dialog).getByRole('button', { name: 'Rectifier' }))

      await waitFor(() => expect(paieApi.rectifierBulletin).toHaveBeenCalledWith(
        '77', expect.objectContaining({
          periode_cible: 6, type_bulletin: 'rectificatif',
        })))
    })

  it('la simulation what-if appelle simulationBulletin sans modifier le bulletin réel',
    async () => {
      renderAt()
      await userEvent.click(await screen.findByRole('tab', { name: 'Simulation' }))
      await userEvent.click(await screen.findByRole('button', { name: 'Simuler' }))

      await waitFor(() => expect(paieApi.simulationBulletin).toHaveBeenCalledWith(
        12, expect.objectContaining({ periode: 5, prime: '0' })))
      expect(await screen.findByText('net_a_payer')).toBeInTheDocument()
      // Le bulletin réel n'est jamais re-fetché par la simulation.
      expect(paieApi.getBulletin).toHaveBeenCalledTimes(1)
    })
})
