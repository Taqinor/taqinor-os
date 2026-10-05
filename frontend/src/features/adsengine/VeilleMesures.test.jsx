import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { documentContrat } from '../../test/fixtures/contractSamples'

/* VEIL33 — Panneau « Mesures ». Charge utile = contrat committé
   veille_mesures.json (PACT13) : ses valeurs `null` (taux de domaine, part de
   dropshippers) doivent s'afficher « non mesurable » + motif, jamais « 0 ». */

const MESURES = documentContrat('adsengine', 'veille_mesures').exemple

const mocks = vi.hoisted(() => ({ mesures: vi.fn() }))
vi.mock('./adsengineApi', () => ({ default: { veille: mocks } }))

import VeilleMesures from './VeilleMesures'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.mesures.mockResolvedValue({ data: MESURES })
})

describe('VeilleMesures', () => {
  it('valeurs null : « non mesurable » + motif, jamais 0', async () => {
    render(<VeilleMesures decouverteId={17} />)
    const domaine = await screen.findByTestId('ae-veille-mesures-domaine')
    expect(MESURES.taux_remplissage_domaine.valeur).toBeNull()
    expect(domaine.textContent).toContain('non mesurable')
    expect(domaine.textContent).toContain(MESURES.taux_remplissage_domaine.motif_fr)
    expect(domaine.textContent).not.toMatch(/\b0\s*%/)
    const drop = screen.getByTestId('ae-veille-mesures-dropshipper')
    expect(drop.textContent).toContain('non mesurable')
    expect(drop.textContent).not.toMatch(/\b0\s*%/)
    expect(mocks.mesures).toHaveBeenCalledWith(17)
  })

  it('valeurs mesurées affichées telles que servies', async () => {
    render(<VeilleMesures decouverteId={17} />)
    expect((await screen.findByTestId('ae-veille-mesures-rappel')).textContent)
      .toBe(`${MESURES.rappel_concurrents_nommes.trouves} / ${MESURES.rappel_concurrents_nommes.total}`)
    expect(screen.getByTestId('ae-veille-mesures-actives').textContent).toBe('62 %')
    expect(screen.getByTestId('ae-veille-mesures-ppa-moyenne').textContent).toBe('77,6')
  })

  it('sans découverte choisie : aucun appel', () => {
    render(<VeilleMesures />)
    expect(screen.getByTestId('ae-veille-mesures-vide')).toBeTruthy()
    expect(mocks.mesures).not.toHaveBeenCalled()
  })
})
