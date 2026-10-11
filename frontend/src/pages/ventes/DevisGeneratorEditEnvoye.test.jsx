// QJR532 (Groupe QJR5, D-QJR5-1) — un devis ENVOYÉ s'ouvre et se corrige sur
// place dans l'Édition complète (bandeau non bloquant, enregistrement sans
// `statut`) ; un ACCEPTÉ affiche la raison serveur (`raison_non_modifiable`) et
// quitte l'écran. L'écran RÉEL est rendu ; le devis rouvert porte l'identité et
// les droits de l'exemple COMMITTÉ du contrat `devis_modifiabilite.json`
// (PACT10 — jamais un mock écrit à la main).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorEditEnvoye.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { toast } from '../../ui/confirm'

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

describe('QJR532 — un devis envoyé se corrige sur place', () => {
  it('envoyé : formulaire chargé, bandeau non bloquant, enregistrement SANS statut', async () => {
    const rouvert = devisRouvert('exemple_envoye')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    const erreur = vi.spyOn(toast, 'error')
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    const bandeau = await screen.findByTestId('devis-envoye-banner')
    expect(bandeau.textContent).toMatch(/Devis envoyé le .*28/)
    expect(bandeau.textContent).toMatch(/visibles sur le lien de la proposition/)
    expect(bandeau.textContent).toMatch(/Le statut reste Envoyé/)
    expect(screen.queryByText(/nouvelle version/i)).toBeNull()
    expect(erreur).not.toHaveBeenCalled()
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [id, , { entete: payload }] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(id).toBe(rouvert.data.id)
    expect(payload).not.toHaveProperty('statut')
  })

  it('brouillon : pas de bandeau « envoyé »', async () => {
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    expect(screen.queryByTestId('devis-envoye-banner')).toBeNull()
  })

  it('accepté : toast de la raison serveur, retour, aucun formulaire d\'édition', async () => {
    const rouvert = devisRouvert('exemple_accepte')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    const erreur = vi.spyOn(toast, 'error')
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(erreur).toHaveBeenCalledWith('Devis accepté : révisez-le'))
    await screen.findByText('APRES-ENREGISTREMENT')
    expect(ventesApi.patchDevis).not.toHaveBeenCalled()
  })
})
