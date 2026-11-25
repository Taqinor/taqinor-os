/* CAL165 — la provenance de chaque paramètre normatif.

   Ce qui est prouvé ici :
   1. les CINQ origines (`fiche`, `pvgis`, `societe`, `saisie`, `hypothese`)
      rendent chacune leur pastille ;
   2. un chiffre SANS provenance déclarée n'est PAS rendu — le composant refuse
      et écrit « — » + « non sourcée » (c'est le Done de la tâche) ;
   3. l'infobulle CITE la référence textuelle quand le serveur en publie une ;
   4. l'écran lit EXACTEMENT le contrat committé
      `apps/calepinage/contract_samples/parametres_calepinage.json`
      (PACT10/13 — `reponseContrat`, jamais une charge utile écrite à la main). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { parametres: { get: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import SourcesNormatives, { Provenance, ValeurSourcee } from './Provenance'
import { ORIGINES } from './Provenance.helpers'

const servir = (variante) => {
  calepinageApi.parametres.get
    .mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage', variante))
}

const rendreEcran = () => render(
  <MemoryRouter><SourcesNormatives /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Provenance (CAL165) — la pastille', () => {
  it('rend les cinq origines, chacune avec son libellé', () => {
    const origines = Object.keys(ORIGINES)
    expect(origines).toEqual(['fiche', 'pvgis', 'societe', 'saisie', 'hypothese'])
    origines.forEach((origine) => {
      cleanup()
      render(<Provenance origine={origine} />)
      const pastille = screen.getByTestId('cal165-pastille')
      expect(pastille).toHaveAttribute('data-origine', origine)
      expect(pastille).toHaveTextContent(ORIGINES[origine].libelle)
    })
  })

  it('origine absente ou inventée ⇒ « non sourcée »', () => {
    render(<Provenance origine="inventee" />)
    const pastille = screen.getByTestId('cal165-pastille')
    expect(pastille).toHaveAttribute('data-origine', 'non-declaree')
    expect(pastille).toHaveTextContent('non sourcée')
  })

  it('l’infobulle cite la référence texte quand il y en a une', () => {
    render(<Provenance origine="societe" reference="UTE C 15-712-1 — chute DC" />)
    expect(screen.getByTestId('cal165-pastille'))
      .toHaveAttribute('title', expect.stringContaining('UTE C 15-712-1 — chute DC'))
  })
})

describe('ValeurSourcee (CAL165) — le refus', () => {
  it('sans provenance déclarée, le chiffre N’EST PAS rendu', () => {
    render(<ValeurSourcee valeur={26} unite="m/s" testId="essai" />)
    expect(screen.getByTestId('cal165-valeur')).toHaveTextContent('—')
    expect(screen.queryByText(/26/)).toBeNull()
    expect(screen.getByTestId('cal165-pastille')).toHaveTextContent('non sourcée')
  })

  it('avec provenance déclarée, le chiffre est rendu et la référence affichée', () => {
    render(
      <ValeurSourcee
        valeur={26}
        unite="m/s"
        origine="saisie"
        reference="relevé de site"
        decimals={1}
        testId="essai"
      />,
    )
    const bloc = screen.getByTestId('essai')
    expect(within(bloc).getByTestId('cal165-valeur')).toHaveTextContent('26,0 m/s')
    expect(within(bloc).getByTestId('cal165-reference')).toHaveTextContent('relevé de site')
  })

  it('une valeur absente reste « — » même avec une provenance déclarée', () => {
    render(<ValeurSourcee valeur={null} origine="fiche" testId="essai" />)
    expect(screen.getByTestId('cal165-valeur')).toHaveTextContent('—')
  })
})

describe('Écran « Sources des paramètres normatifs » (CAL165)', () => {
  it('affiche les paramètres du contrat AVEC leur source', async () => {
    servir('exemple')
    rendreEcran()

    await screen.findByTestId('cal165-ecran')

    const lestage = screen.getByTestId('cal165-lestage')
    expect(within(lestage).getByText('vitesse vent reference m s')).toBeInTheDocument()
    // La valeur ET sa source viennent du contrat, mot pour mot.
    const echantillon = reponseContrat('calepinage', 'parametres_calepinage', 'exemple').data
    const attendue = echantillon.lestage.vitesse_vent_reference_m_s
    expect(within(lestage).getByText(attendue.source)).toBeInTheDocument()

    const norme = screen.getByTestId('cal165-norme')
    expect(within(norme).getByText(echantillon.norme_electrique.reference)).toBeInTheDocument()
    const coefficient = echantillon.norme_electrique.coefficients.chute_dc_max_pct
    expect(within(norme).getByText(coefficient.reference)).toBeInTheDocument()

    // Aucune pastille « non sourcée » : chaque valeur servie porte sa source.
    expect(screen.queryAllByText('non sourcée')).toHaveLength(0)
  })

  it('ACAL937 — sans norme : « Choisir la norme » ouvre le champ de norme ; avec : « Changer la norme »', async () => {
    servir('exemple_vide')
    rendreEcran()
    await screen.findByTestId('cal165-ecran')
    const lien = within(screen.getByTestId('cal165-norme')).getByRole('link', { name: 'Choisir la norme' })
    expect(lien).toHaveAttribute('href', '/calepinage/reglages#norme')
    expect(screen.getByTestId('cal165-norme')).toHaveTextContent('Aucune norme électrique choisie')

    cleanup()
    servir('exemple')
    rendreEcran()
    await screen.findByTestId('cal165-ecran')
    const change = within(screen.getByTestId('cal165-norme')).getByRole('link', { name: 'Changer la norme' })
    expect(change).toHaveAttribute('href', '/calepinage/reglages#norme')
  })

  it('ACAL938 — « Saisir le lestage » mène à la carte Lestage des Réglages', async () => {
    servir('exemple_vide')
    rendreEcran()
    await screen.findByTestId('cal165-ecran')
    const lien = within(screen.getByTestId('cal165-lestage')).getByRole('link', { name: 'Saisir le lestage' })
    expect(lien).toHaveAttribute('href', '/calepinage/reglages#lestage')
  })

  it('sections vides : rien n’est inventé, chaque omission est dite', async () => {
    servir('exemple_vide')
    rendreEcran()

    await screen.findByTestId('cal165-ecran')
    expect(screen.getByTestId('cal165-norme')).toHaveTextContent(
      'Aucune norme électrique choisie',
    )
    expect(screen.getByTestId('cal165-lestage')).toHaveTextContent(
      'Aucun paramètre de lestage enregistré',
    )
    expect(screen.getByTestId('cal165-degagements')).toHaveTextContent(
      'Aucun dégagement enregistré',
    )
  })

  it('erreur réseau : message français, aucune valeur inventée', async () => {
    calepinageApi.parametres.get.mockRejectedValue(new Error('boum'))
    rendreEcran()

    expect(await screen.findByTestId('cal165-erreur')).toHaveTextContent(
      'Paramètres normatifs indisponibles.',
    )
  })
})

describe('T4-X3-002 / 013 — les retraits par arête et les allées par pays portent LEUR source', () => {
  it('chaque entrée de liste montre sa valeur et sa source, jamais « non sourcée » à tort', async () => {
    const servi = reponseContrat('calepinage', 'parametres_calepinage', 'exemple')
    servi.data = {
      ...servi.data,
      degagements: {
        retraits_par_arete: [
          { type: 'faitage', retrait_m: 0.3, source: 'X3 test retrait', reference: '' },
        ],
        allees_circulation: [
          { pays: 'ma', largeur_m: 1, source: 'X3 test allée', reference: 'Réf. allée' },
        ],
      },
    }
    calepinageApi.parametres.get.mockResolvedValue(servi)
    rendreEcran()
    await screen.findByTestId('cal165-ecran')
    const degagements = screen.getByTestId('cal165-degagements')
    expect(degagements).toHaveTextContent('Faîtage')
    expect(degagements).toHaveTextContent('0,3')
    expect(degagements).toHaveTextContent('X3 test retrait')
    expect(degagements).toHaveTextContent('MA')
    expect(degagements).toHaveTextContent('X3 test allée')
    expect(within(degagements).queryAllByText('non sourcée')).toHaveLength(0)
  })
})

describe('T4-X3-001 — la norme choisie est dite même sans coefficient saisi', () => {
  it('norme enregistrée, aucun coefficient propre à la société : la page nomme la norme', async () => {
    const servi = reponseContrat('calepinage', 'parametres_calepinage', 'exemple')
    servi.data = {
      ...servi.data,
      norme_electrique: { norme: 'nf_c_15_100', reference: 'X3-ref test', coefficients: {} },
    }
    calepinageApi.parametres.get.mockResolvedValue(servi)
    rendreEcran()
    await screen.findByTestId('cal165-ecran')
    const norme = screen.getByTestId('cal165-norme')
    expect(norme).not.toHaveTextContent('Aucune norme électrique choisie')
    expect(norme).toHaveTextContent('NF C 15-100')
    expect(norme).toHaveTextContent('X3-ref test')
    expect(norme).toHaveTextContent('ceux de la norme s’appliquent')
    expect(within(norme).getByRole('link', { name: 'Changer la norme' })).toBeInTheDocument()
  })
})
