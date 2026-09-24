import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CAL36 — créer un calepinage depuis un LEAD **ou** un CLIENT.
   ----------------------------------------------------------------------------
   Ce que ce fichier prouve, point par point du « Done » de la tâche :
     * créer sans lead NI client est impossible côté écran — et le refus SERVEUR
       (qui nomme le champ) s'affiche tel quel quand il arrive ;
     * un lead d'une autre société n'apparaît jamais : la recherche part au
       serveur, jamais dans une liste pré-chargée que l'écran filtrerait ;
     * le contexte géographique est LU, jamais deviné — pas d'épingle, pas de
       GPS ⇒ « non renseigné », et surtout aucun centre du Maroc inventé ;
     * un CLIENT n'a pas d'épingle de toiture : son point de départ est le
       géocodage de son adresse, et sans adresse rien n'est deviné ;
     * après création, l'écran redirige vers `/calepinage/:id`.
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  getLeads: vi.fn(),
  searchClients: vi.fn(),
  navigate: vi.fn(),
  // CALX352 — les deux listes de départ et la porte CALX351.
  modeles: vi.fn(),
  getParametres: vi.fn(),
  depuisModele: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      create: mocks.create,
      modeles: (...a) => mocks.modeles(...a),
      depuisModele: (...a) => mocks.depuisModele(...a),
    },
    parametres: { get: (...a) => mocks.getParametres(...a) },
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: { getLeads: mocks.getLeads, searchClients: mocks.searchClients },
}))

import CalepinageNouveau from './CalepinageNouveau'

const rendre = () => render(<MemoryRouter><CalepinageNouveau /></MemoryRouter>)

const LEAD_AVEC_EPINGLE = {
  id: 1, nom: 'Lead', prenom: 'd’essai', ville: 'Casablanca',
  roof_point: { lat: 33.5, lng: -7.6 },
}
const LEAD_SANS_REPERE = { id: 2, nom: 'Lead', prenom: 'sans repère', ville: 'Berrechid' }
const LEAD_GPS_SAISI = { id: 5, nom: 'Lead', prenom: 'GPS saisi', ville: 'Settat', gps_lat: '33.0', gps_lng: '-7.6' }
const LEAD_LAT_SEULE = { id: 6, nom: 'Lead', prenom: 'latitude seule', ville: 'Settat', gps_lat: '33.0' }
const CLIENT_AVEC_ADRESSE = { id: 3, nom: 'Client', prenom: 'd’essai', adresse: '12 rue d’essai' }
const CLIENT_SANS_ADRESSE = { id: 4, nom: 'Client', prenom: 'sans adresse' }

/* Radix Tabs sélectionne sur `mousedown` (pas sur `click`) : un
   `fireEvent.click` seul laisserait l'onglet Lead actif et le test échouerait
   sur un symptôme qui n'existe pas dans le navigateur. */
const allerSurOnglet = (nom) => {
  const onglet = screen.getByRole('tab', { name: nom })
  fireEvent.mouseDown(onglet)
  fireEvent.click(onglet)
}

const choisirDansCombobox = async (nomChamp, libelleOption) => {
  fireEvent.click(screen.getByRole('combobox', { name: nomChamp }))
  fireEvent.click(await screen.findByText(libelleOption))
}

/* CALX352 — un MODÈLE tel que `modeles()` le sert (CalepinageSerializer :
   `layout_nb_panneaux`, `layout_hash`). */
const MODELE = {
  id: 5, titre: 'Villa type R+1', layout_nb_panneaux: 12,
  layout_hash: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9',
}
/* Les réglages société : l'échantillon COMMITTÉ (préréglage nommé
   `villa_standard`), jamais une forme tapée à la main. */
const REGLAGES = exempleContrat('calepinage', 'parametres_calepinage')
/* La réponse de `depuis-modele` : le DÉTAIL agrégé du contrat committé. */
const DETAIL = exempleContrat('calepinage', 'calepinage_detail')

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getLeads.mockResolvedValue({
    data: [LEAD_AVEC_EPINGLE, LEAD_SANS_REPERE, LEAD_GPS_SAISI, LEAD_LAT_SEULE],
  })
  mocks.searchClients.mockResolvedValue({ data: [CLIENT_AVEC_ADRESSE, CLIENT_SANS_ADRESSE] })
  mocks.create.mockResolvedValue({ data: { id: 77 } })
  mocks.modeles.mockResolvedValue({ data: [MODELE] })
  mocks.getParametres.mockResolvedValue({ data: REGLAGES })
  mocks.depuisModele.mockResolvedValue(reponseContrat('calepinage', 'calepinage_detail'))
})

