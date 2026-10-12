// QJR530 — rouvrir un devis MULTI-VILLAS restaure le mode « villas » et ses
// groupes. Avant : la réouverture ne restaurait que le ×N (`nombre_proprietes`) ;
// `groupe_index` valait null hors mode 'villas' à l'enregistrement, donc
// ouvrir puis enregistrer SANS retouche dégroupait tout (même après QJR517,
// qui fait persister groupe_index / groupe_label côté serveur).
//
// Écran RÉEL rendu, charge envoyée lue sur les API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorVillasReouverture.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'


vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock({ getPrixApplicable: vi.fn() }))

import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { ONDULEUR, PANNEAU, declarerBeforeEachDevis, makeDevisStore, mockEcrituresDevisOk, renderRouteSortie } from './devisGenerator.testHelpers.jsx'


const CABLE = {
  id: 103, nom: 'Câble solaire 6mm²', prix_vente: 20, tva: 20, is_archived: false,
}

const makeStore = () => makeDevisStore('normal', 'Commercial')

declarerBeforeEachDevis({
  stockApi, ventesApi, produits: [PANNEAU, ONDULEUR, CABLE], localStorage: true,
  extra: () => {
    ventesApi.getDevisById.mockResolvedValue({
      data: {
        id: 530, reference: 'DEV-202609-0530', statut: 'brouillon', modifiable: true, raison_non_modifiable: '', revision_possible: false, is_active: true, client: 9,
        mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
        etude_params: { scenario: 'Sans batterie' },
        lignes: [
          { id: 1, produit: CABLE.id, designation: CABLE.nom, quantite: '50',
            prix_unitaire: '20.00', taux_tva: '20.00', ordre: 0,
            type_ligne: 'produit', optionnelle: false, groupe_index: 0, groupe_label: '' },
          { id: 2, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '8',
            prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 1,
            type_ligne: 'produit', optionnelle: false, groupe_index: 1, groupe_label: 'Villa A' },
          { id: 3, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
            prix_unitaire: '9000.00', taux_tva: '20.00', ordre: 2,
            type_ligne: 'produit', optionnelle: false, groupe_index: 2, groupe_label: 'Villa B' },
        ],
      },
    })
    mockEcrituresDevisOk(ventesApi)
  },
})

describe('QJR530 — réouverture d’un devis multi-villas', () => {
  it('restaure le mode villas : colonne Villa rendue et groupes renvoyés tels quels sans retouche', async () => {
    renderRouteSortie(DevisGenerator, makeStore(), '/ventes/devis/nouveau?edit=530', 'APRES-ENREGISTREMENT')
    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalledWith('530'))
    // La colonne « Villa » de la table des lignes est rendue (mode 'villas').
    expect(await screen.findByRole('columnheader', { name: 'Villa' })).toBeInTheDocument()
    const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await userEvent.click(bouton)
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const lignes = ventesApi.replaceLignesDevis.mock.calls.at(-1)[1]
    const groupes = Object.fromEntries(lignes.map(l =>
      [l.designation, [l.groupe_index, l.groupe_label]]))
    expect(groupes).toEqual({
      [CABLE.nom]: [0, ''],
      [PANNEAU.nom]: [1, 'Villa A'],
      [ONDULEUR.nom]: [2, 'Villa B'],
    })
  })
})
