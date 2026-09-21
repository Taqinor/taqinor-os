import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat, exempleContrat } from '../../test/fixtures/contractSamples'

// CALX26 — les deux portes réelles (`views/archivage.py`) sont mockées : ce
// test prouve le GESTE de l'écran, jamais le serveur (qui a ses propres tests,
// `tests/test_cal208_archiver.py`).
vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      archiver: vi.fn(),
      restaurerCorbeille: vi.fn(),
      // CALX33 — la fabrique CRUD partagée (`api/resource.js`) : PATCH sur
      // `/calepinage/calepinages/<id>/`.
      update: vi.fn(),
      // CALX42 — le drapeau « modèle » : sa LECTURE (CAL246) et ses deux
      // portes d'écriture (`views/bibliotheque.py`).
      modeles: vi.fn(),
      marquerModele: vi.fn(),
      demarquerModele: vi.fn(),
      // CALX35 — la porte HTTP du service de copie CAL14.
      dupliquer: vi.fn(),
    },
  },
}))

/* ============================================================================
   CAL17 (moitié écran) — L'ÉCRAN LIT TOUT L'AGRÉGAT, ou il rougit.
   ----------------------------------------------------------------------------
   La moitié SERVEUR est déjà là (`views/calepinages.py::detail_calepinage`,
   `forme_serveur: complete`, vérifiée par `scripts/check_api_shapes.py`). Rien
   ne garantissait en face que l'écran en lise une seule clé — et un agrégat que
   personne ne lit se périme en silence, exactement comme les neuf chemins AO
   appelés sous aucune route (03/08/2026).

   CE TEST PARCOURT LE CONTRAT. Il ne cite aucune clé à la main : il lit
   `Object.keys(exemple)` du fichier COMMITTÉ et exige un rendu pour chacune. Le
   jour où le serveur publie une vingt-deuxième clé, ce test la réclame.

   IL VÉRIFIE AUSSI LA DISCIPLINE DU NULL, celle que le contrat impose : sur
   `exemple_vide`, une grandeur non mesurée vaut `null` — l'écran rend « — » et
   JAMAIS un `0`, qui ferait lire « aucune version » là où rien n'a encore été
   enregistré.
   ========================================================================== */

// CALX35 — `MemoryRouter` et `Link` restent RÉELS (les tests de liens du
// contrat les exigent) ; seule la navigation impérative est observée.
const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

import calepinageApi from '../../api/calepinageApi'
import FicheCalepinage from './FicheCalepinage'

const DOC = documentContrat('calepinage', 'calepinage_detail')
const DETAIL = exempleContrat('calepinage', 'calepinage_detail')
const DETAIL_VIDE = exempleContrat('calepinage', 'calepinage_detail',
  'exemple_vide')

// `statut` et `statut_libelle` sont DEUX clés du contrat, rendues en deux
// champs distincts (le libellé lisible et le code technique).
const CLES = Object.keys(DOC.exemple)

const rendre = (detail) => render(
  <MemoryRouter><FicheCalepinage detail={detail} /></MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  // CALX42 — par défaut, la fiche lit la liste des modèles au montage : ce
  // calepinage-ci n'en est pas un.
  calepinageApi.calepinages.modeles.mockResolvedValue({ data: [] })
})
afterEach(() => { cleanup() })

