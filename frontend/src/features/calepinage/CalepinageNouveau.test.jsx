import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

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
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/calepinageApi', () => ({
  default: { calepinages: { create: mocks.create } },
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

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getLeads.mockResolvedValue({
    data: [LEAD_AVEC_EPINGLE, LEAD_SANS_REPERE, LEAD_GPS_SAISI, LEAD_LAT_SEULE],
  })
  mocks.searchClients.mockResolvedValue({ data: [CLIENT_AVEC_ADRESSE, CLIENT_SANS_ADRESSE] })
  mocks.create.mockResolvedValue({ data: { id: 77 } })
})

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
