import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   ERR-QAH-CALEPINAGE-LISTE-SANS-RATTACHEMENT (qa-explorer, 2026-09-28).
   ----------------------------------------------------------------------------
   La liste affichait « Sans rattachement » / « Sans responsable » pour une
   étude qui a POURTANT un lead et un responsable, parce que le sérialiseur
   de liste ne rendait que l'identifiant opaque du lead (`lead: 77`) et
   `responsable: null` quand personne n'était SAISI en propre sur le
   calepinage (le détail, lui, sait retomber sur le responsable du lead —
   CALX406). Ce fichier prouve l'écran CONSOMME la forme désormais publiée
   par le sérialiseur (`CalepinageSerializer.to_representation`, CALX407) :
   `lead: {id, nom, ville}` et un `responsable`/`responsable_nom` qui portent
   le repli quand le calepinage n'a personne d'assigné en propre.
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  getLeads: vi.fn(),
  searchClients: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/calepinageApi', () => ({
  default: { calepinages: { list: mocks.list } },
}))

vi.mock('../../api/crmApi', () => ({
  default: { getLeads: mocks.getLeads, searchClients: mocks.searchClients },
}))

import CalepinageList from './CalepinageList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const rendre = () => render(
  <MemoryRouter><ThemeProvider><CalepinageList /></ThemeProvider></MemoryRouter>,
)

/** La forme RÉELLE que rend désormais la liste (CALX407) : `lead` imbriqué,
 * `responsable` en repli sur le propriétaire du lead (identifiant + nom
 * séparé — jamais un objet, contrairement au détail). */
const LIGNE_AVEC_RATTACHEMENT = {
  id: 77,
  reference: 'CAL-2609-0077',
  nom: 'MON-ETUDE',
  statut: 'en_cours',
  statut_libelle: 'En cours',
  lead: { id: 77, nom: 'Toiture Anfa', ville: 'Casablanca' },
  client: null,
  responsable: 3,
  responsable_nom: 'demo_admin',
  image: { url: null },
  layout_stale: null,
  layout_nb_panneaux: null,
  modifie_le: '2026-09-28T10:00:00Z',
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({
    data: { count: 1, next: null, previous: null,
           results: [LIGNE_AVEC_RATTACHEMENT] },
  })
  mocks.getLeads.mockResolvedValue({ data: [] })
  mocks.searchClients.mockResolvedValue({ data: [] })
})

describe('ERR-QAH-CALEPINAGE-LISTE-SANS-RATTACHEMENT', () => {
  it('affiche le NOM du lead rattaché, jamais « Sans rattachement »', async () => {
    rendre()
    const vignette = await screen.findByTestId(
      `cal-vignette-${LIGNE_AVEC_RATTACHEMENT.id}`)
    expect(vignette).toHaveTextContent('Toiture Anfa')
    expect(vignette).not.toHaveTextContent('Sans rattachement')
  })

  it('affiche le NOM du responsable (repli sur le lead), jamais « Sans '
    + 'responsable »', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    const responsable = await screen.findByTestId(
      `cal-responsable-${LIGNE_AVEC_RATTACHEMENT.id}`)
    expect(responsable).toHaveTextContent('demo_admin')
    expect(responsable).not.toHaveTextContent('Sans responsable')
  })

  it('affiche le NOM saisi à la création, jamais un titre générique '
    + '(ERR-QAH-CALEPINAGE-NOM-CREATION-PERDU)', async () => {
    rendre()
    const vignette = await screen.findByTestId(
      `cal-vignette-${LIGNE_AVEC_RATTACHEMENT.id}`)
    expect(vignette).toHaveTextContent('MON-ETUDE')
  })
})
