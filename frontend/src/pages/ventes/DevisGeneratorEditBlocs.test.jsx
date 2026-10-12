// QJR540 — les blocs livrés du modal DevisForm (supprimé) vivent dans
// l'Édition complète : le calepinage qui pilote le devis (CAL40), les pièces
// jointes du devis (ventes.devis), les compteurs de relations et le bandeau
// « En attente de signature client ». L'écran RÉEL est rendu ; identité/droits
// et clé `calepinage` viennent des exemples COMMITTÉS des contrats.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorEditBlocs.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'

import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiAvecLead())
vi.mock('../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/parametresApi', () => ({
  default: { getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
}))
vi.mock('../../api/recordsApi', () => ({
  default: {
    getAttachments: vi.fn(() => Promise.resolve({ data: [] })),
    deleteAttachment: vi.fn(),
  },
}))
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import recordsApi from '../../api/recordsApi'
import DevisGenerator from './DevisGenerator'
import { bancEdition, devisResidentielRouvert } from './devisGenerator.testHelpers.jsx'


function devisRouvert(variante, calepinage = 'exemple') {
  return devisResidentielRouvert(variante, {
    id: 12,
    ...exempleContrat('calepinage', 'calepinage_du_devis', calepinage),
    factures_liees: [{ id: 3 }], bon_commande_etat: null, chantier: null,
    layout_stale: null, layout_nb_panneaux: null,
  })
}

const { renderEdition } = bancEdition({ DevisGenerator, stockApi, crmApi, ventesApi })

describe('QJR540 — blocs repris de DevisForm dans l’Édition complète', () => {
  it('?edit=12 avec calepinage : bloc calepinage, pièces jointes ventes.devis 12, compteurs', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert('exemple_envoye'))
    renderEdition(12)
    expect(await screen.findByTestId('cal-bloc-calepinage-devis')).toBeTruthy()
    await waitFor(() => expect(recordsApi.getAttachments).toHaveBeenCalledWith('ventes.devis', 12))
    expect(screen.getByText('Pièces jointes')).toBeTruthy()
    expect(screen.getByText(/factures liées/)).toBeTruthy()
    expect(screen.getByTestId('devis-attente-signature').textContent)
      .toMatch(/En attente de signature client/)
  })

  it('brouillon sans calepinage : aucun bloc calepinage vide, pas de bandeau de signature', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert('exemple_brouillon', 'exemple_vide'))
    renderEdition(12)
    await waitFor(() => expect(recordsApi.getAttachments).toHaveBeenCalledWith('ventes.devis', 12))
    expect(screen.queryByTestId('cal-bloc-calepinage-devis')).toBeNull()
    expect(screen.queryByTestId('devis-attente-signature')).toBeNull()
  })
})

