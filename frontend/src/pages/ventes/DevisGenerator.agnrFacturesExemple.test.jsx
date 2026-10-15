// AGNR13 — une facture mensuelle d'EXEMPLE ne part jamais : chaque case du
// détail mensuel porte sa provenance (exemple | dérivée | tapée) ; tant
// qu'une case est « exemple », `factures_mensuelles_reelles` ne part pas et
// les mois non saisis sont nommés sous la carte. Écran RÉEL monté, corps lu
// sur le serveur factice (jamais un espion sur un setter).
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrFacturesExemple.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, fireEvent, waitFor } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable, DEVIS_REGISTRE, DEVIS_ENVOYE_LES_DEUX } from './DevisGeneratorGoldenHarnais'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

cycleEcran({ date: DATE_FIGEE })

const cases = () => [...document.querySelectorAll('.gen-monthly-grid input')]
const taper = async (el, v) => { await act(async () => { fireEvent.change(el, { target: { value: v } }) }) }

async function enregistrer(vue) {
  const bouton = [...document.querySelectorAll('button')]
    .find((b) => /Enregistrer les modifications/.test(b.textContent || ''))
  await act(async () => { fireEvent.click(bouton) })
  await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled(), { timeout: 5000 })
  await attendreStable(vue.container, act)
  // L'étude part par la FUSION (`PATCH etude-params`) après replace-lines.
  const [, , extra] = vue.ventesApi.replaceLignesDevis.mock.calls.at(-1)
  const fusion = vue.ventesApi.patchEtudeParams.mock.calls.at(-1)?.[1] || {}
  return { ...(extra?.etude_params || {}), ...fusion }
}

describe('AGNR13 — jamais une facture mensuelle d’exemple', () => {
  it('Janvier seul tapé ⇒ aucune série envoyée, les 11 autres mois sont nommés', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    expect(cases()).toHaveLength(12)
    await taper(cases()[0], '900')
    const message = document.querySelector('[data-testid="mois-non-saisis"]')
    expect(message?.textContent).toMatch(/Fév/)
    expect(message?.textContent).not.toMatch(/Jan,/)
    const etude = await enregistrer(vue)
    expect(etude).not.toHaveProperty('factures_mensuelles_reelles')
  }, 60000)

  it('les 12 mois tapés ⇒ la série part avec les 12 valeurs tapées', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    const valeurs = [900, 850, 800, 700, 650, 900, 1200, 1300, 1000, 750, 700, 850]
    for (let i = 0; i < 12; i += 1) await taper(cases()[i], String(valeurs[i]))
    expect(document.querySelector('[data-testid="mois-non-saisis"]')).toBeNull()
    const etude = await enregistrer(vue)
    expect(etude.factures_mensuelles_reelles).toEqual(valeurs)
  }, 60000)

  it('vider une case ne la rend pas « tapée »', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    for (let i = 0; i < 12; i += 1) await taper(cases()[i], '600')
    await taper(cases()[3], '')
    expect(document.querySelector('[data-testid="mois-non-saisis"]')?.textContent).toMatch(/Avr/)
    const etude = await enregistrer(vue)
    expect(etude).not.toHaveProperty('factures_mensuelles_reelles')
  }, 60000)

  it('série relue d’un devis (12 mois) ⇒ ré-enregistrée telle quelle sans retouche', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_ENVOYE_LES_DEUX.id}`, { devis: DEVIS_ENVOYE_LES_DEUX })
    await attendreStable(vue.container, act)
    const etude = await enregistrer(vue)
    expect(etude.factures_mensuelles_reelles)
      .toEqual(DEVIS_ENVOYE_LES_DEUX.etude_params.factures_mensuelles_reelles)
  }, 60000)
})

// AGNR34 (D-AGNR-1 option (a)) — deux factures ⇒ `factures_hiver_ete`, jamais
// une série dérivée « réelle » ; la grille montre les marches du moteur « estimé ».
const MARCHES = [500, 500, 500, 500, 1200, 1200, 1200, 1200, 1200, 1200, 500, 500]
const DEUX_FACTURES = { hiver_mad: 500, ete_mad: 1200, ete_differente: true }

describe('AGNR34 — deux factures hiver / été', () => {
  it('hiver 500 / été 1 200 tapés ⇒ marches « estimé », corps factures_hiver_ete', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    await taper(document.getElementById('gen-hiver'), '500')
    await taper(document.getElementById('gen-ete'), '1200')
    expect(cases().map((c) => Number(c.value))).toEqual(MARCHES)
    expect(document.querySelectorAll('[data-testid^="mois-estime-"]')).toHaveLength(12)
    const etude = await enregistrer(vue)
    expect(etude.factures_hiver_ete).toEqual(DEUX_FACTURES)
    expect(etude).not.toHaveProperty('factures_mensuelles_reelles')
  }, 60000)

  it('rouvert ⇒ grille « estimé » identique, ré-enregistré sans toucher ⇒ même clé', async () => {
    const devis = { ...DEVIS_REGISTRE, etude_params: { ...DEVIS_REGISTRE.etude_params, factures_hiver_ete: DEUX_FACTURES } }
    const vue = await monter(`/ventes/devis/nouveau?edit=${devis.id}`, { devis })
    await attendreStable(vue.container, act)
    expect(cases().map((c) => Number(c.value))).toEqual(MARCHES)
    expect(document.querySelectorAll('[data-testid^="mois-estime-"]')).toHaveLength(12)
    const etude = await enregistrer(vue)
    expect(etude.factures_hiver_ete).toEqual(DEUX_FACTURES)
    expect(etude).not.toHaveProperty('factures_mensuelles_reelles')
  }, 60000)
})
