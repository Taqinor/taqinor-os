import { reponseContrat } from '../../test/fixtures/contractSamples'
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { mockMatchMedia } from '../../test/matchMedia'

/* WIR112 — Équipes terrain canoniques (DC40) : CRUD depuis Paramètres. */

const EQUIPES = [
  { id: 1, nom: 'Équipe Nord', membres: [10], chef: 10, nb_membres: 1, actif: true },
  { id: 2, nom: 'Équipe Sud', membres: [], chef: null, nb_membres: 0, actif: false },
]
const USERS = [
  { id: 10, username: 'ahmed' },
  { id: 11, username: 'sara' },
]

const {
  getEquipes, saveEquipe, deleteEquipe, apiGet, apiPatch, saveEquipeCom, rolesMock, getDispatch, attribuerLead,
  getEquipesCom, getAssignableUsers, getReglesAttribution, saveRegleAttribution, saveReglagesDispatch, getCanaux,
  getCockpitEquipe, saveObjectif, deleteObjectif,
} = vi.hoisted(() => ({
  getEquipes: vi.fn(),
  saveEquipe: vi.fn(() => Promise.resolve({ data: {} })),
  deleteEquipe: vi.fn(() => Promise.resolve({ data: {} })),
  apiGet: vi.fn(),
  apiPatch: vi.fn(() => Promise.resolve({ data: {} })),
  saveEquipeCom: vi.fn(() => Promise.resolve({ data: {} })),
  getDispatch: vi.fn(),
  attribuerLead: vi.fn(() => Promise.resolve({ data: {} })),
  getEquipesCom: vi.fn(() => Promise.resolve({ data: [{ id: 7, membres: [4, 5] }] })),
  getAssignableUsers: vi.fn(() => Promise.resolve({ data: [{ id: 4, username: 'sara' }, { id: 5, username: 'amine' }] })),
  getReglesAttribution: vi.fn(() => Promise.resolve({ data: [] })),
  saveRegleAttribution: vi.fn(() => Promise.resolve({ data: {} })),
  saveReglagesDispatch: vi.fn(() => Promise.resolve({ data: {} })),
  getCanaux: vi.fn(() => Promise.resolve({ data: [] })),
  getCockpitEquipe: vi.fn(),
  saveObjectif: vi.fn(() => Promise.resolve({ data: {} })),
  deleteObjectif: vi.fn(() => Promise.resolve({ data: {} })),
  rolesMock: {
    getOrganisation: vi.fn(),
    getPostes: vi.fn(),
    getDepartements: vi.fn(),
    getRoles: vi.fn(),
    savePoste: vi.fn(() => Promise.resolve({ data: {} })),
    saveDepartement: vi.fn(() => Promise.resolve({ data: {} })),
    saveEquipeOrg: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../api/axios', () => ({ default: { get: apiGet, patch: apiPatch } }))
vi.mock('../../api/crmApi', () => ({
  default: {
    saveEquipe: saveEquipeCom, getDispatch, attribuerLead, getEquipes: getEquipesCom,
    getAssignableUsers, getReglesAttribution, saveRegleAttribution, saveReglagesDispatch, getCanaux,
    getCockpitEquipe, saveObjectif, deleteObjectif,
  },
}))
vi.mock('../../api/rolesApi', () => ({ default: rolesMock }))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getEquipesTerrain: getEquipes,
    saveEquipeTerrain: saveEquipe,
    deleteEquipeTerrain: deleteEquipe,
  },
}))