describe('FicheCalepinage — l’agrégat CAL17 est lu EN ENTIER', () => {
  it('rend une clé du contrat, et le contrat en publie bien vingt-trois', () => {
    // Garde de dérive : si le contrat grossit, la liste ci-dessous grossit avec
    // lui et le test suivant exigera le rendu de la nouvelle clé.
    expect(CLES.length).toBe(23)
  })

  it.each(CLES)('affiche la clé publiée « %s »', (cle) => {
    rendre(DETAIL)
    expect(screen.getByTestId(`cal-fiche-${cle}`)).toBeInTheDocument()
  })

  it('affiche les valeurs SERVIES, telles quelles', () => {
    rendre(DETAIL)

    expect(screen.getByTestId('cal-fiche-reference'))
      .toHaveTextContent(DETAIL.reference)
    expect(screen.getByTestId('cal-fiche-nom')).toHaveTextContent(DETAIL.nom)
    expect(screen.getByTestId('cal-fiche-statut_libelle'))
      .toHaveTextContent(DETAIL.statut_libelle)
    expect(screen.getByTestId('cal-fiche-cree_par'))
      .toHaveTextContent(DETAIL.cree_par.nom_complet)
    expect(screen.getByTestId('cal-fiche-versions'))
      .toHaveTextContent(String(DETAIL.versions.total))
    expect(screen.getByTestId('cal-fiche-variantes'))
      .toHaveTextContent(`retenue #${DETAIL.variantes.retenue_id}`)
    expect(screen.getByTestId('cal-fiche-layout_present'))
      .toHaveTextContent('Oui')
    expect(screen.getByTestId('cal-fiche-contexte_geographique'))
      .toHaveTextContent(DETAIL.contexte_geographique.ville)
  })

  it('les rattachements sont des LIENS vers les écrans qui les portent', () => {
    rendre(DETAIL)

    expect(screen.getByRole('link', { name: DETAIL.lead.nom }))
      .toHaveAttribute('href', `/crm/leads/${DETAIL.lead.id}`)
    expect(screen.getByRole('link', { name: DETAIL.devis.reference }))
      .toHaveAttribute('href', `/ventes/devis/${DETAIL.devis.id}/design`)
    expect(screen.getByRole('link', { name: 'Voir l’aperçu' }))
      .toHaveAttribute('href', DETAIL.image.url)
  })

  it('calepinage NEUF : toutes les clés restent rendues, et « — » jamais « 0 »', () => {
    rendre(DETAIL_VIDE)

    for (const cle of CLES) {
      expect(screen.getByTestId(`cal-fiche-${cle}`)).toBeInTheDocument()
    }
    // Le contrat sert `null` (non mesuré) : l'écran ne publie PAS un zéro.
    expect(DETAIL_VIDE.versions.total).toBeNull()
    expect(screen.getByTestId('cal-fiche-versions')).toHaveTextContent('—')
    expect(screen.getByTestId('cal-fiche-versions')).not.toHaveTextContent('0')
    expect(screen.getByTestId('cal-fiche-variantes')).toHaveTextContent('—')
    expect(screen.getByTestId('cal-fiche-layout_present')).toHaveTextContent('Non')
    // Ni devis, ni client, ni aperçu : aucun lien mort n'est fabriqué.
    expect(screen.getByTestId('cal-fiche-devis')).toHaveTextContent('—')
    expect(screen.getByTestId('cal-fiche-client')).toHaveTextContent('—')
    expect(screen.queryByRole('link', { name: 'Voir l’aperçu' })).toBeNull()
    // Les permissions de l'exemple vide : modifier + supprimer, PAS retenir.
    expect(screen.getByTestId('cal-fiche-permissions'))
      .toHaveTextContent('modifier, supprimer')
  })

  it('agrégat pas encore lu : rien — jamais une fiche de tirets', () => {
    rendre(null)
    expect(screen.queryByTestId('cal-fiche-calepinage')).toBeNull()
  })
})

/* ============================================================================
   CALX26 — ARCHIVER (confirmation en deux temps) / RESTAURER.
   ----------------------------------------------------------------------------
   Les deux portes existent depuis CAL208 et n'avaient AUCUN consommateur.
   Ce qui est prouvé ici : le premier clic ne fait que demander confirmation,
   le second appelle la porte ; une fois archivé, le seul bouton d'écriture
   restant est « Restaurer » ; un refus du serveur s'affiche SOUS le geste
   fautif, en le nommant.
   ========================================================================== */

const SANS_DROIT = {
  ...DETAIL,
  permissions: { ...DETAIL.permissions, peut_modifier: false },
}

