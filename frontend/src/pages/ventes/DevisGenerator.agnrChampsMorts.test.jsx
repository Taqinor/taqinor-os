// AGNR26 — le champ mort « Heures de pompage effectives / jour » n'est plus
// rendu (plus rien ne le lisait depuis AGR114/AGR130) ; un brouillon ancien
// qui le porte se restaure sans erreur.
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrChampsMorts.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, fireEvent, screen } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable, reprendreBrouillon } from './DevisGeneratorGoldenHarnais'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

cycleEcran({ date: DATE_FIGEE })

describe('AGNR26 — champ « Heures de pompage » retiré', () => {
  it('générateur agricole : aucun #gen-heures', async () => {
    const vue = await monter('/ventes/devis/nouveau')
    await attendreStable(vue.container, act)
    await act(async () => { fireEvent.click(await screen.findByRole('radio', { name: /Agricole/ })) })
    await attendreStable(vue.container, act)
    expect(document.getElementById('gen-hmt')).not.toBeNull()
    expect(document.getElementById('gen-heures')).toBeNull()
    expect(document.body.textContent).not.toMatch(/Heures de pompage effectives/)
  }, 60000)

  it('un brouillon ancien portant `pompeHeures` se restaure sans erreur', async () => {
    window.localStorage.setItem('taqinor:draft:devis:new', JSON.stringify({
      savedAt: '2026-10-07T10:00:00Z',
      data: { pompeHeures: '9', note: 'Brouillon ancien' },
    }))
    const vue = await monter('/ventes/devis/nouveau')
    await reprendreBrouillon(vue)
    expect(document.querySelector('textarea[placeholder^="Conditions particulières"]')?.value)
      .toBe('Brouillon ancien')
    expect(document.getElementById('gen-heures')).toBeNull()
  }, 60000)
})
