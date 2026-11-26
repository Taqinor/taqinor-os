/* Nouveau fichier car : `ResumeAtelier.jsx` n'avait aucun module de test (seul `e2eHooks.test.mjs` cite son hook).
   R5B-N2 (rejeu du 26/11) — la feuille « Avancé » résumait « 5 panneaux · 3,55 kWc · — » (le pan de toit seul) pendant que la
   barre disait « 49 panneaux · 34,79 kWc » (toit + champ au sol + ombrière) : un seul compte pour tout le calepinage. */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

vi.mock('./simulationFraiche', () => ({ useSimulationFraiche: () => null }))

const { default: ResumeAtelier } = await import('./ResumeAtelier')

afterEach(cleanup)

const DOCUMENT = {
  result: { panels: 5, kwc: 3.55 },
  zones: [{ id: 'z1', vertices: [[0, 0], [1, 0], [1, 1]], geometry: { count: 5, kwc: 3.55 } }],
  poseSurfaces: [
    { kind: 'sol', id: 's1', moduleWc: 710, engine: { modules: 28 } },
    { kind: 'ombriere', id: 'o1', moduleWc: 710, engine: { modules: 16 } },
  ],
}

describe('ResumeAtelier — un seul compte pour tout le calepinage (R5B-N2)', () => {
  it('toit 5 + sol 28 + ombrière 16 : « 49 panneaux · 34,79 kWc », jamais le pan seul', () => {
    render(<ResumeAtelier calepinageId={2} lireLayout={() => DOCUMENT} />)
    expect(screen.getByTestId('cal-resume-panneaux')).toHaveTextContent('49 panneaux')
    expect(screen.getByTestId('cal-resume-kwc').textContent.replace(/\s/g, ' ')).toBe('34,79 kWc')
  })

  it('aucune pose comptée sur le document : le `result` servi, comme avant', () => {
    render(<ResumeAtelier calepinageId={2} lireLayout={() => ({ result: { panels: 5, kwc: 3.55 } })} />)
    expect(screen.getByTestId('cal-resume-panneaux')).toHaveTextContent('5 panneaux')
  })
})
