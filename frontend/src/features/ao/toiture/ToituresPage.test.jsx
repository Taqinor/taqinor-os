import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* ============================================================================
   AOF190bis — encastrement de « Toitures & relevés » dans un onglet de fiche.
   ----------------------------------------------------------------------------
   `ToituresPage` ne prenait AUCUNE propriété : elle listait toutes les
   affaires de la société et retombait sur la première. Encastrée telle
   quelle sous le titre d'une affaire, elle aurait pu très bien afficher les
   toitures d'une AUTRE affaire — un défaut SILENCIEUX (aucune erreur, aucun
   404 : juste la mauvaise donnée sous le bon titre).

   `affaireId` FOURNI doit donc :
     - filtrer le serveur sur CETTE affaire (`?appel_offre=<id>`, le nom du
       champ réel — `ToitureAOViewSet.get_queryset`, `apps/ao/views.py`) ;
     - ne JAMAIS lister les affaires de la société (aucun sélecteur à
       nourrir, aucune requête à faire) ;
     - masquer le sélecteur d'affaire (proposer d'en changer serait le piège
       que l'encastrement doit précisément éviter).
   `affaireId` ABSENT doit laisser la page pleine largeur `/ao/toitures`
   strictement inchangée (sélecteur + repli sur la première affaire chargée).
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  affairesList: vi.fn(),
  toituresList: vi.fn(),
  toituresCreate: vi.fn(),
  toituresUpdate: vi.fn(),
  batimentsList: vi.fn(),
}))
const toastMocks = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))

vi.mock('../../../api/aoApi', () => ({
  default: {
    affaires: { list: mocks.affairesList },
    toitures: {
      list: mocks.toituresList,
      create: mocks.toituresCreate,
      update: mocks.toituresUpdate,
    },
    batiments: { list: mocks.batimentsList },
  },
}))
vi.mock('../../../api/recordsApi', () => ({
  default: { uploadAttachment: vi.fn() },
}))
vi.mock('../../../ui', async () => {
  const actual = await vi.importActual('../../../ui')
  return { ...actual, toast: { success: toastMocks.success, error: toastMocks.error } }
})

import ToituresPage from './ToituresPage'

const AFFAIRES = [
  { id: 5, reference_acheteur: 'AO-2026-005' },
  { id: 6, reference_acheteur: 'AO-2026-006' },
]

const TOITURE = {
  id: 41, designation: 'Toiture atelier', forme_display: 'Rectangle',
  surface_m2: '312.5', niveau: 'RDC', type_couverture_display: 'Bac acier',
}

const BATIMENTS = [
  { id: 31, code: 'A', designation: 'Atelier' },
  { id: 32, code: 'B', designation: 'Magasin' },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.affairesList.mockResolvedValue({ data: AFFAIRES })
  mocks.toituresList.mockResolvedValue({ data: [TOITURE] })
  mocks.batimentsList.mockResolvedValue({ data: BATIMENTS })
  mocks.toituresCreate.mockResolvedValue({ data: { id: 99 } })
  mocks.toituresUpdate.mockResolvedValue({ data: { id: 41 } })
})

/* Ouvre le wizard, remplit ses deux champs et valide. Le wizard se ferme
   TOUJOURS lui-même (`onOpenChange(false)` juste après `onCreer`) : c'est
   pourquoi un refus doit rester lisible SUR LA PAGE, pas seulement en toast. */
async function creerViaWizard({ nom = 'Toiture Nord', batiment }) {
  // Le bouton reste désactivé tant que les bâtiments de l'affaire ne sont pas
  // chargés : sans cette attente, on cliquerait dans le vide.
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Nouvelle toiture' })).toBeEnabled())
  await userEvent.click(screen.getByRole('button', { name: 'Nouvelle toiture' }))
  const champNom = await screen.findByLabelText('Nom de la toiture')
  await userEvent.type(champNom, nom)
  if (batiment !== undefined) {
    await userEvent.type(screen.getByLabelText('Bâtiment (facultatif)'), batiment)
  }
  // `&apos;` du wizard rend une apostrophe DROITE : le motif tolère les deux.
  await userEvent.click(screen.getByRole('button', { name: /Ouvrir l.atelier/ }))
}

