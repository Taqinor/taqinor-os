import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* AUDV21/XFLT10 — la création d'une visite technique propose la prochaine
   date NARSA (périodicité légale par type fiscal) dès qu'un actif véhicule
   est choisi, sans jamais écraser une date déjà saisie à la main. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const proposerDateNarsa = vi.fn(() => Promise.resolve({ data: { date_proposee: '2027-03-15' } }))
const visitesCreate = vi.fn(() => Promise.resolve({ data: { id: 1 } }))

vi.mock('../../../api/flotteApi', () => ({
  default: {
    visitesTechniques: {
      proposerDateNarsa: (...args) => proposerDateNarsa(...args),
      create: (...args) => visitesCreate(...args),
    },
  },
}))

import VisiteTechniqueDialog from './VisiteTechniqueDialog'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(<ThemeProvider>{ui}</ThemeProvider>)
}

const ACTIFS = [
  { id: 5, label: 'Véhicule 12345-A-6' },
  { id: 8, label: 'Nacelle Genie Z-45' },
]

describe('VisiteTechniqueDialog — proposition de date NARSA (AUDV21)', () => {
  it('propose la date NARSA à la sélection d’un actif et pré-remplit "Prochaine visite"', async () => {
    const user = userEvent.setup()
    withProviders(<VisiteTechniqueDialog actifs={ACTIFS} onClose={() => {}} onSaved={() => {}} />)

    await user.selectOptions(screen.getByLabelText('Actif (véhicule ou engin)'), '5')

    await waitFor(() => expect(proposerDateNarsa).toHaveBeenCalledWith('5'))
    await waitFor(() => expect(screen.getByLabelText('Prochaine visite')).toHaveValue('2027-03-15'))
    expect(screen.getByText(/Date NARSA proposée/)).toBeInTheDocument()
  })

  it('n’écrase jamais une date "Prochaine visite" déjà saisie à la main pendant que la proposition arrive', async () => {
    // Race : l'utilisateur tape SA date avant que l'appel réseau ne résolve.
    let resolveProposition
    proposerDateNarsa.mockReturnValueOnce(new Promise((resolve) => { resolveProposition = resolve }))
    const user = userEvent.setup()
    withProviders(<VisiteTechniqueDialog actifs={ACTIFS} onClose={() => {}} onSaved={() => {}} />)

    await user.selectOptions(screen.getByLabelText('Actif (véhicule ou engin)'), '5')
    await waitFor(() => expect(proposerDateNarsa).toHaveBeenCalledWith('5'))

    const champProchaine = screen.getByLabelText('Prochaine visite')
    await user.type(champProchaine, '2027-06-01')
    expect(champProchaine).toHaveValue('2027-06-01')

    // La proposition réseau arrive APRÈS la saisie manuelle : elle ne doit
    // jamais écraser la valeur déjà tapée par l'utilisateur.
    resolveProposition({ data: { date_proposee: '2027-03-15' } })
    await waitFor(() => expect(proposerDateNarsa).toHaveBeenCalledTimes(1))
    expect(champProchaine).toHaveValue('2027-06-01')
  })

  it('envoie actif_flotte/centre/date_visite/date_prochaine à la création', async () => {
    const user = userEvent.setup()
    withProviders(<VisiteTechniqueDialog actifs={ACTIFS} onClose={() => {}} onSaved={() => {}} />)

    await user.selectOptions(screen.getByLabelText('Actif (véhicule ou engin)'), '5')
    await waitFor(() => expect(screen.getByLabelText('Prochaine visite')).toHaveValue('2027-03-15'))
    await user.type(screen.getByLabelText('Centre de visite'), 'CT Casablanca')
    await user.type(screen.getByLabelText('Date de la visite'), '2026-03-15')

    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(visitesCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        actif_flotte: 5,
        centre: 'CT Casablanca',
        date_visite: '2026-03-15',
        date_prochaine: '2027-03-15',
      }),
    ))
  })

  it('reste silencieux (aucune proposition) quand l’actif est un engin', async () => {
    proposerDateNarsa.mockResolvedValueOnce({ data: { date_proposee: null } })
    const user = userEvent.setup()
    withProviders(<VisiteTechniqueDialog actifs={ACTIFS} onClose={() => {}} onSaved={() => {}} />)

    await user.selectOptions(screen.getByLabelText('Actif (véhicule ou engin)'), '8')

    await waitFor(() => expect(proposerDateNarsa).toHaveBeenCalledWith('8'))
    expect(screen.getByLabelText('Prochaine visite')).toHaveValue('')
    expect(screen.queryByText(/Date NARSA proposée/)).not.toBeInTheDocument()
  })
})
