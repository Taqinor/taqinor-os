// ERR-QAH-FIG-PAYBACK-FORMULE-ECRAN — quand l'étude horaire SERVEUR a
// répondu, la carte ROI de l'écran affiche le payback du MOTEUR (cashflow 25
// ans QX39, `paybackMoteurHoraire`), plus `coût ÷ économie` ; un cumul qui ne
// croise jamais zéro s'affiche « Non rentabilisé sur 25 ans ».
//
// L'écran RÉEL est rendu en édition (`?edit=`), l'aperçu horaire mocké ; la
// valeur lue est l'ancre QA-FIGURES `data-figure="payback_ans"` — aucune
// lecture de source (QJR239).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorPaybackMoteur.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { paybackMoteurHoraire } from '../../features/ventes/solar'
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock({
    getLead: vi.fn(() => Promise.reject(new Error('sans lead'))),
}))
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock({
    getPrixApplicable: vi.fn(),
    postEtudeHorairePreview: vi.fn(),
}))

import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { ONDULEUR, PANNEAU, declarerBeforeEachDevis, lignesResidentielles, makeDevisStore } from './devisGenerator.testHelpers.jsx'

// 8 × 1 200 HT à 10 % + 9 000 HT à 20 % = 10 560 + 10 800 = 21 360 TTC ;
// l'onduleur (10 800 TTC) est la provision de remplacement de l'option.
const TOTAL_SANS = 21360
const ONDULEUR_TTC = 10800

// Contrat committé (PACT10) : l'aperçu horaire servi par le serveur.
const CONTRAT = exempleContrat('ventes', 'etude_horaire')
const ANNUEL = CONTRAT.etude.annuel

function devisRouvert() {
  return {
    data: {
      id: 336, reference: 'DEV-202609-0201', statut: 'brouillon', modifiable: true, raison_non_modifiable: '', revision_possible: false, is_active: true, lead: null, client: 9,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie' },
      lignes: lignesResidentielles(PANNEAU, ONDULEUR),
    },
  }
}

const makeStore = () => makeDevisStore('normal', 'Commercial')

function renderEdition() {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=336']}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

async function paybackAffiche(container) {
  let valeur = null
  await waitFor(() => {
    const ancre = container.querySelector(
      '[data-figure="payback_ans"][data-figure-option="sans"]')
    valeur = ancre?.getAttribute('data-figure-value') ?? null
    expect(valeur).not.toBeNull()
    // L'aperçu serveur a répondu : la carte « Taux de couverture » n'existe
    // que dans cette branche.
    expect(container.querySelector('[data-figure="couverture_pct"]')).not.toBeNull()
  }, { timeout: 5000 })
  return valeur
}

declarerBeforeEachDevis({ stockApi, ventesApi, produits: [PANNEAU, ONDULEUR], devis: () => devisRouvert(), localStorage: true })

function repondreAvecEconomie(eco) {
  ventesApi.postEtudeHorairePreview.mockResolvedValue({
    data: {
      ...CONTRAT,
      etude: {
        ...CONTRAT.etude,
        annuel: { ...ANNUEL, economie_sans_mad: eco, economie_avec_mad: eco },
      },
    },
  })
}

describe('ERR-QAH-FIG-PAYBACK-FORMULE-ECRAN — carte ROI de la branche serveur', () => {
  it('affiche le payback du MOTEUR (cashflow 25 ans), jamais coût ÷ économie', async () => {
    repondreAvecEconomie(4580)
    const { container } = renderEdition()
    const attendu = paybackMoteurHoraire(TOTAL_SANS, 4580, {
      annuel: { ...ANNUEL, economie_sans_mad: 4580, economie_avec_mad: 4580 },
      inverterReplaceCost: ONDULEUR_TTC,
    })
    expect(attendu.jamaisRembourse).toBe(false)
    // Témoin : la division naïve donnerait un AUTRE chiffre.
    expect(attendu.paybackYears).not.toBe(Math.round((TOTAL_SANS / 4580) * 100) / 100)
    expect(await paybackAffiche(container)).toBe(`${attendu.paybackYears} ans`)
    expect(ventesApi.postEtudeHorairePreview).toHaveBeenCalled()
  })

  it('un cumul qui ne croise jamais zéro : « Non rentabilisé sur 25 ans », jamais « 25 ans »', async () => {
    repondreAvecEconomie(300)
    expect(paybackMoteurHoraire(TOTAL_SANS, 300, {
      inverterReplaceCost: ONDULEUR_TTC }).jamaisRembourse).toBe(true)
    const { container } = renderEdition()
    expect(await paybackAffiche(container)).toBe('Non rentabilisé sur 25 ans')
  })
})