describe('ToituresPage — encastrée avec `affaireId` (AOF190bis)', () => {
  it('filtre le serveur sur `appel_offre` — CETTE affaire, jamais un repli sur une autre', async () => {
    render(<ToituresPage affaireId={7} />)
    await waitFor(() => expect(mocks.toituresList).toHaveBeenCalledWith({ appel_offre: 7 }))
    expect(await screen.findByText('Toiture atelier')).toBeInTheDocument()
  })

  it('ne liste JAMAIS les affaires de la société quand `affaireId` est fourni', async () => {
    render(<ToituresPage affaireId={7} />)
    await waitFor(() => expect(mocks.toituresList).toHaveBeenCalled())
    expect(mocks.affairesList).not.toHaveBeenCalled()
  })

  it('masque le sélecteur d’affaire — l’onglet a déjà choisi l’affaire', async () => {
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')
    expect(screen.queryByLabelText('Affaire')).toBeNull()
    expect(document.getElementById('ao-toitures-affaire')).toBeNull()
  })

  it('affaire sans toiture → état vide EXPLICITE, jamais une liste muette ou celle d’une autre affaire', async () => {
    mocks.toituresList.mockResolvedValue({ data: [] })
    render(<ToituresPage affaireId={9} />)
    expect(await screen.findByText('Aucune toiture relevée pour cette affaire.')).toBeInTheDocument()
    expect(mocks.affairesList).not.toHaveBeenCalled()
  })
})

describe('ToituresPage — page pleine largeur `/ao/toitures`, sans `affaireId` (non-régression)', () => {
  it('liste les affaires, retombe sur la première et rend le sélecteur', async () => {
    render(<ToituresPage />)
    await waitFor(() => expect(mocks.affairesList).toHaveBeenCalled())
    await waitFor(() => expect(mocks.toituresList).toHaveBeenCalledWith({ appel_offre: 5 }))
    expect(await screen.findByText('Toiture atelier')).toBeInTheDocument()

    expect(screen.getByLabelText('Affaire')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'AO-2026-005' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'AO-2026-006' })).toBeInTheDocument()
  })

  it('affaire sans toiture (page pleine largeur) → même état vide explicite', async () => {
    mocks.toituresList.mockResolvedValue({ data: [] })
    render(<ToituresPage />)
    await waitFor(() => expect(mocks.affairesList).toHaveBeenCalled())
    expect(await screen.findByText('Aucune toiture relevée pour cette affaire.')).toBeInTheDocument()
  })
})

/* ============================================================================
   RÉPARATION 03/08/2026 — « Nouvelle toiture » : le bouton qui manquait.
   ----------------------------------------------------------------------------
   `NouvelleToitureWizard` existait, testé, importé NULLE PART : on pouvait
   lire des toitures sans jamais en créer une.

   Ce que ces tests protègent, dans l'ordre de gravité :
     1. `ToitureAO` n'a AUCUNE FK vers l'appel d'offres — une toiture se
        rattache à un BÂTIMENT. Un bâtiment inconnu de l'affaire est REFUSÉ
        avec son motif ; il ne retombe JAMAIS sur un autre ;
     2. le wizard émet un objet d'ATELIER dont la plupart des champs n'existent
        pas au modèle : seul ce que `ToitureAOSerializer` accepte est envoyé,
        JAMAIS `company`, JAMAIS `surface_m2` (recalculée par le serveur) ;
     3. après une création réussie, la liste se recharge.
   ========================================================================== */
