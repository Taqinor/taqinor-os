import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import CalibrationRevisions from './CalibrationRevisions.jsx'

/* NTHCM6 — écran « Calibration des révisions ». PACT10 : la charge utile vient
   de l'exemple committé `apps/rh/contract_samples/calibration_revisions.json`,
   le même fichier que `scripts/check_api_shapes.py` compare au dictionnaire
   réellement renvoyé par `CycleRevisionSalarialeViewSet.calibration`. */

const CONTRAT = exempleContrat('rh', 'calibration_revisions')
const CYCLE = CONTRAT.cycle

vi.mock('../../api/rhApi', () => ({
  default: {
    getCyclesRevision: vi.fn(),
    getCalibrationCycle: vi.fn(),
    validerCalibrationCycle: vi.fn(),
  },
}))

function renderEcran() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <CalibrationRevisions />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

async function choisirLeCycle() {
  renderEcran()
  await screen.findByLabelText('Cycle de révision')
  fireEvent.change(screen.getByLabelText('Cycle de révision'),
    { target: { value: String(CYCLE.id) } })
}

describe('CalibrationRevisions (NTHCM6)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    rhApi.getCyclesRevision.mockResolvedValue({
      data: [{ id: CYCLE.id, libelle: CYCLE.libelle }],
    })
  })

  it('n’interroge pas la calibration tant qu’aucun cycle n’est choisi', async () => {
    renderEcran()
    await screen.findByLabelText('Cycle de révision')
    expect(rhApi.getCalibrationCycle).not.toHaveBeenCalled()
  })

  it('affiche toutes les propositions et l’enveloppe par manager', async () => {
    rhApi.getCalibrationCycle.mockResolvedValue(
      reponseContrat('rh', 'calibration_revisions'))
    await choisirLeCycle()

    expect(await screen.findByText(String(CONTRAT.nb_propositions)))
      .toBeTruthy()
    for (const proposition of CONTRAT.propositions) {
      expect(screen.getAllByText(proposition.employe).length)
        .toBeGreaterThan(0)
    }
    const manager = CONTRAT.par_manager[0]
    expect(screen.getAllByText(manager.manager).length).toBeGreaterThan(0)
    expect(rhApi.getCalibrationCycle)
      .toHaveBeenCalledWith(String(CYCLE.id))
  })

  it('rend la distribution telle que le serveur l’a agrégée', async () => {
    rhApi.getCalibrationCycle.mockResolvedValue(
      reponseContrat('rh', 'calibration_revisions'))
    await choisirLeCycle()

    expect(await screen.findByText('Distribution des augmentations'))
      .toBeTruthy()
    // Une ligne par tranche du vocabulaire FERMÉ servi — l'écran n'en
    // invente ni n'en retire aucune.
    for (const tranche of CONTRAT.distribution) {
      expect(screen.getByText(`${tranche.tranche} %`)).toBeTruthy()
    }
  })

  it('valide la calibration et recharge le cycle figé', async () => {
    rhApi.getCalibrationCycle.mockResolvedValue(
      reponseContrat('rh', 'calibration_revisions'))
    rhApi.validerCalibrationCycle.mockResolvedValue({ data: {} })
    await choisirLeCycle()
    await screen.findByText(String(CONTRAT.nb_propositions))

    rhApi.getCalibrationCycle.mockResolvedValue(
      reponseContrat('rh', 'calibration_revisions', 'exemple_vide'))
    fireEvent.click(screen.getByRole('button', {
      name: /Valider la calibration/,
    }))

    await waitFor(() => {
      expect(rhApi.validerCalibrationCycle)
        .toHaveBeenCalledWith(String(CYCLE.id))
    })
    expect(await screen.findByText(/Cycle déjà figé/)).toBeTruthy()
  })

  it('désactive la validation quand le cycle est déjà clos', async () => {
    rhApi.getCalibrationCycle.mockResolvedValue(
      reponseContrat('rh', 'calibration_revisions', 'exemple_vide'))
    await choisirLeCycle()

    const bouton = await screen.findByRole('button', {
      name: /Cycle déjà figé/,
    })
    expect(bouton.disabled).toBe(true)
    expect(screen.getByText(/les décisions sont figées/)).toBeTruthy()
  })
})
