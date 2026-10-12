// CIQ126 (remplace QJR528) — le C&I n'a plus de part diurne d'écran : le
// profil de charge est DÉCLARÉ au moteur serveur (jours, plages, talon). Un
// devis industriel v1 rouvert (part_diurne_pct 65) n'affiche aucun curseur et
// ne renvoie jamais cette clé, ni aucune dérivée de l'étude locale.
// Écran RÉEL rendu, charge envoyée lue sur les API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorPartDiurne.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'


vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock({
    getPrixApplicable: vi.fn(),
}))

import stockApi from '../../api/stockApi'
import parametresApi from '../../api/parametresApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { bancIndustriel, devisIndustrielBrouillon, renderRouteSortie } from './devisGenerator.testHelpers.jsx'

const { makeStore } = bancIndustriel({ DevisGenerator, stockApi, ventesApi, parametresApi,
    devis: () => devisIndustrielBrouillon({ id: 528, mode: 'industriel',  etude_params: { scenario: 'Sans batterie', conso_annuelle: 60000, part_diurne_pct: 65 } }),
})

describe('CIQ126 — part diurne industrielle : ni relue, ni affichée, ni renvoyée', () => {
  it('?edit= industriel part_diurne_pct 65 → aucun curseur, aucune clé v1 renvoyée', async () => {
    const devis528 = await ventesApi.getDevisById()
    Object.assign(devis528.data.etude_params, { consommation: { kwh_annuel: 62000 } })
    ventesApi.getDevisById.mockResolvedValue(devis528)
    renderRouteSortie(DevisGenerator, makeStore(), '/ventes/devis/nouveau?edit=528', 'APRES-ENREGISTREMENT')
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Industriel/ })).toHaveAttribute('aria-checked', 'true'))
    await screen.findByTestId('ci-profil')
    expect(screen.queryByText('Consommation diurne (%)')).toBeNull()
    const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await userEvent.click(bouton)
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled())
    const etude = ventesApi.patchEtudeParams.mock.calls.at(-1)[1]
    for (const k of ['part_diurne_pct', 'taux_autoconso', 'taux_couverture', 'payback', 'etude_kwc_base']) {
      expect(etude).not.toHaveProperty(k)
    }
    expect(etude.consommation.kwh_annuel).toBe(62000)
  })
})
