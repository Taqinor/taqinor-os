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
import { cloneElement } from 'react'
import { render, screen, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

// jsdom : ResponsiveContainer n'a pas de taille — dimensions fixes (convention BarArrondie.test).
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ResponsiveContainer: ({ children, height }) => cloneElement(children, {
      width: 640, height: typeof height === 'number' ? height : 240,
    }),
  }
})

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { get: vi.fn(), resultat: vi.fn() } },
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

beforeEach(() => {
  vi.clearAllMocks()
  // ACAL1611 — par défaut : aucune simulation (P50 null), donc aucune comparaison.
  calepinageApi.calepinages.resultat.mockResolvedValue(reponseContrat('calepinage', 'calepinage_resultat', 'exemple_vide'))
})
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

  it('R3-07 — un nom de grandeur resté dans un motif ou une source passe par les libellés français', async () => {
    const detail = exempleContrat('calepinage', 'calepinage_detail', 'exemple')
    calepinageApi.calepinages.get.mockResolvedValue({ data: detail })
    const reponse = reponseContrat('ventes', 'ventes_economie', 'exemple')
    reponse.data.omissions = [{ cle: 'van_mad', motif: 'non publié : horizon_ans non saisi ; taux non fourni : taux_actualisation_pct' }]
    reponse.data.hypotheses[0] = { ...reponse.data.hypotheses[0], source: 'hypothèse (taux_actualisation_pct)' }
    ventesApi.getEconomieDevis.mockResolvedValue(reponse)
    rendre()
    const bloc = await screen.findByTestId('calx289-bloc')
    expect(bloc.textContent).not.toMatch(/[a-z]+_(mad|pct|ans|kwh)\b/)
    expect(bloc).toHaveTextContent("non publié : horizon non saisi ; taux non fourni : taux d'actualisation")
  })

  it('R3-07 — une entrée de remplacement est nommée « Remplacement n° N », jamais « remplacements[0] »', async () => {
    const detail = exempleContrat('calepinage', 'calepinage_detail', 'exemple')
    calepinageApi.calepinages.get.mockResolvedValue({ data: detail })
    const reponse = reponseContrat('ventes', 'ventes_economie', 'exemple')
    reponse.data.hypotheses = [
      ...reponse.data.hypotheses,
      { cle: 'remplacements[0]', valeur: 35000, source: 'devis fournisseur — batterie : remplacer en année 12', saisie_le: null },
    ]
    ventesApi.getEconomieDevis.mockResolvedValue(reponse)
    rendre()
    const bloc = await screen.findByTestId('calx289-bloc')
    expect(bloc.textContent).not.toMatch(/remplacements\[/)
    expect(bloc).toHaveTextContent('Remplacement n° 1')
    expect(bloc).toHaveTextContent('batterie : remplacer en année 12')
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
      "non publié : l'horizon : non saisi ; non fourni : le taux d'actualisation, l'indexation tarifaire, la dégradation annuelle",
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

  it("ACAL448 : le graphique du flux se trace ; une valeur null est un trou ; flux vide = aucun graphique", async () => {
    const detail = exempleContrat('calepinage', 'calepinage_detail', 'exemple')
    calepinageApi.calepinages.get.mockResolvedValue({ data: detail })
    const exemple = reponseContrat('ventes', 'ventes_economie', 'exemple')
    ventesApi.getEconomieDevis.mockResolvedValue(exemple)

    rendre()
    const graphique = await screen.findByTestId('acal448-graphique')
    // Une barre par année de l'exemple (11), la courbe du cumul et le repère du retour servi.
    expect(graphique.querySelectorAll('.recharts-bar-rectangle path')).toHaveLength(11)
    expect(graphique.querySelector('.recharts-line')).not.toBeNull()
    expect(graphique.querySelector('.recharts-reference-line')).not.toBeNull()
    // La table du flux reste telle quelle.
    expect(screen.getAllByTestId('calx289-flux-ligne')).toHaveLength(11)
    cleanup()

    // Une valeur null = pas de barre, jamais 0.
    const avecTrou = structuredClone(exemple)
    avecTrou.data.flux[3].flux_mad = null
    ventesApi.getEconomieDevis.mockResolvedValue(avecTrou)
    rendre()
    const g2 = await screen.findByTestId('acal448-graphique')
    expect(g2.querySelectorAll('.recharts-bar-rectangle path')).toHaveLength(10)
    cleanup()

    // Flux vide : aucun graphique, les omissions restent lues.
    ventesApi.getEconomieDevis
      .mockResolvedValue(reponseContrat('ventes', 'ventes_economie', 'exemple_vide'))
    rendre()
    await screen.findByTestId('calx289-bloc')
    expect(screen.queryByTestId('acal448-graphique')).toBeNull()
  })

  describe("ACAL1611 — l'écart entre la production du devis et le P50 servi est nommé", () => {
    const monter = async (p50Modifie) => {
      calepinageApi.calepinages.get.mockResolvedValue({ data: exempleContrat('calepinage', 'calepinage_detail', 'exemple') })
      ventesApi.getEconomieDevis.mockResolvedValue(reponseContrat('ventes', 'ventes_economie', 'exemple'))
      const resultat = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
      if (p50Modifie !== undefined) resultat.data.production.total.p50_kwh = p50Modifie
      // Demande croisée — l'écart est celui que le SERVEUR sert (`ecart_devis.ecart_pct` = (P50 − devis) ÷ devis, au dixième),
      // jamais recalculé à l'écran : les trois nombres servis sont cohérents entre eux (devis 10 000, P50 servi).
      const p50Servi = resultat.data.production.total.p50_kwh
      resultat.data.ecart_devis = { ...resultat.data.ecart_devis, production_devis_kwh: 10000, p50_calepinage_kwh: p50Servi,
        ecart_pct: Math.round(((p50Servi - 10000) / 10000) * 1000) / 10 }
      calepinageApi.calepinages.resultat.mockResolvedValue(resultat)
      rendre()
      return screen.findByTestId('calx289-bloc')
    }

    it("devis 10 000 kWh ≠ P50 13 000 kWh : une phrase nomme les deux chiffres, l'écart et la méthode du devis", async () => {
      const bloc = await monter()
      const phrase = await within(bloc).findByTestId('acal1611-ecart-production')
      expect(phrase).toHaveTextContent(/10.000 kWh\/an/)
      expect(phrase).toHaveTextContent(/13.000 kWh\/an/)
      expect(phrase).toHaveTextContent(/écart \+30,0 %/) // valeur SERVIE (P50 − devis) ÷ devis, le signe du serveur et du bandeau
      expect(phrase).toHaveTextContent('méthode du devis')
    })

    it("à l'égalité (à 1 % près) : aucune phrase", async () => {
      const bloc = await monter(10050)
      await screen.findByTestId('calx289-hypotheses')
      await vi.waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalled())
      expect(within(bloc).queryByTestId('acal1611-ecart-production')).toBeNull()
    })

    it('Demande croisée — l’écart affiché est LA valeur servie, jamais un recalcul : un `ecart_pct` servi différent s’affiche tel quel, sans `ecart_devis` rien', async () => {
      calepinageApi.calepinages.get.mockResolvedValue({ data: exempleContrat('calepinage', 'calepinage_detail', 'exemple') })
      ventesApi.getEconomieDevis.mockResolvedValue(reponseContrat('ventes', 'ventes_economie', 'exemple'))
      const resultat = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
      resultat.data.ecart_devis = { ...resultat.data.ecart_devis, ecart_pct: 7.7 } // ≠ de tout recalcul (+30,0 ou −23,1)
      calepinageApi.calepinages.resultat.mockResolvedValue(resultat)
      rendre()
      const phrase = await within(await screen.findByTestId('calx289-bloc')).findByTestId('acal1611-ecart-production')
      expect(phrase).toHaveTextContent(/écart \+7,7 %/)
      cleanup()
      resultat.data.ecart_devis = null // devis qui n'imprime pas la simulation : le serveur ne sert aucun écart
      calepinageApi.calepinages.resultat.mockResolvedValue(resultat)
      rendre()
      const bloc = await screen.findByTestId('calx289-bloc')
      await vi.waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalledTimes(2))
      expect(within(bloc).queryByTestId('acal1611-ecart-production')).toBeNull()
    })

    it('ACAL1915 — écart non servi mais motif servi (`ecart_devis_motif`) : la phrase du serveur, telle quelle ; écart servi : pas de motif', async () => {
      calepinageApi.calepinages.get.mockResolvedValue({ data: exempleContrat('calepinage', 'calepinage_detail', 'exemple') })
      ventesApi.getEconomieDevis.mockResolvedValue(reponseContrat('ventes', 'ventes_economie', 'exemple'))
      const resultat = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
      const motif = exempleContrat('calepinage', 'calepinage_resultat', 'acal1915_ecart_devis_motif').ecart_devis_motif
      resultat.data.ecart_devis = null
      resultat.data.ecart_devis_motif = motif
      calepinageApi.calepinages.resultat.mockResolvedValue(resultat)
      rendre()
      const bloc = await screen.findByTestId('calx289-bloc')
      expect(await within(bloc).findByTestId('acal1915-ecart-motif')).toHaveTextContent(motif)
      expect(within(bloc).queryByTestId('acal1611-ecart-production')).toBeNull()
      cleanup()
      resultat.data.ecart_devis = { ...exempleContrat('calepinage', 'calepinage_resultat', 'exemple_ecart_devis').ecart_devis }
      resultat.data.ecart_devis_motif = ''
      calepinageApi.calepinages.resultat.mockResolvedValue(resultat)
      rendre()
      const bloc2 = await screen.findByTestId('calx289-bloc')
      await vi.waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalledTimes(2))
      expect(within(bloc2).queryByTestId('acal1915-ecart-motif')).toBeNull()
    })

    it('sans simulation (P50 null) : aucune phrase', async () => {
      calepinageApi.calepinages.get.mockResolvedValue({ data: exempleContrat('calepinage', 'calepinage_detail', 'exemple') })
      ventesApi.getEconomieDevis.mockResolvedValue(reponseContrat('ventes', 'ventes_economie', 'exemple'))
      rendre()
      const bloc = await screen.findByTestId('calx289-bloc')
      await vi.waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalled())
      expect(within(bloc).queryByTestId('acal1611-ecart-production')).toBeNull()
    })
  })
})
