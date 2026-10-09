// AGNR29 (C-AGNR-022) — la « marge indicative » est rendue par UN composant
// partagé (`MargeIndicative`) au Rail sous la table ET au rail latéral : avec
// une ligne sans prix d'achat (pompe OSP non tarifée à l'achat), les DEUX
// disent « marge partielle : 1 ligne sans prix d'achat » et aucun pourcentage.
// Avant : le rail latéral affichait « NN % » calculé sur un coût partiel.
//
// Harnais du golden (seules les quatre API sont mockées, jamais l'écran).
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, waitFor } from '@testing-library/react'

import {
  monter, attendreStable, CATALOGUE, DEVIS_AGRICOLE_POMPE, DEVIS_REGISTRE,
} from './DevisGeneratorGoldenHarnais'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

cycleEcran()

// Le bloc « Marge indicative (interne) » de chaque rail, texte compris.
const blocsMarge = (container) => [...container.querySelectorAll('div')]
  .filter((d) => d.children.length >= 2
    && (d.firstElementChild?.textContent || '').trim() === 'Marge indicative (interne)')
  .map((d) => d.textContent)

async function ouvrir(devis, catalogue) {
  const vue = await monter(`/ventes/devis/nouveau?edit=${devis.id}`, {
    devis, avant: (apis) => { apis.stockApi.getProduits.mockResolvedValue({ data: catalogue }) },
  })
  await waitFor(() => expect(blocsMarge(vue.container).length).toBe(2), { timeout: 5000 })
  await attendreStable(vue.container, act, { stables: 10 })
  return vue
}

describe('AGNR29 — marge indicative : même règle aux deux rails', () => {
  it('une ligne sans prix d’achat : « marge partielle » aux DEUX rails, aucun pourcentage', async () => {
    const catalogue = CATALOGUE.map((p) => (p.id === 201 ? { ...p, prix_achat: null } : p))
    const vue = await ouvrir(DEVIS_AGRICOLE_POMPE, catalogue)
    const blocs = blocsMarge(vue.container)
    for (const texte of blocs) {
      expect(texte).toContain('marge partielle : 1 ligne sans prix d\'achat')
      expect(texte).not.toMatch(/\(\s*-?\d+\s*%\)/)
    }
  }, 60000)

  it('aucune ligne sans achat : même montant et même % aux deux rails', async () => {
    const vue = await ouvrir(DEVIS_REGISTRE, CATALOGUE)
    const [rail, lateral] = blocsMarge(vue.container)
    const pct = (t) => t.match(/\((-?\d+) %\)/)?.[1]
    expect(pct(rail)).toBeTruthy()
    expect(pct(lateral)).toBe(pct(rail))
    expect(rail).not.toContain('marge partielle')
    expect(lateral).not.toContain('marge partielle')
  }, 60000)
})
