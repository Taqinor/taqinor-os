// AGEN11 (D-ACAL-97, contrôle C4-E7) — l'aperçu de l'écran devis (production,
// économies, payback) vient du MOTEUR UNIQUE : la conception rangée du lead
// (`GET conception/<lead>/`) puis l'aperçu sans écriture de ce qui est tapé
// (`POST conception/apercu/`, ADEV152), « Calcul en cours… » pendant l'appel ;
// le payback affiché est celui SERVI (devis de référence, comme le PDF), jamais
// un cashflow refait dans le navigateur. La saisie reste libre : le nombre
// tapé part tel quel, jamais arrondi.
//
// L'écran RÉEL est rendu en édition (`?edit=`) ; la valeur lue est l'ancre
// QA-FIGURES `data-figure` — aucune lecture de source. Les réponses mockées
// sont celles du contrat committé `conception_lead.json` (PACT10).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorPaybackMoteur.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { act, fireEvent, render, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { exempleContrat, documentContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock({
    getLead: vi.fn(() => Promise.reject(new Error('sans lead'))),
}))
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock({
    getPrixApplicable: vi.fn(),
    // Le jumeau horaire ne répond jamais : seules les routes du moteur unique servent.
    postEtudeHorairePreview: vi.fn(() => new Promise(() => {})),
    getConceptionLead: vi.fn(),
    apercuConception: vi.fn(),
}))
// AGEN13 — le calcul local (`calc/roi.js`) n'existe plus : sa disparition est
// épinglée par `features/ventes/solar.test.mjs` (cas AGEN13).

import ventesApi from '../../api/ventesApi'
import stockApi from '../../api/stockApi'
import DevisGenerator from './DevisGenerator'
import { ONDULEUR, PANNEAU, declarerBeforeEachDevis, lignesResidentielles, makeDevisStore } from './devisGenerator.testHelpers.jsx'

const RANGEE = exempleContrat('ventes', 'conception_lead')
const APERCU = documentContrat('ventes', 'conception_lead').apercu.reponse
// L'aperçu sur l'investissement des lignes de l'écran : son payback diffère de la version rangée.
const APERCU_SUR_LES_LIGNES = { ...APERCU, valeurs: { sans: { ...APERCU.valeurs.sans,
  payback: { valeur: 4.2, unite: 'ans', source: 'devis' } } } }
// Sans investissement dans le corps, le serveur ne sert aucun payback.
const APERCU_SANS_PRIX = { ...APERCU, valeurs: { sans: { ...APERCU.valeurs.sans,
  payback: { valeur: null, unite: 'ans', source: 'moteur' } } } }

function devisRouvert(lead) {
  return {
    data: {
      id: 336, reference: 'DEV-202609-0201', statut: 'brouillon', modifiable: true, raison_non_modifiable: '',
      revision_possible: false, is_active: true, lead, client: 9,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie' },
      lignes: lignesResidentielles(PANNEAU, ONDULEUR),
    },
  }
}

declarerBeforeEachDevis({ stockApi, ventesApi, produits: [PANNEAU, ONDULEUR], devis: () => devisRouvert(RANGEE.lead), localStorage: true })

