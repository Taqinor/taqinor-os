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
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const rendre = () => render(
  <MemoryRouter><ThemeProvider><CalepinageList /></ThemeProvider></MemoryRouter>,
)

/** ACAL197 — la forme RÉELLE que rend la liste, lue sur l'échantillon de
 * contrat committé (`calepinage_liste.json`, D06-T01) : plus de fixture
 * tapée à la main. Un lead seul (sans client) : l'étude a POURTANT un
 * rattachement, le nom du lead. */
const EXEMPLE = exempleContrat('calepinage', 'calepinage_liste').results[0]
const LIGNE_AVEC_RATTACHEMENT = { ...EXEMPLE, client: null, client_apercu: null }

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
    expect(vignette).toHaveTextContent(LIGNE_AVEC_RATTACHEMENT.lead.nom)
    expect(vignette).not.toHaveTextContent('Sans rattachement')
  })

  it('affiche le NOM du responsable (repli sur le lead), jamais « Sans '
    + 'responsable »', async () => {
    rendre()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    const responsable = await screen.findByTestId(
      `cal-responsable-${LIGNE_AVEC_RATTACHEMENT.id}`)
    expect(responsable).toHaveTextContent(LIGNE_AVEC_RATTACHEMENT.responsable_nom)
    expect(responsable).not.toHaveTextContent('Sans responsable')
  })

  it('affiche le NOM saisi à la création, jamais un titre générique '
    + '(ERR-QAH-CALEPINAGE-NOM-CREATION-PERDU)', async () => {
    rendre()
    const vignette = await screen.findByTestId(
      `cal-vignette-${LIGNE_AVEC_RATTACHEMENT.id}`)
    expect(vignette).toHaveTextContent(LIGNE_AVEC_RATTACHEMENT.nom)
  })
})
