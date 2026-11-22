/* ACAL1007 — le bandeau « Conception rapide » lit le détail SERVI, affirmé sur l'échantillon
   COMMITTÉ `calepinage_detail.json` (ACAL1005) : `exemple_rapide` l'affiche avec son motif et
   « J'ai vérifié le toit » appelle l'enregistrement ; `exemple` (`complet`) n'affiche rien ; après
   l'enregistrement, le détail relu `complet` le fait disparaître. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { get: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import BandeauConceptionRapide from './BandeauConceptionRapide'

const COMPLET = exempleContrat('calepinage', 'calepinage_detail')
const RAPIDE = { ...COMPLET, ...exempleContrat('calepinage', 'calepinage_detail', 'exemple_rapide') }

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('BandeauConceptionRapide', () => {
  it('calepinage rapide : bandeau, motif servi, et « J’ai vérifié le toit » enregistre', async () => {
    calepinageApi.calepinages.get.mockResolvedValue({ data: RAPIDE })
    const onVerifier = vi.fn().mockResolvedValue(true)
    render(<BandeauConceptionRapide calepinageId={7} onVerifier={onVerifier} rechargerLe={null} />)

    const bandeau = await screen.findByTestId('cal-conception-rapide')
    expect(bandeau).toHaveTextContent('Conception rapide — à vérifier sur place')
    expect(bandeau).toHaveTextContent(RAPIDE.etat_conception_motif)
    fireEvent.click(screen.getByTestId('cal-conception-rapide-verifier'))
    await waitFor(() => expect(onVerifier).toHaveBeenCalledTimes(1))
    expect(calepinageApi.calepinages.get).toHaveBeenCalledWith(7)
  })

  it('calepinage complet : rien', async () => {
    calepinageApi.calepinages.get.mockResolvedValue({ data: COMPLET })
    render(<BandeauConceptionRapide calepinageId={7} onVerifier={vi.fn()} rechargerLe={null} />)
    await waitFor(() => expect(calepinageApi.calepinages.get).toHaveBeenCalled())
    expect(screen.queryByTestId('cal-conception-rapide')).toBeNull()
  })

  it('après l’enregistrement, le détail relu « complet » le fait disparaître', async () => {
    calepinageApi.calepinages.get.mockResolvedValueOnce({ data: RAPIDE })
    const { rerender } = render(
      <BandeauConceptionRapide calepinageId={7} onVerifier={vi.fn()} rechargerLe={null} />)
    await screen.findByTestId('cal-conception-rapide')

    calepinageApi.calepinages.get.mockResolvedValueOnce({ data: COMPLET })
    rerender(<BandeauConceptionRapide calepinageId={7} onVerifier={vi.fn()} rechargerLe="2026-11-22T10:00:00Z" />)
    await waitFor(() => expect(screen.queryByTestId('cal-conception-rapide')).toBeNull())
  })

  it('lecture seule (aucun enregistreur) : le bandeau sans bouton', async () => {
    calepinageApi.calepinages.get.mockResolvedValue({ data: RAPIDE })
    render(<BandeauConceptionRapide calepinageId={7} onVerifier={null} rechargerLe={null} />)
    await screen.findByTestId('cal-conception-rapide')
    expect(screen.queryByTestId('cal-conception-rapide-verifier')).toBeNull()
  })
})
