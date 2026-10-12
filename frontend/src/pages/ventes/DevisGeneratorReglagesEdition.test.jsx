// QJR527 — l'Édition complète (`?edit=`) charge AUSSI les réglages société
// (tarif kWh, rendement, TVA, productible, remise max) et relit le prix cible
// DU DEVIS. Avant : l'effet des réglages sortait dès qu'editId était posé —
// l'étude industrielle était re-persistée au tarif par défaut du code (et
// imprimée), et chaque enregistrement en édition EFFAÇAIT prix_cible_kwc.
//
// Écran RÉEL rendu, charge envoyée lue sur les API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorReglagesEdition.test.jsx
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
  profil: {
    onee_tarif_kwh: 1.5, prix_cible_kwc_defaut: 9000,
  },
    devis: () => devisIndustrielBrouillon({ id: 510, mode: 'industriel', prix_cible_kwc: '8500.00', etude_params: { scenario: 'Sans batterie', conso_annuelle: 60000 } }),
})

describe('QJR527 — Édition complète : réglages société chargés, prix cible du devis relu', () => {
  it('renvoie prix_cible_kwc du devis et re-persiste l\'étude au tarif SOCIÉTÉ', async () => {
    // CIQ125 — consommation déclarée (entrée v2) du devis 510 rouvert.
    const d510 = (await ventesApi.getDevisById()).data
    d510.etude_params = { ...d510.etude_params, consommation: { kwh_annuel: 60000 } }
    ventesApi.getDevisById.mockResolvedValue({ data: d510 })
    renderRouteSortie(DevisGenerator, makeStore(), '/ventes/devis/nouveau?edit=510', 'APRES-ENREGISTREMENT')
    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalled())
    await waitFor(() => expect(parametresApi.getProfile).toHaveBeenCalled())
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Industriel/ })).toHaveAttribute('aria-checked', 'true'))
    const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await userEvent.click(bouton)
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled())

    // La cible DU DEVIS gagne (jamais effacée, jamais le défaut société 9000).
    const payload = ventesApi.replaceLignesDevis.mock.calls.at(-1)[2].entete
    expect(payload.prix_cible_kwc).toBe('8500')

    // CIQ126 — l'étude C&I n'est plus calculée par l'écran (ni au tarif de la
    // société ni au 1,75 du code) : seules les ENTRÉES partent, le serveur
    // écrit les dérivées (propriétaire `moteur_ci`).
    const etude = ventesApi.patchEtudeParams.mock.calls.at(-1)[1]
    expect(etude).not.toHaveProperty('payback')
    expect(etude).not.toHaveProperty('taux_autoconso')
    expect(etude.consommation.kwh_annuel).toBe(60000)
  })
})
