import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { formatMAD, formatNumber, formatPercent } from '../../lib/format'

/* PV76 — Carte « Étude bancable » de la fiche devis.

   PACT13 : la charge utile n'est PAS tapée à la main. Elle vient de l'exemple
   COMMITTÉ dans l'app (`apps/ventes/contract_samples/simulation.json`), le
   même fichier que `scripts/check_api_shapes.py` compare à la charge RÉELLE
   posée par `apps.ventes.etude` / la tâche PV74. Si le serveur change de
   forme, l'exemple change et ce test casse tout seul. Les valeurs affichées
   sont comparées au résultat des MÊMES helpers de formatage que le composant
   (`lib/format.js`), jamais à une chaîne recopiée à la main. */

vi.mock('../../api/ventesApi', () => ({
  default: {
    simulerEtudeDevis: vi.fn(),
    getSimulationStatus: vi.fn(),
  },
}))

import ventesApi from '../../api/ventesApi'
import EtudeBancable from './EtudeBancable'

const SIMULATION = exempleContrat('ventes', 'simulation').simulation

const devisAvecEtude = { id: 5, reference: 'DEV-5', etude_params: { simulation: SIMULATION } }
const devisSansEtude = { id: 6, reference: 'DEV-6', etude_params: {} }

// `Intl.NumberFormat('fr-FR')` groupe les milliers avec une espace fine
// insécable (U+202F) ; le normaliseur PAR DÉFAUT de testing-library la
// collapse en espace ASCII avant comparaison — on applique la MÊME
// normalisation à la chaîne attendue pour comparer des égaux.
const norm = (s) => s.replace(/\s+/g, ' ').trim()

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('EtudeBancable (PV76) — état vide', () => {
  it('sans simulation : invite à LANCER, jamais de carte de chiffres', () => {
    render(<EtudeBancable devis={devisSansEtude} onRefresh={vi.fn()} />)
    expect(screen.getByText('Aucune étude bancable pour ce devis.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Lancer la simulation/ })).toBeInTheDocument()
    expect(screen.queryByText('Étude bancable')).not.toBeInTheDocument()
  })
})

describe('EtudeBancable (PV76) — carte lecture seule', () => {
  it('rend P50/P90/PR/payback/VAN/TRI + la cascade des pertes depuis le contrat PACT10', () => {
    render(<EtudeBancable devis={devisAvecEtude} onRefresh={vi.fn()} />)

    expect(screen.getByText('Étude bancable')).toBeInTheDocument()
    expect(screen.getByText('P50')).toBeInTheDocument()
    expect(screen.getByText(
      norm(`${formatNumber(SIMULATION.pr.p50_kwh, { decimals: 0 })} kWh`)))
      .toBeInTheDocument()
    expect(screen.getByText(
      norm(`${formatNumber(SIMULATION.pr.p90_kwh, { decimals: 0 })} kWh`)))
      .toBeInTheDocument()
    expect(screen.getByText(
      formatPercent(SIMULATION.pr.performance_ratio * 100, { decimals: 1 })))
      .toBeInTheDocument()
    expect(screen.getByText(`${SIMULATION.projection_25y.payback_year} ans`))
      .toBeInTheDocument()
    expect(screen.getByText(norm(formatMAD(SIMULATION.projection_25y.npv, { decimals: 0 }))))
      .toBeInTheDocument()
    expect(screen.getByText(
      formatPercent(SIMULATION.projection_25y.irr * 100, { decimals: 1 })))
      .toBeInTheDocument()

    // Mini-cascade des pertes : un libellé FR par clé du contrat, jamais la
    // clé technique anglaise brute affichée à l'écran.
    expect(screen.getByText('Température')).toBeInTheDocument()
    expect(screen.getByText(
      formatPercent(SIMULATION.pr.loss_breakdown.temperature, { decimals: 1 })))
      .toBeInTheDocument()
    expect(screen.queryByText('temperature')).not.toBeInTheDocument()
  })

  it('« Recalculer l\'étude » relance PV74 (202 + jeton) puis rafraîchit au statut ready', async () => {
    vi.useFakeTimers()
    try {
      ventesApi.simulerEtudeDevis.mockResolvedValue(
        { data: { job_id: 'tok123', status: 'pending', zones: 1 } })
      ventesApi.getSimulationStatus.mockResolvedValue(
        { data: { status: 'ready', simulation: SIMULATION } })
      const onRefresh = vi.fn()
      render(<EtudeBancable devis={devisAvecEtude} onRefresh={onRefresh} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Recalculer l'étude/ }))
        await Promise.resolve()
      })
      expect(ventesApi.simulerEtudeDevis).toHaveBeenCalledWith(devisAvecEtude.id)

      await act(async () => {
        vi.advanceTimersByTime(3000)
        await Promise.resolve()
        await Promise.resolve()
      })

      expect(ventesApi.getSimulationStatus).toHaveBeenCalledWith(devisAvecEtude.id, 'tok123')
      expect(onRefresh).toHaveBeenCalledTimes(1)
    } finally {
      vi.useRealTimers()
    }
  })
})
