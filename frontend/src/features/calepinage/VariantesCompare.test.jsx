import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

/* ============================================================================
   CAL42 — le comparatif des variantes, prouvé SUR LE CONTRAT.
   ----------------------------------------------------------------------------
   AUCUN MOCK ÉCRIT À LA MAIN (PACT13) : la charge utile est l'exemple committé
   `apps/calepinage/contract_samples/variantes_comparer.json`, le même fichier
   que `scripts/check_api_shapes.py` compare au dictionnaire RÉELLEMENT renvoyé
   par la vue. Un PAYLOAD maison serait une DEUXIÈME source de vérité — c'est
   exactement ce qui a laissé l'écran AO Tableau de bord partir en production
   le 03/08/2026 avec zéro clé sur six concordante, les deux suites vertes.

   Les deux invariants durs :
     1. les ÉCARTS viennent du serveur — aucun calcul d'écran ;
     2. retenir une variante rend l'ANCIENNE non retenue à l'écran, parce que le
        serveur le dit au rechargement.
   ========================================================================== */

const mocks = vi.hoisted(() => ({ comparer: vi.fn(), retenirVariante: vi.fn() }))

vi.mock('../../api/calepinageApi', () => ({
  default: { calepinages: { comparer: mocks.comparer, retenirVariante: mocks.retenirVariante } },
}))

import VariantesCompare from './VariantesCompare'
import { exempleContrat } from '../../test/fixtures/contractSamples'

const CONTRAT = exempleContrat('calepinage', 'variantes_comparer')
const CONTRAT_UNE_SEULE = exempleContrat('calepinage', 'variantes_comparer', 'exemple_vide')

const RETENUE = CONTRAT.lignes.find((l) => l.est_retenue)
const AUTRE = CONTRAT.lignes.find((l) => !l.est_retenue && l.simulee)
const NON_SIMULEE = CONTRAT.lignes.find((l) => !l.simulee)

const rendre = () => render(
  <MemoryRouter initialEntries={['/calepinage/1/variantes']}>
    <Routes>
      <Route path="/calepinage/:id/variantes" element={<VariantesCompare />} />
    </Routes>
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.comparer.mockResolvedValue({ data: CONTRAT })
  mocks.retenirVariante.mockResolvedValue({ data: {} })
})

