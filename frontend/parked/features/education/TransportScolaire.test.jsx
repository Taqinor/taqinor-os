import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const { circuits, arrets, affectations, eleves, vehicules } = vi.hoisted(() => ({
  circuits: { list: vi.fn(), create: vi.fn(), update: vi.fn() },
  arrets: { list: vi.fn(), create: vi.fn() },
  affectations: { list: vi.fn(), create: vi.fn() },
  eleves: { list: vi.fn() },
  vehicules: { list: vi.fn() },
}))

vi.mock('../../api/educationApi', () => ({
  default: {
    circuitsTransport: circuits,
    arretsTransport: arrets,
    affectationsTransport: affectations,
    eleves,
  },
}))
vi.mock('../../api/flotteApi', () => ({ default: { vehicules } }))
vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

import TransportScolaire from './TransportScolaire'
import config from './module.config.jsx'

/* ============================================================================
   PACT80 — Transport scolaire. Le backend NTEDU23 était entier ; le client
   éducation n'avait AUCUNE entrée pour ce sujet. Les trois clauses du contrat
   sont verrouillées ici : véhicule pris DANS LE PARC (FK réelle), arrêts
   ORDONNÉS, et indisponibilité = avertissement DOUX qui n'empêche jamais
   l'enregistrement.
   ========================================================================== */

function afficher() {
  return render(
    <ThemeProvider>
      <TransportScolaire />
    </ThemeProvider>,
  )
}

