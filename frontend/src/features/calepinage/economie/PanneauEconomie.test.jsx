/* CALX289 — l'onglet « Économie » de l'atelier, en lecture seule.

   Ce qui est prouvé ici : le devis lu vient de l'agrégat de détail du
   calepinage (`contract_samples/calepinage_detail.json`, clé `devis`) et le
   bloc économie vient EXACTEMENT du contrat partagé
   `apps/ventes/contract_samples/ventes_economie.json` (CALX280/288) —
   `exemple` ET `exemple_vide`, jamais un payload tapé à la main (PACT10). Un
   calepinage sans devis lié n'affiche AUCUN nombre, seulement le motif ; un
   indicateur `null` s'affiche en clair (« non publié : … »), jamais un zéro
   ni un tiret muet ; et ce panneau LECTURE SEULE ne rend aucun champ de
   saisie. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { get: vi.fn() } },
}))
vi.mock('../../../api/ventesApi', () => ({
  default: { getEconomieDevis: vi.fn() },
}))

import calepinageApi from '../../../api/calepinageApi'
import ventesApi from '../../../api/ventesApi'
import PanneauEconomie from './PanneauEconomie'

const rendre = () => render(
  <MemoryRouter><PanneauEconomie calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PanneauEconomie (CALX289)', () => {
  it("sans devis lié : rend le motif du serveur et aucun nombre — n'appelle même pas ventesApi", async () => {
    calepinageApi.calepinages.get
      .mockResolvedValue(reponseContrat('calepinage', 'calepinage_detail', 'exemple_vide'))
    ventesApi.getEconomieDevis.mockResolvedValue({ data: {} })

    rendre()

    const panneau = await screen.findByTestId('calx289-panneau')
    within(panneau).getByTestId('calx289-sans-devis')

    // Aucun bloc économie, aucun indicateur, aucun chiffre — jamais un tiret.
    expect(within(panneau).queryByTestId('calx289-bloc')).not.toBeInTheDocument()
    expect(within(panneau).queryByTestId('calx289-indicateurs')).not.toBeInTheDocument()
    expect(ventesApi.getEconomieDevis).not.toHaveBeenCalled()
  })

  it("avec devis lié et l'exemple committé : les cinq indicateurs et les deux omissions sont EXACTEMENT ceux du contrat", async () => {
    const detail = exempleContrat('calepinage', 'calepinage_detail', 'exemple')
    calepinageApi.calepinages.get.mockResolvedValue({ data: detail })
    ventesApi.getEconomieDevis
      .mockResolvedValue(reponseContrat('ventes', 'ventes_economie', 'exemple'))

    rendre()

    const bloc = await screen.findByTestId('calx289-bloc')

    // Le devis lu est bien celui rattaché au calepinage (`devis.id` du détail).
    expect(ventesApi.getEconomieDevis).toHaveBeenCalledWith(detail.devis.id)

    const indicateurs = within(bloc).getByTestId('calx289-indicateurs')
    // `formatMAD`/`formatNumber` insèrent une espace fine insécable dans les
    // milliers : le `.` du regex l'attrape quel que soit le caractère exact
    // (piège déjà banqué par PanneauBatterie.test.jsx).
    expect(within(indicateurs).getByText(/20.000 MAD/)).toBeInTheDocument() // van_mad
    expect(within(indicateurs).getByText(/3,46/)).toBeInTheDocument() // tri_pct
    expect(within(indicateurs).getByText(/1,00 MAD\/kWh/)).toBeInTheDocument() // lcoe_mad_kwh
    expect(within(indicateurs).getAllByText(/9 ans/).length).toBeGreaterThanOrEqual(2) // retour_ans + retour_actualise_ans

    // Les DEUX omissions de l'exemple, visibles en clair, et RIEN d'autre.
    const omissions = within(bloc).getByTestId('calx289-omissions')
    const lignes = within(omissions).getAllByTestId('calx289-omission')
    expect(lignes).toHaveLength(2)
    expect(lignes[0]).toHaveTextContent(
      'non publié : aucune charge annuelle saisie — aucune n\'est portée au flux',
    )
    expect(lignes[1]).toHaveTextContent(
      'non publié : aucun remplacement d\'équipement saisi (retirer, remplacer ou prolonger) — aucun n\'est porté au flux',
    )

    // Le flux importé du contrat est rendu tel quel (11 lignes, année 0 à 10).
    const flux = within(bloc).getByTestId('calx289-flux')
    expect(within(flux).getAllByTestId('calx289-flux-ligne')).toHaveLength(11)

    // LECTURE SEULE : aucun champ de saisie nulle part dans le panneau.
    expect(screen.queryAllByRole('textbox')).toHaveLength(0)
  })

  it("avec devis lié mais l'exemple_vide (aucun taux/horizon saisi par la société) : chaque indicateur affiche son propre motif, jamais un zéro", async () => {
    const detail = exempleContrat('calepinage', 'calepinage_detail', 'exemple')
    calepinageApi.calepinages.get.mockResolvedValue({ data: detail })
    ventesApi.getEconomieDevis
      .mockResolvedValue(reponseContrat('ventes', 'ventes_economie', 'exemple_vide'))

    rendre()

    const bloc = await screen.findByTestId('calx289-bloc')
    const indicateurs = within(bloc).getByTestId('calx289-indicateurs')

    // Les cinq indicateurs sont TOUS omis dans exemple_vide : chacun porte son
    // propre motif nommé (le serveur préfixe déjà « non publié : » pour ceux-
    // là — jamais doublé ici), jamais une valeur numérique inventée.
    const vanMad = within(indicateurs).getByTestId('calx289-indicateur-van_mad')
    expect(vanMad).toHaveTextContent(
      'non publié : horizon_ans non saisi ; taux non fourni : taux_actualisation_pct, indexation_pct, degradation_pct',
    )
    expect(vanMad.textContent).not.toMatch(/non publié : non publié/)

    const lcoe = within(indicateurs).getByTestId('calx289-indicateur-lcoe_mad_kwh')
    expect(lcoe.textContent).not.toMatch(/non publié : non publié/)

    // Aucun tableau de flux (le flux est vide) — mais les onze omissions
    // (les cinq indicateurs + les six grandeurs d'entrée) restent visibles.
    expect(within(bloc).queryByTestId('calx289-flux')).not.toBeInTheDocument()
    const omissions = within(bloc).getByTestId('calx289-omissions')
    expect(within(omissions).getAllByTestId('calx289-omission')).toHaveLength(11)

    expect(screen.queryAllByRole('textbox')).toHaveLength(0)
  })
})
