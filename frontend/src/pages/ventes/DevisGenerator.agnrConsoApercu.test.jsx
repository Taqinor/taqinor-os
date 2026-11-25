// AGNR24 / E7d (revue lot 4, B2) — l'aperçu du moteur unique reçoit la
// consommation que le devis ENREGISTRE : le corps de `POST conception/apercu/`
// porte `imposes.consommation.kwh_annuel` = la `conso_annuelle` du corps
// enregistré (même sélecteur, `entreesDeEtat`). 12 factures de 800 MAD ⇒
// 5 880 kWh des deux côtés ; « Facture réelle » en MAD ⇒ idem ; rien de tapé ⇒
// aucune consommation imposée (le moteur lit le lead / le devis).
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrConsoApercu.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, fireEvent, waitFor } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable, DEVIS_REGISTRE } from './DevisGeneratorGoldenHarnais'
import { consoAnnuelleDepuisFactures } from '../../features/ventes/calc/tarifs.js'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

cycleEcran({ date: DATE_FIGEE })

const enregistrer = async (vue) => {
  const bouton = [...document.querySelectorAll('button')]
    .find((b) => /Enregistrer les modifications/.test(b.textContent || ''))
  await act(async () => { fireEvent.click(bouton) })
  await waitFor(() => expect(vue.ventesApi.patchEtudeParams).toHaveBeenCalled(), { timeout: 5000 })
  return vue.ventesApi.patchEtudeParams.mock.calls.at(-1)[1]
}
const dernierCorpsApercu = (vue) => vue.ventesApi.apercuConception.mock.calls.at(-1)?.[0]

describe('AGNR24 — la conso de l’aperçu est celle du corps enregistré', () => {
  it('12 × 800 MAD : l’aperçu reçoit les 5 880 kWh que le devis enregistre', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    for (const c of [...document.querySelectorAll('.gen-monthly-grid input')]) {
      await act(async () => { fireEvent.change(c, { target: { value: '800' } }) })
    }
    await attendreStable(vue.container, act)
    await waitFor(() => expect(dernierCorpsApercu(vue)?.imposes?.consommation).toBeTruthy(), { timeout: 5000 })
    const corpsApercu = dernierCorpsApercu(vue)
    const corps = await enregistrer(vue)
    expect(consoAnnuelleDepuisFactures(Array(12).fill(800), 'onee')).toBe(5880)
    expect(corps.conso_annuelle).toBe(5880)
    expect(corpsApercu.imposes.consommation).toEqual({ kwh_annuel: corps.conso_annuelle, source: 'factures' })
  }, 60000)

  it('« Facture réelle » en MAD : même consommation à l’aperçu et à l’enregistrement', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    const champ = document.querySelector('#gen-realbill')
    await act(async () => { fireEvent.change(champ, { target: { value: '900' } }) })
    await attendreStable(vue.container, act)
    await waitFor(() => expect(dernierCorpsApercu(vue)?.imposes?.consommation).toBeTruthy(), { timeout: 5000 })
    const corpsApercu = dernierCorpsApercu(vue)
    const corps = await enregistrer(vue)
    expect(corps.conso_annuelle).toBeGreaterThan(0)
    expect(corpsApercu.imposes.consommation).toEqual({ kwh_annuel: corps.conso_annuelle, source: 'facture_reelle' })
  }, 60000)

  it('rien de tapé : aucune consommation imposée à l’aperçu', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    const imposees = vue.ventesApi.apercuConception.mock.calls.filter(([c]) => c?.imposes?.consommation)
    expect(imposees).toEqual([])
  }, 60000)
})
