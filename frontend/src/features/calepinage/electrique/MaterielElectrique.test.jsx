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
    calepinages: { entreeElectrique: vi.fn(), enregistrerEntreeElectrique: vi.fn(), configurationsOnduleur: vi.fn() },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import MaterielElectrique from './MaterielElectrique'
import { libelleProvenance } from './MaterielElectrique.helpers'

const EXEMPLE = exempleContrat('calepinage', 'calepinage_entree_electrique')
const VIDE = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_vide')

const rendre = () => render(
  <MemoryRouter><MaterielElectrique calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('MaterielElectrique (ACAL149)', () => {
  it('T4-X7-011 — un matériel désigné prévient l’écran (la liste « Prêt à envoyer ? » se relit)', async () => {
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: EXEMPLE })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    const surEnregistre = vi.fn()
    render(<MemoryRouter><MaterielElectrique calepinageId={1} surEnregistre={surEnregistre} /></MemoryRouter>)
    await screen.findByTestId('acal149-formulaire')
    await userEvent.selectOptions(document.getElementById('acal149-champ-module_produit'), '4112')
    await waitFor(() => expect(surEnregistre).toHaveBeenCalledTimes(1))
  })

  it('ACAL1987 — choisir dans la liste DÉSIGNE (un POST, sans autre bouton) puis affiche les valeurs RELUES du GET', async () => {
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

    // Le choix dans la liste compte comme désignation : aucun clic sur « Enregistrer le matériel » n'est requis.
    await userEvent.selectOptions(document.getElementById('acal149-champ-module_produit'), '4112')

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

  it('provenance de la conception affichée et surchargeable', async () => {
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue(reponseContrat('calepinage', 'calepinage_entree_electrique'))
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })

    rendre()
    await screen.findByTestId('acal149-formulaire')
    // Relecture E5 M3 — le matériel choisi par le moteur (provenance `moteur`) n'est jamais « à désigner ».
    expect(screen.getByTestId('acal149-provenance-onduleur')).toHaveTextContent('de la conception')
    expect(libelleProvenance(EXEMPLE.materiel.onduleur)).toBe('de la conception')
    expect(libelleProvenance({ ...EXEMPLE.materiel.onduleur, provenance: 'devis' })).toBe('ligne du devis')
    // T4-B4-007 — le module posé à l'étape Panneaux sert le calcul électrique (provenance `pose`) : jamais « à désigner ».
    expect(libelleProvenance({ ...EXEMPLE.materiel.module, provenance: 'pose' })).toBe('posé à l’étape Panneaux')

    // On surcharge le module par un autre choix : le corps le porte.
    await userEvent.selectOptions(document.getElementById('acal149-champ-module_produit'), '')
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
    // ACAL1740 — le nom français de la table commune, jamais la clé brute.
    expect(option).toHaveTextContent('Tension maximale absolue (V)')
    expect(option).not.toHaveTextContent(incomplet.champs_manquants[0])
  })

  it('un refus 400 s’affiche sous le champ nommé, mot pour mot', async () => {
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: EXEMPLE })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
      response: { status: 400, data: { onduleur_produit: 'Produit hors société.' } },
    })

    rendre()
    await screen.findByTestId('acal149-formulaire')
    await userEvent.selectOptions(document.getElementById('acal149-champ-module_produit'), '4112')

    expect(await screen.findByTestId('acal149-erreur-onduleur_produit')).toHaveTextContent('Produit hors société.')
  })

  describe('ACAL617 — Comparer avec d’autres onduleurs', () => {
    const CONF = exempleContrat('calepinage', 'calepinage_configurations_onduleur')
    const ouvrir = async () => {
      calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: EXEMPLE })
      calepinageApi.calepinages.configurationsOnduleur.mockResolvedValue({ data: CONF })
      rendre()
      await screen.findByTestId('acal149-formulaire')
      expect(calepinageApi.calepinages.configurationsOnduleur).not.toHaveBeenCalled() // rien ne part avant le clic
      await userEvent.click(screen.getByTestId('acal617-lien'))
    }

    it('cartes d’après l’échantillon : nombres servis, pastilles, « Retenu » sans bouton', async () => {
      await ouvrir()
      const retenue = await screen.findByTestId('acal617-carte-42')
      expect(retenue).toHaveTextContent('Rapport DC/AC 1,16')
      expect(retenue).toHaveTextContent('Entrées utilisées 2 sur 2')
      expect(retenue).toHaveTextContent('Conforme')
      expect(retenue).toHaveTextContent('Retenu')
      expect(screen.queryByTestId('acal617-appliquer-42')).toBeNull()
      expect(screen.getByTestId('acal617-carte-43')).toHaveTextContent('À surveiller')
      expect(screen.getByTestId('acal617-carte-43')).toHaveTextContent(CONF.configurations[1].alertes[0])
      expect(screen.getByTestId('acal617-fiche-44')).toHaveTextContent('puissance AC')
    })

    it('« Appliquer » envoie l’identifiant de la carte comme onduleur, relit l’entrée et les cartes', async () => {
      await ouvrir()
      calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
      const lectures = calepinageApi.calepinages.entreeElectrique.mock.calls.length
      await userEvent.click(await screen.findByTestId('acal617-appliquer-43'))

      await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalledTimes(1))
      const [id, corps] = calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0]
      expect(id).toBe(1)
      expect(corps.onduleur_produit).toBe(43)
      expect(Object.keys(corps).sort()).toEqual(['module_produit', 'onduleur_produit', 'optimiseur_produit'])
      await waitFor(() => expect(calepinageApi.calepinages.entreeElectrique.mock.calls.length).toBeGreaterThan(lectures))
      await waitFor(() => expect(calepinageApi.calepinages.configurationsOnduleur).toHaveBeenCalledTimes(2))
    })

    it('un refus 4xx s’affiche, mot pour mot', async () => {
      await ouvrir()
      calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
        response: { status: 400, data: { onduleur_produit: 'Produit hors société.' } },
      })
      await userEvent.click(await screen.findByTestId('acal617-appliquer-43'))
      expect(await screen.findByTestId('acal617-erreur')).toHaveTextContent('Produit hors société.')
    })

    it('sans onduleur désigné : le motif servi, aucune carte', async () => {
      calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: EXEMPLE })
      calepinageApi.calepinages.configurationsOnduleur.mockResolvedValue({
        data: exempleContrat('calepinage', 'calepinage_configurations_onduleur', 'exemple_vide'),
      })
      rendre()
      await screen.findByTestId('acal149-formulaire')
      await userEvent.click(screen.getByTestId('acal617-lien'))
      expect(await screen.findByTestId('acal617-vide')).toHaveTextContent('Aucun onduleur désigné')
    })
  })

  it('ACAL1952 — le matériel retenu par le devis est dit, avec l’écart d’une saisie contraire', async () => {
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: EXEMPLE })
    rendre()
    const bloc = await screen.findByTestId('acal149-devis-retenu')
    expect(bloc).toHaveTextContent(`Repris du devis ${EXEMPLE.devis_retenu.reference} (option sans batterie)`)
    expect(bloc).toHaveTextContent(EXEMPLE.devis_retenu.onduleur.designation)
    expect(bloc).toHaveTextContent(`Écart avec le devis — ${EXEMPLE.devis_retenu.ecarts[0]}`)
  })

  it('ACAL1950 — le bloc « repris du devis » décrit le même devis que la conception retenue (référence, statut, option, onduleurs)', () => {
    // Deux échantillons, UN devis : `calepinage_conception_retenue.json` (ce que le devis a retenu, lu par le serveur) et le
    // bloc `devis_retenu` que cet écran affiche. Si l'un dérive sans l'autre, ce cas casse.
    const conception = exempleContrat('calepinage', 'calepinage_conception_retenue')
    const { reference, statut, option, nombre_onduleurs: nombre } = EXEMPLE.devis_retenu
    expect({ reference, statut, option, nombre }).toEqual({
      reference: conception.reference, statut: conception.statut, option: conception.option,
      nombre: conception.onduleurs[0].quantite,
    })
  })

  it('ACAL1952 — sans devis lié, aucun bloc « repris du devis »', async () => {
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: VIDE })
    rendre()
    await screen.findByTestId('acal149-formulaire')
    expect(screen.queryByTestId('acal149-devis-retenu')).toBeNull()
  })

  it('une lecture en panne le DIT, sans inventer de matériel', async () => {
    calepinageApi.calepinages.entreeElectrique.mockRejectedValue(new Error('boum'))

    rendre()

    expect(await screen.findByTestId('acal149-erreur')).toBeInTheDocument()
    expect(screen.queryByTestId('acal149-panneau')).toBeNull()
  })
})
