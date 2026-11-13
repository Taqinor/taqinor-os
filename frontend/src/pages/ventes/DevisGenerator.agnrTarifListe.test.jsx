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
// RGEN6 — `computeROI` ENROBÉ (même fonction, appels observés) pour lire l'efficacité reçue.
vi.mock('../../features/ventes/calc/roi', async (importOriginal) => {
  const m = await importOriginal()
  return { ...m, computeROI: vi.fn(m.computeROI) }
})

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

// AERR126 (C-AERR-097) — deux réponses de palier dans le désordre : la réponse
// de la DERNIÈRE quantité demandée gagne (jeton par ligne), même si la réponse
// d'une quantité antérieure arrive après.
describe('AERR126 — réponses de tarif périmées ignorées', () => {
  it('réponses de palier dans le désordre : la dernière quantité gagne', async () => {
    let armer = false
    let libererPalier1
    const palier1 = new Promise((r) => { libererPalier1 = r })
    const prixPaliers = (params) => {
      if (armer && String(params?.produit) === '102') {
        if (Number(params?.quantite) === 1) {
          return palier1.then(() => ({ data: { ...LISTE_ONDULEUR, prix: '1500.00', liste_nom: 'Unitaire' } }))
        }
        const volume = Number(params?.quantite) >= 10
        return Promise.resolve({ data: { ...LISTE_ONDULEUR, prix: volume ? '1350.00' : '1450.00', liste_nom: volume ? 'Volume' : 'Moyen' } })
      }
      return prixApplicable(params)
    }
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, {
      devis: DEVIS_REGISTRE,
      avant: (apis) => { apis.ventesApi.getPrixApplicable.mockImplementation(prixPaliers) },
    })
    const { container } = vue
    const onduleur = () => ligneDe(container, 'Onduleur réseau 5kW Monophasé')
    await waitFor(() => expect(onduleur()).toBeTruthy(), { timeout: 5000 })
    await attendreStable(container, act, { stables: 10 })

    armer = true
    const qte = () => onduleur().querySelector('[data-role="line-qty"]')
    // La ligne est à 1 : on la passe à 3 (1 450 HT → 1 740 TTC) pour que « 1 » soit une vraie frappe.
    await act(async () => { fireEvent.change(qte(), { target: { value: '3' } }) })
    await waitFor(() => expect(puDe(onduleur()).value).toBe('1740'))
    await act(async () => { fireEvent.change(qte(), { target: { value: '1' } }) })
    await act(async () => { fireEvent.change(qte(), { target: { value: '10' } }) })
    await waitFor(() => expect(puDe(onduleur()).value).toBe('1620'))

    // La réponse du palier « 1 » arrive en dernier : elle est ignorée.
    await act(async () => { libererPalier1(); await palier1 })
    await attendreStable(container, act, { stables: 10 })
    expect(puDe(onduleur()).value).toBe('1620')
    expect(container.textContent).toMatch(/Tarif : Volume/)
    expect(container.textContent).not.toMatch(/Tarif : Unitaire/)

    const enregistrer = [...container.querySelectorAll('button')]
      .find((b) => /Enregistrer les modifications/.test(b.textContent))
    await act(async () => { fireEvent.click(enregistrer) })
    await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled(), { timeout: 5000 })
    const envoye = vue.ventesApi.replaceLignesDevis.mock.calls.at(-1)[1]
    const lignesEnvoyees = Array.isArray(envoye) ? envoye : envoye.lignes
    expect(lignesEnvoyees.find((l) => l.designation === 'Onduleur réseau 5kW Monophasé')?.prix_unitaire)
      .toBe('1350.00')
  }, 60000)
})

describe('RGEN6 rendement_global ignoré', () => {
  it('une société à rendement_global = 0,7 garde efficiency = EFFICIENCY (0,8) dans l’aperçu local', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, {
      devis: DEVIS_REGISTRE,
      avant: (apis) => { apis.parametresApi.getProfile.mockResolvedValue({ data: { rendement_global: 0.7 } }) },
    })
    const { container } = vue
    // L'instance que l'écran a importée (après `resetModules` du harnais).
    const { computeROI } = await import('../../features/ventes/calc/roi')
    const { EFFICIENCY } = await import('../../features/ventes/solar')
    await waitFor(() => expect(vue.parametresApi.getProfile).toHaveBeenCalled(), { timeout: 5000 })
    await waitFor(() => expect(computeROI).toHaveBeenCalled(), { timeout: 5000 })
    await attendreStable(container, act, { stables: 10 })
    expect(EFFICIENCY).toBe(0.8)
    const efficacites = computeROI.mock.calls.map(([args]) => args.efficiency)
    expect(efficacites.length).toBeGreaterThan(0)
    expect(efficacites.every((e) => e === EFFICIENCY)).toBe(true)
  }, 60000)
})
