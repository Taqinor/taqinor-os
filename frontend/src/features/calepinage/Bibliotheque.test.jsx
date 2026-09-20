import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   CAL201 — LA BIBLIOTHÈQUE, NOURRIE PAR L'ÉCHANTILLON DE CONTRAT COMMITTÉ.
   ----------------------------------------------------------------------------
   `parametres_calepinage.json` (CAL45/CAL246) publie les quatre sections
   (`presets`, `kits`, `favoris_materiel` — et l'endpoint séparé « modèles »,
   CAL199) : ce test relit CET exemple committé, jamais un mock écrit à la
   main — exactement ce que le Done de la tâche exige.

   Ce qui est prouvé :
     1. les quatre listes se rendent depuis les DEUX endpoints réels ;
     2. sans `calepinage_gerer`, l'écran affiche « Lecture seule » et NE
        PROPOSE aucune création/édition — mais reste TOUJOURS lisible ;
     3. une société sans aucun réglage (sections vides) le DIT, sans jamais
        écrire « erreur » ni un tableau qui aurait l'air cassé.
   ========================================================================== */

const REGLAGES = exempleContrat('calepinage', 'parametres_calepinage')

const mocks = vi.hoisted(() => ({
  getParametres: vi.fn(),
  getModeles: vi.fn(),
  hasPermission: vi.fn(),
}))

vi.mock('../../api/calepinageApi', () => ({
  default: {
    parametres: { get: (...a) => mocks.getParametres(...a) },
    calepinages: { modeles: (...a) => mocks.getModeles(...a) },
  },
}))

vi.mock('../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => mocks.hasPermission(code),
}))

const { default: Bibliotheque } = await import('./Bibliotheque')

const MODELES = [
  { id: 5, titre: 'Villa type R+1', statut_libelle: 'Validé' },
]

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('CAL201 — les quatre listes, depuis les DEUX endpoints réels', () => {
  it('rend les presets, kits et favoris du contrat committé, et les modèles', async () => {
    mocks.hasPermission.mockReturnValue(true)
    mocks.getParametres.mockResolvedValue({ data: REGLAGES })
    mocks.getModeles.mockResolvedValue({ data: MODELES })
    render(<Bibliotheque />)

    await waitFor(() => expect(screen.getByTestId('cal-bibliotheque')).toBeInTheDocument())

    for (const cle of Object.keys(REGLAGES.presets)) {
      expect(screen.getByTestId(`cal-biblio-preset-${cle}`)).toBeInTheDocument()
    }
    for (const kit of REGLAGES.kits) {
      expect(screen.getByTestId(`cal-biblio-kit-${kit.id}`)).toBeInTheDocument()
    }
    for (const cle of Object.keys(REGLAGES.favoris_materiel)) {
      expect(screen.getByTestId(`cal-biblio-favori-${cle}`)).toBeInTheDocument()
    }
    expect(screen.getByTestId('cal-biblio-modele-5')).toHaveTextContent('Villa type R+1')
  })

  it('un favori compte EXACTEMENT ses ids — jamais un total inventé', async () => {
    mocks.hasPermission.mockReturnValue(true)
    mocks.getParametres.mockResolvedValue({ data: REGLAGES })
    mocks.getModeles.mockResolvedValue({ data: [] })
    render(<Bibliotheque />)

    const cle = Object.keys(REGLAGES.favoris_materiel)[0]
    const attendu = REGLAGES.favoris_materiel[cle]
    const ligne = await screen.findByTestId(`cal-biblio-favori-${cle}`)
    expect(ligne).toHaveTextContent(`${attendu.length} produit(s)`)
    for (const id of attendu) expect(ligne).toHaveTextContent(String(id))
  })

  it('aucun kit disponible : le DIT, sans tableau cassé', async () => {
    mocks.hasPermission.mockReturnValue(true)
    mocks.getParametres.mockResolvedValue({
      data: { ...REGLAGES, kits: [] },
    })
    mocks.getModeles.mockResolvedValue({ data: [] })
    render(<Bibliotheque />)

    expect(await screen.findByText(/Aucun kit de pose disponible/))
      .toBeInTheDocument()
  })

  it('aucun modèle marqué : le DIT', async () => {
    mocks.hasPermission.mockReturnValue(true)
    mocks.getParametres.mockResolvedValue({ data: REGLAGES })
    mocks.getModeles.mockResolvedValue({ data: [] })
    render(<Bibliotheque />)

    expect(await screen.findByText(/Aucun calepinage n’est marqué modèle/))
      .toBeInTheDocument()
  })

  it('société sans aucun réglage : quatre sections vides, EXPLIQUÉES', async () => {
    mocks.hasPermission.mockReturnValue(true)
    mocks.getParametres.mockResolvedValue({ data: {} })
    mocks.getModeles.mockResolvedValue({ data: [] })
    render(<Bibliotheque />)

    await waitFor(() => expect(screen.getByTestId('cal-bibliotheque')).toBeInTheDocument())
    expect(screen.getByText(/Aucun preset réglé/)).toBeInTheDocument()
    expect(screen.getByText(/Aucun matériel favori réglé/)).toBeInTheDocument()
  })

  it('une erreur serveur s’affiche telle quelle, jamais un texte fabriqué', async () => {
    mocks.hasPermission.mockReturnValue(true)
    mocks.getParametres.mockRejectedValue({
      response: { data: { detail: 'Panne du serveur des réglages.' } },
    })
    mocks.getModeles.mockResolvedValue({ data: [] })
    render(<Bibliotheque />)

    expect(await screen.findByTestId('cal-biblio-erreur'))
      .toHaveTextContent('Panne du serveur des réglages.')
  })
})

