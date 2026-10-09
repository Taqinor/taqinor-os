// AGNR15 (C-AGNR-003) — `/ventes/prix-applicable/` sert un prix HT (contrat
// AGNR1, `unite: 'HT'`) : `refreshTarif` le convertit au taux de la LIGNE
// avant de l'écrire dans le P.U. TTC de l'écran. Avant : « 1350.00 » posé tel
// quel dans un champ TTC, puis ré-enregistré 1 125,00 HT (÷ 1,2).
//
// Harnais du golden (seules les quatre API sont mockées, jamais l'écran) ;
// assert sur la VALEUR du champ et sur le corps `replace-lines` enregistré.
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, waitFor, fireEvent } from '@testing-library/react'

import { monter, attendreStable, DEVIS_REGISTRE } from './DevisGeneratorGoldenHarnais'
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

// Contrat AGNR1 : l'exemple « liste » (1 961,82 HT) et sa variante à 1 350 HT.
const CONTRAT = exempleContrat('ventes', 'prix_applicable')
const LISTE_PANNEAU = { ...CONTRAT, produit: 101 } // 1961.82 HT, panneau à 10 %
const LISTE_ONDULEUR = { ...CONTRAT, produit: 102, prix: '1350.00', liste_nom: 'Revendeur' } // 20 %

const prixApplicable = (params) => Promise.resolve({
  data: String(params?.produit) === '101' ? LISTE_PANNEAU : LISTE_ONDULEUR,
})

cycleEcran()

const ligneDe = (container, designation) => [...container.querySelectorAll('tr[data-line-key]')]
  .find((tr) => [...tr.querySelectorAll('input')].some((i) => i.value === designation))
const puDe = (tr) => tr.querySelector('td[data-label="Prix unit. TTC"] input')

describe('AGNR15 — prix de liste HT converti au taux de la ligne', () => {
  it('la frappe d’une quantité pose 1 620 / 2 158 TTC et enregistre 1 350,00 / 1 961,82 HT', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, {
      devis: DEVIS_REGISTRE,
      avant: (apis) => { apis.ventesApi.getPrixApplicable.mockImplementation(prixApplicable) },
    })
    const { container } = vue
    await waitFor(() => expect(ligneDe(container, 'Onduleur réseau 5kW Monophasé')).toBeTruthy(), { timeout: 5000 })
    await attendreStable(container, act, { stables: 10 })

    const onduleur = ligneDe(container, 'Onduleur réseau 5kW Monophasé')
    const panneau = ligneDe(container, 'Panneau Canadien Solar 715W')
    await act(async () => {
      fireEvent.change(onduleur.querySelector('[data-role="line-qty"]'), { target: { value: '2' } })
      fireEvent.change(panneau.querySelector('[data-role="line-qty"]'), { target: { value: '9' } })
    })
    await waitFor(() => expect(puDe(ligneDe(container, 'Onduleur réseau 5kW Monophasé')).value).toBe('1620'))
    await waitFor(() => expect(puDe(ligneDe(container, 'Panneau Canadien Solar 715W')).value).toBe('2158'))
    // Le badge de la liste reste.
    expect(container.textContent).toMatch(/Tarif : Revendeur/)

    const bouton = [...container.querySelectorAll('button')]
      .find((b) => /Enregistrer les modifications/.test(b.textContent))
    await act(async () => { fireEvent.click(bouton) })
    await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled(), { timeout: 5000 })
    const corps = vue.ventesApi.replaceLignesDevis.mock.calls.at(-1)[1]
    const lignes = Array.isArray(corps) ? corps : corps.lignes
    const pu = (designation) => lignes.find((l) => l.designation === designation)?.prix_unitaire
    expect(pu('Onduleur réseau 5kW Monophasé')).toBe('1350.00')
    expect(pu('Panneau Canadien Solar 715W')).toBe('1961.82')
  }, 60000)
})
