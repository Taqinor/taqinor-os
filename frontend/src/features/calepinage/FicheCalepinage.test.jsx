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

beforeEach(() => { vi.clearAllMocks() })
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
          // CALX26 — la fiche les appelle au CLIC ; déclarées ici pour que le
          // module monté par ce test ait la même surface que le vrai client.
          archiver: vi.fn(), restaurerCorbeille: vi.fn(),
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