describe('TransportScolaire (PACT80)', () => {
  beforeEach(() => {
    circuits.list.mockResolvedValue({
      data: [{ id: 7, nom: 'Circuit Nord', vehicule: 42, actif: true }],
    })
    // Volontairement DANS LE DÉSORDRE : l'écran doit les remettre en ordre.
    arrets.list.mockResolvedValue({
      data: [
        { id: 3, circuit: 7, nom: 'Terminus école', ordre: 3, heure_passage_estimee: '07:45' },
        { id: 1, circuit: 7, nom: 'Place Al Massira', ordre: 1, heure_passage_estimee: '07:15' },
        { id: 2, circuit: 7, nom: 'Avenue Hassan II', ordre: 2, heure_passage_estimee: '07:30' },
      ],
    })
    affectations.list.mockResolvedValue({ data: [] })
    eleves.list.mockResolvedValue({ data: [{ id: 11, nom: 'Alami', prenom: 'Sara' }] })
    vehicules.list.mockResolvedValue({
      data: [{ id: 42, immatriculation: '1234-A-56' }],
    })
    circuits.create.mockResolvedValue({ data: { id: 8 } })
    arrets.create.mockResolvedValue({ data: { id: 9 } })
    affectations.create.mockResolvedValue({ data: { id: 5, avertissement: null } })
  })

  afterEach(() => {
    vi.clearAllMocks()
    cleanup()
  })

  it('lit le parc par le client de la FLOTTE et pose la FK véhicule à la création',
    async () => {
      afficher()
      await waitFor(() => expect(vehicules.list).toHaveBeenCalled())
      // Le véhicule se CHOISIT dans le parc : jamais une immatriculation libre.
      await screen.findByRole('option', { name: '1234-A-56' })

      fireEvent.change(screen.getByLabelText(/Nom du circuit/i),
                       { target: { value: 'Circuit Sud' } })
      fireEvent.change(screen.getByLabelText(/Véhicule \(parc flotte\)/i),
                       { target: { value: '42' } })
      fireEvent.click(screen.getByRole('button', { name: /Créer le circuit/i }))

      await waitFor(() => expect(circuits.create).toHaveBeenCalledWith({
        nom: 'Circuit Sud', vehicule: 42,
      }))
    })

  it('affiche les arrêts DANS L’ORDRE du parcours, pas dans celui du serveur',
    async () => {
      afficher()
      // Le nom de l'arrêt et l'heure de passage sont deux nœuds de texte
      // frères dans le <li> (rendus par deux expressions JSX distinctes) :
      // on cible celui qui COMMENCE par le nom de l'arrêt, sans exiger un
      // texte exact qui inclurait l'heure.
      const premier = await screen.findByText(/^Place Al Massira/)
      const liste = premier.closest('ol')
      const noms = Array.from(liste.querySelectorAll('li')).map((li) => li.textContent)
      expect(noms[0]).toContain('Place Al Massira')
      expect(noms[1]).toContain('Avenue Hassan II')
      expect(noms[2]).toContain('Terminus école')
    })

  it('crée un arrêt avec son ordre sur le circuit', async () => {
    afficher()
    // « Circuit Nord » apparaît aussi comme <option> dans les deux <select>
    // de circuit (arrêt et affectation) : on cible explicitement l'élément
    // de la liste des circuits rendus, seul indicateur fiable que le
    // chargement initial est terminé.
    await screen.findByText('Circuit Nord', { selector: 'strong' })

    fireEvent.change(screen.getByLabelText(/Circuit de l’arrêt/i),
                     { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText(/Nom de l’arrêt/i),
                     { target: { value: 'Rond-point Anfa' } })
    fireEvent.change(screen.getByLabelText(/Ordre sur le circuit/i),
                     { target: { value: '4' } })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter l’arrêt/i }))

    await waitFor(() => expect(arrets.create).toHaveBeenCalledWith({
      circuit: 7, nom: 'Rond-point Anfa', ordre: 4, heure_passage_estimee: null,
    }))
  })

  it('AVERTIT sans jamais bloquer quand le véhicule est indisponible', async () => {
    affectations.create.mockResolvedValue({
      data: { id: 5, avertissement: 'Le véhicule du circuit n’est pas opérationnel.' },
    })
    afficher()
    // Voir la note plus haut : on vise l'élément de la liste des circuits,
    // pas l'une des <option> homonymes.
    await screen.findByText('Circuit Nord', { selector: 'strong' })

    fireEvent.change(screen.getByLabelText(/^Élève$/i), { target: { value: '11' } })
    fireEvent.change(screen.getByLabelText(/Circuit de l’élève/i),
                     { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText(/^Début$/i), { target: { value: '2026-09-01' } })
    fireEvent.click(screen.getByRole('button', { name: /^Affecter$/i }))

    // 1) L'affectation EST partie au serveur…
    await waitFor(() => expect(affectations.create).toHaveBeenCalledTimes(1))
    // 2) …l'avertissement est affiché comme un STATUT, pas comme une erreur…
    const bandeau = await screen.findByRole('status')
    expect(bandeau.textContent).toContain('n’est pas opérationnel')
    expect(bandeau.textContent).toContain('a bien été enregistrée')
    // 3) …et la liste est rechargée : rien n'a été annulé.
    expect(affectations.list.mock.calls.length).toBeGreaterThan(1)
  })

  it('n’affiche aucun avertissement quand le véhicule est disponible', async () => {
    afficher()
    // Voir la note plus haut : on vise l'élément de la liste des circuits,
    // pas l'une des <option> homonymes.
    await screen.findByText('Circuit Nord', { selector: 'strong' })

    fireEvent.change(screen.getByLabelText(/^Élève$/i), { target: { value: '11' } })
    fireEvent.change(screen.getByLabelText(/Circuit de l’élève/i),
                     { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText(/^Début$/i), { target: { value: '2026-09-01' } })
    fireEvent.click(screen.getByRole('button', { name: /^Affecter$/i }))

    await waitFor(() => expect(affectations.create).toHaveBeenCalledTimes(1))
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('affiche un message visible quand un chargement échoue, jamais un vide silencieux',
    async () => {
      // Les 5 ressources sont chargées via useEducationResource, qui expose un
      // champ `error` — un GET en échec ne doit jamais se travestir en
      // « Aucun circuit pour l'instant » sans un mot dessus.
      circuits.list.mockRejectedValue(new Error('boom'))
      afficher()

      const bandeau = await screen.findByRole('alert')
      expect(bandeau.textContent).toContain('Chargement impossible.')

      // L'état vide honnête reste affiché en dessous (pas de faux-semblant
      // « ça marche »), mais l'échec, lui, est maintenant dit.
      expect(await screen.findByText('Aucun circuit pour l’instant.')).toBeInTheDocument()
    })

  it('est ATTEIGNABLE : la route et l’entrée de nav sont déclarées', () => {
    const route = config.routes.find((r) => r.path === '/education/transport')
    expect(route).toBeTruthy()
    expect(route.component).toBeTruthy()
    expect(route.roles.length).toBeGreaterThan(0)

    const nav = config.nav.items.find((i) => i.to === '/education/transport')
    expect(nav).toBeTruthy()
    expect(nav.label).toBe('Transport scolaire')
    expect(nav.icon).toBeTruthy()

    const titre = config.titles.find(([chemin]) => chemin === '/education/transport')
    expect(titre?.[1]).toBe('Transport scolaire')
  })
})
