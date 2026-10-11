// QJR572 — Scénario, Option recommandée et nombre de panneaux de l'Édition
// complète suivent le REGISTRE de surcharges (il gagne au PDF) : une surcharge
// posée s'affiche à la réouverture, et la changer à l'écran met le registre
// à jour à l'enregistrement. Registre vide → aucun appel au registre.
//
// L'écran RÉEL est rendu (`?edit=<id>`) ; ce que l'enregistrement envoie est
// lu sur les API mockées (garde QJR239 : aucun regex sur le source).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorRegistreEcran.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiAvecLead())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock({
    lireOverrides: vi.fn(),
    getPrixApplicable: vi.fn(),
}))

import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { ONDULEUR, PANNEAU, declarerBeforeEachDevis, lignesResidentielles, makeDevisStore, renderEditionPage } from './devisGenerator.testHelpers.jsx'

const LES_DEUX = 'Les deux (Sans + Avec)'

function devisRouvert() {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', 'exemple_brouillon')
  return {
    data: {
      ...contrat, client: 9, lead: null,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: LES_DEUX },
      lignes: lignesResidentielles(PANNEAU, ONDULEUR),
    },
  }
}

const registre = (effectif) => ({ overrides: {}, effectif, lignes: {} })
const REGISTRE_SANS = registre({
  scenario: { auto: LES_DEUX, manuel: 'Sans batterie', effectif: 'Sans batterie', source: 'manuel' },
})
const REGISTRE_VIDE = registre({
  scenario: { auto: LES_DEUX, manuel: null, effectif: LES_DEUX, source: 'auto' },
})

const makeStore = () => makeDevisStore('normal', 'Commercial')

function renderEdition(id) {
  return renderEditionPage(DevisGenerator, makeStore(), id, 'APRES-ENREGISTREMENT')
}

const scenarioAffiche = () => document.getElementById('gen-scenario')?.textContent ?? ''

declarerBeforeEachDevis({
  stockApi, ventesApi, produits: [PANNEAU, ONDULEUR], localStorage: true,
  extra: () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert())
    ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
    ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
    ventesApi.poserOverrides.mockImplementation((_id, patch) => Promise.resolve({
      data: registre({ scenario: { auto: LES_DEUX, manuel: patch.scenario?.valeur,
        effectif: patch.scenario?.valeur, source: 'manuel' } }),
    }))
  },
})

async function enregistrer() {
  await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
  await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1))
}

describe('QJR572 — l’écran suit le registre de surcharges', () => {
  it('un scénario imposé par le registre s’affiche à la réouverture, avec le retour à l’automatique', async () => {
    ventesApi.lireOverrides.mockResolvedValue({ data: REGISTRE_SANS })
    renderEdition(devisRouvert().data.id)
    await waitFor(() => expect(scenarioAffiche()).toContain('Sans batterie seulement'))
    expect(screen.getByTestId('registre-impose-scenario')).toHaveTextContent(/revenir à l.automatique/)
  })

  it('changer le scénario imposé puis enregistrer pose la nouvelle valeur au registre', async () => {
    ventesApi.lireOverrides.mockResolvedValue({ data: REGISTRE_SANS })
    renderEdition(devisRouvert().data.id)
    await waitFor(() => expect(scenarioAffiche()).toContain('Sans batterie seulement'))
    await userEvent.click(document.getElementById('gen-scenario'))
    await userEvent.click(await screen.findByRole('option', { name: /Les deux/ }))
    await waitFor(() => expect(scenarioAffiche()).toContain('Les deux'))
    await enregistrer()
    await waitFor(() => expect(ventesApi.poserOverrides).toHaveBeenCalledTimes(1))
    const [id, patch] = ventesApi.poserOverrides.mock.calls[0]
    expect(id).toBe(devisRouvert().data.id)
    expect(patch).toEqual({ scenario: { valeur: LES_DEUX } })
    expect(ventesApi.regenererOverride).not.toHaveBeenCalled()
  })

  it('registre sans surcharge : l’enregistrement n’écrit rien au registre', async () => {
    ventesApi.lireOverrides.mockResolvedValue({ data: REGISTRE_VIDE })
    renderEdition(devisRouvert().data.id)
    await waitFor(() => expect(ventesApi.lireOverrides).toHaveBeenCalled())
    expect(screen.queryByTestId('registre-impose-scenario')).toBeNull()
    await enregistrer()
    expect(ventesApi.poserOverrides).not.toHaveBeenCalled()
    expect(ventesApi.regenererOverride).not.toHaveBeenCalled()
  })
})
