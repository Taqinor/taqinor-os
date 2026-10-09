// AGNR18 (C-AGNR-007) — après un modèle appliqué (10 × « Panneau Jinko 550W »)
// sur un devis rouvert dont le `panelW` d'état vient d'un panneau 715 W, le
// kWc FACTURÉ par les lignes est 5,5 (watt LU de chaque ligne), jamais
// 10 × 715 = 7,15 : le corps de l'aperçu horaire porte `kwc: 5.5`.
//
// Harnais du golden (seules les quatre API sont mockées, jamais l'écran).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, waitFor, fireEvent, cleanup } from '@testing-library/react'

import {
  monter, attendreStable, CATALOGUE, DEVIS_ETUDE_HORAIRE,
} from './DevisGeneratorGoldenHarnais'
import { exempleContrat } from '../../test/fixtures/contractSamples'

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

const JINKO = {
  id: 108, nom: 'Panneau Jinko 550W', prix_vente: 1000, tva: 10, is_archived: false, prix_achat: 700,
}
const MODELE = {
  id: 9, nom: 'Modèle 5,5 kWc', mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0.00',
  etude_params_snapshot: {},
  lignes_snapshot: [
    { produit_id: 108, designation: 'Panneau Jinko 550W', quantite: '10', prix_unitaire: '1000',
      remise: '0', taux_tva: '10', ordre: 0, variante: '', type_ligne: 'produit', optionnelle: false },
    { produit_id: 102, designation: 'Onduleur réseau 5kW Monophasé', quantite: '1', prix_unitaire: '9000',
      remise: '0', taux_tva: '20', ordre: 1, variante: '', type_ligne: 'produit', optionnelle: false },
  ],
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
})
afterEach(() => { cleanup() })

const bouton = (container, re) => [...container.querySelectorAll('button')].find((b) => re.test(b.textContent))

describe('AGNR18 — kWc des lignes au watt de chaque ligne panneau', () => {
  it('modèle 10 × Jinko 550W appliqué ⇒ corps de l’aperçu horaire `kwc: 5.5`', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_ETUDE_HORAIRE.id}`, {
      devis: DEVIS_ETUDE_HORAIRE,
      etudeHoraire: exempleContrat('ventes', 'etude_horaire'),
      avant: (apis) => {
        apis.stockApi.getProduits.mockResolvedValue({ data: [...CATALOGUE, JINKO] })
        apis.ventesApi.getPresets.mockResolvedValue({ data: [MODELE] })
      },
    })
    const { container } = vue
    await waitFor(() => expect(vue.ventesApi.postEtudeHorairePreview).toHaveBeenCalled(), { timeout: 5000 })
    await attendreStable(container, act, { stables: 10 })

    await act(async () => { fireEvent.click(bouton(container, /Modèles de devis/)) })
    await waitFor(() => expect(bouton(container, /^Appliquer$/)).toBeTruthy(), { timeout: 5000 })
    await act(async () => { fireEvent.click(bouton(container, /^Appliquer$/)) })
    await waitFor(() => {
      const corps = vue.ventesApi.postEtudeHorairePreview.mock.calls.at(-1)[0]
      expect(corps.kwc).toBe(5.5)
    }, { timeout: 5000 })
  }, 60000)
})
