// QJR575 — le défaut « Non précisée » de la catégorie commerciale se persiste
// null : un devis commercial sans categorie_commerciale, rouvert puis
// enregistré, renvoie `categorie_commerciale: null` (jamais la sentinelle).
// Écran RÉEL rendu, charge envoyée lue sur les API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorCategorieCommerciale.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'


vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition())

import stockApi from '../../api/stockApi'
import parametresApi from '../../api/parametresApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { bancIndustriel, devisIndustrielBrouillon, renderRouteSortie } from './devisGenerator.testHelpers.jsx'

const { makeStore } = bancIndustriel({ DevisGenerator, stockApi, ventesApi, parametresApi,
    devis: () => devisIndustrielBrouillon({ id: 575, mode: 'commercial',  etude_params: { scenario: 'Sans batterie', conso_annuelle: 60000 } }),
})

describe('QJR575 — catégorie commerciale « Non précisée » persistée null', () => {
  it('?edit= commercial sans catégorie → enregistrement avec categorie_commerciale null', async () => {
    // CIQ125 — un devis C&I sans consommation ne s'enregistre pas : le devis
    // rouvert porte sa consommation déclarée (entrée v2).
    const rouvert575 = (await ventesApi.getDevisById()).data
    ventesApi.getDevisById.mockResolvedValue({ data: { ...rouvert575,
      etude_params: { ...rouvert575.etude_params, consommation: { kwh_annuel: 48000 } } } })
    renderRouteSortie(DevisGenerator, makeStore(), '/ventes/devis/nouveau?edit=575', 'APRES-ENREGISTREMENT')
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Commercial/ })).toHaveAttribute('aria-checked', 'true'))
    const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await userEvent.click(bouton)
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled())
    const etude = ventesApi.patchEtudeParams.mock.calls.at(-1)[1]
    expect(etude).toHaveProperty('categorie_commerciale', null)
  })
})