/* Les deux listes arrivent APRÈS le premier rendu : on attend qu'elles
   soient servies avant d'y choisir quoi que ce soit. */
const attendreChoix = async () => {
  await waitFor(() => expect(screen.getByLabelText(/Partir d’un modèle/)).not.toBeDisabled())
  await waitFor(() => expect(screen.getByLabelText(/Jeu de réglages société/)).not.toBeDisabled())
}

describe('CalepinageNouveau (CAL36)', () => {
  it('ouvre sur l’onglet Lead, avec les deux onglets disponibles', () => {
    rendre()
    expect(screen.getByRole('tab', { name: 'Lead' })).toHaveAttribute('data-state', 'active')
    expect(screen.getByRole('tab', { name: 'Client' })).toBeInTheDocument()
  })

  it('la recherche de LEADS part au SERVEUR (seul bornage société possible)', async () => {
    rendre()
    fireEvent.click(screen.getByRole('combobox', { name: 'Lead' }))
    await waitFor(() => expect(mocks.getLeads).toHaveBeenCalled())
    // Aucun filtrage local : l'écran n'a jamais de liste complète en main.
    expect(mocks.getLeads.mock.calls[0][0]).toHaveProperty('q')
  })

  it('la recherche de CLIENTS part au SERVEUR', async () => {
    rendre()
    allerSurOnglet('Client')
    fireEvent.click(screen.getByRole('combobox', { name: 'Client' }))
    await waitFor(() => expect(mocks.searchClients).toHaveBeenCalled())
  })

  it('CRÉER SANS RIEN est impossible : l’erreur se pose SOUS le champ et le bandeau le NOMME', async () => {
    rendre()
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    expect(await screen.findByTestId('erreur-lead')).toHaveTextContent(/Choisissez le lead/)
    expect(screen.getByRole('alert')).toHaveTextContent('Lead')
    expect(screen.getByRole('button', { name: /Corriger le champ « Lead »/ })).toBeInTheDocument()
    // Rien n'est envoyé au serveur.
    expect(mocks.create).not.toHaveBeenCalled()
  })

  it('sur l’onglet CLIENT, le champ nommé est « Client », pas « Lead »', async () => {
    rendre()
    allerSurOnglet('Client')
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    expect(await screen.findByTestId('erreur-client')).toHaveTextContent(/Choisissez le client/)
    expect(screen.queryByTestId('erreur-lead')).not.toBeInTheDocument()
  })

  it('un LEAD choisi affiche sa ville et la SOURCE de son repère', async () => {
    rendre()
    await choisirDansCombobox('Lead', 'Lead d’essai')
    expect(await screen.findByText('Casablanca')).toBeInTheDocument()
    expect(screen.getByText(/Épingle posée par le client/)).toBeInTheDocument()
  })

  it('un LEAD sans repère affiche « non renseigné » — aucune coordonnée inventée', async () => {
    rendre()
    await choisirDansCombobox('Lead', 'Lead sans repère')
    expect(await screen.findByText('non renseigné')).toBeInTheDocument()
  })

  it('à défaut d’épingle, les coordonnées SAISIES dans la fiche font la source', async () => {
    rendre()
    await choisirDansCombobox('Lead', 'Lead GPS saisi')
    expect(await screen.findByText(/Coordonnées GPS saisies/)).toBeInTheDocument()
  })

  it('une LATITUDE SEULE n’est pas une position : rien n’est complété', async () => {
    rendre()
    await choisirDansCombobox('Lead', 'Lead latitude seule')
    expect(await screen.findByText('non renseigné')).toBeInTheDocument()
    expect(screen.queryByText(/Coordonnées GPS saisies/)).not.toBeInTheDocument()
  })

  it('un CLIENT part de son ADRESSE (géocodage serveur), jamais d’une épingle', async () => {
    rendre()
    allerSurOnglet('Client')
    await choisirDansCombobox('Client', 'Client d’essai')
    expect(await screen.findByText('12 rue d’essai')).toBeInTheDocument()
    expect(screen.getByText(/Géocodage de l’adresse du client/)).toBeInTheDocument()
  })

  it('un CLIENT sans adresse : « non renseigné », rien n’est deviné', async () => {
    rendre()
    allerSurOnglet('Client')
    await choisirDansCombobox('Client', 'Client sans adresse')
    await waitFor(() => expect(screen.getAllByText('non renseigné').length).toBeGreaterThan(0))
    expect(screen.queryByText(/Géocodage de l’adresse du client/)).not.toBeInTheDocument()
  })

  it('créer depuis un LEAD envoie `{lead}` et redirige vers `/calepinage/:id`', async () => {
    rendre()
    await choisirDansCombobox('Lead', 'Lead d’essai')
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({ lead: '1' }))
    expect(mocks.navigate).toHaveBeenCalledWith('/calepinage/77')
  })

  it('créer depuis un CLIENT envoie `{client}` — jamais les deux à la fois', async () => {
    rendre()
    allerSurOnglet('Client')
    await choisirDansCombobox('Client', 'Client d’essai')
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({ client: '3' }))
    expect(mocks.create.mock.calls[0][0]).not.toHaveProperty('lead')
  })

  it('le nom facultatif ne part QUE s’il est saisi', async () => {
    rendre()
    await choisirDansCombobox('Lead', 'Lead d’essai')
    fireEvent.change(screen.getByLabelText(/Nom du calepinage/), { target: { value: '  Hangar 2  ' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({ lead: '1', nom: 'Hangar 2' }))
  })

  it('le REFUS SERVEUR nommant le champ s’affiche SOUS ce champ, tel quel', async () => {
    mocks.create.mockRejectedValue({
      response: { data: { lead: ['Indiquez un lead ou un client, jamais les deux.'] } },
    })
    rendre()
    await choisirDansCombobox('Lead', 'Lead d’essai')
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    expect(await screen.findByTestId('erreur-lead'))
      .toHaveTextContent('Indiquez un lead ou un client, jamais les deux.')
    expect(screen.getByRole('button', { name: /Corriger le champ « Lead »/ })).toBeInTheDocument()
  })

  it('un refus GLOBAL (`detail`) s’affiche dans le bandeau, sans texte fabriqué', async () => {
    mocks.create.mockRejectedValue({ response: { data: { detail: 'Module désactivé pour votre société.' } } })
    rendre()
    await choisirDansCombobox('Lead', 'Lead d’essai')
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    expect(await screen.findByRole('alert'))
      .toHaveTextContent('Module désactivé pour votre société.')
    expect(mocks.navigate).not.toHaveBeenCalled()
  })

  it('choisir une cible EFFACE l’erreur posée sur ce champ', async () => {
    rendre()
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    expect(await screen.findByTestId('erreur-lead')).toBeInTheDocument()
    await choisirDansCombobox('Lead', 'Lead d’essai')
    await waitFor(() => expect(screen.queryByTestId('erreur-lead')).not.toBeInTheDocument())
  })
})

