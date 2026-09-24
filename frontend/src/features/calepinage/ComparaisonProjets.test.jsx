import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'

/* ============================================================================
   CALX342 — la comparaison de calepinages, prouvée SUR LE CONTRAT.
   ----------------------------------------------------------------------------
   AUCUN MOCK ÉCRIT À LA MAIN (PACT13) : la charge utile est l'exemple committé
   `apps/calepinage/contract_samples/calepinage_comparaison_projets.json`
   (CALX331) — le même fichier que le test backend RECALCULE ligne pour ligne
   (`tests/test_calx341_comparaison_projets.py`). Les invariants durs :
     1. une colonne NON SIMULÉE affiche le MOTIF du serveur et « — », jamais 0 ;
     2. la sélection voyage dans l'URL (`?ids=`) et c'est ELLE qui part au
        serveur ;
     3. les identifiants ignorés sont listés, jamais tus.
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  comparerProjets: vi.fn(), comparatifXlsx: vi.fn(), telechargerBlob: vi.fn(),
  list: vi.fn(), getLeads: vi.fn(), searchClients: vi.fn(),
}))

vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      comparerProjets: mocks.comparerProjets,
      comparatifXlsx: mocks.comparatifXlsx,
      list: mocks.list,
    },
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: { getLeads: mocks.getLeads, searchClients: mocks.searchClients },
}))

vi.mock('./exportImage', () => ({ telechargerBlob: mocks.telechargerBlob }))

import ComparaisonProjets from './ComparaisonProjets'
import CalepinageList from './CalepinageList'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const CONTRAT = exempleContrat('calepinage', 'calepinage_comparaison_projets')
const CONTRAT_VIDE = exempleContrat('calepinage', 'calepinage_comparaison_projets', 'exemple_vide')

const SIMULE = CONTRAT.lignes.find((l) => l.simule)
const NON_SIMULES = CONTRAT.lignes.filter((l) => !l.simule)

function Adresse() {
  const location = useLocation()
  return <div data-testid="adresse">{`${location.pathname}${location.search}`}</div>
}

const rendre = (url = '/calepinage/comparaison?ids=1,2,3,9') => render(
  <MemoryRouter initialEntries={[url]}>
    <Routes>
      <Route path="/calepinage/comparaison" element={<><ComparaisonProjets /><Adresse /></>} />
      <Route path="*" element={<Adresse />} />
    </Routes>
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.comparerProjets.mockResolvedValue({ data: CONTRAT })
  mocks.comparatifXlsx.mockResolvedValue({ data: new Blob(['xlsx']) })
})

describe('ComparaisonProjets (CALX342)', () => {
  it('le contrat committé porte un calepinage simulé ET des non simulés', () => {
    expect(SIMULE).toBeTruthy()
    expect(NON_SIMULES.length).toBeGreaterThan(0)
    for (const ligne of NON_SIMULES) {
      expect(ligne.p50_kwh).toBeNull()
      expect(ligne.motif).toBeTruthy()
    }
  })

  it('envoie au serveur les identifiants de l’URL, dans l’ordre', async () => {
    rendre()
    await waitFor(() => expect(mocks.comparerProjets).toHaveBeenCalledWith([1, 2, 3, 9]))
  })

  it('rend une colonne par calepinage et une ligne par grandeur du contrat', async () => {
    rendre()
    const grille = await screen.findByRole('grid', { name: 'Comparaison des calepinages' })
    for (const ligne of CONTRAT.lignes) {
      expect(within(grille).getByText(ligne.titre)).toBeInTheDocument()
    }
    for (const colonne of CONTRAT.colonnes) {
      expect(within(grille).getByText((texte) => texte.startsWith(colonne.libelle)))
        .toBeInTheDocument()
    }
  })

  it('une colonne non simulée affiche le motif du serveur et « — », jamais 0', async () => {
    rendre()
    const grille = await screen.findByRole('grid')
    for (const ligne of NON_SIMULES) {
      expect(within(grille).getByTestId(`cal-comparaison-motif-${ligne.id}`))
        .toHaveTextContent(ligne.motif)
      const cellule = within(grille).getByTestId(`cal-comparaison-p50_kwh-${ligne.id}`)
      expect(cellule).toHaveTextContent('—')
      expect(cellule.textContent).not.toMatch(/\b0\b/)
    }
    expect(within(grille).getByTestId(`cal-comparaison-p50_kwh-${SIMULE.id}`).textContent)
      .not.toBe('—')
  })

  it('liste les identifiants ignorés avec le motif du serveur', async () => {
    rendre()
    const bloc = await screen.findByTestId('cal-comparaison-refus')
    for (const refus of CONTRAT.refus) {
      expect(bloc).toHaveTextContent(`Calepinage #${refus.id}`)
      expect(bloc).toHaveTextContent(refus.motif)
    }
  })

  it('retirer un calepinage réécrit la sélection de l’URL', async () => {
    rendre()
    const grille = await screen.findByRole('grid')
    fireEvent.click(within(grille).getByRole('button', {
      name: `Retirer ${NON_SIMULES[0].titre} de la comparaison`,
    }))
    await waitFor(() => expect(screen.getByTestId('adresse').textContent)
      .not.toContain(`${NON_SIMULES[0].id},`))
  })

  it('le classeur est demandé au serveur pour les calepinages comparés', async () => {
    rendre()
    await screen.findByRole('grid')
    fireEvent.click(screen.getByTestId('cal-comparaison-classeur'))
    const ids = CONTRAT.lignes.map((l) => l.id)
    await waitFor(() => expect(mocks.comparatifXlsx).toHaveBeenCalledWith(ids[0], ids.slice(1)))
    await waitFor(() => expect(mocks.telechargerBlob).toHaveBeenCalled())
  })

  it('un refus du classeur affiche la phrase du serveur', async () => {
    const refus = CONTRAT_VIDE.refus[0].motif
    mocks.comparatifXlsx.mockRejectedValue({
      response: { data: new Blob([JSON.stringify({ ids: refus })]) },
    })
    rendre()
    await screen.findByRole('grid')
    fireEvent.click(screen.getByTestId('cal-comparaison-classeur'))
    expect(await screen.findByTestId('cal-comparaison-motif-classeur')).toHaveTextContent(refus)
  })

  it('sans identifiant, aucun appel et un renvoi vers la liste', async () => {
    rendre('/calepinage/comparaison')
    expect(await screen.findByText('Aucun calepinage à comparer')).toBeInTheDocument()
    expect(mocks.comparerProjets).not.toHaveBeenCalled()
    expect(screen.getByRole('link', { name: 'Choisir dans la liste' }))
      .toHaveAttribute('href', '/calepinage?comparer=1')
  })

  it('tous les identifiants refusés : la forme du contrat est gardée et le dit', async () => {
    mocks.comparerProjets.mockResolvedValue({ data: CONTRAT_VIDE })
    rendre('/calepinage/comparaison?ids=9')
    expect(await screen.findByText(/Aucun des calepinages demandés/)).toBeInTheDocument()
    expect(screen.queryByRole('grid')).toBeNull()
  })
})

/* ── La porte : le mode « Comparer » de la LISTE ────────────────────────────
   La route n'est utile que si on l'atteint : la liste coche de 2 à 5
   calepinages et ouvre `/calepinage/comparaison?ids=…`. Les lignes de la liste
   viennent du contrat `calepinage_detail.json` (deux calepinages distincts). */