describe('CALX26 — archivage et restauration depuis la fiche', () => {
  it('premier clic : demande confirmation, n’archive RIEN', async () => {
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-archiver'))

    expect(screen.getByTestId('cal-fiche-archiver-confirmation'))
      .toBeInTheDocument()
    expect(screen.getByTestId('cal-fiche-archiver')).toHaveTextContent(
      'Confirmer l’archivage')
    expect(calepinageApi.calepinages.archiver).not.toHaveBeenCalled()
  })

  it('second clic : archive, et le bandeau coupe les gestes d’écriture', async () => {
    calepinageApi.calepinages.archiver.mockResolvedValue({
      data: { calepinage: DETAIL.id, archive: true },
    })
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-archiver'))
    await userEvent.click(screen.getByTestId('cal-fiche-archiver'))

    await waitFor(() => expect(calepinageApi.calepinages.archiver)
      .toHaveBeenCalledWith(DETAIL.id))
    expect(await screen.findByTestId('cal-fiche-bandeau-archive'))
      .toBeInTheDocument()
    // Le SEUL bouton d'écriture qui reste.
    expect(screen.queryByTestId('cal-fiche-archiver')).toBeNull()
    expect(screen.getByTestId('cal-fiche-restaurer')).toBeInTheDocument()
  })

  it('« Annuler » remet le bouton dans son état initial', async () => {
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-archiver'))
    await userEvent.click(screen.getByTestId('cal-fiche-archiver-annuler'))

    expect(screen.getByTestId('cal-fiche-archiver')).toHaveTextContent('Archiver')
    expect(screen.queryByTestId('cal-fiche-archiver-confirmation')).toBeNull()
    expect(calepinageApi.calepinages.archiver).not.toHaveBeenCalled()
  })

  it('archiver puis restaurer revient à l’état initial', async () => {
    calepinageApi.calepinages.archiver.mockResolvedValue({
      data: { calepinage: DETAIL.id, archive: true },
    })
    calepinageApi.calepinages.restaurerCorbeille.mockResolvedValue({
      data: { calepinage: DETAIL.id, archive: false },
    })
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-archiver'))
    await userEvent.click(screen.getByTestId('cal-fiche-archiver'))
    await userEvent.click(await screen.findByTestId('cal-fiche-restaurer'))

    await waitFor(() => expect(calepinageApi.calepinages.restaurerCorbeille)
      .toHaveBeenCalledWith(DETAIL.id))
    expect(await screen.findByTestId('cal-fiche-archiver'))
      .toHaveTextContent('Archiver')
    expect(screen.queryByTestId('cal-fiche-bandeau-archive')).toBeNull()
  })

  it('refus serveur : le motif s’affiche SOUS le geste, qui est nommé', async () => {
    const MOTIF = "Impossible d'archiver un calepinage non enregistré."
    calepinageApi.calepinages.archiver.mockRejectedValue({
      response: { status: 400, data: { calepinage: MOTIF } },
    })
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-archiver'))
    await userEvent.click(screen.getByTestId('cal-fiche-archiver'))

    const bloc = await screen.findByTestId('cal-fiche-archivage-erreur')
    // Le motif du SERVEUR, mot pour mot — jamais un « non enregistré »
    // générique fabriqué par l'écran.
    expect(bloc).toHaveTextContent(MOTIF)
    expect(bloc).toHaveTextContent('Archiver')
    expect(screen.queryByTestId('cal-fiche-bandeau-archive')).toBeNull()
  })

  it('sans le droit de gérer : AUCUN bouton d’écriture n’est proposé', () => {
    rendre(SANS_DROIT)
    expect(screen.queryByTestId('cal-fiche-actions')).toBeNull()
    expect(screen.queryByTestId('cal-fiche-archiver')).toBeNull()
    // La fiche reste entièrement lisible : « lecture seule » n'est pas « rien ».
    expect(screen.getByTestId('cal-fiche-calepinage')).toBeInTheDocument()
  })
})

/* ============================================================================
   CALX33 — RENOMMER UN CALEPINAGE APRÈS SA CRÉATION.
   ----------------------------------------------------------------------------
   `calepinages.update` existait sans appelant : le nom posé à la création
   était définitif. Ce qui est prouvé : sans le droit de gérer, aucun bouton
   d'édition ; un titre vide est refusé AVANT envoi ; un refus serveur pointe
   le champ (sous lui, et dans un bandeau qui le nomme).
   ========================================================================== */

