// QJR544 (contrat QJR504, devis_replace_lines_entete.json) — enregistrer
// l'Édition complète = UN seul appel replace-lines portant l'en-tête et les
// choix d'écran : zéro PATCH d'en-tête, donc plus d'en-tête appliqué aux
// anciennes lignes quand les lignes sont refusées. L'écran RÉEL est rendu ;
// ce que l'enregistrement envoie est lu sur les API mockées (QJR239).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorEditionAtomique.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiAvecLead())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { bancEdition } from './devisGenerator.testHelpers.jsx'


const { renderEdition, devisRouvert } = bancEdition({ DevisGenerator, stockApi, crmApi, ventesApi })

describe('QJR544 — une édition = un seul replace-lines', () => {
  it('UN replaceLignesDevis avec entete (sans statut) et choix d\u2019écran, zéro patchDevis', async () => {
    const rouvert = devisRouvert('exemple_envoye')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1))
    const [id, lignes, extra] = ventesApi.replaceLignesDevis.mock.calls[0]
    expect(id).toBe(rouvert.data.id)
    expect(Array.isArray(lignes)).toBe(true)
    const attendu = exempleContrat('ventes', 'devis_replace_lines_entete', 'corps')
    for (const cle of Object.keys(extra.entete)) {
      expect(Object.keys(attendu.entete)).toContain(cle)
    }
    expect(extra.entete).not.toHaveProperty('statut')
    expect(extra.entete.taux_tva).toBeDefined()
    expect(extra.etude_params).toEqual(expect.objectContaining({ scenario: 'Sans batterie' }))
    expect(ventesApi.patchDevis).not.toHaveBeenCalled()
  })
})