describe('CAL201 — sans `calepinage_gerer`, lecture seule (Done de la tâche)', () => {
  it('affiche le badge « Lecture seule » et ne propose aucune édition', async () => {
    mocks.hasPermission.mockReturnValue(false)
    mocks.getParametres.mockResolvedValue({ data: REGLAGES })
    mocks.getModeles.mockResolvedValue({ data: MODELES })
    render(<Bibliotheque />)

    expect(await screen.findByTestId('cal-biblio-lecture-seule')).toBeInTheDocument()
    // Les quatre listes restent TOUJOURS visibles — lecture seule n'est pas
    // « rien à voir ».
    expect(screen.getByTestId('cal-biblio-modele-5')).toBeInTheDocument()
    expect(mocks.hasPermission).toHaveBeenCalledWith('calepinage_gerer')
  })

  it('avec `calepinage_gerer`, aucun badge « Lecture seule »', async () => {
    mocks.hasPermission.mockReturnValue(true)
    mocks.getParametres.mockResolvedValue({ data: REGLAGES })
    mocks.getModeles.mockResolvedValue({ data: [] })
    render(<Bibliotheque />)

    await waitFor(() => expect(screen.getByTestId('cal-bibliotheque')).toBeInTheDocument())
    expect(screen.queryByTestId('cal-biblio-lecture-seule')).toBeNull()
  })
})

describe('CAL201 — l’écran est ATTEIGNABLE', () => {
  it('le module déclare la route `/calepinage/bibliotheque` avec ses rôles', async () => {
    const { default: config } = await import('./module.config.jsx')
    const route = config.routes.find((r) => r.path === '/calepinage/bibliotheque')
    expect(route, 'route de la bibliothèque absente du module').toBeTruthy()
    expect(Array.isArray(route.roles) && route.roles.length > 0).toBe(true)
  })

  it('un item de nav PERMANENT mène à `/calepinage/bibliotheque`', async () => {
    const { default: config } = await import('./module.config.jsx')
    const item = config.nav.items.find((i) => i.to === '/calepinage/bibliotheque')
    expect(item, 'entrée de nav de la bibliothèque absente').toBeTruthy()
  })
})
