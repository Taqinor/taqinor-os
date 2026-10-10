// AGNR21 — trois issues pour l'enregistrement : ok / PARTIEL / échec. Quand
// `PATCH etude-params` est refusé APRÈS l'écriture des lignes, l'écran reste
// sur le formulaire, le message serveur est visible dans un bandeau
// persistant et un nouvel essai ne crée jamais un second devis.
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrEnregistrementPartiel.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'

import { DATE_FIGEE, LEAD, monter, attendreStable, DEVIS_REGISTRE, autoRemplirAvecPanneaux } from './DevisGeneratorGoldenHarnais'
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

const REFUS = {
  response: {
    status: 400,
    data: { detail: 'Facture(s) mensuelle(s) inférieure(s) aux lignes fixes du compteur (39,94 MAD TTC/mois).' },
  },
}

cycleEcran({ date: DATE_FIGEE })

const cliquerEnregistrer = async (re) => {
  const b = [...document.querySelectorAll('button')].find((x) => re.test(x.textContent || ''))
  expect(b, `bouton ${re}`).toBeTruthy()
  await act(async () => { fireEvent.click(b) })
}

describe('AGNR21 — enregistrement partiel', () => {
  it('édition : étude refusée ⇒ formulaire conservé, bandeau persistant, aucun panneau de succès', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_REGISTRE.id}`, {
      devis: DEVIS_REGISTRE,
      avant: ({ ventesApi }) => { ventesApi.patchEtudeParams.mockRejectedValue(REFUS) },
    })
    await attendreStable(vue.container, act)
    await cliquerEnregistrer(/Enregistrer les modifications/)
    await waitFor(() => expect(vue.ventesApi.patchEtudeParams).toHaveBeenCalled())
    await attendreStable(vue.container, act)
    expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('APRES-ENREGISTREMENT')).toBeNull()
    expect(document.querySelector('form')).not.toBeNull()
    const bandeau = screen.getByTestId('reserve-enregistrement')
    expect(bandeau.textContent).toMatch(/Devis enregistré, étude non attachée : Facture\(s\) mensuelle\(s\)/)
    // Un nouvel essai réédite le même devis.
    await cliquerEnregistrer(/Enregistrer les modifications/)
    await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(2))
    expect(vue.ventesApi.createDevisAtomic).not.toHaveBeenCalled()
  }, 60000)

  it('création : étude refusée ⇒ le nouvel essai édite le devis créé, jamais un second', async () => {
    const vue = await monter(`/ventes/devis/nouveau?lead=${LEAD.id}`, {
      avant: ({ ventesApi }) => {
        ventesApi.composerDevis.mockResolvedValue({ data: exempleContrat('ventes', 'devis_composition', 'exemple') })
        ventesApi.createDevisAtomic.mockResolvedValue({
          data: { id: 900, reference: 'DEV-202610-0900', statut: 'brouillon', updated_at: '2026-10-08T09:00:00Z' },
        })
        ventesApi.patchEtudeParams.mockRejectedValue(REFUS)
      },
    })
    await attendreStable(vue.container, act)
    await autoRemplirAvecPanneaux('8')
    await waitFor(() => expect(vue.ventesApi.composerDevis).toHaveBeenCalled())
    await attendreStable(vue.container, act)
    await cliquerEnregistrer(/Créer le devis/)
    await waitFor(() => expect(vue.ventesApi.createDevisAtomic).toHaveBeenCalledTimes(1), { timeout: 5000 })
    await attendreStable(vue.container, act)
    expect(screen.getByTestId('reserve-enregistrement')).toBeTruthy()
    await cliquerEnregistrer(/Enregistrer les modifications/)
    await waitFor(() => expect(vue.ventesApi.replaceLignesDevis).toHaveBeenCalled())
    expect(vue.ventesApi.replaceLignesDevis.mock.calls.at(-1)[0]).toBe(900)
    expect(vue.ventesApi.createDevisAtomic).toHaveBeenCalledTimes(1)
  }, 60000)
})
