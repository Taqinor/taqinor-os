import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CALX346 — le différentiel de versions, prouvé SUR LE CONTRAT (PACT13).
   ----------------------------------------------------------------------------
   Les réponses du serveur sont les exemples committés
   `apps/calepinage/contract_samples/calepinage_versions_diff.json` (CALX333),
   le même fichier que le test backend `test_calx345_diff_versions.py`
   affirme. Les invariants durs du « Done » :
     1. onglet monté (couvert par `atelier/onglets.js`, vérifié en-dehors) ;
     2. deux versions identiques affichent un état vide EXPLICITE ;
     3. sans choix de droite, le différentiel se lit contre l'ÉTAT COURANT
        (`id: null`) — jamais une seconde route.
   ========================================================================== */

const mocks = vi.hoisted(() => ({ versions: vi.fn(), versionsDiff: vi.fn() }))

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      versions: mocks.versions,
      versionsDiff: mocks.versionsDiff,
    },
  },
}))

const { default: DiffVersions } = await import('./DiffVersions')
const { exempleContrat } = await import('../../../test/fixtures/contractSamples')

const DIFF_EXEMPLE = exempleContrat('calepinage', 'calepinage_versions_diff')
const DIFF_IDENTIQUES = exempleContrat('calepinage', 'calepinage_versions_diff', 'exemple_identiques')
const DIFF_CONTRE_COURANT = exempleContrat('calepinage', 'calepinage_versions_diff', 'exemple_contre_courant')

const V1 = { id: 12, libelle: 'Version du 19/09 — avant reprise', cree_le: '2026-09-19T09:00:00Z' }
const V2 = { id: 13, libelle: 'Ré-enregistrement à l’identique', cree_le: '2026-09-19T09:05:00Z' }
const V3 = { id: 15, libelle: 'Restauration de la version #9', cree_le: '2026-09-19T11:30:00Z' }

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => cleanup())

const rendre = (props = {}) => render(
  <MemoryRouter><DiffVersions calepinageId={5} {...props} /></MemoryRouter>,
)

describe('DiffVersions — état initial (CALX346)', () => {
  it('sans version, un état vide explicite — AUCUN appel au différentiel', async () => {
    mocks.versions.mockResolvedValue({ data: [] })
    rendre()
    expect(await screen.findByText('Aucune version à comparer')).toBeInTheDocument()
    expect(mocks.versionsDiff).not.toHaveBeenCalled()
  })

  it('compare par défaut contre l’ÉTAT COURANT (aucun `contre` envoyé)', async () => {
    mocks.versions.mockResolvedValue({ data: [V3, V2, V1] })
    mocks.versionsDiff.mockResolvedValue({ data: DIFF_CONTRE_COURANT })
    rendre()

    await waitFor(() => expect(mocks.versionsDiff).toHaveBeenCalledWith(5, String(V2.id), undefined))
    expect(await screen.findByTestId('cal-diff-versions-tableau')).toBeInTheDocument()
    expect(screen.getByTestId('cal-diff-versions-ligne-modules')).toHaveTextContent('12')
    expect(screen.getByTestId('cal-diff-versions-ligne-modules')).toHaveTextContent('14')
  })
})

describe('DiffVersions — choisir deux versions (CALX346)', () => {
  it('affiche le tableau champ/avant/après du contrat, un champ absent des deux côtés est OMIS', async () => {
    mocks.versions.mockResolvedValue({ data: [V3, V2, V1] })
    mocks.versionsDiff.mockResolvedValue({ data: DIFF_EXEMPLE })
    const utilisateur = userEvent.setup()
    rendre()

    await waitFor(() => expect(mocks.versionsDiff).toHaveBeenCalled())
    await utilisateur.selectOptions(await screen.findByTestId('cal-diff-versions-gauche'), String(V1.id))
    await utilisateur.selectOptions(screen.getByTestId('cal-diff-versions-droite'), String(V3.id))

    await waitFor(() => expect(mocks.versionsDiff).toHaveBeenCalledWith(5, String(V1.id), String(V3.id)))
    const tableau = await screen.findByTestId('cal-diff-versions-tableau')
    expect(tableau).toHaveTextContent('Nombre de modules')
    expect(tableau).toHaveTextContent('Puissance crête (kWc)')
    // `version_moteur` est ABSENT des deux côtés dans l'exemple : jamais affiché.
    expect(screen.queryByTestId('cal-diff-versions-ligne-version_moteur')).toBeNull()
    // Un champ présent d'un seul côté (inclinaison du pan B) porte `null` — jamais `0`.
    const ligne = screen.getByTestId('cal-diff-versions-ligne-pan:PAN-B:inclinaison_deg')
    expect(ligne).toHaveTextContent('15')
    expect(ligne).toHaveTextContent('—')
  })

  it('deux versions identiques affichent un état vide EXPLICITE, jamais un tableau vide', async () => {
    mocks.versions.mockResolvedValue({ data: [V2, V1] })
    mocks.versionsDiff.mockResolvedValue({ data: DIFF_IDENTIQUES })
    const utilisateur = userEvent.setup()
    rendre()

    await waitFor(() => expect(mocks.versionsDiff).toHaveBeenCalled())
    await utilisateur.selectOptions(await screen.findByTestId('cal-diff-versions-gauche'), String(V1.id))
    await utilisateur.selectOptions(screen.getByTestId('cal-diff-versions-droite'), String(V2.id))

    expect(await screen.findByText('Aucun écart')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-diff-versions-tableau')).toBeNull()
  })

  it('un échec du calcul affiche un motif, jamais un plantage silencieux', async () => {
    mocks.versions.mockResolvedValue({ data: [V2, V1] })
    mocks.versionsDiff.mockRejectedValue(new Error('boom'))
    rendre()
    expect(await screen.findByTestId('cal-diff-versions-erreur')).toHaveTextContent('différentiel')
  })
})

describe('DiffVersions — la restauration reste dans PanneauVersions (CALX346)', () => {
  it('un lien renvoie vers l’onglet Versions, AUCUN bouton d’écriture ici', async () => {
    mocks.versions.mockResolvedValue({ data: [V2, V1] })
    mocks.versionsDiff.mockResolvedValue({ data: DIFF_IDENTIQUES })
    rendre()
    const lien = await screen.findByTestId('cal-diff-versions-lien-versions')
    expect(lien).toHaveAttribute('href', '/calepinage/5?onglet=versions')
    // Le mot « restaurer » n'apparaît que dans la phrase de renvoi ci-dessus —
    // aucun BOUTON de restauration n'existe sur cet onglet, LECTURE PURE.
    expect(screen.queryByRole('button', { name: /restaurer/i })).not.toBeInTheDocument()
  })
})