describe('ToituresPage — création via NouvelleToitureWizard', () => {
  it('traduit le brouillon du wizard en champs du MODÈLE (ni company, ni surface)', async () => {
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')
    await waitFor(() => expect(mocks.batimentsList).toHaveBeenCalledWith({ appel_offre: 7 }))

    await creerViaWizard({ nom: 'Toiture Nord', batiment: 'B' })

    await waitFor(() => expect(mocks.toituresCreate).toHaveBeenCalled())
    const corps = mocks.toituresCreate.mock.calls[0][0]
    // Le bâtiment RÉSOLU (id), jamais le texte tapé, jamais l'id d'affaire.
    expect(corps.batiment).toBe(32)
    expect(corps.designation).toBe('Toiture Nord')
    expect(corps.contour_local_m).toEqual([])
    // Champs INTERDITS et champs d'atelier qui n'existent pas au modèle.
    expect(corps).not.toHaveProperty('company')
    expect(corps).not.toHaveProperty('surface_m2')
    expect(corps).not.toHaveProperty('appel_offre')
    for (const inconnu of ['editeur', 'portes', 'nom', 'statut', 'underlay', 'zones', 'obstacles']) {
      expect(corps).not.toHaveProperty(inconnu)
    }
  })

  it('recharge la liste après une création réussie', async () => {
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')
    const avant = mocks.toituresList.mock.calls.length

    await creerViaWizard({ batiment: 'A' })

    await waitFor(() => expect(mocks.toituresCreate).toHaveBeenCalled())
    await waitFor(() => expect(mocks.toituresList.mock.calls.length).toBeGreaterThan(avant))
  })

  it('bâtiment INCONNU de l’affaire → refus MOTIVÉ, aucune création, aucun repli silencieux', async () => {
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')

    await creerViaWizard({ batiment: 'Z' })

    expect(await screen.findByText(/Bâtiment « Z » inconnu de cette affaire/)).toBeInTheDocument()
    // Le motif nomme les bâtiments RÉELS de l'affaire — jamais un « erreur ».
    expect(screen.getByText(/A — Atelier, B — Magasin/)).toBeInTheDocument()
    expect(mocks.toituresCreate).not.toHaveBeenCalled()
  })

  it('bâtiment non renseigné + plusieurs bâtiments → refus MOTIVÉ (jamais « le premier »)', async () => {
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')

    await creerViaWizard({})

    expect(await screen.findByText(/Précisez le bâtiment/)).toBeInTheDocument()
    expect(mocks.toituresCreate).not.toHaveBeenCalled()
  })

  it('bâtiment non renseigné + UN SEUL bâtiment → création sur celui-là (aucune ambiguïté)', async () => {
    mocks.batimentsList.mockResolvedValue({ data: [BATIMENTS[0]] })
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')

    await creerViaWizard({})

    await waitFor(() => expect(mocks.toituresCreate).toHaveBeenCalled())
    expect(mocks.toituresCreate.mock.calls[0][0].batiment).toBe(31)
  })

  it('affaire SANS bâtiment → bouton désactivé et cause ÉCRITE (jamais grisé sans explication)', async () => {
    mocks.batimentsList.mockResolvedValue({ data: [] })
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Nouvelle toiture' })).toBeDisabled())
    expect(screen.getByText(/n’a aucun bâtiment/)).toBeInTheDocument()
  })

  it('refus du serveur → son motif est affiché, jamais un échec muet', async () => {
    mocks.toituresCreate.mockRejectedValue({
      response: { data: { batiment: ['Ce bâtiment n’existe pas dans votre société.'] } },
    })
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')

    await creerViaWizard({ batiment: 'A' })

    expect(await screen.findByText(/Ce bâtiment n’existe pas dans votre société./))
      .toBeInTheDocument()
  })
})

