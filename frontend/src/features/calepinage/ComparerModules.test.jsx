import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'

/* ============================================================================
   ACAL600 — « Comparer d'autres modules » : cocher 2 à 3 modules du stock, créer
   les variantes (ACAL594) et ouvrir le comparatif. Charges utiles = exemples
   committés (PACT13) : `calepinage_modules_disponibles.json` et
   `calepinage_variantes_par_module.json`.
   ========================================================================== */

const mocks = vi.hoisted(() => ({ modulesDisponibles: vi.fn(), variantesParModule: vi.fn() }))
vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      modulesDisponibles: mocks.modulesDisponibles,
      variantesParModule: mocks.variantesParModule,
    },
  },
}))

import ComparerModules from './ComparerModules'
import { exempleContrat } from '../../test/fixtures/contractSamples'

const DISPONIBLES = exempleContrat('calepinage', 'calepinage_modules_disponibles')
const VIDE = exempleContrat('calepinage', 'calepinage_modules_disponibles', 'exemple_vide')
const CREEES = exempleContrat('calepinage', 'calepinage_variantes_par_module')
const REFUS = exempleContrat('calepinage', 'calepinage_variantes_par_module', 'exemple_refus')

const COMPLET = DISPONIBLES.modules[0].module
// Trois fiches complètes : le module des pans + deux autres (cotes du contrat).
const TROIS = {
  ...DISPONIBLES,
  modules: [
    DISPONIBLES.modules[0],
    { ...DISPONIBLES.modules[0], module: { ...COMPLET, id: 'produit-9001', libelle: 'Module B 430 Wc' } },
    { ...DISPONIBLES.modules[0], module: { ...COMPLET, id: 'produit-9002', libelle: 'Module C 600 Wc' } },
    DISPONIBLES.modules[1],
  ],
}

function Lieu() {
  const lieu = useLocation()
  return <p data-testid="lieu">{`${lieu.pathname}${lieu.search}`}</p>
}

const rendre = () => render(
  <MemoryRouter initialEntries={['/calepinage/5']}>
    <Routes>
      <Route path="*" element={<><ComparerModules calepinageId={5} /><Lieu /></>} />
    </Routes>
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.modulesDisponibles.mockResolvedValue({ data: TROIS })
  mocks.variantesParModule.mockResolvedValue({ status: 201, data: CREEES })
})

describe('ComparerModules (ACAL600)', () => {
  it('2 modules cochés ⇒ un appel variantesParModule, puis navigation', async () => {
    rendre()
    fireEvent.click(await screen.findByTestId('cal-comparer-modules'))
    fireEvent.click(await screen.findByTestId('cal-comparer-module-produit-9001'))
    fireEvent.click(screen.getByTestId('cal-comparer-module-produit-9002'))
    fireEvent.click(screen.getByTestId('cal-comparer-modules-valider'))
    await waitFor(() => expect(mocks.variantesParModule)
      .toHaveBeenCalledWith(5, ['produit-9001', 'produit-9002']))
    expect(mocks.variantesParModule).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(screen.getByTestId('lieu'))
      .toHaveTextContent('/calepinage/5?onglet=variantes'))
  })

  it('une fiche incomplète est listée, non cochable, avec son motif ; au plus trois', async () => {
    rendre()
    fireEvent.click(await screen.findByTestId('cal-comparer-modules'))
    const incomplet = DISPONIBLES.modules[1]
    expect(await screen.findByTestId(`cal-comparer-module-${incomplet.module.id}`)).toBeDisabled()
    expect(screen.getByText(incomplet.motif)).toBeInTheDocument()
    for (const id of [COMPLET.id, 'produit-9001', 'produit-9002']) {
      fireEvent.click(screen.getByTestId(`cal-comparer-module-${id}`))
    }
    expect(screen.getByTestId('cal-comparer-modules-valider')).toBeEnabled()
  })

  it('D-ACAL-71 : « En stock » et les cotes seulement quand le stock est servi ; rien d’inventé sinon', async () => {
    mocks.modulesDisponibles.mockResolvedValue({ data: {
      ...TROIS,
      modules: TROIS.modules.map((e, i) => ({ ...e, en_stock: i === 0 ? true : null })), // 1 servi en stock, les autres non servis
    } })
    rendre()
    fireEvent.click(await screen.findByTestId('cal-comparer-modules'))
    await screen.findByTestId(`cal-comparer-module-${COMPLET.id}`)
    expect(screen.getAllByText(/^En stock · 580 Wc/)).toHaveLength(1)
    expect(screen.getAllByText(/^580 Wc/)).toHaveLength(2) // non servi : les cotes seules, jamais « 0 » ni « rupture »
    expect(screen.queryByText(/rupture/i)).toBeNull()
  })

  it('refus du serveur affiché sous le module', async () => {
    const libelle = 'Module B 430 Wc'
    mocks.variantesParModule.mockRejectedValue({
      response: { status: 409, data: { modules: `« ${libelle} » : ${REFUS.modules.split(' : ')[1]}` } },
    })
    rendre()
    fireEvent.click(await screen.findByTestId('cal-comparer-modules'))
    fireEvent.click(await screen.findByTestId('cal-comparer-module-produit-9001'))
    fireEvent.click(screen.getByTestId('cal-comparer-module-produit-9002'))
    fireEvent.click(screen.getByTestId('cal-comparer-modules-valider'))
    const refus = await screen.findByTestId('cal-comparer-refus-produit-9001')
    expect(refus).toHaveTextContent(libelle)
    expect(screen.getByTestId('lieu')).toHaveTextContent('/calepinage/5')
    expect(screen.getByTestId('lieu')).not.toHaveTextContent('onglet=variantes')
  })

  it('sans module complet ⇒ motif servi, pas de bouton', async () => {
    mocks.modulesDisponibles.mockResolvedValue({ data: VIDE })
    rendre()
    const motif = await screen.findByTestId('cal-comparer-modules-absent')
    expect(motif).toHaveTextContent(VIDE.motif_liste_vide)
    expect(screen.queryByTestId('cal-comparer-modules')).toBeNull()
  })
})