function renderEdition() {
  return render(
    <Provider store={makeDevisStore('normal', 'Commercial')}>
      <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=336']}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

const figure = (container, nom) => container
  .querySelector(`[data-figure="${nom}"][data-figure-option="sans"], [data-figure="${nom}"]:not([data-figure-option])`)
  ?.getAttribute('data-figure-value') ?? null

describe('AGEN11 — l’aperçu de l’écran devis vient du moteur unique', () => {
  it('avec lead : la conception rangée, puis l’aperçu de la saisie ; payback de l’aperçu ; saisie non arrondie', async () => {
    ventesApi.getConceptionLead.mockResolvedValue({ data: RANGEE })
    ventesApi.apercuConception.mockImplementation((corps) => Promise.resolve({
      data: corps?.investissement ? APERCU_SUR_LES_LIGNES : APERCU }))
    const { container } = renderEdition()

    await waitFor(() => expect(ventesApi.getConceptionLead).toHaveBeenCalledWith(String(RANGEE.lead)), { timeout: 5000 })
    await waitFor(() => expect(container.querySelector('[data-testid="bandeau-modele-conception"]')).not.toBeNull(),
      { timeout: 5000 })
    const hiver = container.querySelector('#gen-hiver')
    await act(async () => { fireEvent.change(hiver, { target: { value: '1400.5' } }) })
    expect(hiver.value).toBe('1400.5')  // jamais arrondi ni refusé
    await waitFor(() => {
      const corps = ventesApi.apercuConception.mock.calls.at(-1)?.[0]
      expect(corps?.lead).toBe(RANGEE.lead)
      expect(corps?.entrees?.facture_hiver).toBe('1400.5')  // tel que tapé
    }, { timeout: 5000 })
    const production = APERCU.valeurs.sans.production_annuelle.valeur
    // La production affichée est celle de l'APERÇU (12 000), plus celle rangée (10 000).
    await waitFor(() => expect((figure(container, 'production_annuelle_kwh') || '').replace(/\D/g, ''))
      .toBe(String(production)), { timeout: 5000 })
    // E7d (M1) — le payback est celui de l'APERÇU, calculé sur le TTC des lignes de
    // l'écran (envoyé avec le corps), jamais celui du devis de référence de la version rangée.
    const corps = ventesApi.apercuConception.mock.calls.at(-1)[0]
    expect(String(Math.round(corps.investissement.sans))).toBe((figure(container, 'total_ttc') || '').replace(/\D/g, ''))
    expect(figure(container, 'payback_ans')).toBe(`${APERCU_SUR_LES_LIGNES.valeurs.sans.payback.valeur} ans`)
    expect(figure(container, 'payback_ans')).not.toBe(`${RANGEE.valeurs.sans.payback.valeur} ans`)
  }, 20000)

  it('lignes sans prix : le payback dit « après enregistrement », aucun investissement envoyé', async () => {
    const devis = devisRouvert(RANGEE.lead)
    devis.data.lignes = devis.data.lignes.map((l) => ({ ...l, prix_unitaire: '0.00' }))
    ventesApi.getDevisById.mockResolvedValue(devis)
    ventesApi.getConceptionLead.mockResolvedValue({ data: RANGEE })
    ventesApi.apercuConception.mockResolvedValue({ data: APERCU_SANS_PRIX })
    const { container } = renderEdition()
    await act(async () => { fireEvent.change(container.querySelector('#gen-hiver'), { target: { value: '1400' } }) })
    await waitFor(() => expect(container.querySelector('[data-testid="bandeau-modele-conception"]')).not.toBeNull(),
      { timeout: 5000 })
    await waitFor(() => expect(ventesApi.apercuConception).toHaveBeenCalled(), { timeout: 5000 })
    expect(ventesApi.apercuConception.mock.calls.every(([c]) => !('investissement' in c))).toBe(true)
    const roi = container.querySelector('[data-figure="payback_ans"]')
    expect(roi?.textContent || container.textContent).toContain('après enregistrement')
  }, 20000)

  it('sans lead : rien avant la saisie, « Calcul en cours… » pendant l’appel, puis les chiffres servis', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert(null))
    let repondre
    ventesApi.apercuConception.mockImplementation(() => new Promise((r) => { repondre = r }))
    const { container } = renderEdition()
    await waitFor(() => expect(container.querySelector('#gen-hiver')).not.toBeNull(), { timeout: 5000 })
    expect(ventesApi.getConceptionLead).not.toHaveBeenCalled()
    await act(async () => { fireEvent.change(container.querySelector('#gen-hiver'), { target: { value: '1400' } }) })
    await waitFor(() => expect(container.querySelector('[data-testid="apercu-conception-attente"]')?.textContent)
      .toContain('Calcul en cours'), { timeout: 5000 })
    await waitFor(() => expect(ventesApi.apercuConception).toHaveBeenCalled(), { timeout: 5000 })
    const corps = ventesApi.apercuConception.mock.calls.at(-1)[0]
    expect(corps).toMatchObject({ lead: null, calepinage: null, entrees: { facture_hiver: '1400', type_installation: 'residentiel' } })
    await act(async () => { repondre({ data: APERCU }) })
    await waitFor(() => expect(container.querySelector('[data-testid="bandeau-modele-conception"]')).not.toBeNull(),
      { timeout: 5000 })
    expect((figure(container, 'economie_annuelle') || '').replace(/\D/g, ''))
      .toBe(String(APERCU.valeurs.sans.economies_annuelles.valeur))
    // E7d (M1) — sans lead ni devis de référence, le payback est celui de l'aperçu sur les
    // lignes chiffrées de l'écran (plus « N/A » pour un brouillon aux lignes chiffrées).
    expect(corps.investissement.sans).toBeGreaterThan(0)
    expect(figure(container, 'payback_ans')).toBe(`${APERCU.valeurs.sans.payback.valeur} ans`)
  }, 20000)

  // E7d (revue lot 4, M2) — un aperçu en ÉCHEC après une saisie est DIT : la phrase du
  // serveur (400 nommant un champ) ou « Aperçu indisponible — Réessayer » (5xx, réseau) ;
  // les cartes ne retombent JAMAIS sur la version rangée comme si elle était à jour.
  it('aperçu en échec : la phrase du serveur, jamais les chiffres rangés ; Réessayer relance', async () => {
    ventesApi.getConceptionLead.mockResolvedValue({ data: RANGEE })
    const detail = '« facture_hiver » : valeur illisible.'
    ventesApi.apercuConception.mockRejectedValue({ response: { status: 400, data: { detail, champ: 'facture_hiver' } } })
    const { container } = renderEdition()
    await waitFor(() => expect(container.querySelector('[data-testid="bandeau-modele-conception"]')).not.toBeNull(),
      { timeout: 5000 })
    expect(container.textContent).not.toContain('ceux de la fiche du lead et du document')
    await act(async () => { fireEvent.change(container.querySelector('#gen-hiver'), { target: { value: '1400' } }) })
    await waitFor(() => expect(container.querySelector('[data-testid="apercu-conception-attente"]')?.textContent)
      .toContain(detail), { timeout: 5000 })
    expect(figure(container, 'production_annuelle_kwh')).toBeNull()  // jamais la version rangée
    ventesApi.apercuConception.mockRejectedValue(new Error('Network Error'))
    await act(async () => { fireEvent.change(container.querySelector('#gen-hiver'), { target: { value: '1500' } }) })
    await waitFor(() => expect(container.querySelector('[data-testid="apercu-conception-attente"]')?.textContent)
      .toContain('Aperçu indisponible — Réessayer'), { timeout: 5000 })
    const appels = ventesApi.apercuConception.mock.calls.length
    ventesApi.apercuConception.mockResolvedValue({ data: APERCU })
    const bouton = [...container.querySelectorAll('button')].find((b) => b.textContent === 'Réessayer')
    await act(async () => { fireEvent.click(bouton) })
    await waitFor(() => expect(ventesApi.apercuConception.mock.calls.length).toBeGreaterThan(appels), { timeout: 5000 })
    await waitFor(() => expect((figure(container, 'production_annuelle_kwh') || '').replace(/\D/g, ''))
      .toBe(String(APERCU.valeurs.sans.production_annuelle.valeur)), { timeout: 5000 })
  }, 30000)

  // E7d (revue lot 4, M3) — un refus du moteur est TOUJOURS dit (sa phrase, son
  // champ) : jamais remplacé par les chiffres d'un autre calcul ; aucun appel à
  // l'aperçu horaire.
  it('conception refusée : la phrase et le champ du refus, aucun chiffre', async () => {
    const refus = exempleContrat('ventes', 'conception_lead', 'exemple_refus')
    ventesApi.getConceptionLead.mockResolvedValue({ data: RANGEE })
    ventesApi.apercuConception.mockResolvedValue({ data: refus })
    const { container } = renderEdition()
    await act(async () => { fireEvent.change(container.querySelector('#gen-hiver'), { target: { value: '1400' } }) })
    await waitFor(() => expect(container.querySelector('[data-testid="apercu-conception-attente"]')?.textContent)
      .toContain(refus.refus.message), { timeout: 5000 })
    expect(container.querySelector('[data-testid="apercu-conception-attente"]').getAttribute('data-champ'))
      .toBe(refus.refus.champ)
    expect(figure(container, 'production_annuelle_kwh')).toBeNull()
    expect(ventesApi.postEtudeHorairePreview).not.toHaveBeenCalled()
  }, 20000)
})