/* ============================================================================
   CALX352 — PARTIR D'UN MODÈLE et/ou d'un JEU DE RÉGLAGES société.
   ----------------------------------------------------------------------------
     * aucun choix fait ⇒ la création d'aujourd'hui (`create`), inchangée ;
     * un modèle choisi affiche son nombre de modules et son empreinte AVANT
       validation, puis part par la porte CALX351 (`depuis-modele`), dont la
       réponse est le DÉTAIL du contrat committé ;
     * les deux formes de jeux de réglages sont offertes (liste `jeux` et
       préréglages nommés), jamais `kits` ni un interrupteur ;
     * un refus serveur nommant `preset_id` s'affiche SOUS le champ du jeu.
   ========================================================================== */
describe('CalepinageNouveau — modèle et jeu de réglages (CALX352)', () => {
  it('aucun choix fait : la création d’aujourd’hui, jamais la porte des modèles', async () => {
    rendre()
    await attendreChoix()
    await choisirDansCombobox('Lead', 'Lead d’essai')
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({ lead: '1' }))
    expect(mocks.depuisModele).not.toHaveBeenCalled()
  })

  it('un modèle choisi affiche son nombre de modules et son empreinte avant validation', async () => {
    rendre()
    await attendreChoix()
    expect(screen.queryByTestId('cal-nouveau-modele-apercu')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/Partir d’un modèle/), { target: { value: '5' } })
    const apercu = await screen.findByTestId('cal-nouveau-modele-apercu')
    expect(apercu).toHaveTextContent('12')
    expect(apercu).toHaveTextContent(MODELE.layout_hash.slice(0, 12))
    expect(mocks.depuisModele).not.toHaveBeenCalled()
  })

  it('un modèle sans nombre de modules connu : « non renseigné », rien n’est deviné', async () => {
    mocks.modeles.mockResolvedValue({ data: [{ id: 9, titre: 'Hangar', layout_nb_panneaux: null, layout_hash: '' }] })
    rendre()
    await attendreChoix()
    fireEvent.change(screen.getByLabelText(/Partir d’un modèle/), { target: { value: '9' } })
    const apercu = await screen.findByTestId('cal-nouveau-modele-apercu')
    expect(apercu).toHaveTextContent('non renseigné')
  })

  it('créer depuis un modèle part par `depuis-modele` et ouvre le calepinage servi', async () => {
    rendre()
    await attendreChoix()
    await choisirDansCombobox('Lead', 'Lead d’essai')
    fireEvent.change(screen.getByLabelText(/Partir d’un modèle/), { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    await waitFor(() => expect(mocks.depuisModele)
      .toHaveBeenCalledWith({ lead_id: '1', modele_id: '5' }))
    expect(mocks.create).not.toHaveBeenCalled()
    expect(mocks.navigate).toHaveBeenCalledWith(`/calepinage/${DETAIL.id}`)
  })

  it('un jeu de réglages SEUL part aussi par la porte CALX351, sur le client choisi', async () => {
    rendre()
    await attendreChoix()
    allerSurOnglet('Client')
    await choisirDansCombobox('Client', 'Client d’essai')
    fireEvent.change(screen.getByLabelText(/Jeu de réglages société/), {
      target: { value: 'villa_standard' },
    })
    fireEvent.change(screen.getByLabelText(/Nom du calepinage/), { target: { value: 'Hangar 2' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    await waitFor(() => expect(mocks.depuisModele).toHaveBeenCalledWith({
      client_id: '3', preset_id: 'villa_standard', titre: 'Hangar 2',
    }))
  })

  it('les deux formes de jeux sont offertes — jamais `kits` ni un interrupteur', async () => {
    mocks.getParametres.mockResolvedValue({
      data: {
        ...REGLAGES,
        presets: {
          jeux: [{ id: 'villa', nom: 'Villa tuiles' }],
          hangar: { orientation: 'paysage', source: 'Fiche pose' },
          kits: [{ id: 3 }],
          feu_vert_bureau_etudes: true,
          approbation_exigee: false,
        },
      },
    })
    rendre()
    await attendreChoix()
    const select = screen.getByLabelText(/Jeu de réglages société/)
    const options = Array.from(select.querySelectorAll('option')).map((o) => o.value)
    expect(options).toEqual(['', 'villa', 'hangar'])
  })

  it('aucun modèle ni jeu enregistré : l’écran le DIT, la création reste possible', async () => {
    mocks.modeles.mockResolvedValue({ data: [] })
    mocks.getParametres.mockResolvedValue({ data: { ...REGLAGES, presets: {} } })
    rendre()
    await attendreChoix()
    expect(screen.getByTestId('cal-nouveau-modeles-vide')).toBeInTheDocument()
    expect(screen.getByTestId('cal-nouveau-jeux-vide')).toBeInTheDocument()
  })

  it('un refus serveur nommant `preset_id` s’affiche SOUS le champ du jeu, et le bandeau le NOMME', async () => {
    mocks.depuisModele.mockRejectedValue({
      response: { data: { preset_id: 'Jeu de réglages inconnu : « villa_standard ».' } },
    })
    rendre()
    await attendreChoix()
    await choisirDansCombobox('Lead', 'Lead d’essai')
    fireEvent.change(screen.getByLabelText(/Jeu de réglages société/), {
      target: { value: 'villa_standard' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    expect(await screen.findByTestId('erreur-preset'))
      .toHaveTextContent('Jeu de réglages inconnu : « villa_standard ».')
    expect(screen.getByRole('button', { name: /Corriger le champ « Jeu de réglages société »/ }))
      .toBeInTheDocument()
    expect(mocks.navigate).not.toHaveBeenCalled()
  })

  it('une liste de départ indisponible ne bloque pas la création ordinaire', async () => {
    mocks.modeles.mockRejectedValue(new Error('réseau'))
    mocks.getParametres.mockRejectedValue(new Error('réseau'))
    rendre()
    await attendreChoix()
    await choisirDansCombobox('Lead', 'Lead d’essai')
    fireEvent.click(screen.getByRole('button', { name: /Créer le calepinage/ }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({ lead: '1' }))
  })
})