/* ============================================================================
   PACT166 — l'atelier de traçage, assemblé et ATTEIGNABLE.
   ----------------------------------------------------------------------------
   Six composants d'atelier étaient livrés et importés par personne : la page
   affichait à leur place un `EmptyState` disant que le canvas existait « dans
   une autre lane ». Ce que ces tests protègent :
     1. l'atelier est RÉELLEMENT monté sur écran large (canvas + tableau de
        géométrie + barre d'état), et l'ancien renvoi à une autre lane a
        disparu ;
     2. le contour du SERVEUR (`contour_local_m`, liste de `[x, y]`) est chargé
        dans la voie clavier — un atelier qui repartirait d'un contour vide
        effacerait le relevé au premier enregistrement ;
     3. « Enregistrer » écrit `contour_local_m` et RIEN d'autre : jamais
        `surface_m2` (recalculée par le serveur), jamais `company` ;
     4. l'historique est PARTAGÉ : un ajout fait au tableau s'annule depuis la
        barre d'actions de la coquille.
   ========================================================================== */

const TOITURE_TRACEE = {
  ...TOITURE,
  contour_local_m: [[0, 0], [10, 0], [10, 5], [0, 5]],
}

describe('ToituresPage — atelier de traçage (PACT166)', () => {
  it('monte l’atelier (canvas + géométrie + barre d’état) au lieu du renvoi à une autre lane', async () => {
    mocks.toituresList.mockResolvedValue({ data: [TOITURE_TRACEE] })
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')

    expect(await screen.findByLabelText(/Atelier de traçage — contour de la toiture/))
      .toBeInTheDocument()
    expect(document.querySelector('[data-ao-canvas]')).not.toBeNull()
    expect(document.querySelector('[data-tableau-geometrie]')).not.toBeNull()
    expect(screen.getByRole('toolbar', { name: "Outils de l'atelier" })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: "État de l'atelier" })).toBeInTheDocument()

    // Le message qui renvoyait le traçage à « sa propre lane » n'existe plus.
    expect(screen.queryByText(/livré par sa propre lane/)).toBeNull()
  })

  it('rend la légende de provenance avec le composant qui en est la source (ProvenanceBadge)', async () => {
    mocks.toituresList.mockResolvedValue({ data: [TOITURE_TRACEE] })
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')

    expect(document.querySelector('[data-ao-legende-provenance]')).not.toBeNull()
    for (const libelle of ['Mesuré', 'À confirmer', 'Plan / déduit', 'Deviné']) {
      expect(screen.getByText(libelle)).toBeInTheDocument()
    }
  })

  it('charge le contour du SERVEUR dans la voie clavier (jamais un contour vide)', async () => {
    mocks.toituresList.mockResolvedValue({ data: [TOITURE_TRACEE] })
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')

    // 4 sommets, 0 obstacle.
    expect(document.querySelector('[data-tableau-geometrie]').dataset.tableauGeometrie)
      .toBe('4:0')
    expect(screen.getByLabelText('x (m) — Sommet B')).toHaveValue('10')
    expect(screen.getByLabelText('y (m) — Sommet C')).toHaveValue('5')
  })

  it('« Enregistrer » écrit contour_local_m en [x, y] — jamais surface_m2, jamais company', async () => {
    mocks.toituresList.mockResolvedValue({ data: [TOITURE_TRACEE] })
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')

    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(mocks.toituresUpdate).toHaveBeenCalled())
    const [id, corps] = mocks.toituresUpdate.mock.calls[0]
    expect(id).toBe(41)
    expect(corps).toEqual({ contour_local_m: [[0, 0], [10, 0], [10, 5], [0, 5]] })
    expect(corps).not.toHaveProperty('surface_m2')
    expect(corps).not.toHaveProperty('company')
  })

  it('refus du serveur à l’enregistrement → son motif est AFFICHÉ, jamais un échec muet', async () => {
    mocks.toituresList.mockResolvedValue({ data: [TOITURE_TRACEE] })
    mocks.toituresUpdate.mockRejectedValue({
      response: { data: { contour_local_m: ['Le contour se croise (nœud papillon).'] } },
    })
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')

    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(await screen.findByText(/Le contour se croise/)).toBeInTheDocument()
  })

  it('historique PARTAGÉ : un sommet ajouté au tableau s’annule depuis la coquille', async () => {
    mocks.toituresList.mockResolvedValue({ data: [TOITURE_TRACEE] })
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')

    expect(screen.getByRole('button', { name: 'Annuler' })).toBeDisabled()

    await userEvent.click(screen.getByRole('button', { name: 'Ajouter un sommet' }))
    await waitFor(() => expect(
      document.querySelector('[data-tableau-geometrie]').dataset.tableauGeometrie,
    ).toBe('5:0'))
    expect(screen.getByRole('button', { name: 'Annuler' })).toBeEnabled()

    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(
      document.querySelector('[data-tableau-geometrie]').dataset.tableauGeometrie,
    ).toBe('4:0'))
  })

  it('aucune toiture → état vide EXPLICITE, jamais un atelier vide qui a l’air prêt', async () => {
    mocks.toituresList.mockResolvedValue({ data: [] })
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Aucune toiture relevée pour cette affaire.')

    expect(document.querySelector('[data-ao-canvas]')).toBeNull()
    expect(screen.getByText(/Relevez une première toiture/)).toBeInTheDocument()
  })

  it('plusieurs toitures → un sélecteur ouvre l’autre toiture dans l’atelier', async () => {
    const AUTRE = { ...TOITURE, id: 42, designation: 'Toiture bureaux', contour_local_m: [] }
    mocks.toituresList.mockResolvedValue({ data: [TOITURE_TRACEE, AUTRE] })
    render(<ToituresPage affaireId={7} />)
    // Deux toitures : « Toiture atelier » apparaît en carte ET en option du
    // sélecteur — on attend donc le sélecteur lui-même, jamais un texte ambigu.
    await screen.findByLabelText('Toiture')

    expect(document.querySelector('[data-tableau-geometrie]').dataset.tableauGeometrie)
      .toBe('4:0')

    await userEvent.selectOptions(screen.getByLabelText('Toiture'), '42')

    await waitFor(() => expect(
      document.querySelector('[data-tableau-geometrie]').dataset.tableauGeometrie,
    ).toBe('0:0'))
  })
})