import EquipeTerrainSection from './EquipeTerrainSection'
import EquipeSection from './EquipeSection'
import AttributionLeadsPage from '../crm/AttributionLeadsPage'
import CockpitEquipePage from '../crm/CockpitEquipePage'
import { MemoryRouter } from 'react-router-dom'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('EquipeTerrainSection (WIR112)', () => {
  it('liste les équipes terrain avec membres et état', async () => {
    getEquipes.mockResolvedValue({ data: EQUIPES })
    render(<EquipeTerrainSection assignables={USERS} />)
    expect(await screen.findByDisplayValue('Équipe Nord')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Équipe Sud')).toBeInTheDocument()
    // Distinct des équipes commerciales/projet — titre propre.
    expect(screen.getByText('Équipes terrain')).toBeInTheDocument()
    expect(screen.getByText('1 membre(s)')).toBeInTheDocument()
  })

  it('crée une équipe terrain', async () => {
    getEquipes.mockResolvedValue({ data: [] })
    const user = userEvent.setup()
    render(<EquipeTerrainSection assignables={USERS} />)
    await screen.findByPlaceholderText('Nouvelle équipe terrain')
    await user.type(screen.getByPlaceholderText('Nouvelle équipe terrain'), 'Équipe Test')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(saveEquipe).toHaveBeenCalledWith(null, { nom: 'Équipe Test' }))
  })

  it('bascule un membre dans une équipe', async () => {
    getEquipes.mockResolvedValue({ data: EQUIPES })
    const user = userEvent.setup()
    render(<EquipeTerrainSection assignables={USERS} />)
    const row = await screen.findByTestId('equipe-terrain-1')
    // sara (id 11) n'est pas membre → clic ajoute.
    await user.click(within(row).getByRole('button', { name: 'sara' }))
    await waitFor(() => expect(saveEquipe).toHaveBeenCalledWith(1, { membres: [10, 11] }))
  })
})

/* Vue « Organisation » (EquipeSection) : organigramme Direction → départements →
   équipes → personnes. Le payload est l'`exemple` du contrat committé côté
   serveur (apps/roles/contract_samples/organisation.json), jamais une forme
   recopiée à la main (PACT10). */

const CONTRAT = JSON.parse(readFileSync(join(
  // eslint-disable-next-line no-undef -- vitest tourne sous Node : cwd = frontend/
  process.cwd(), '..', 'backend', 'django_core', 'apps', 'roles',
  'contract_samples', 'organisation.json'), 'utf8'))
const ORG = CONTRAT.exemple

const ROLES = [
  { id: 1, nom: 'Directeur' },
  { id: 2, nom: 'Commercial responsable' },
  { id: 3, nom: 'Commercial' },
  { id: 4, nom: 'Technicien' },
]
const POSTES = [
  { id: 20, intitule: 'Chargée de clientèle', departement: 2, role: 3, actif: true },
  { id: 21, intitule: 'Technicien terrain', departement: null, role: 4, actif: true },
]
const DEPARTEMENTS = [
  { id: 1, nom: 'Direction', responsable: 1, est_direction: true, ordre: 0, actif: true },
  { id: 2, nom: 'Commercial', responsable: 2, est_direction: false, ordre: 1, actif: true },
]
const USERS_ORG = [
  { id: 1, username: 'reda', is_active: true },
  { id: 2, username: 'meryem', is_active: true },
  { id: 9, username: 'yassine', is_active: true },
]

function monterOrg(props = { canManageSensitive: true }) {
  rolesMock.getOrganisation.mockResolvedValue({ data: ORG })
  rolesMock.getPostes.mockResolvedValue({ data: POSTES })
  rolesMock.getDepartements.mockResolvedValue({ data: DEPARTEMENTS })
  rolesMock.getRoles.mockResolvedValue({ data: ROLES })
  apiGet.mockResolvedValue({ data: USERS_ORG })
  return render(<EquipeSection {...props} />)
}

