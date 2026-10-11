// QJR546 — appliquer un modèle REMPLACE les lignes à l'écran (édition comme
// création) : un modèle d'un autre marché pose ses lignes, sa remise, sa TVA et
// son marché ; une ligne au produit sans prix est ABSENTE et NOMMÉE ; l'étude du
// client source n'est jamais reprise. L'écran RÉEL est rendu ; ce que
// l'Enregistrer suivant envoie est lu sur les API mockées (QJR239).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorPresetApplique.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { estimerMois } from '../../features/ventes/solar'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { toast } from '../../ui/confirm'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiAvecLead())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition({
    getPresets: vi.fn(() => Promise.resolve({ data: [] })),
    savePreset: vi.fn(),
    deletePreset: vi.fn(),
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { LEAD, ONDULEUR, PANNEAU, declarerBeforeEachDevis, lignesResidentielles, makeDevisStore, mockEcrituresDevisOk, renderEditionPage } from './devisGenerator.testHelpers.jsx'

const PANNEAU_SANS_PRIX = {
  id: 103, nom: 'Panneau archivé 400W', prix_vente: 0, tva: 20,
  is_archived: false, prix_achat: 0,
}
const PRESET = {
  id: 9, nom: 'Modèle usine', mode_installation: 'industriel',
  taux_tva: '10.00', remise_globale: '3.00',
  etude_params_snapshot: { factures_mensuelles_reelles: [99, 99, 99] },
  lignes_snapshot: [
    { produit_id: 101, designation: 'Panneau Canadien Solar 715W', quantite: '20',
      prix_unitaire: '1000', remise: '0', taux_tva: '10' },
    { produit_id: 102, designation: 'Onduleur réseau 5kW Monophasé', quantite: '2',
      prix_unitaire: '8000', remise: '0', taux_tva: '20' },
    { produit_id: 103, designation: 'Panneau archivé 400W', quantite: '4',
      prix_unitaire: '500', remise: '0', taux_tva: '20' },
  ],
}

function devisRouvert(variante) {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', variante)
  return {
    data: {
      ...contrat, lead: LEAD.id, client: 9, date_envoi: '2026-09-28T10:00:00Z',
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: {
        scenario: 'Sans batterie',
        factures_mensuelles_reelles: estimerMois(3000, 3000),
      },
      lignes: lignesResidentielles(PANNEAU, ONDULEUR),
    },
  }
}

const makeStore = () => makeDevisStore('normal', 'Commercial')

function renderEdition(id) {
  return renderEditionPage(DevisGenerator, makeStore(), id, 'APRES-ENREGISTREMENT')
}

declarerBeforeEachDevis({
  stockApi, crmApi, ventesApi, produits: [PANNEAU, ONDULEUR, PANNEAU_SANS_PRIX], localStorage: true,
  extra: () => {
    ventesApi.getPresets.mockResolvedValue({ data: [PRESET] })
    crmApi.getLead.mockResolvedValue({ data: LEAD })
    mockEcrituresDevisOk(ventesApi)
  },
})

describe('QJR546 — un modèle appliqué remplace les lignes à l’écran', () => {
  it('modèle d’un autre marché : lignes, remise, TVA et marché posés ; produit sans prix absent et nommé', async () => {
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    const avertir = vi.spyOn(toast, 'warning')
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByRole('button', { name: /Modèles de devis/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(avertir).toHaveBeenCalled())
    expect(avertir.mock.calls.at(-1)[0]).toMatch(/Panneau archivé 400W/)
    // CIQ125 — un devis industriel exige une consommation ou une taille explicite.
    fireEvent.change(await screen.findByLabelText(/Taille explicite/), { target: { value: '10' } })

    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, lignes, { entete }] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    const produits = lignes.map(l => Number(l.produit))
    expect(produits).toContain(PANNEAU.id)
    expect(produits).toContain(ONDULEUR.id)
    expect(produits).not.toContain(PANNEAU_SANS_PRIX.id)
    const panneaux = lignes.find(l => Number(l.produit) === PANNEAU.id)
    expect(Number(panneaux.quantite)).toBe(20)
    expect(String(entete.remise_globale)).toBe('3')
    expect(parseFloat(entete.taux_tva)).toBe(10)
    expect(entete.mode_installation).toBe('industriel')
    expect(ventesApi.patchDevis).not.toHaveBeenCalled()
  })
})

describe('QJR547 — les lignes du modèle passent par le mappeur de réouverture', () => {
  it('ligne variante « avec » + prix_manuel → verrou de prix et variante gardés', async () => {
    ventesApi.getPresets.mockResolvedValue({ data: [{
      ...PRESET, mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0.00',
      lignes_snapshot: [
        { produit_id: 101, designation: 'Panneau Canadien Solar 715W', quantite: '8',
          prix_unitaire: '1000', remise: '0', taux_tva: '10', ordre: 0, variante: '',
          type_ligne: 'produit', optionnelle: false, prix_manuel: false, quantite_manuelle: false },
        { produit_id: 102, designation: 'Onduleur réseau 5kW Monophasé', quantite: '1',
          prix_unitaire: '7500', remise: '0', taux_tva: '20', ordre: 1, variante: 'avec',
          type_ligne: 'produit', optionnelle: false, prix_manuel: true, quantite_manuelle: false },
      ],
    }] })
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByRole('button', { name: /Modèles de devis/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Appliquer' }))
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, lignes] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    const onduleur = lignes.find(l => Number(l.produit) === ONDULEUR.id)
    expect(onduleur.variante).toBe('avec')
    expect(onduleur.prix_manuel).toBe(true)
  })
})