/* ============================================================================
   PACT167 — la BOÎTE À OUTILS de l'atelier (calage, tracé, obstacles, zones,
   cotes, import).
   ----------------------------------------------------------------------------
   Seize fichiers d'outils de relevé étaient livrés et importés par personne.
   Ce que ces tests protègent :
     1. chaque famille d'outils est RÉELLEMENT montée dans un onglet de la boîte
        à outils, pas seulement importée ;
     2. le tracé écrit dans le MÊME contour que les deux autres voies — un outil
        qui garderait son tracé pour lui serait un atelier à deux vérités ;
     3. les refus sont MOTIVÉS et LISIBLES (« prête à publier » n'existe pas au
        serveur) — jamais un bouton qui ne fait rien sans le dire.

   Deux outils sont volontairement chargés en `lazy()` (`UnderlayPdf` fabrique
   un worker pdf.js au chargement du module, `RepriseCarte` tire l'alias
   `@roofpro` absent de la config Vitest) : l'onglet « Import » n'est donc pas
   ouvert ici — un test qui l'ouvrirait paierait ces deux modules.
   ========================================================================== */

const TOITURE_VIERGE = { ...TOITURE, contour_local_m: [] }

async function ouvrirAtelier(toiture) {
  mocks.toituresList.mockResolvedValue({ data: [toiture] })
  render(<ToituresPage affaireId={7} />)
  await screen.findByText('Toiture atelier')
}

