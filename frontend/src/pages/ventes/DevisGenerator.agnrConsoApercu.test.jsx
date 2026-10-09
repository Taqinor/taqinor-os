// AGNR24 — l'aperçu reçoit la consommation que l'écran ENREGISTRE
// (`consoEcran`, même cascade que le corps) : 12 factures de 800 MAD sans
// facture réelle ⇒ aperçu au modèle « factures » (plus le bandeau
// « Estimation… renseignez la facture réelle »), et la conso enregistrée
// est celle des 12 factures au barème (5 880 kWh).
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrConsoApercu.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, fireEvent, waitFor } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable, DEVIS_REGISTRE } from './DevisGeneratorGoldenHarnais'
import { consoAnnuelleDepuisFactures } from '../../features/ventes/solar'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

cycleEcran({ date: DATE_FIGEE })

describe('AGNR24 — la conso de l’aperçu est celle du corps enregistré', () => {
  it('12 × 800 MAD sans facture réelle ⇒ modèle « factures », conso 5 880 enregistrée', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, { devis: DEVIS_REGISTRE })
    await attendreStable(vue.container, act)
    const cases = [...document.querySelectorAll('.gen-monthly-grid input')]
    for (const c of cases) {
      await act(async () => { fireEvent.change(c, { target: { value: '800' } }) })
    }
    await attendreStable(vue.container, act)
    const texte = document.body.textContent
    expect(texte).toMatch(/Facture réelle ONEE ≈/)
    expect(texte).not.toMatch(/Estimation \(production × autoconsommation × tarif moyen\)/)

    const bouton = [...document.querySelectorAll('button')]
      .find((b) => /Enregistrer les modifications/.test(b.textContent || ''))
    await act(async () => { fireEvent.click(bouton) })
    await waitFor(() => expect(vue.ventesApi.patchEtudeParams).toHaveBeenCalled(), { timeout: 5000 })
    const corps = vue.ventesApi.patchEtudeParams.mock.calls.at(-1)[1]
    const attendu = consoAnnuelleDepuisFactures(Array(12).fill(800), 'onee')
    expect(attendu).toBe(5880)
    expect(corps.conso_annuelle).toBe(attendu)
  }, 60000)
})
