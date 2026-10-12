// QJR580 — en Édition complète, le lead et le client du devis sont en LECTURE
// SEULE : l'enregistrement d'édition ne porte ni lead ni client, donc un
// sélecteur actif laissait croire à une réaffectation (jetée) tout en
// ré-semant les factures du NOUVEAU lead sur le devis de l'ANCIEN. « Changer de
// client = créer un nouveau devis ». Le nom vient du devis (lead_nom /
// client_nom, DevisSerializer), jamais de `leads.find` (lead hors page 1).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorLeadLectureSeule.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { estimerMois } from '../../features/ventes/solar'
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock({
    // Le lead 7 du devis n'est PAS dans la page de leads chargée.
    getLeads: vi.fn(() => Promise.resolve({ data: [{ id: 99, nom: 'Autre', prenom: 'Lead' }] })),
    getLead: vi.fn(),
}))
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { ONDULEUR, PANNEAU, declarerBeforeEachDevis, lignesResidentielles, makeDevisStore, mockEcrituresDevisOk, renderRouteSortie } from './devisGenerator.testHelpers.jsx'


function devis42() {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', 'exemple_brouillon')
  return {
    data: {
      ...contrat, id: 42, lead: 7, client: 9,
      lead_nom: 'Hamid Lointain', client_nom: 'Hamid',
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie', factures_mensuelles_reelles: estimerMois(2000, 2000) },
      lignes: lignesResidentielles(PANNEAU, ONDULEUR),
    },
  }
}

const makeStore = () => makeDevisStore('normal', 'Commercial')

declarerBeforeEachDevis({
  stockApi, crmApi, ventesApi, produits: [PANNEAU, ONDULEUR], localStorage: true,
  extra: () => {
    // La relecture du lead par id échoue : le libellé vient du DEVIS.
    crmApi.getLead.mockRejectedValue(new Error('indisponible'))
    ventesApi.getDevisById.mockResolvedValue(devis42())
    mockEcrituresDevisOk(ventesApi)
  },
})

describe('QJR580 — lead et client en lecture seule en Édition complète', () => {
  it('?edit=42 (lead 7 hors page de leads) : aucun sélecteur, nom du devis affiché, enregistrement sans lead', async () => {
    const { container } = renderRouteSortie(DevisGenerator, makeStore(), '/ventes/devis/nouveau?edit=42', 'APRES-ENREGISTREMENT')
    const lecture = await screen.findByTestId('gen-lead-lecture-seule')
    await waitFor(() => expect(lecture.textContent).toMatch(/Hamid Lointain/))
    expect(lecture.textContent).toMatch(/Changer de client = créer un nouveau devis/)
    expect(container.querySelector('#gen-lead')).toBeNull()
    expect(container.querySelector('#gen-client')).toBeNull()

    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    expect(screen.queryByText('Sélectionnez un lead ou un client')).toBeNull()
    const [, , { entete: payload }] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(payload).not.toHaveProperty('lead')
    expect(payload).not.toHaveProperty('client')
  })
})