describe('ToituresPage — boîte à outils de l’atelier (PACT167)', () => {
  it('onglet « Calage » : fond de calque image + calibration deux points', async () => {
    await ouvrirAtelier(TOITURE_VIERGE)

    await userEvent.click(screen.getByRole('tab', { name: 'Calage' }))

    expect(screen.getByLabelText('Plan à caler (image ou PDF)')).toBeInTheDocument()
    expect(document.querySelector('[data-ao-underlay="image"]')).not.toBeNull()
    expect(document.querySelector('[data-ao-calibration]')).not.toBeNull()
    // Sans fond de calque, l'échelle n'est pas « inconnue » : elle est SANS OBJET.
    expect(screen.getByText('Tracé direct')).toBeInTheDocument()
  })

  it('onglet « Tracé » : ce que l’outil trace devient LE contour de l’atelier', async () => {
    await ouvrirAtelier(TOITURE_VIERGE)

    await userEvent.click(screen.getByRole('tab', { name: 'Tracé' }))
    expect(document.querySelector('[data-ao-outil-trace]')).not.toBeNull()

    await userEvent.type(screen.getByLabelText('Longueur (m)'), '10')
    await userEvent.click(document.querySelector('[data-ao-trace-direction="0"]'))

    // Retour à la voie clavier : le contour tracé y est, sur la MÊME géométrie.
    await userEvent.click(screen.getByRole('tab', { name: 'Géométrie' }))
    await waitFor(() => expect(
      document.querySelector('[data-tableau-geometrie]').dataset.tableauGeometrie,
    ).toBe('2:0'))
    expect(screen.getByLabelText('x (m) — Sommet B')).toHaveValue('10')
  })

  it('onglet « Obstacles » : planche de pose + liste synchronisée', async () => {
    await ouvrirAtelier(TOITURE_TRACEE)

    await userEvent.click(screen.getByRole('tab', { name: 'Obstacles' }))

    expect(document.querySelector('[data-ao-outils-obstacles]')).not.toBeNull()
    expect(document.querySelector('[data-ao-inspecteur]')).not.toBeNull()
    expect(document.querySelector('[data-ao-obstacles]')).not.toBeNull()
  })

  it('un obstacle saisi au TABLEAU apparaît dans la liste d’obstacles (une seule vérité)', async () => {
    await ouvrirAtelier(TOITURE_TRACEE)

    await userEvent.click(screen.getByRole('button', { name: 'Ajouter un obstacle' }))
    await waitFor(() => expect(
      document.querySelector('[data-tableau-geometrie]').dataset.tableauGeometrie,
    ).toBe('4:1'))

    await userEvent.click(screen.getByRole('tab', { name: 'Obstacles' }))
    await waitFor(() => expect(
      document.querySelector('[data-ao-obstacles]').dataset.aoObstacles,
    ).toBe('1'))
  })

  it('« prête à publier » → REFUS motivé et lisible (le serveur ne modélise pas cet état)', async () => {
    await ouvrirAtelier(TOITURE_TRACEE)

    await userEvent.click(screen.getByRole('tab', { name: 'Obstacles' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Marquer la toiture prête à publier' }),
    )

    const note = await screen.findByText(/ne porte AUCUN état/)
    expect(note).toBeInTheDocument()
    expect(document.querySelector('[data-ao-atelier-note]')).not.toBeNull()
  })

  it('onglets « Zones » et « Cotes » : les outils sont montés, pas seulement importés', async () => {
    await ouvrirAtelier(TOITURE_TRACEE)

    await userEvent.click(screen.getByRole('tab', { name: 'Zones' }))
    expect(document.querySelector('[data-ao-zones]')).not.toBeNull()

    await userEvent.click(screen.getByRole('tab', { name: 'Cotes' }))
    expect(document.querySelector('[data-ao-chaines]')).not.toBeNull()
    expect(document.querySelector('[data-ao-fermetures]')).not.toBeNull()
    expect(document.querySelector('[data-ao-points-lever]')).not.toBeNull()
  })
})
