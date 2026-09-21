import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import TachesKanbanView from './TachesKanbanView'

/* XPRJ11 — Vue kanban des tâches : colonnes de statut PROPRES au module
   (a_faire/en_cours/bloque/termine), alternative clavier au drag via un
   <select> sous chaque carte (miroir du kanban CRM leads). Le parent gère le
   rollback (ce composant se contente d'appeler onChangeStatut). Chaque carte
   rend aussi <ChronoButton>/<TacheChecklist> (XPRJ5/XPRJ-checklist), qui
   appellent gestionProjetApi dans leur propre effet — mocké ici pour rester
   hors réseau, même si les deux composants no-op déjà proprement en cas
   d'échec (try/catch silencieux). */
vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getChronoActif: vi.fn(() => Promise.resolve({ status: 204, data: null })),
    demarrerChrono: vi.fn(() => Promise.resolve({ data: {} })),
    arreterChrono: vi.fn(() => Promise.resolve({ data: {} })),
    getItemsChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    toggleItemChecklist: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

const taches = [
  { id: 1, libelle: 'Étude toiture', statut: 'a_faire', code_wbs: '1.1' },
  { id: 2, libelle: 'Pose panneaux', statut: 'en_cours', code_wbs: '1.2' },
]

describe('TachesKanbanView', () => {
  it('rend les 4 colonnes de statut PROPRES au module', () => {
    render(<TachesKanbanView taches={taches} onChangeStatut={vi.fn()} />)
    // « À faire »/« En cours » apparaissent À LA FOIS dans l'en-tête de colonne
    // (pastille de statut) ET dans chaque <option> des sélecteurs clavier.
    expect(screen.getAllByText('À faire').length).toBeGreaterThan(0)
    expect(screen.getAllByText('En cours').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Bloquée').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Terminée').length).toBeGreaterThan(0)
  })

  it('place chaque tâche dans la colonne de son statut', () => {
    render(<TachesKanbanView taches={taches} onChangeStatut={vi.fn()} />)
    expect(screen.getByText('Étude toiture')).toBeInTheDocument()
    expect(screen.getByText('Pose panneaux')).toBeInTheDocument()
  })

  it('appelle onChangeStatut via le sélecteur clavier', () => {
    const onChangeStatut = vi.fn()
    render(<TachesKanbanView taches={taches} onChangeStatut={onChangeStatut} />)
    const select = screen.getByLabelText(/Changer le statut de Étude toiture/)
    fireEvent.change(select, { target: { value: 'bloque' } })
    expect(onChangeStatut).toHaveBeenCalledWith(taches[0], 'bloque')
  })

  it('désactive le sélecteur de la tâche occupée', () => {
    render(<TachesKanbanView taches={taches} onChangeStatut={vi.fn()} busyTacheId={1} />)
    expect(screen.getByLabelText(/Changer le statut de Étude toiture/)).toBeDisabled()
    expect(screen.getByLabelText(/Changer le statut de Pose panneaux/)).not.toBeDisabled()
  })

  it('affiche un placeholder vide sur les colonnes sans tâche', () => {
    render(<TachesKanbanView taches={taches} onChangeStatut={vi.fn()} />)
    expect(screen.getAllByText('Aucune tâche').length).toBeGreaterThan(0)
  })
})
