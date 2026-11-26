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

/* ACAL1733 — « En savoir plus » de la bande d'alertes de la coque : offert seulement s'il y a quelque chose à
   déplier (une seconde alerte repliée, un texte tronqué). Mutant : toujours rendre le bouton ⇒ échec. */
describe('ACAL1733 — BandeauAlertes : « En savoir plus » seulement avec quelque chose à déplier', () => {
  it('une seule alerte courte : pas de bouton ; deux alertes : le bouton déplie puis « Réduire »', async () => {
    const { BandeauAlertes } = await import('./coque/BandeauxCoque')
    const { rerender } = render(
      <BandeauAlertes><p className="sr-only">annonce</p><p>Conception rapide — à vérifier</p></BandeauAlertes>)
    expect(screen.queryByRole('button', { name: 'En savoir plus' })).toBeNull()
    rerender(<BandeauAlertes><p>Conception rapide — à vérifier</p><p>Le lead déclare : tuiles</p></BandeauAlertes>)
    const plus = screen.getByRole('button', { name: 'En savoir plus' })
    fireEvent.click(plus)
    expect(screen.getByRole('button', { name: 'Réduire' })).toHaveAttribute('aria-expanded', 'true')
  })

  it('ACAL1733 : un seul ResizeObserver pour le contenu, quel que soit le nombre de rendus, et il est déconnecté au démontage', async () => {
    const { BandeauAlertes } = await import('./coque/BandeauxCoque')
    const crees = []
    const original = globalThis.ResizeObserver
    globalThis.ResizeObserver = class {
      constructor() { this.observe = vi.fn(); this.disconnect = vi.fn(); crees.push(this) }
    }
    try {
      const { rerender, unmount } = render(<BandeauAlertes><p>Une alerte</p></BandeauAlertes>)
      const apresMontage = crees.length
      rerender(<BandeauAlertes><p>Une alerte</p><p>Une autre</p></BandeauAlertes>)
      rerender(<BandeauAlertes><p>Une alerte</p><p>Une autre</p><p>Encore</p></BandeauAlertes>)
      expect(crees.length).toBe(apresMontage) // aucun observateur de plus à chaque rendu
      unmount()
      crees.forEach((o) => expect(o.disconnect).toHaveBeenCalled())
    } finally {
      globalThis.ResizeObserver = original
    }
  })

  it('« (non vendue) » ne s’affiche plus : la cible estimée se dit « estimation »', async () => {
    const { libelleCibleEstimee } = await import('./contexteAtelier')
    const texte = libelleCibleEstimee({ source: 'factures', panneaux: 4, refus: null })
    expect(texte).toBe('Cible estimée depuis les factures du lead : 4 panneaux')
    expect(texte).not.toMatch(/non vendue/)
  })
})
