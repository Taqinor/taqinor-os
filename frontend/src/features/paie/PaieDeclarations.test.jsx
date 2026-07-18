import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR37 — `paieApi.journalDePaie`/`journalVentile` (écriture OD équilibrée
   du journal de paie, apps/paie/services.py:journal_de_paie, via
   compta.services) étaient construits sans déclencheur UI. On couvre le
   bouton « Passer l'écriture comptable » de l'onglet Charges & GL : garde
   sans période choisie, puis passage réel avec confirmation de la
   référence renvoyée par le serveur.
   Radix Select ne s'ouvre pas de façon fiable sous jsdom (portail + pointer
   events) — pattern établi (pages/ventes/ListesPrixPage.test.jsx,
   pages/monitoring/ClientPortalPage.test.jsx) : remplacer les primitives
   Select par un <select> natif pour piloter le choix, le reste de
   `../../ui` reste réel. */
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

vi.mock('../../api/paieApi', () => ({
  default: {
    getPeriodes: vi.fn(() => Promise.resolve({
      data: [{ id: 3, libelle: 'Juillet 2026', mois: 7, annee: 2026 }],
    })),
    journalDePaie: vi.fn(() => Promise.resolve({
      data: { ecriture_id: 91, reference: 'PAIE-2026-07' },
    })),
    journalVentile: vi.fn(() => Promise.resolve({
      data: { id: 92, reference: 'PAIE-2026-07-V' },
    })),
  },
}))

import paieApi from '../../api/paieApi'
import PaieDeclarations from './PaieDeclarations.jsx'

function wrap(ui) {
  return render(
    <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>,
  )
}

describe('PaieDeclarations — Charges & GL (WIR37, journal de paie → comptabilité)', () => {
  beforeEach(() => { paieApi.journalDePaie.mockClear() })

  it('refuse de passer l’écriture sans période choisie', async () => {
    wrap(<PaieDeclarations />)
    await userEvent.click(screen.getByRole('tab', { name: 'Charges & GL' }))
    await userEvent.click(
      await screen.findByRole('button', { name: 'Passer l’écriture comptable' }))
    expect(paieApi.journalDePaie).not.toHaveBeenCalled()
  })

  it('passe l’écriture comptable de la période sélectionnée et affiche la référence',
    async () => {
      wrap(<PaieDeclarations />)
      await userEvent.click(screen.getByRole('tab', { name: 'Charges & GL' }))

      const select = await screen.findByRole('combobox')
      await userEvent.selectOptions(select, '3')

      await userEvent.click(
        screen.getByRole('button', { name: 'Passer l’écriture comptable' }))

      await waitFor(() => expect(paieApi.journalDePaie).toHaveBeenCalledWith(3))
      expect(await screen.findByText(/PAIE-2026-07/)).toBeInTheDocument()
    })
})
