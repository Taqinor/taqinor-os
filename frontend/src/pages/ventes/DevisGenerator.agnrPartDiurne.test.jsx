// AGNR44 / D-AGNR-2 (a) — le curseur « Consommation diurne (%) » (aperçu local
// seulement, jamais enregistré ni relu) est retiré : le repli local prend la
// part diurne par défaut du marché et le dit. Un ancien brouillon portant
// `dayUsage` se restaure sans erreur.
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrPartDiurne.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, screen } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable, reprendreBrouillon } from './DevisGeneratorGoldenHarnais'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

cycleEcran({ date: DATE_FIGEE })

describe('AGNR44 — curseur « Consommation diurne » retiré', () => {
  it('résidentiel : aucun curseur, la mention « hypothèse par défaut » est là', async () => {
    const vue = await monter('/ventes/devis/nouveau')
    await attendreStable(vue.container, act)
    expect(screen.queryByTestId('curseur-part-diurne')).toBeNull()
    expect(document.body.textContent).not.toMatch(/Consommation diurne \(%\)/)
    expect(document.querySelector('input[type="range"][min="10"][max="100"]')).toBeNull()
    const mention = screen.getByTestId('part-diurne-defaut')
    expect(mention.textContent).toMatch(/hypothèse par défaut/)
  }, 60000)

  it('un brouillon ancien portant `dayUsage` se restaure sans erreur', async () => {
    window.localStorage.setItem('taqinor:draft:devis:new', JSON.stringify({
      savedAt: '2026-10-07T10:00:00Z',
      data: { dayUsage: '90', note: 'Brouillon ancien' },
    }))
    const vue = await monter('/ventes/devis/nouveau')
    await reprendreBrouillon(vue)
    expect(document.querySelector('textarea[placeholder^="Conditions particulières"]')?.value)
      .toBe('Brouillon ancien')
    expect(screen.getByTestId('part-diurne-defaut').textContent).not.toMatch(/90 %/)
  }, 60000)
})