describe('CALX33 — le nom de la fiche est éditable sur place', () => {
  it('sans le droit de gérer : aucun bouton d’édition', () => {
    rendre(SANS_DROIT)
    expect(screen.queryByTestId('cal-fiche-nom-editer')).toBeNull()
    // La valeur reste LUE — lecture seule n'est pas « rien à voir ».
    expect(screen.getByTestId('cal-fiche-nom')).toHaveTextContent(DETAIL.nom)
  })

  it('crayon → champ → enregistrer : PATCH sur `titre`, nom mis à jour', async () => {
    calepinageApi.calepinages.update.mockResolvedValue({ data: {} })
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-nom-editer'))
    const champ = screen.getByTestId('cal-fiche-nom-champ')
    await userEvent.clear(champ)
    await userEvent.type(champ, 'Toiture atelier nord')
    await userEvent.click(screen.getByTestId('cal-fiche-nom-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.update)
      .toHaveBeenCalledWith(DETAIL.id, { titre: 'Toiture atelier nord' }))
    expect(await screen.findByTestId('cal-fiche-nom'))
      .toHaveTextContent('Toiture atelier nord')
    expect(screen.queryByTestId('cal-fiche-nom-champ')).toBeNull()
  })

  it('un titre VIDE est refusé AVANT tout envoi', async () => {
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-nom-editer'))
    await userEvent.clear(screen.getByTestId('cal-fiche-nom-champ'))
    await userEvent.click(screen.getByTestId('cal-fiche-nom-enregistrer'))

    expect(calepinageApi.calepinages.update).not.toHaveBeenCalled()
    expect(screen.getByTestId('cal-fiche-nom-erreur'))
      .toHaveTextContent('ne peut pas être vide')
    // Le champ reste ouvert : on corrige, on ne recommence pas.
    expect(screen.getByTestId('cal-fiche-nom-champ')).toBeInTheDocument()
  })

  it('refus serveur : le motif est SOUS le champ et le bandeau le NOMME', async () => {
    const MOTIF = 'Ce nom est déjà porté par un autre calepinage.'
    calepinageApi.calepinages.update.mockRejectedValue({
      response: { status: 400, data: { titre: [MOTIF] } },
    })
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-nom-editer'))
    await userEvent.clear(screen.getByTestId('cal-fiche-nom-champ'))
    await userEvent.type(screen.getByTestId('cal-fiche-nom-champ'), 'Doublon')
    await userEvent.click(screen.getByTestId('cal-fiche-nom-enregistrer'))

    expect(await screen.findByTestId('cal-fiche-nom-erreur'))
      .toHaveTextContent(MOTIF)
    const bandeau = screen.getByTestId('cal-fiche-bandeau-nom')
    expect(bandeau).toHaveTextContent('Nom')
    expect(bandeau).toHaveTextContent(MOTIF)
  })

  it('« Annuler » ferme le champ sans rien envoyer', async () => {
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-nom-editer'))
    await userEvent.click(screen.getByTestId('cal-fiche-nom-annuler'))

    expect(screen.queryByTestId('cal-fiche-nom-champ')).toBeNull()
    expect(calepinageApi.calepinages.update).not.toHaveBeenCalled()
    expect(screen.getByTestId('cal-fiche-nom')).toHaveTextContent(DETAIL.nom)
  })

  it('archivé : le renommage n’est plus proposé (le bandeau coupe l’écriture)', async () => {
    calepinageApi.calepinages.archiver.mockResolvedValue({
      data: { calepinage: DETAIL.id, archive: true },
    })
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-archiver'))
    await userEvent.click(screen.getByTestId('cal-fiche-archiver'))

    expect(await screen.findByTestId('cal-fiche-bandeau-archive'))
      .toBeInTheDocument()
    expect(screen.queryByTestId('cal-fiche-nom-editer')).toBeNull()
  })
})

/* ============================================================================
   CALX42 — LE DRAPEAU « MODÈLE », BASCULÉ DEPUIS LA FICHE.
   ----------------------------------------------------------------------------
   `services/modeles.py` portait `marquer_modele`/`demarquer_modele` depuis
   CAL199 sans aucune route. Ce qui est prouvé ici : la bascule LIT l'état à
   la seule source qui existe (`GET calepinages/modeles/`), n'en suppose
   jamais un, et disparaît sans le droit de gérer.
   ========================================================================== */
describe('CALX42 — marquer / démarquer un calepinage comme modèle', () => {
  it('lit le drapeau à la liste des modèles, puis propose la bascule', async () => {
    calepinageApi.calepinages.modeles.mockResolvedValue({
      data: [{ id: DETAIL.id, titre: DETAIL.nom }],
    })
    rendre(DETAIL)

    expect(await screen.findByTestId('cal-fiche-modele'))
      .toHaveTextContent('Retirer des modèles')
  })

  it('marque le calepinage et bascule le libellé', async () => {
    calepinageApi.calepinages.marquerModele.mockResolvedValue({
      data: { calepinage: DETAIL.id, modele: true },
    })
    rendre(DETAIL)

    const bouton = await screen.findByTestId('cal-fiche-modele')
    expect(bouton).toHaveTextContent('Marquer comme modèle')
    await userEvent.click(bouton)

    await waitFor(() => expect(calepinageApi.calepinages.marquerModele)
      .toHaveBeenCalledWith(DETAIL.id))
    expect(await screen.findByTestId('cal-fiche-modele'))
      .toHaveTextContent('Retirer des modèles')
  })

  it('démarque par l’AUTRE porte, jamais par la même', async () => {
    calepinageApi.calepinages.modeles.mockResolvedValue({
      data: [{ id: DETAIL.id }],
    })
    calepinageApi.calepinages.demarquerModele.mockResolvedValue({
      data: { calepinage: DETAIL.id, modele: false },
    })
    rendre(DETAIL)

    await userEvent.click(await screen.findByTestId('cal-fiche-modele'))

    await waitFor(() => expect(calepinageApi.calepinages.demarquerModele)
      .toHaveBeenCalledWith(DETAIL.id))
    expect(calepinageApi.calepinages.marquerModele).not.toHaveBeenCalled()
  })

  it('drapeau NON LU : aucune bascule n’est proposée sur un état supposé', async () => {
    calepinageApi.calepinages.modeles.mockRejectedValue(new Error('réseau'))
    rendre(DETAIL)

    await waitFor(() => expect(calepinageApi.calepinages.modeles)
      .toHaveBeenCalled())
    expect(screen.queryByTestId('cal-fiche-modele')).toBeNull()
  })

  it('refus serveur : le motif s’affiche, sous le geste NOMMÉ', async () => {
    const MOTIF = 'Impossible de marquer un calepinage non enregistré comme modèle.'
    calepinageApi.calepinages.marquerModele.mockRejectedValue({
      response: { status: 400, data: { calepinage: MOTIF } },
    })
    rendre(DETAIL)

    await userEvent.click(await screen.findByTestId('cal-fiche-modele'))

    const bloc = await screen.findByTestId('cal-fiche-modele-erreur')
    expect(bloc).toHaveTextContent(MOTIF)
    expect(bloc).toHaveTextContent('Modèle')
  })

  it('sans le droit de gérer : aucune bascule', async () => {
    rendre(SANS_DROIT)
    await waitFor(() => expect(calepinageApi.calepinages.modeles)
      .toHaveBeenCalled())
    expect(screen.queryByTestId('cal-fiche-modele')).toBeNull()
  })
})

/* ============================================================================
   CALX35 — DUPLIQUER : LA CONFIRMATION ÉNUMÈRE AVANT DE COPIER.
   ----------------------------------------------------------------------------
   `services/variantes.py::dupliquer` existe depuis CAL14 sans aucune route.
   Ce qui est prouvé : la boîte de confirmation ÉNUMÈRE ce que la copie laisse
   derrière elle (versions, variantes, lien devis, fil d'activité, pièces
   produites) AVANT de dupliquer ; le drapeau `avec_variantes` part explicite,
   à `true` par défaut (comportement d'aujourd'hui) ; le bouton ouvre le
   NOUVEAU calepinage.
   ========================================================================== */
describe('CALX35 — dupliquer un calepinage depuis sa fiche', () => {
  it('la confirmation ÉNUMÈRE ce que la copie laisse derrière elle', async () => {
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-dupliquer'))

    const boite = screen.getByTestId('cal-fiche-dupliquer-confirmation')
    for (const terme of ['versions', 'variantes', 'devis', 'activité',
      'pièces produites']) {
      expect(boite).toHaveTextContent(terme)
    }
    // Rien n'a été dupliqué par le seul fait d'ouvrir la boîte.
    expect(calepinageApi.calepinages.dupliquer).not.toHaveBeenCalled()
  })

  it('confirme : `avec_variantes` part EXPLICITE, à true par défaut', async () => {
    calepinageApi.calepinages.dupliquer.mockResolvedValue({
      data: { calepinage: 77, reference: 'CAL-2609-0077' },
    })
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-dupliquer'))
    expect(screen.getByTestId('cal-fiche-dupliquer-variantes')).toBeChecked()
    await userEvent.click(screen.getByTestId('cal-fiche-dupliquer-confirmer'))

    await waitFor(() => expect(calepinageApi.calepinages.dupliquer)
      .toHaveBeenCalledWith(DETAIL.id, { avec_variantes: true }))
    // Le bouton OUVRE la copie.
    expect(navigateMock).toHaveBeenCalledWith('/calepinage/77')
  })

  it('case décochée : les variantes figurent dans ce qui reste derrière', async () => {
    calepinageApi.calepinages.dupliquer.mockResolvedValue({
      data: { calepinage: 78 },
    })
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-dupliquer'))
    await userEvent.click(screen.getByTestId('cal-fiche-dupliquer-variantes'))

    const boite = screen.getByTestId('cal-fiche-dupliquer-confirmation')
    expect(boite).toHaveTextContent('les variantes ;')
    await userEvent.click(screen.getByTestId('cal-fiche-dupliquer-confirmer'))

    await waitFor(() => expect(calepinageApi.calepinages.dupliquer)
      .toHaveBeenCalledWith(DETAIL.id, { avec_variantes: false }))
  })

  it('« Annuler » referme sans rien dupliquer', async () => {
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-dupliquer'))
    await userEvent.click(screen.getByTestId('cal-fiche-dupliquer-annuler'))

    expect(screen.queryByTestId('cal-fiche-dupliquer-confirmation')).toBeNull()
    expect(calepinageApi.calepinages.dupliquer).not.toHaveBeenCalled()
  })

  it('refus serveur : le motif s’affiche, le geste est NOMMÉ, rien n’est ouvert', async () => {
    const MOTIF = "Le calepinage à dupliquer n'est pas enregistré."
    calepinageApi.calepinages.dupliquer.mockRejectedValue({
      response: { status: 400, data: { calepinage: MOTIF } },
    })
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-dupliquer'))
    await userEvent.click(screen.getByTestId('cal-fiche-dupliquer-confirmer'))

    const bloc = await screen.findByTestId('cal-fiche-dupliquer-erreur')
    expect(bloc).toHaveTextContent(MOTIF)
    expect(bloc).toHaveTextContent('Dupliquer')
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('archivé : la duplication n’est plus proposée', async () => {
    calepinageApi.calepinages.archiver.mockResolvedValue({
      data: { calepinage: DETAIL.id, archive: true },
    })
    rendre(DETAIL)

    await userEvent.click(screen.getByTestId('cal-fiche-archiver'))
    await userEvent.click(screen.getByTestId('cal-fiche-archiver'))

    expect(await screen.findByTestId('cal-fiche-bandeau-archive'))
      .toBeInTheDocument()
    expect(screen.queryByTestId('cal-fiche-dupliquer')).toBeNull()
  })
})

/* L'écran RÉEL la monte : sans montage, la fiche serait un composant de plus
   écrit pour personne (l'oubli du 03/08/2026). */
describe('AtelierPanneaux monte la fiche sur UNE seule lecture de l’agrégat', () => {
  it('lit l’agrégat une fois et le partage avec la fiche et le bouton devis', async () => {
    vi.resetModules()
    const get = vi.fn().mockResolvedValue({ data: DETAIL })
    vi.doMock('../../api/calepinageApi', () => ({
      default: {
        calepinages: {
          get, genererDevis: vi.fn(), syncDevis: vi.fn(),
          // CALX26/CALX42 — la fiche les appelle au CLIC (et lit `modeles`
          // au montage) ; déclarées ici pour que le module monté par ce test
          // ait la même surface que le vrai client.
          archiver: vi.fn(), restaurerCorbeille: vi.fn(),
          modeles: vi.fn().mockResolvedValue({ data: [] }),
          marquerModele: vi.fn(), demarquerModele: vi.fn(),
          dupliquer: vi.fn(),
        },
        // CAL70 — PanneauAllees (monté par AtelierPanneaux) lit les réglages
        // société au montage.
        parametres: { get: vi.fn().mockResolvedValue({ data: { degagements: {} } }) },
        moteur: { calculer: vi.fn() },
      },
    }))
    vi.doMock('../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))
    const { default: AtelierPanneaux } = await import('./AtelierPanneaux')
    const CTX = exempleContrat('calepinage', 'calepinage_design_context')

    render(
      <MemoryRouter>
        <AtelierPanneaux calepinageId={DETAIL.id} contexte={CTX} />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('cal-fiche-calepinage')).toBeInTheDocument()
    // UNE lecture, pas deux : la fiche et le bouton devis partagent la vérité.
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))
    expect(screen.getByTestId('cal-bouton-devis')).toBeInTheDocument()
    vi.doUnmock('../../api/calepinageApi')
  })
})
