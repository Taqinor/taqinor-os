/* ACAL266 — l'onglet Affectation GARDE et MONTRE les affectations obsolètes.

   Une ligne manuelle dont le module n'existe plus (pan réduit ou supprimé,
   `electrique.affectation_obsolete`, ACAL265) n'est JAMAIS élaguée en
   silence au POST : elle repart avec l'enregistrement d'une autre chaîne, et
   ne disparaît qu'après le geste nommé « Retirer l'affectation obsolète ».

   Réponses tirées du contrat COMMITTÉ `calepinage_resultat.json`
   (`exemple_perime` porte `affectation_obsolete: [{module: 'z2#9', …}]`) et
   `calepinage_entree_electrique.json` (relecture de l'entrée enregistrée). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      resultat: vi.fn(),
      evaluerElectrique: vi.fn(),
      enregistrerEntreeElectrique: vi.fn(),
      entreeElectrique: vi.fn(),
    },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import AffectationChaines from './AffectationChaines'

const perime = () => reponseContrat('calepinage', 'calepinage_resultat', 'exemple_perime')
const [OBSOLETE] = perime().data.electrique.affectation_obsolete
const [A1] = perime().data.electrique.affectation.map((ligne) => ligne.module)

/** L'entrée enregistrée : la forme du contrat, avec la ligne orpheline. */
const entreeEnregistree = () => {
  const reponse = reponseContrat('calepinage', 'calepinage_entree_electrique', 'exemple')
  const donnees = JSON.parse(JSON.stringify(reponse.data))
  donnees.entree.affectation_manuelle = [
    { module: OBSOLETE.module, chaine: 2, mppt: 2, onduleur: 1 },
  ]
  return { data: donnees }
}

const rendre = () => render(
  <MemoryRouter><AffectationChaines calepinageId={1} /></MemoryRouter>,
)

const affecterA1 = () => {
  const caseA1 = screen.getByTestId(`cal234-module-${A1}`)
  fireEvent.pointerDown(caseA1)
  fireEvent.pointerUp(caseA1)
  fireEvent.change(screen.getByTestId('cal234-champ-chaine'), { target: { value: '1' } })
  fireEvent.change(screen.getByTestId('cal234-champ-mppt'), { target: { value: '1' } })
  fireEvent.change(screen.getByTestId('cal234-champ-onduleur'), { target: { value: '1' } })
  fireEvent.click(screen.getByTestId('cal234-affecter'))
}

beforeEach(() => {
  vi.clearAllMocks()
  calepinageApi.calepinages.resultat.mockResolvedValue(perime())
  calepinageApi.calepinages.entreeElectrique.mockResolvedValue(entreeEnregistree())
  calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data: {
    verdict: 'alerte', publiable: false, bloquants: [], alertes: [],
    manquantes: [], regle_mppt: null, regle_chaine: null, temperatures: null,
  } })
  calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue(perime())
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AffectationChaines — affectations obsolètes (ACAL266)', () => {
  it("une orpheline n'est pas élaguée au POST", async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')
    // L'écran AFFICHE l'obsolète avec son motif servi.
    expect(screen.getByTestId(`acal266-obsolete-${OBSOLETE.module}`))
      .toHaveTextContent(OBSOLETE.motif)
    await waitFor(() => expect(calepinageApi.calepinages.entreeElectrique)
      .toHaveBeenCalledWith(1))

    affecterA1()
    await waitFor(() => expect(screen.getByTestId('cal234-enregistrer')).not.toBeDisabled())
    fireEvent.click(screen.getByTestId('cal234-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique)
      .toHaveBeenCalled())
    const [, corps] = calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0]
    expect(corps.affectation_manuelle).toEqual(expect.arrayContaining([
      { module: OBSOLETE.module, chaine: 2, mppt: 2, onduleur: 1 },
      { module: A1, chaine: 1, mppt: 1, onduleur: 1 },
    ]))
  })

  it('le geste « Retirer » la retire du POST suivant', async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')
    await waitFor(() => expect(calepinageApi.calepinages.entreeElectrique).toHaveBeenCalled())

    fireEvent.click(screen.getByTestId(`acal266-retirer-${OBSOLETE.module}`))
    await waitFor(() => expect(screen.getByTestId('cal234-enregistrer')).not.toBeDisabled())
    fireEvent.click(screen.getByTestId('cal234-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique)
      .toHaveBeenCalled())
    const [, corps] = calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0]
    expect(corps.affectation_manuelle.map((l) => l.module))
      .not.toContain(OBSOLETE.module)
  })
})
