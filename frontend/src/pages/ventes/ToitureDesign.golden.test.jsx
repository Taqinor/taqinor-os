import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, waitFor, act } from '@testing-library/react'
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

const journalApi = []
const enregistrer = (nom, valeur) => vi.fn((...args) => {
  journalApi.push({ appel: nom, args })
  return valeur
})
const serializeLayout = enregistrer('serializeLayout', LAYOUT)
const snapshot = enregistrer('snapshot', null)
const setReferenceContourVisible = enregistrer('setReferenceContourVisible')
const recommencerDepuisTraceClient = enregistrer('recommencerDepuisTraceClient', true)

import '../../test/toitureDesignHarnessCalepinage'
import '../../test/toitureDesignHarnessNavigation'
import {
  initRoofToolPro8, LAYOUT, LEAD_88, ecranCalepinage, ecranDevis, ecranLead,
  brancherBoot, simulerApiLead,
} from '../../test/toitureDesignHarness'
import api from '../../api/axios'
import calepinageApi from '../../api/calepinageApi'

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
  brancherBoot({
    serializeLayout, snapshot, setReferenceContourVisible,
    recommencerDepuisTraceClient,
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ToitureDesign — GOLDEN des trois modes (SPL194)', () => {
  it('mode lead : DOM + journal du builder', async () => {
    simulerApiLead(api, LEAD_88)
    const dom = await bootEtDom(ecranLead(88))
    figer('toitureDesign.lead.html', dom)
    figer('toitureDesign.lead.boot.json', jsonStable(journalDuBoot()))
  })

  it('mode devis : DOM + journal du builder', async () => {
    // ACAL37 (D-ACAL-1) — la route devis ouvre le CALEPINAGE lié (instantané régénéré).
    const CTX = exempleContrat('calepinage', 'calepinage_design_context')
    calepinageApi.calepinages.depuisModele.mockResolvedValue(
      { data: { id: CTX.calepinage.id } })
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    const dom = await bootEtDom(ecranDevis(CTX.calepinage.devis_lie.id))
    figer('toitureDesign.devis.html', dom)
    figer('toitureDesign.devis.boot.json', jsonStable(journalDuBoot()))
  })

  it('mode calepinage : DOM + journal du builder', async () => {
    const CTX = exempleContrat('calepinage', 'calepinage_design_context')
    calepinageApi.calepinages.designContext.mockResolvedValue(
      reponseContrat('calepinage', 'calepinage_design_context'))
    const dom = await bootEtDom(ecranCalepinage(CTX.calepinage.id))
    figer('toitureDesign.calepinage.html', dom)
    figer('toitureDesign.calepinage.boot.json', jsonStable(journalDuBoot()))
  })
})