describe('EquipeSection — Organisation', () => {
  beforeEach(() => mockMatchMedia(false))

  it('affiche Direction, départements, équipes et à compléter (arbre)', async () => {
    monterOrg()
    const direction = await screen.findByTestId('org-direction')
    expect(within(direction).getByText('Reda Kasri')).toBeInTheDocument()
    expect(screen.getByTestId('org-arbre')).toBeInTheDocument()

    const dept = screen.getByTestId('org-dept-2')
    expect(within(dept).getByText('Responsable commerciale')).toBeInTheDocument()
    const com = screen.getByTestId('org-equipe-commerciale-7')
    expect(within(com).getByText('Commerciale')).toBeInTheDocument()
    expect(within(com).getByText('Reçoit les nouveaux leads')).toBeInTheDocument()
    expect(within(com).getByText('Sara')).toBeInTheDocument()

    const orph = screen.getByRole('region', { name: 'Équipes sans département' })
    expect(within(orph).getByTestId('org-equipe-terrain-8')).toBeInTheDocument()

    const manque = screen.getByTestId('org-a-completer')
    expect(within(manque).getByText('Yassine')).toBeInTheDocument()
    expect(within(manque).getByText('fonction manquante')).toBeInTheDocument()
  })

  it('complète une personne : PATCH /users/<id>/ avec fonction et rôle de la fonction', async () => {
    const user = userEvent.setup()
    monterOrg()
    const manque = await screen.findByTestId('org-a-completer')
    await user.click(within(manque).getByRole('button', { name: 'Compléter' }))
    await user.selectOptions(await screen.findByLabelText('Fonction'), '21')
    expect(screen.getByText('rôle de la fonction : Technicien')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(apiPatch).toHaveBeenCalledWith('/users/9/', { fonction: 21, role: 4 }))
  })

  it('édite une équipe commerciale via crmApi.saveEquipe (département, chef, membres)', async () => {
    const user = userEvent.setup()
    monterOrg()
    await user.click(await screen.findByRole('button', { name: "Modifier l'équipe Casa" }))
    expect(screen.getByLabelText("Type d'équipe")).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(saveEquipeCom).toHaveBeenCalledWith(7, {
      // Membres non touchés : non renvoyés (jamais retirer un membre caché).
      nom: 'Casa', departement: 2, responsable: 3, recoit_leads: true,
    }))
  })

  it("crée une équipe terrain via installationsApi et affiche l'erreur serveur", async () => {
    const user = userEvent.setup()
    saveEquipe.mockRejectedValueOnce({ response: { status: 400, data: { membres: ['Membre invalide.'] } } })
    monterOrg()
    await user.click(await screen.findByRole('button', { name: '+ Équipe' }))
    await user.selectOptions(screen.getByLabelText("Type d'équipe"), 'terrain')
    await user.type(screen.getByLabelText('Nom'), 'Sud')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(saveEquipe).toHaveBeenCalledWith(null, {
      nom: 'Sud', departement: null, membres: [], chef: null,
    }))
    expect(await screen.findByText('Membre invalide.')).toBeInTheDocument()
  })

  it('crée un département et archive une fonction (onglets)', async () => {
    const user = userEvent.setup()
    monterOrg()
    await user.click(await screen.findByRole('button', { name: '+ Département' }))
    await user.type(screen.getByLabelText('Nom'), 'Marketing')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(rolesMock.saveDepartement).toHaveBeenCalledWith(
      null, expect.objectContaining({ nom: 'Marketing' })))

    await user.click(screen.getByRole('tab', { name: 'Fonctions' }))
    expect(await screen.findByTestId('poste-20')).toBeInTheDocument()
    await user.click(within(screen.getByTestId('poste-20')).getByRole('button', { name: 'Archiver' }))
    await waitFor(() => expect(rolesMock.savePoste).toHaveBeenCalledWith(20, { actif: false }))
  })

  it("lecture seule pour un non-admin : aucune action d'édition", async () => {
    monterOrg({ canManageSensitive: false })
    await screen.findByTestId('org-direction')
    expect(screen.queryByRole('button', { name: /Modifier/ })).toBeNull()
    expect(screen.queryByRole('button', { name: '+ Équipe' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Compléter' })).toBeNull()
    expect(rolesMock.getRoles).not.toHaveBeenCalled()
  })

  it("sous 768 px : liste imbriquée repliable au lieu de l'arbre", async () => {
    mockMatchMedia(true)
    monterOrg()
    expect(await screen.findByTestId('org-liste')).toBeInTheDocument()
    expect(screen.queryByTestId('org-arbre')).toBeNull()
  })
})

/* Attribution des leads (fondateur 27/10/2026) : écran du responsable. Les
   payloads sont l'`exemple` / `exemple_vide` du contrat committé côté serveur
   (apps/crm/contract_samples/dispatch_leads.json), jamais une forme retapée. */

const DISPATCH = JSON.parse(readFileSync(join(
  // eslint-disable-next-line no-undef -- vitest tourne sous Node : cwd = frontend/
  process.cwd(), '..', 'backend', 'django_core', 'apps', 'crm',
  'contract_samples', 'dispatch_leads.json'), 'utf8'))

describe('AttributionLeadsPage (attribution des leads)', () => {
  it('affiche le lead du contrat et ses membres, le proposé sélectionné', async () => {
    getDispatch.mockResolvedValue({ data: DISPATCH.exemple })
    render(<AttributionLeadsPage />)
    expect(await screen.findByText('Karim Tazi')).toBeInTheDocument()
    expect(screen.getByText('1 en attente')).toBeInTheDocument()
    expect(screen.getByText(/Règle : ville Casablanca/)).toBeInTheDocument()
    expect(screen.getByText('au plafond')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Sara/ })).toHaveAttribute('aria-selected', 'true')
  })

  it('Entrée attribue au proposé ; → puis Entrée attribue au suivant', async () => {
    getDispatch.mockResolvedValue({ data: DISPATCH.exemple })
    const user = userEvent.setup()
    render(<AttributionLeadsPage />)
    await screen.findByText('Karim Tazi')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(attribuerLead).toHaveBeenCalledWith(1712, 4))
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('option', { name: /Amine/ })).toHaveAttribute('aria-selected', 'true')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(attribuerLead).toHaveBeenLastCalledWith(1712, 5))
  })

  it('un clic sur un membre attribue à ce membre', async () => {
    getDispatch.mockResolvedValue({ data: DISPATCH.exemple })
    const user = userEvent.setup()
    render(<AttributionLeadsPage />)
    await user.click(await screen.findByRole('option', { name: /Amine/ }))
    await waitFor(() => expect(attribuerLead).toHaveBeenCalledWith(1712, 5))
  })

  it('état vide quand aucun lead n’attend', async () => {
    getDispatch.mockResolvedValue(reponseContrat('crm', 'dispatch_leads', 'exemple_file_vide'))
    render(<AttributionLeadsPage />)
    expect(await screen.findByText('Aucun lead en attente')).toBeInTheDocument()
    expect(attribuerLead).not.toHaveBeenCalled()
  })

  it('sans équipe dirigée : le dit au lieu d’une file vide', async () => {
    getDispatch.mockResolvedValue(reponseContrat('crm', 'dispatch_leads', 'exemple_vide'))
    render(<AttributionLeadsPage />)
    expect(await screen.findByText(/ne dirigez aucune équipe commerciale/)).toBeInTheDocument()
  })

  it('panneau de réglages visible avec equipes_reglables, absent sinon', async () => {
    getDispatch.mockResolvedValue({ data: DISPATCH.exemple })
    render(<AttributionLeadsPage />)
    expect(await screen.findByRole('button', { name: /Réglages de l’attribution/ })).toBeInTheDocument()
    cleanup()
    getDispatch.mockResolvedValue(reponseContrat('crm', 'dispatch_leads', 'exemple_vide'))
    render(<AttributionLeadsPage />)
    await screen.findByText(/ne dirigez aucune équipe commerciale/)
    expect(screen.queryByRole('button', { name: /Réglages de l’attribution/ })).toBeNull()
  })

  it('règle à choix multiples : deux types cochés envoyés en tableau', async () => {
    getDispatch.mockResolvedValue({ data: DISPATCH.exemple })
    const user = userEvent.setup()
    render(<AttributionLeadsPage />)
    await user.click(await screen.findByRole('button', { name: /Réglages de l’attribution/ }))
    await user.click(await screen.findByRole('button', { name: /Ajouter une règle/ }))
    await user.click(screen.getByRole('checkbox', { name: 'Résidentiel' }))
    await user.click(screen.getByRole('checkbox', { name: 'Commercial' }))
    const membre = screen.getByRole('combobox')
    await waitFor(() => expect(within(membre).getByRole('option', { name: 'Sara' })).toBeInTheDocument())
    await user.selectOptions(membre, 'Sara')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(saveRegleAttribution).toHaveBeenCalledWith(null, expect.objectContaining({
      equipe: 7, types_installation: ['residentiel', 'commercial'], sources: [], membre: 4,
    })))
  })

  it('le délai enregistré passe par saveReglagesDispatch', async () => {
    getDispatch.mockResolvedValue({ data: DISPATCH.exemple })
    const user = userEvent.setup()
    render(<AttributionLeadsPage />)
    await user.click(await screen.findByRole('button', { name: /Réglages de l’attribution/ }))
    const champ = await screen.findByLabelText(/Délai avant attribution automatique/)
    await user.clear(champ)
    await user.type(champ, '9')
    await user.tab()
    await waitFor(() => expect(saveReglagesDispatch).toHaveBeenCalledWith(7, { delai_minutes: 9 }))
  })
})

