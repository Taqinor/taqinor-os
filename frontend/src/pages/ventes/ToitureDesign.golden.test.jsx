import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, waitFor, act } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* SPL194 — GOLDEN de l'écran ToitureDesign dans ses TROIS modes (lead, devis,
   calepinage), capturé sur le code AVANT tout déplacement (SPL213-SPL216).

   Pour chaque mode on épingle (1) le DOM de document.body une fois le boot
   résolu et (2) le JOURNAL des appels du builder simulé (options passées à
   `initRoofToolPro8`, dont le payload d'hydratation issu de
   leadToBuilderPayload / contexteToDevisPayload / contexteCalepinageVersPayload,
   et les méthodes de l'API builder appelées), pour que l'effet de boot soit
   prouvé et pas seulement le DOM.

   Les charges utiles viennent des exemples de contrat COMMITTÉS (PACT13).
   Régénérer volontairement : `VITE_UPDATE_GOLDEN=1 npx vitest run
   src/pages/ventes/ToitureDesign.golden.test.jsx`. */

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisDesignContext: vi.fn(),
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    syncDevisLayout: vi.fn(),
    shareLinkDevis: vi.fn(),
    whatsappPreviewDevis: vi.fn(),
    reviserDevis: vi.fn(),
  },
}))
vi.mock('../../api/calepinageApi', async (importOriginal) => {
  const actual = await importOriginal()
  const espionner = (groupe) => Object.fromEntries(
    Object.entries(groupe).map(([cle, valeur]) => [
      cle,
      typeof valeur === 'function'
        ? vi.fn(() => Promise.resolve({ data: null }))
        : valeur,
    ]),
  )
  return {
    default: Object.fromEntries(
      Object.entries(actual.default).map(([nom, groupe]) => [
        nom,
        (groupe && typeof groupe === 'object') ? espionner(groupe) : groupe,
      ]),
    ),
  }
})
vi.mock('../../api/crmApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getLeadPhotoToit: vi.fn(() => Promise.resolve({
        data: { visite_id: null, url: null, texture_calage: null },
      })),
    },
  }
})
vi.mock('../../lib/toast', () => ({ toastInfo: vi.fn() }))
vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))
vi.mock('../../providers/confirm-context', () => ({
  useConfirm: () => () => Promise.resolve(true),
}))
const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

const LAYOUT = { version: 2, zones: [{ id: 'z1' }] }
const journalApi = []
const enregistrer = (nom, valeur) => vi.fn((...args) => {
  journalApi.push({ appel: nom, args })
  return valeur
})
const serializeLayout = enregistrer('serializeLayout', LAYOUT)
const snapshot = enregistrer('snapshot', null)
const setReferenceContourVisible = enregistrer('setReferenceContourVisible')
const recommencerDepuisTraceClient = enregistrer('recommencerDepuisTraceClient', true)
const initRoofToolPro8 = vi.fn((options) => {
  options?.onApiReady?.({
    serializeLayout, snapshot, setReferenceContourVisible,
    recommencerDepuisTraceClient,
  })
})
vi.mock('@roofbuilder', () => ({ initRoofToolPro8: (...a) => initRoofToolPro8(...a) }))

import api from '../../api/axios'
import ventesApi from '../../api/ventesApi'
import calepinageApi from '../../api/calepinageApi'
import ToitureDesign from './ToitureDesign'

const DOSSIER = resolve(dirname(fileURLToPath(import.meta.url)),
  '../../features/calepinage/__golden__')
const MAJ = !!import.meta.env.VITE_UPDATE_GOLDEN

function figer(nom, contenu) {
  const chemin = resolve(DOSSIER, nom)
  if (MAJ || !existsSync(chemin)) {
    mkdirSync(DOSSIER, { recursive: true })
    writeFileSync(chemin, contenu)
  }
  const CR = String.fromCharCode(13)
  const attendu = readFileSync(chemin, 'utf8').split(CR).join('')
  expect(contenu).toBe(attendu)
}

// Journal JSON : fonctions -> "[fn]", ordre des clés conservé.
const jsonStable = (v) => JSON.stringify(
  v, (_k, x) => (typeof x === 'function' ? '[fn]' : x), 2) + '\n'

function journalDuBoot() {
  return {
    initRoofToolPro8_appels: initRoofToolPro8.mock.calls.map(([o]) => o),
    api_builder_appels: journalApi,
  }
}

async function bootEtDom(ui) {
  render(ui)
  await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
  await act(async () => { await new Promise((r) => setTimeout(r, 50)) })
  return document.body.innerHTML.replace(/></g, '>\n<')
}

beforeEach(() => {
  vi.clearAllMocks()
  journalApi.length = 0
  delete window.__taqinorRoofBooted
  initRoofToolPro8.mockImplementation((options) => {
    options?.onApiReady?.({
      serializeLayout, snapshot, setReferenceContourVisible,
      recommencerDepuisTraceClient,
    })
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ToitureDesign — GOLDEN des trois modes (SPL194)', () => {
  it('mode lead : DOM + journal du builder', async () => {
    const lead = {
      id: 88, nom: 'Alaoui', prenom: 'Youssef', ville: 'Casablanca',
      telephone: '0600000000', roof_point: { lat: 33.5, lng: -7.6 },
      roof_outline: [[33.5, -7.6]], bill_kwh: 7200,
    }
    api.get.mockImplementation((url) => {
      if (url.startsWith('/crm/leads/')) return Promise.resolve({ data: lead })
      if (url === '/ventes/roof-config/') {
        return Promise.resolve({ data: { available: true, maptilerKey: 'k-lead' } })
      }
      return Promise.reject(new Error(`URL inattendue ${url}`))
    })
    const dom = await bootEtDom(
      <MemoryRouter initialEntries={['/devis-design/88']}>
        <Routes>
          <Route path="/devis-design/:id" element={<ToitureDesign />} />
        </Routes>
      </MemoryRouter>,
    )
    figer('toitureDesign.lead.html', dom)
    figer('toitureDesign.lead.boot.json', jsonStable(journalDuBoot()))
  })

  it('mode devis : DOM + journal du builder', async () => {
    const CTX = exempleContrat('ventes', 'devis_design_context')
    ventesApi.getDevisDesignContext.mockResolvedValue(
      reponseContrat('ventes', 'devis_design_context'))
    const dom = await bootEtDom(
      <MemoryRouter initialEntries={[`/ventes/devis/${CTX.devis.id}/design`]}>
        <Routes>
          <Route path="/ventes/devis/:id/design"
            element={<ToitureDesign mode="devis" />} />
        </Routes>
      </MemoryRouter>,
    )
    figer('toitureDesign.devis.html', dom)
    figer('toitureDesign.devis.boot.json', jsonStable(journalDuBoot()))
  })

  it('mode calepinage : DOM + journal du builder', async () => {
    const CTX = exempleContrat('calepinage', 'calepinage_design_context')
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    const dom = await bootEtDom(
      <MemoryRouter initialEntries={[`/calepinage/${CTX.calepinage.id}`]}>
        <Routes>
          <Route path="/calepinage/:id"
            element={<ToitureDesign mode="calepinage" />} />
        </Routes>
      </MemoryRouter>,
    )
    figer('toitureDesign.calepinage.html', dom)
    figer('toitureDesign.calepinage.boot.json', jsonStable(journalDuBoot()))
  })
})
