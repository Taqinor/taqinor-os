import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
  // CALX30 — `GET/PUT parametres/profils-types/` (CAL149).
  getProfilsTypes: vi.fn(),
  putProfilsTypes: vi.fn(),
}))

vi.mock('../../api/calepinageApi', () => ({
  default: {
    parametres: {
      get: (...a) => mocks.getParametres(...a),
      profilsTypes: (...a) => mocks.getProfilsTypes(...a),
      enregistrerProfilsTypes: (...a) => mocks.putProfilsTypes(...a),
    },
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

/* CALX30 — la forme SERVIE par `views/consommation.py` : un profil SAISI par
   la société, puis un profil de REPLI étiqueté « hypothèse interne » avec sa
   provenance (`services/profils_types.py`). */
const COURBE_24 = Array.from({ length: 24 }, () => 1 / 24)
const PROFILS = [
  {
    id: 3, cle: 'villa', libelle: 'Villa Casablanca', famille: 'residentiel',
    source: 'societe', provenance: 'Relevé de compteur, mars 2026',
    courbes: { annuel: COURBE_24 }, saisons: ['annuel'],
  },
  {
    id: null, cle: 'commercial', libelle: 'Commercial / tertiaire (repli)',
    famille: 'commercial', source: 'hypothese_interne',
    provenance: 'Profil codé en dur dans le dépôt — HYPOTHÈSE INTERNE.',
    courbes: { annuel: COURBE_24 }, saisons: ['annuel'],
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  // Défaut commun à TOUS les tests : la bibliothèque lit trois endpoints.
  mocks.getProfilsTypes.mockResolvedValue({ data: { profils: PROFILS } })
})
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

/* ============================================================================
   CALX30 — LES PROFILS TYPES, ÉDITABLES, ET LE REPLI QUI RESTE UN REPLI.
   ========================================================================== */
describe('CALX30 — profils types de consommation', () => {
  const rendreAvecDroit = async () => {
    mocks.hasPermission.mockReturnValue(true)
    mocks.getParametres.mockResolvedValue({ data: REGLAGES })
    mocks.getModeles.mockResolvedValue({ data: [] })
    render(<Bibliotheque />)
    await waitFor(() => expect(screen.getByTestId('cal-biblio-profils-liste'))
      .toBeInTheDocument())
  }

  it('un profil de REPLI porte son étiquette et sa provenance', async () => {
    await rendreAvecDroit()

    expect(screen.getByTestId('cal-biblio-profil-repli-1'))
      .toHaveTextContent('Hypothèse interne')
    expect(screen.getByTestId('cal-biblio-profil-provenance-1'))
      .toHaveTextContent('HYPOTHÈSE INTERNE')
    // Il n'est PAS éditable : aucun champ de saisie sur cette ligne.
    expect(screen.queryByTestId('cal-biblio-profil-cle-1')).toBeNull()
    expect(screen.queryByTestId('cal-biblio-profil-retirer-1')).toBeNull()
  })

  it('un repli ne peut pas être présenté comme une mesure : il n’est jamais envoyé', async () => {
    mocks.putProfilsTypes.mockResolvedValue({ data: { profils: PROFILS } })
    await rendreAvecDroit()

    await userEvent.click(screen.getByTestId('cal-biblio-profils-enregistrer'))

    await waitFor(() => expect(mocks.putProfilsTypes).toHaveBeenCalled())
    const envoyes = mocks.putProfilsTypes.mock.calls[0][0]
    expect(envoyes).toHaveLength(1)
    expect(envoyes[0].cle).toBe('villa')
    // La courbe part sous le nom que le PUT attend (`courbe`), telle que le
    // serveur l'a servie — aucune valeur n'est arrondie ni inventée.
    expect(envoyes[0].courbe.annuel).toEqual(COURBE_24)
    expect(envoyes[0].provenance).toBe('Relevé de compteur, mars 2026')
  })

  it('l’enregistrement remonte l’erreur serveur SOUS le profil fautif', async () => {
    const MOTIF = 'Profil « villa » : La provenance est obligatoire.'
    mocks.putProfilsTypes.mockRejectedValue({
      response: { status: 400, data: { 'villa.provenance': [MOTIF] } },
    })
    await rendreAvecDroit()

    await userEvent.click(screen.getByTestId('cal-biblio-profils-enregistrer'))

    // Ligne 0 = le profil « villa » : c'est LÀ que le motif s'affiche.
    expect(await screen.findByTestId('cal-biblio-profil-erreur-0'))
      .toHaveTextContent(MOTIF)
    expect(screen.queryByTestId('cal-biblio-profils-erreur')).toBeNull()
  })

  it('un refus « profils[N] » retombe sur la bonne ligne malgré le repli', async () => {
    const MOTIF = 'Le profil n°1 n’a pas de clé.'
    mocks.putProfilsTypes.mockRejectedValue({
      response: { status: 400, data: { 'profils[0].cle': [MOTIF] } },
    })
    await rendreAvecDroit()

    await userEvent.click(screen.getByTestId('cal-biblio-profils-enregistrer'))

    expect(await screen.findByTestId('cal-biblio-profil-erreur-0'))
      .toHaveTextContent(MOTIF)
  })

  it('un refus qui ne vise aucun profil est dit sans être réécrit', async () => {
    const MOTIF = 'Les profils types se donnent en liste ordonnée.'
    mocks.putProfilsTypes.mockRejectedValue({
      response: { status: 400, data: { profils: [MOTIF] } },
    })
    await rendreAvecDroit()

    await userEvent.click(screen.getByTestId('cal-biblio-profils-enregistrer'))

    expect(await screen.findByTestId('cal-biblio-profils-erreur'))
      .toHaveTextContent(MOTIF)
  })

  it('« Ajouter un profil » ne remplit AUCUNE valeur par défaut', async () => {
    await rendreAvecDroit()

    await userEvent.click(screen.getByTestId('cal-biblio-profil-ajouter'))

    expect(screen.getByTestId('cal-biblio-profil-cle-2')).toHaveValue('')
    expect(screen.getByTestId('cal-biblio-profil-libelle-2')).toHaveValue('')
    expect(screen.getByTestId('cal-biblio-profil-provenance-2')).toHaveValue('')
    expect(screen.getByTestId('cal-biblio-profil-courbe-2')).toHaveValue('')
    expect(screen.getByTestId('cal-biblio-profil-famille-2')).toHaveValue('')
  })

  it('sans `calepinage_gerer` : consultation seule, aucun geste d’écriture', async () => {
    mocks.hasPermission.mockReturnValue(false)
    mocks.getParametres.mockResolvedValue({ data: REGLAGES })
    mocks.getModeles.mockResolvedValue({ data: [] })
    render(<Bibliotheque />)

    await waitFor(() => expect(screen.getByTestId('cal-biblio-profils-liste'))
      .toBeInTheDocument())
    expect(screen.queryByTestId('cal-biblio-profil-ajouter')).toBeNull()
    expect(screen.queryByTestId('cal-biblio-profils-enregistrer')).toBeNull()
    expect(screen.getByTestId('cal-biblio-profil-cle-0')).toBeDisabled()
  })

  it('aucun profil servi : le DIT, sans tableau cassé', async () => {
    mocks.hasPermission.mockReturnValue(true)
    mocks.getParametres.mockResolvedValue({ data: REGLAGES })
    mocks.getModeles.mockResolvedValue({ data: [] })
    mocks.getProfilsTypes.mockResolvedValue({ data: { profils: [] } })
    render(<Bibliotheque />)

    expect(await screen.findByText(/Aucun profil type servi/))
      .toBeInTheDocument()
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
