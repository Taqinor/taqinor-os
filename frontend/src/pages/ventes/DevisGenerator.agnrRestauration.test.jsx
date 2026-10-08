// AGNR22 (C-AGNR-013) — « Revenir à cette version » envoie l'étude de
// l'instantané TELLE QUE SERVIE (clés écran absentes à null, AGNR9), jamais
// le `choixEcran()` de l'écran d'avant ; une version sans étude est REFUSÉE
// avec un message ; après restauration l'écran rechargé affiche le total de la
// version choisie (mono), pas celui du ×4 posé depuis.
//
// Harnais du golden ; serveur factice qui applique la fusion d'`ecrire` sur
// une copie du devis (une clé à null est RETIRÉE) puis la resert au chargeur.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, waitFor, fireEvent, cleanup, screen } from '@testing-library/react'

import { monter, attendreStable, DEVIS_REGISTRE } from './DevisGeneratorGoldenHarnais'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { toast } from '../../ui/confirm'

const { apiAuto } = vi.hoisted(() => ({
  apiAuto: () => {
    const fns = {}
    return {
      default: new Proxy(fns, {
        get(cible, cle) {
          if (typeof cle !== 'string' || cle === 'then' || cle === '__esModule') return undefined
          if (!cible[cle]) cible[cle] = vi.fn(() => Promise.resolve({ data: {} }))
          return cible[cle]
        },
      }),
    }
  },
}))
vi.mock('../../api/crmApi', () => apiAuto())
vi.mock('../../api/stockApi', () => apiAuto())
vi.mock('../../api/parametresApi', () => apiAuto())
vi.mock('../../api/ventesApi', () => apiAuto())

// Le devis passé à ×4 (et enregistré) depuis sa V1 mono.
const DEVIS_X4 = {
  ...DEVIS_REGISTRE, id: 52, reference: 'DEV-202610-052', updated_at: '2026-10-08T08:00:00Z',
  etude_params: { scenario: 'Sans batterie', nombre_proprietes: 4 },
}
const SNAP = exempleContrat('ventes', 'devis_historique_configuration').snapshots[0]
const versionV1 = (etude) => ({
  ...SNAP, id: 90, date: '2026-09-29T08:00:00+00:00',
  contenu: {
    lignes: DEVIS_REGISTRE.lignes.map((l) => { const c = { ...l, lot: null }; delete c.id; return c }),
    remise_globale: '0.00', echeancier: [],
    ...(etude === undefined ? {} : { etude }),
  },
})

// Serveur factice : `replace-lines` fusionne `etude_params` (null retire la
// clé) et remplace les lignes ; `getDevisById` resert l'état courant.
function serveur(apis) {
  let courant = structuredClone(DEVIS_X4)
  apis.ventesApi.getDevisById.mockImplementation(() => Promise.resolve({ data: structuredClone(courant) }))
  apis.ventesApi.replaceLignesDevis.mockImplementation((id, lignes, extra = {}) => {
    const etude = { ...courant.etude_params }
    for (const [cle, valeur] of Object.entries(extra.etude_params || {})) {
      if (valeur === null) delete etude[cle]
      else etude[cle] = valeur
    }
    courant = {
      ...courant, etude_params: etude, updated_at: '2026-10-08T09:30:00Z',
      lignes: lignes.map((l, i) => ({ id: 100 + i, ...l })),
    }
    return Promise.resolve({ data: structuredClone(courant) })
  })
}

beforeEach(() => {
  try { window.localStorage.clear() } catch { /* stockage indisponible */ }
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

const totalRail = (container) => container.querySelector('[data-testid="gen-rail-total"]')?.textContent || ''

async function ouvrir(etude) {
  const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_X4.id}`, {
    devis: DEVIS_X4, historique: { snapshots: [versionV1(etude), { ...SNAP, id: 91 }] },
    avant: serveur,
  })
  await attendreStable(vue.container, act, { stables: 10 })
  return vue
}

describe('AGNR22 — restaurer une version rejoue SON étude, jamais l’écran d’avant', () => {
  it('V1 mono restaurée sur un devis ×4 : etude_params de l’instantané (nombre_proprietes: null) et total mono affiché', async () => {
    const vue = await ouvrir({ scenario: 'Sans batterie', nombre_proprietes: null, kit_retire: null })
    // ×4 posé depuis V1 : l'écran rouvert l'affiche.
    expect(vue.container.textContent).toMatch(/total pour 4 propriétés/)
    const totalMono = totalRail(vue.container)
    await act(async () => { fireEvent.click(await screen.findByRole('button', { name: /Revenir à cette version/ })) })
    await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled(), { timeout: 5000 })
    const extra = vue.ventesApi.replaceLignesDevis.mock.calls.at(-1)[2]
    expect(extra.etude_params).toEqual({ scenario: 'Sans batterie', nombre_proprietes: null, kit_retire: null })
    await waitFor(() => expect(vue.ventesApi.getDevisById.mock.calls.length).toBeGreaterThan(1), { timeout: 5000 })
    await attendreStable(vue.container, act, { stables: 10 })
    // L'écran rechargé est celui de V1 : mono, plus aucun ×4.
    expect(vue.container.textContent).not.toMatch(/total pour 4 propriétés/)
    expect(totalRail(vue.container)).toBe(totalMono)
  }, 60000)

  it('une version SANS étude est refusée avec un message, rien n’est écrit', async () => {
    const vue = await ouvrir(undefined)
    const erreur = vi.spyOn(toast, 'error')
    await act(async () => { fireEvent.click(await screen.findByRole('button', { name: /Revenir à cette version/ })) })
    await attendreStable(vue.container, act, { stables: 5 })
    expect(vue.ventesApi.replaceLignesDevis).not.toHaveBeenCalled()
    expect(erreur).toHaveBeenCalledWith('Version sans étude — restauration impossible.')
  }, 60000)
})