describe('VariantesCompare (CAL42)', () => {
  it('le contrat committé porte bien les trois cas que l’écran doit rendre', () => {
    // Garde de la fixture elle-même : si le contrat change de forme, ce test
    // dit POURQUOI les suivants cassent, au lieu d'échouer sur un symptôme.
    expect(RETENUE).toBeTruthy()
    expect(AUTRE).toBeTruthy()
    expect(NON_SIMULEE).toBeTruthy()
    expect(RETENUE.ecart_modules).toBe(0)
    expect(NON_SIMULEE.ecart_p50_kwh).toBeNull()
  })

  it('charge le comparatif du calepinage de l’URL', async () => {
    rendre()
    await waitFor(() => expect(mocks.comparer).toHaveBeenCalledWith('1'))
  })

  it('rend UNE COLONNE PAR VARIANTE, avec son libellé', async () => {
    rendre()
    const tableau = await screen.findByTestId('cal-tableau-variantes')
    for (const ligne of CONTRAT.lignes) {
      expect(within(tableau).getAllByText(ligne.nom).length).toBeGreaterThan(0)
    }
  })

  it('modules, kWc, orientation et marges viennent des clés du contrat', async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    expect(screen.getByTestId(`cal-modules-${RETENUE.id}`))
      .toHaveTextContent(String(RETENUE.total_modules))
    expect(screen.getByTestId(`cal-kwc-${RETENUE.id}`))
      .toHaveTextContent(String(RETENUE.kwc).replace('.', ','))
    expect(screen.getByTestId(`cal-orientation-${RETENUE.id}`))
      .toHaveTextContent(RETENUE.orientation.orientation_module)
    expect(screen.getByTestId(`cal-marges-${RETENUE.id}`))
      .toHaveTextContent(RETENUE.marges.rangee_critique)
  })

  it('LES ÉCARTS SONT CEUX DU SERVEUR — jamais recalculés à l’écran', async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    // La retenue porte un écart MESURÉ, nul par construction : « 0 », pas « — ».
    expect(screen.getByTestId(`cal-ecart_modules-${RETENUE.id}`)).toHaveTextContent('0')
    // L'autre variante porte l'écart SIGNÉ du contrat (−2 modules ici).
    const signe = AUTRE.ecart_modules < 0 ? '−' : '+'
    expect(screen.getByTestId(`cal-ecart_modules-${AUTRE.id}`))
      .toHaveTextContent(`${signe}${Math.abs(AUTRE.ecart_modules)}`)
  })

  it('une variante NON SIMULÉE est dite « non simulée » — jamais « 0 kWh »', async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    expect(screen.getByTestId(`cal-p50-${NON_SIMULEE.id}`)).toHaveTextContent('non simulée')
    expect(screen.getByTestId(`cal-pr-${NON_SIMULEE.id}`)).toHaveTextContent('non simulée')
    expect(screen.getByTestId(`cal-p50-${NON_SIMULEE.id}`)).not.toHaveTextContent('0')
  })

  it('une marge NON MESURÉE (`null`) ne s’affiche pas comme « au ras »', async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    expect(RETENUE.marges.bande_min_cm).toBeNull()
    // La bande absente ne produit aucun « 0 cm » : seule la marge mesurée sort.
    expect(screen.getByTestId(`cal-marges-${RETENUE.id}`)).not.toHaveTextContent('bande')
  })

  it('« Retenir » appelle le serveur puis RECHARGE — l’ancienne retenue perd son badge', async () => {
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    expect(screen.getByTestId(`cal-retenue-${RETENUE.id}`)).toBeInTheDocument()

    // Le serveur bascule : au rechargement, c'est AUTRE qui est retenue.
    const apresBascule = {
      ...CONTRAT,
      retenue_id: AUTRE.id,
      lignes: CONTRAT.lignes.map((l) => ({ ...l, est_retenue: l.id === AUTRE.id })),
    }
    mocks.comparer.mockResolvedValue({ data: apresBascule })

    const cellule = screen.getByTestId(`cal-ecart_modules-${AUTRE.id}`).closest('table')
    const boutons = within(cellule).getAllByRole('button', { name: 'Retenir' })
    fireEvent.click(boutons[0])

    await waitFor(() => expect(mocks.retenirVariante).toHaveBeenCalledWith('1', AUTRE.id))
    await waitFor(() => expect(screen.getByTestId(`cal-retenue-${AUTRE.id}`)).toBeInTheDocument())
    expect(screen.queryByTestId(`cal-retenue-${RETENUE.id}`)).not.toBeInTheDocument()
  })

  it('un refus de « Retenir » s’affiche tel quel, et la retenue ne bouge pas', async () => {
    mocks.retenirVariante.mockRejectedValue({
      response: { data: { detail: 'Calepinage verrouillé.' } },
    })
    rendre()
    await screen.findByTestId('cal-tableau-variantes')
    fireEvent.click(screen.getAllByRole('button', { name: 'Retenir' })[0])
    expect(await screen.findByRole('alert')).toHaveTextContent('Calepinage verrouillé.')
    expect(screen.getByTestId(`cal-retenue-${RETENUE.id}`)).toBeInTheDocument()
  })

  it('la vue CÔTE À CÔTE compare deux variantes, écarts serveur inclus', async () => {
    rendre()
    const bloc = await screen.findByTestId('cal-cote-a-cote')
    expect(within(bloc).getByLabelText('Variante de gauche')).toBeInTheDocument()
    expect(within(bloc).getByLabelText('Variante de droite')).toBeInTheDocument()
    expect(within(bloc).getAllByText('Écart P50 / retenue').length).toBe(2)
    expect(within(bloc).getAllByText('Plan').length).toBe(2)
  })

  it('l’OMBRAGE affiché est le poste de perte publié, AVEC sa source', async () => {
    const shading = RETENUE.production.pertes_dominantes.find((p) => p.poste === 'shading')
    expect(shading, 'le contrat ne publie plus de poste `shading`').toBeTruthy()
    rendre()
    const bloc = await screen.findByTestId('cal-cote-a-cote')
    expect(within(bloc).getByText(new RegExp(shading.source))).toBeInTheDocument()
  })

  it('un calepinage à UNE SEULE variante : rien à comparer, et AUCUN écart nul affiché', async () => {
    mocks.comparer.mockResolvedValue({ data: CONTRAT_UNE_SEULE })
    rendre()
    expect(await screen.findByTestId('cal-cote-a-cote-vide')).toBeInTheDocument()
    const seule = CONTRAT_UNE_SEULE.lignes[0]
    expect(seule.ecart_modules).toBeNull()
    // `null` = il n'y a rien à quoi se comparer. Ce n'est PAS un écart nul.
    expect(screen.getByTestId(`cal-ecart_modules-${seule.id}`)).toHaveTextContent('—')
  })

  it('une erreur de chargement s’affiche telle quelle', async () => {
    mocks.comparer.mockRejectedValue({ response: { data: { detail: 'Accès refusé.' } } })
    rendre()
    expect(await screen.findByRole('alert')).toHaveTextContent('Accès refusé.')
  })
})
