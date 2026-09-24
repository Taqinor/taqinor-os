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
  // CALX43 — `PUT parametres/` : la SEULE porte d'écriture des deux sections.
  putParametres: vi.fn(),
  // CALX42 — « Partir de ce modèle » (action de LISTE).
  creerDepuisModele: vi.fn(),
  // CALX352 — « Marquer comme modèle » (porte `marquer-modele`, CALX42).
  marquerModele: vi.fn(),
}))

vi.mock('../../api/calepinageApi', () => ({
  default: {
    parametres: {
      get: (...a) => mocks.getParametres(...a),
      update: (...a) => mocks.putParametres(...a),
      profilsTypes: (...a) => mocks.getProfilsTypes(...a),
      enregistrerProfilsTypes: (...a) => mocks.putProfilsTypes(...a),
    },
    calepinages: {
      modeles: (...a) => mocks.getModeles(...a),
      creerDepuisModele: (...a) => mocks.creerDepuisModele(...a),
      marquerModele: (...a) => mocks.marquerModele(...a),
    },
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

/* ============================================================================
   CALX43 — PRÉRÉGLAGES ET FAVORIS MATÉRIEL, ÉDITABLES PAR LA PORTE EXISTANTE.
   ----------------------------------------------------------------------------
   Ce qui est prouvé : sans le droit de gérer, tout reste en lecture avec le
   badge existant ; une valeur sans source est refusée et la LIGNE est
   pointée ; un préréglage neuf n'arrive avec AUCUNE valeur par défaut ; les
   entrées réservées de la section (`jeux`, `kits`) traversent intactes.
   ========================================================================== */
describe('CALX43 — édition des préréglages et des favoris', () => {
  const rendreAvecDroit = async (reglages = REGLAGES) => {
    mocks.hasPermission.mockReturnValue(true)
    mocks.getParametres.mockResolvedValue({ data: reglages })
    mocks.getModeles.mockResolvedValue({ data: [] })
    render(<Bibliotheque />)
    await waitFor(() => expect(screen.getByTestId('cal-biblio-presets-edition'))
      .toBeInTheDocument())
  }

  it('sans `calepinage_gerer` : lecture seule, le badge existant, aucune édition', async () => {
    mocks.hasPermission.mockReturnValue(false)
    mocks.getParametres.mockResolvedValue({ data: REGLAGES })
    mocks.getModeles.mockResolvedValue({ data: [] })
    render(<Bibliotheque />)

    expect(await screen.findByTestId('cal-biblio-lecture-seule')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-biblio-presets-edition')).toBeNull()
    expect(screen.queryByTestId('cal-biblio-favoris-edition')).toBeNull()
    expect(screen.getByText(/la création\/édition des\s+presets n’est pas proposée ici/))
      .toBeInTheDocument()
  })

  it('un préréglage sans source est REFUSÉ et sa ligne est pointée', async () => {
    await rendreAvecDroit()

    // La ligne 0 vient du contrat committé et ne porte AUCUNE source.
    await userEvent.click(screen.getByTestId('cal-biblio-presets-enregistrer'))

    expect(screen.getByTestId('cal-biblio-preset-erreur-0'))
      .toHaveTextContent('doit porter sa source')
    expect(mocks.getParametres).toHaveBeenCalledTimes(1)
    // Rien n'a été envoyé : le PUT n'est pas appelé sur une valeur sans source.
    expect(mocks.putParametres).not.toHaveBeenCalled()
  })

  it('avec sa source, le préréglage part — et `jeux`/`kits` traversent intacts', async () => {
    mocks.putParametres.mockResolvedValue({ data: REGLAGES })
    await rendreAvecDroit({
      ...REGLAGES,
      presets: {
        ...REGLAGES.presets,
        jeux: [{ id: 'maison', nom: 'Jeu maison' }],
        kits: [{ id: 7 }],
      },
    })

    await userEvent.type(screen.getByTestId('cal-biblio-preset-source-0'),
      'Fiche produit du fabricant, 2026')
    await userEvent.click(screen.getByTestId('cal-biblio-presets-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalled())
    const corps = mocks.putParametres.mock.calls[0][0]
    const cle = Object.keys(REGLAGES.presets)[0]
    expect(corps.presets[cle].source).toBe('Fiche produit du fabricant, 2026')
    // Les deux entrées réservées sont RENVOYÉES telles quelles : éditer un
    // préréglage n'efface pas le catalogue de kits (leçon services/presets).
    expect(corps.presets.jeux).toEqual([{ id: 'maison', nom: 'Jeu maison' }])
    expect(corps.presets.kits).toEqual([{ id: 7 }])
    // La section `favoris_materiel` n'est PAS touchée par cet envoi.
    expect(corps.favoris_materiel).toBeUndefined()
  })

  it('« Ajouter un préréglage » n’invente AUCUNE valeur par défaut', async () => {
    await rendreAvecDroit()

    await userEvent.click(screen.getByTestId('cal-biblio-preset-ajouter'))

    expect(screen.getByTestId('cal-biblio-preset-cle-1')).toHaveValue('')
    expect(screen.getByTestId('cal-biblio-preset-champs-1')).toHaveValue('')
    expect(screen.getByTestId('cal-biblio-preset-source-1')).toHaveValue('')
  })

  it('un préréglage sans nom est refusé en pointant SA ligne', async () => {
    await rendreAvecDroit()

    await userEvent.click(screen.getByTestId('cal-biblio-preset-ajouter'))
    await userEvent.click(screen.getByTestId('cal-biblio-presets-enregistrer'))

    // La ligne 0 est fautive la première (pas de source) : on la corrige.
    await userEvent.type(screen.getByTestId('cal-biblio-preset-source-0'), 'Facture ONEE')
    await userEvent.click(screen.getByTestId('cal-biblio-presets-enregistrer'))
    expect(screen.getByTestId('cal-biblio-preset-erreur-1'))
      .toHaveTextContent('n’a pas de nom')
  })

  it('le refus SERVEUR s’affiche tel quel, sans être réécrit', async () => {
    const MOTIF = 'Section de réglages inconnue : « presets ».'
    mocks.putParametres.mockRejectedValue({
      response: { status: 400, data: { presets: MOTIF } },
    })
    await rendreAvecDroit()

    await userEvent.type(screen.getByTestId('cal-biblio-preset-source-0'), 'Fiche produit')
    await userEvent.click(screen.getByTestId('cal-biblio-presets-enregistrer'))

    expect(await screen.findByTestId('cal-biblio-presets-erreur'))
      .toHaveTextContent(MOTIF)
  })

  it('un favori dont un identifiant n’en est pas un est refusé, ligne pointée', async () => {
    await rendreAvecDroit()

    await userEvent.clear(screen.getByTestId('cal-biblio-favori-ids-0'))
    await userEvent.type(screen.getByTestId('cal-biblio-favori-ids-0'), '412, panneau')
    await userEvent.click(screen.getByTestId('cal-biblio-favoris-enregistrer'))

    expect(screen.getByTestId('cal-biblio-favori-erreur-0'))
      .toHaveTextContent('n’est pas un identifiant de produit')
    expect(mocks.putParametres).not.toHaveBeenCalled()
  })

  it('les favoris valides partent sous `favoris_materiel`, en entiers', async () => {
    mocks.putParametres.mockResolvedValue({ data: REGLAGES })
    await rendreAvecDroit()

    await userEvent.click(screen.getByTestId('cal-biblio-favoris-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalled())
    const corps = mocks.putParametres.mock.calls[0][0]
    const role = Object.keys(REGLAGES.favoris_materiel)[0]
    expect(corps.favoris_materiel[role])
      .toEqual(REGLAGES.favoris_materiel[role].map(Number))
    expect(corps.presets).toBeUndefined()
  })
})

/* ============================================================================
   CALX42 — « PARTIR DE CE MODÈLE », DEPUIS LA BIBLIOTHÈQUE.
   ========================================================================== */
describe('CALX42 — créer un calepinage depuis un modèle', () => {
  const rendreModeles = async (droit = true) => {
    mocks.hasPermission.mockReturnValue(droit)
    mocks.getParametres.mockResolvedValue({ data: REGLAGES })
    mocks.getModeles.mockResolvedValue({ data: MODELES })
    render(<Bibliotheque />)
    await waitFor(() => expect(screen.getByTestId('cal-biblio-modele-5'))
      .toBeInTheDocument())
  }

  it('sans `calepinage_gerer` : le bouton n’apparaît pas', async () => {
    await rendreModeles(false)
    expect(screen.queryByTestId('cal-biblio-modele-partir-5')).toBeNull()
  })

  it('le rattachement est SAISI — celui du modèle n’est jamais recopié', async () => {
    mocks.creerDepuisModele.mockResolvedValue({ data: { id: 88 } })
    await rendreModeles()

    await userEvent.click(screen.getByTestId('cal-biblio-modele-partir-5'))
    await userEvent.type(screen.getByTestId('cal-biblio-modele-client'), '12')
    await userEvent.click(screen.getByTestId('cal-biblio-modele-creer'))

    await waitFor(() => expect(mocks.creerDepuisModele)
      .toHaveBeenCalledWith({ modele: 5, client: '12' }))
    // Le champ laissé vide n'est PAS envoyé : rien n'est deviné.
    expect(mocks.creerDepuisModele.mock.calls[0][0].lead).toBeUndefined()
    // Le calepinage créé s'ouvre depuis ici.
    expect(await screen.findByTestId('cal-biblio-modele-ouvrir'))
      .toHaveAttribute('href', '/calepinage/88')
  })

  it('refus serveur : le motif s’affiche tel quel, sous la saisie', async () => {
    const MOTIF = 'Créer un projet depuis un modèle exige un nouveau lead ou client.'
    mocks.creerDepuisModele.mockRejectedValue({
      response: { status: 400, data: { client: MOTIF } },
    })
    await rendreModeles()

    await userEvent.click(screen.getByTestId('cal-biblio-modele-partir-5'))
    await userEvent.click(screen.getByTestId('cal-biblio-modele-creer'))

    expect(await screen.findByTestId('cal-biblio-modele-erreur'))
      .toHaveTextContent(MOTIF)
    expect(screen.queryByTestId('cal-biblio-modele-ouvrir')).toBeNull()
  })
})

/* ============================================================================
   CALX352 — « MARQUER COMME MODÈLE », DEPUIS LA BIBLIOTHÈQUE.
   ========================================================================== */
describe('CALX352 — marquer un calepinage comme modèle', () => {
  const rendreBiblio = async (droit = true) => {
    mocks.hasPermission.mockReturnValue(droit)
    mocks.getParametres.mockResolvedValue({ data: REGLAGES })
    mocks.getModeles.mockResolvedValue({ data: MODELES })
    render(<Bibliotheque />)
    await waitFor(() => expect(screen.getByTestId('cal-biblio-modele-5'))
      .toBeInTheDocument())
  }

  it('sans `calepinage_gerer` : le geste n’est pas proposé', async () => {
    await rendreBiblio(false)
    expect(screen.queryByTestId('cal-biblio-marquer')).toBeNull()
  })

  it('marque le calepinage SAISI puis RELIT la liste du serveur', async () => {
    mocks.marquerModele.mockResolvedValue({ data: { calepinage: 12, modele: true } })
    await rendreBiblio()
    mocks.getModeles.mockResolvedValue({
      data: [...MODELES, { id: 12, titre: 'Hangar Maârif' }],
    })

    await userEvent.type(screen.getByTestId('cal-biblio-marquer-id'), '12')
    await userEvent.click(screen.getByTestId('cal-biblio-marquer-bouton'))

    await waitFor(() => expect(mocks.marquerModele).toHaveBeenCalledWith('12'))
    expect(await screen.findByTestId('cal-biblio-modele-12'))
      .toHaveTextContent('Hangar Maârif')
    expect(screen.getByTestId('cal-biblio-marquer-id')).toHaveValue('')
  })

  it('un identifiant qui n’en est pas un n’est PAS envoyé : le motif est sous la saisie', async () => {
    await rendreBiblio()
    await userEvent.type(screen.getByTestId('cal-biblio-marquer-id'), 'villa')
    await userEvent.click(screen.getByTestId('cal-biblio-marquer-bouton'))
    expect(await screen.findByTestId('cal-biblio-marquer-erreur'))
      .toHaveTextContent(/identifiant numérique/)
    expect(mocks.marquerModele).not.toHaveBeenCalled()
  })

  it('refus serveur : le motif s’affiche tel quel, sous la saisie', async () => {
    const MOTIF = 'Pas trouvé.'
    mocks.marquerModele.mockRejectedValue({ response: { status: 404, data: { detail: MOTIF } } })
    await rendreBiblio()
    await userEvent.type(screen.getByTestId('cal-biblio-marquer-id'), '999')
    await userEvent.click(screen.getByTestId('cal-biblio-marquer-bouton'))
    expect(await screen.findByTestId('cal-biblio-marquer-erreur')).toHaveTextContent(MOTIF)
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