describe('CockpitEquipePage (cockpit d’équipe)', () => {
  const monter = () => render(<MemoryRouter><CockpitEquipePage /></MemoryRouter>)

  it('affiche les membres avec réalisé / cible et pourcentage', async () => {
    getCockpitEquipe.mockResolvedValue(reponseContrat('crm', 'cockpit_equipe', 'exemple'))
    monter()
    expect(await screen.findByText('Octobre 2026')).toBeInTheDocument()
    const ligne = screen.getAllByRole('row').find((r) => within(r).queryByText('Sara'))
    expect(within(ligne).getByText('36')).toBeInTheDocument()
    expect(within(ligne).getByText(/\/ 40/)).toBeInTheDocument()
    expect(within(ligne).getByText('90 %')).toBeInTheDocument()
    expect(screen.getByTestId('cockpit-total-objectifs')).toBeInTheDocument()
  })

  it('exemple vide : message sans équipe', async () => {
    getCockpitEquipe.mockResolvedValue(reponseContrat('crm', 'cockpit_equipe', 'exemple_vide'))
    monter()
    expect(await screen.findByText('Vous ne dirigez aucune équipe commerciale.')).toBeInTheDocument()
  })

  it('cellule sans objectif : création par saveObjectif(null, …)', async () => {
    getCockpitEquipe.mockResolvedValue(reponseContrat('crm', 'cockpit_equipe', 'exemple'))
    const user = userEvent.setup()
    monter()
    await screen.findByText('Octobre 2026')
    await user.click(screen.getByRole('button', { name: /Fixer un objectif/ }))
    await user.type(await screen.findByLabelText('Cible'), '30')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(saveObjectif).toHaveBeenCalledWith(null, {
      owner: 4, metric: 'nb_contacts', period_type: 'month', period_year: 2026, period_month: 10, cible: '30.00',
    }))
  })

  it('cellule avec objectif : modification par saveObjectif(id, { cible })', async () => {
    getCockpitEquipe.mockResolvedValue(reponseContrat('crm', 'cockpit_equipe', 'exemple'))
    const user = userEvent.setup()
    monter()
    await screen.findByText('Octobre 2026')
    const ligne = screen.getAllByRole('row').find((r) => within(r).queryByText('Sara'))
    await user.click(within(ligne).getByText(/\/ 40/))
    const champ = await screen.findByLabelText('Cible')
    await user.clear(champ)
    await user.type(champ, '50')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(saveObjectif).toHaveBeenCalledWith(31, { cible: '50.00' }))
  })
})
