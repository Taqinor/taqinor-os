/* ACAL149 — l'onglet « Matériel électrique ».

   Les réponses viennent de l'exemple COMMITTÉ `calepinage_entree_electrique.json`
   (jamais d'un objet tapé à la main) : le composant n'est pas mocké, seule la
   façade `calepinageApi` l'est. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: { entreeElectrique: vi.fn(), enregistrerEntreeElectrique: vi.fn() },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import MaterielElectrique, { libelleProvenance } from './MaterielElectrique'

const EXEMPLE = exempleContrat('calepinage', 'calepinage_entree_electrique')
const VIDE = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_vide')

const rendre = () => render(
  <MemoryRouter><MaterielElectrique calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('MaterielElectrique (ACAL149)', () => {
  it('envoie {module_produit, onduleur_produit} puis affiche les valeurs RELUES du GET', async () => {
    const complet = {
      ...EXEMPLE,
      candidats: {
        ...EXEMPLE.candidats,
        onduleurs: EXEMPLE.candidats.onduleurs.map((c) => ({ ...c, fiche_complete: true, champs_manquants: [] })),
      },
    }
    calepinageApi.calepinages.entreeElectrique
      .mockResolvedValueOnce({ data: { ...VIDE, candidats: EXEMPLE.candidats } })
      .mockResolvedValueOnce({ data: complet })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })

    rendre()
    await screen.findByTestId('acal149-formulaire')
    // Rien n'est désigné : « à désigner », message serveur (absents), aucun produit supposé.
    expect(screen.getByTestId('acal149-provenance-module')).toHaveTextContent('à désigner')

    await userEvent.selectOptions(document.getElementById('acal149-champ-module_produit'), '4112')
    await userEvent.click(screen.getByTestId('acal149-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalledTimes(1))
    const [id, corps] = calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0]
    expect(id).toBe(1)
    expect(corps).toEqual({ module_produit: 4112, onduleur_produit: null, optimiseur_produit: null })

    // Puis la RELECTURE du GET : les valeurs affichées sont celles du serveur.
    await waitFor(() => expect(calepinageApi.calepinages.entreeElectrique).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.getByTestId('acal149-provenance-module')).toHaveTextContent('désigné'))
    expect(document.getElementById('acal149-champ-module_produit')).toHaveValue('4112')
    expect(document.getElementById('acal149-champ-onduleur_produit')).toHaveValue('901')
  })

  it('provenance devis affichée et surchargeable', async () => {
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue(reponseContrat('calepinage', 'calepinage_entree_electrique'))
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })

    rendre()
    await screen.findByTestId('acal149-formulaire')
    expect(screen.getByTestId('acal149-provenance-onduleur')).toHaveTextContent('ligne du devis')
    expect(libelleProvenance(EXEMPLE.materiel.onduleur)).toBe('ligne du devis')

    // On surcharge le module par un autre choix : le corps le porte.
    await userEvent.selectOptions(document.getElementById('acal149-champ-module_produit'), '')
    await userEvent.click(screen.getByTestId('acal149-enregistrer'))
    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalled())
    expect(calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0][1].module_produit).toBeNull()
  })

  it('fiche incomplète non sélectionnable avec ses champs manquants', async () => {
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: EXEMPLE })

    rendre()
    await screen.findByTestId('acal149-formulaire')

    const incomplet = EXEMPLE.candidats.onduleurs.find((c) => c.fiche_complete === false)
    const option = screen.getByTestId(`acal149-candidat-${incomplet.id}`)
    expect(option).toBeDisabled()
    expect(option).toHaveTextContent(incomplet.champs_manquants[0])
  })

  it('un refus 400 s’affiche sous le champ nommé, mot pour mot', async () => {
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: VIDE })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
      response: { status: 400, data: { onduleur_produit: 'Produit hors société.' } },
    })

    rendre()
    await screen.findByTestId('acal149-formulaire')
    await userEvent.click(screen.getByTestId('acal149-enregistrer'))

    expect(await screen.findByTestId('acal149-erreur-onduleur_produit')).toHaveTextContent('Produit hors société.')
  })

  it('une lecture en panne le DIT, sans inventer de matériel', async () => {
    calepinageApi.calepinages.entreeElectrique.mockRejectedValue(new Error('boum'))

    rendre()

    expect(await screen.findByTestId('acal149-erreur')).toBeInTheDocument()
    expect(screen.queryByTestId('acal149-panneau')).toBeNull()
  })
})
