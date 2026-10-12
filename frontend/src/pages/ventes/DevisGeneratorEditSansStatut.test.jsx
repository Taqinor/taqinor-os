// QJR515 (Groupe QJR5, D-QJR5-1) — enregistrer l'Édition complète ne
// rétrograde JAMAIS un devis envoyé en brouillon : `statut` n'est envoyé que
// par la création (atomic), jamais par le PATCH d'édition. L'écran RÉEL est
// rendu et ce que l'enregistrement envoie est lu sur les API mockées (aucune
// lecture de source, QJR239). Le devis rouvert porte l'identité et le statut
// de l'exemple COMMITTÉ du contrat `devis_modifiabilite.json` (PACT10 —
// jamais un mock écrit à la main).
//
// QJR541 — côté serveur `statut` est désormais en LECTURE SEULE : un PATCH qui
// le porterait répondrait 200 SANS le changer (plus de 400). L'écran continue
// de ne jamais l'envoyer, brouillon comme envoyé.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorEditSansStatut.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'


vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiAvecLead())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { bancEdition } from './devisGenerator.testHelpers.jsx'


const { renderEdition, devisRouvert } = bancEdition({ DevisGenerator, stockApi, crmApi, ventesApi, dateEnvoi: null })

describe("QJR515 — le PATCH d'édition ne porte jamais `statut`", () => {
  it('en ?edit=, patchDevis part SANS clé statut', async () => {
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await userEvent.click(bouton)
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [id, , { entete: payload }] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(id).toBe(rouvert.data.id)
    expect(payload).not.toHaveProperty('statut')
    expect(ventesApi.createDevisAtomic).not.toHaveBeenCalled()
  })

  it('envoyé : le PATCH part sans statut (le serveur garde « envoyé »)', async () => {
    const rouvert = devisRouvert('exemple_envoye')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    ventesApi.patchDevis.mockResolvedValue({ data: { id: rouvert.data.id, statut: 'envoye' } })
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, , { entete: payload }] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(payload).not.toHaveProperty('statut')
  })
})
