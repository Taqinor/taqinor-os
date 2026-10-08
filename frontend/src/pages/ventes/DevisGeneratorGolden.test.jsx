// SPL40 — GOLDEN DU GÉNÉRATEUR DE DEVIS (capture seule, avant tout déplacement).
//
// Neuf scénarios montent l'écran RÉEL (`DevisGenerator.jsx`) — seules les
// quatre API (crm, stock, parametres, ventes) sont mockées, jamais l'écran —
// et figent `normalise(container.innerHTML)` dans
// `generator/__golden__/<scénario>.html` ; pour c, d, f, g le test clique
// « Enregistrer les modifications » et fige les `mock.calls` des API
// d'enregistrement dans `<scénario>.appels.txt`. Chaque déplacement du groupe
// SPL (SPL43-SPL55) doit laisser ces fichiers octet-identiques.
//
// Limites (dites d'avance) : Recharts (`ResponsiveContainer`) ne rend rien
// sous jsdom — les props du graphique ne sont pas figées ; un `onClick`
// oublié sur un JSX déplacé ne change pas `innerHTML` : SPL41 (gestes) le
// couvre.
//
// Régénérer (après un changement VOULU de l'écran, jamais pour un
// déplacement) : npx vitest run src/pages/ventes/DevisGeneratorGolden.test.jsx -u
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, waitFor, fireEvent, cleanup } from '@testing-library/react'

import {
  LEAD, DATE_FIGEE, monter, formaterGolden, serialiseAppels, attendreStable,
  DEVIS_ENVOYE_LES_DEUX, DEVIS_INDUSTRIEL_MT, DEVIS_COMMERCIAL_HOTEL, DEVIS_AGRICOLE_POMPE,
  DEVIS_MULTI_VILLAS, DEVIS_REGISTRE, REGISTRE_NON_VIDE, DEVIS_ETUDE_HORAIRE,
} from './DevisGeneratorGoldenHarnais'
import { exempleContrat } from '../../test/fixtures/contractSamples'

// Chaque API est un objet dont TOUTE méthode est un `vi.fn` qui répond
// `{ data: {} }` par défaut ; le scénario pose les réponses qui comptent.
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

const DOSSIER = './generator/__golden__'

async function figerDom(container, nom) {
  const html = await attendreStable(container, act)
  await expect(formaterGolden(html)).toMatchFileSnapshot(`${DOSSIER}/${nom}.html`)
}

async function enregistrerEtFiger(vue, nom) {
  const bouton = [...vue.container.querySelectorAll('button')]
    .find((b) => /Enregistrer les modifications/.test(b.textContent))
  expect(bouton, 'bouton « Enregistrer les modifications »').toBeTruthy()
  await act(async () => { fireEvent.click(bouton) })
  await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled(), { timeout: 5000 })
  await attendreStable(vue.container, act)
  await expect(serialiseAppels(vue.ventesApi)).toMatchFileSnapshot(`${DOSSIER}/${nom}.appels.txt`)
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(DATE_FIGEE)
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

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('SPL40 — golden du générateur (DOM + appels API)', () => {
  it('(a) résidentiel, création vierge', async () => {
    const vue = await monter('/ventes/devis/nouveau')
    await figerDom(vue.container, 'a-residentiel-creation')
  }, 60000)

  it('(b) création depuis ?lead=', async () => {
    const vue = await monter(`/ventes/devis/nouveau?lead=${LEAD.id}`)
    await waitFor(() => expect(vue.crmApi.getLeads).toHaveBeenCalled())
    await figerDom(vue.container, 'b-creation-depuis-lead')
  }, 60000)

  it('(c) ?edit= d’un devis envoyé « Les deux », reco « Sans batterie »', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_ENVOYE_LES_DEUX.id}`,
      { devis: DEVIS_ENVOYE_LES_DEUX })
    await figerDom(vue.container, 'c-edition-envoye-les-deux')
    await enregistrerEtFiger(vue, 'c-edition-envoye-les-deux')
  }, 60000)

  it('(d) industriel MT avec part diurne', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_INDUSTRIEL_MT.id}`,
      { devis: DEVIS_INDUSTRIEL_MT })
    await figerDom(vue.container, 'd-industriel-mt')
    await enregistrerEtFiger(vue, 'd-industriel-mt')
  }, 60000)

  it('(e) commercial hôtel', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_COMMERCIAL_HOTEL.id}`,
      { devis: DEVIS_COMMERCIAL_HOTEL })
    await figerDom(vue.container, 'e-commercial-hotel')
  }, 60000)

  it('(f) agricole avec pompe à courbe', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_AGRICOLE_POMPE.id}`,
      { devis: DEVIS_AGRICOLE_POMPE })
    await figerDom(vue.container, 'f-agricole-pompe-courbe')
    await enregistrerEtFiger(vue, 'f-agricole-pompe-courbe')
  }, 60000)

  it('(g) multi-villas', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_MULTI_VILLAS.id}`,
      { devis: DEVIS_MULTI_VILLAS })
    await figerDom(vue.container, 'g-multi-villas')
    await enregistrerEtFiger(vue, 'g-multi-villas')
  }, 60000)

  it('(h) administrateur, registre de surcharges non vide', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`,
      { devis: DEVIS_REGISTRE, registre: REGISTRE_NON_VIDE, role: 'admin' })
    await waitFor(() => expect(vue.ventesApi.lireOverrides).toHaveBeenCalled())
    await figerDom(vue.container, 'h-admin-registre')
  }, 60000)

  it('(i) résidentiel avec aperçu d’étude horaire serveur', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_ETUDE_HORAIRE.id}`,
      { devis: DEVIS_ETUDE_HORAIRE, etudeHoraire: exempleContrat('ventes', 'etude_horaire') })
    await waitFor(() => expect(vue.ventesApi.postEtudeHorairePreview).toHaveBeenCalled(), { timeout: 5000 })
    await figerDom(vue.container, 'i-residentiel-etude-horaire')
  }, 60000)
})