const DETAIL = exempleContrat('calepinage', 'calepinage_detail')
const DETAIL_VIDE = exempleContrat('calepinage', 'calepinage_detail', 'exemple_vide')

const rendreListe = (url = '/calepinage') => render(
  <MemoryRouter initialEntries={[url]}>
    <ThemeProvider>
      <Routes>
        <Route path="/calepinage" element={<CalepinageList />} />
        <Route path="*" element={<Adresse />} />
      </Routes>
    </ThemeProvider>
  </MemoryRouter>,
)

describe('CalepinageList — mode « Comparer » (CALX342)', () => {
  beforeEach(() => {
    mocks.list.mockResolvedValue({
      data: { count: 2, next: null, previous: null, results: [DETAIL, DETAIL_VIDE] },
    })
    mocks.getLeads.mockResolvedValue({ data: [] })
    mocks.searchClients.mockResolvedValue({ data: [] })
  })

  it('sans le mode, aucune case à cocher n’est posée sur les vignettes', async () => {
    rendreListe()
    await screen.findByTestId(`cal-vignette-${DETAIL.id}`)
    expect(screen.queryByTestId(`cal-comparer-${DETAIL.id}`)).toBeNull()
  })

  it('cocher deux calepinages ouvre la comparaison avec leurs identifiants', async () => {
    rendreListe()
    await screen.findByTestId(`cal-vignette-${DETAIL.id}`)
    fireEvent.click(screen.getByTestId('cal-mode-comparer'))
    expect(screen.getByTestId('cal-ouvrir-comparaison')).toBeDisabled()
    fireEvent.click(screen.getByTestId(`cal-comparer-${DETAIL.id}`))
    fireEvent.click(screen.getByTestId(`cal-comparer-${DETAIL_VIDE.id}`))
    fireEvent.click(screen.getByTestId('cal-ouvrir-comparaison'))
    await waitFor(() => expect(screen.getByTestId('adresse')).toHaveTextContent(
      `/calepinage/comparaison?ids=${DETAIL.id},${DETAIL_VIDE.id}`))
  })

  it('`?comparer=1` ouvre directement le mode (lien « Choisir dans la liste »)', async () => {
    rendreListe('/calepinage?comparer=1')
    expect(await screen.findByTestId('cal-barre-comparaison')).toBeInTheDocument()
  })
})
