import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import Organigramme from './Organigramme.jsx'

/* NTHCM2 — écran « Organigramme ». PACT10 : la charge utile n'est PAS retapée
   ici, elle vient de l'exemple committé
   `apps/rh/contract_samples/organigramme.json` — le même fichier que
   `scripts/check_api_shapes.py` compare au dictionnaire réellement renvoyé par
   `DossierEmployeViewSet.organigramme`. Si le serveur change de forme, ce test
   casse tout seul. */

const CONTRAT = exempleContrat('rh', 'organigramme')
const RACINE = CONTRAT.racines[0]
const CHEF = RACINE.subordonnes[0]
const POSEUSE = CHEF.subordonnes[0]

vi.mock('../../api/rhApi', () => ({
  default: { getOrganigramme: vi.fn() },
}))

function renderEcran() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <Organigramme />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('Organigramme (NTHCM2)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('affiche toute la société imbriquée depuis la racine', async () => {
    rhApi.getOrganigramme.mockResolvedValue(
      reponseContrat('rh', 'organigramme'))
    renderEcran()

    expect(await screen.findByText(RACINE.employe)).toBeTruthy()
    // L'arbre est déplié : les descendants sont rendus, pas seulement la
    // racine.
    expect(screen.getByText(CHEF.employe)).toBeTruthy()
    expect(screen.getByText(POSEUSE.employe)).toBeTruthy()
    expect(screen.getByText(String(CONTRAT.effectif))).toBeTruthy()
  })

  it('replie une branche au clic et la redéplie', async () => {
    rhApi.getOrganigramme.mockResolvedValue(
      reponseContrat('rh', 'organigramme'))
    renderEcran()
    await screen.findByText(RACINE.employe)

    fireEvent.click(screen.getByLabelText(`Replier ${CHEF.employe}`))
    expect(screen.queryByText(POSEUSE.employe)).toBeNull()

    fireEvent.click(screen.getByLabelText(`Déplier ${CHEF.employe}`))
    expect(screen.getByText(POSEUSE.employe)).toBeTruthy()
  })

  it('transmet la recherche au serveur (jamais un filtrage local)', async () => {
    rhApi.getOrganigramme.mockResolvedValue(
      reponseContrat('rh', 'organigramme'))
    renderEcran()
    await screen.findByText(RACINE.employe)

    fireEvent.change(screen.getByLabelText('Rechercher un collaborateur'),
      { target: { value: 'bennani' } })

    await waitFor(() => {
      expect(rhApi.getOrganigramme).toHaveBeenCalledWith({ q: 'bennani' })
    })
  })

  it('rend l’état vide du contrat sans planter', async () => {
    rhApi.getOrganigramme.mockResolvedValue(
      reponseContrat('rh', 'organigramme', 'exemple_vide'))
    renderEcran()
    expect(await screen.findByText('Aucun collaborateur à afficher'))
      .toBeTruthy()
  })

  it('affiche la coupure d’une branche tronquée au lieu de boucler', async () => {
    const tronque = JSON.parse(JSON.stringify(CONTRAT))
    tronque.racines[0].subordonnes[0].tronque = true
    tronque.racines[0].subordonnes[0].subordonnes = []
    rhApi.getOrganigramme.mockResolvedValue({ data: tronque })
    renderEcran()

    expect(await screen.findByText(/Branche coupée/)).toBeTruthy()
    expect(screen.queryByText(POSEUSE.employe)).toBeNull()
  })
})
