/* CALX14 — le panneau « Batterie / hors réseau » de l'atelier.

   Ce qui est prouvé ici : les grandeurs viennent EXACTEMENT des contrats
   `apps/calepinage/contract_samples/calepinage_resultat.json` (forme SERVIE
   par `GET resultat/`, CALX70) et `calepinage_simulation.json` (forme
   DÉTAILLÉE des blocs `batterie`/`hors_reseau`, CALX4 — Done : « le test
   frontend l'importe au lieu d'écrire un payload à la main »), jamais un
   objet tapé à la main. Un bloc OMIS (`motif_absence`) n'affiche AUCUN
   chiffre — seulement le motif du serveur — et la simulation périmée
   (CALX70) affiche le même bandeau de péremption que les autres panneaux. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: { resultat: vi.fn(), simuler: vi.fn() },
    moteur: { resultat: vi.fn() },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import PanneauBatterie from './PanneauBatterie'

const rendre = () => render(
  <MemoryRouter><PanneauBatterie calepinageId={1} /></MemoryRouter>,
)

const servir = (variante) => {
  calepinageApi.calepinages.resultat
    .mockResolvedValue(reponseContrat('calepinage', 'calepinage_resultat', variante))
}

// Base servie (`calepinage_resultat.json`) enrichie des blocs DÉTAILLÉS de
// `calepinage_simulation.json` (CALX4, contrat partagé) — jamais une charge
// écrite à la main.
const donneesSimulees = () => ({
  ...exempleContrat('calepinage', 'calepinage_resultat', 'exemple'),
  batterie: exempleContrat('calepinage', 'calepinage_simulation').batterie,
  hors_reseau: exempleContrat('calepinage', 'calepinage_simulation').hors_reseau,
})

// Les DEUX motifs ci-dessous sont repris TELS QUELS des constantes serveur
// (`services/etapes/batterie.py::MOTIF_SANS_STRATEGIE`,
// `services/etapes/hors_reseau.py::MOTIF_RACCORDE`) — la FORME d'un bloc omis
// (`{groupes: [], total: null, motif_absence}` / son jumeau hors_reseau)
// n'est déclarée dans AUCUN contrat committé (seuls les états simulé/vide/
// périmé le sont) ; elle est donc vérifiée directement contre le code source
// du producteur plutôt qu'inventée.
const MOTIF_SANS_STRATEGIE = "Aucune stratégie de batterie n'a été choisie : "
  + 'le bloc « batterie » est OMIS. Une batterie ne se pilote pas toute '
  + 'seule — tant que personne n’a choisi entre autoconsommation, '
  + 'effacement de pointe, secours et décalage, aucun kWh stocké ne peut '
  + 'être publié.'

const MOTIF_RACCORDE = "Ce calepinage n'est pas déclaré hors réseau : il n'y "
  + "a donc aucun défaut d'alimentation à chiffrer. Le bloc « hors_reseau » "
  + 'est OMIS — c’est le bloc « autoconsommation » (CALX190) qui décrit un '
  + 'site raccordé.'

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PanneauBatterie (CALX14)', () => {
  it('simulé : stratégie, groupes, énergie stockée/restituée et hors-réseau EXACTEMENT tels que servis', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesSimulees() })
    rendre()

    const panneau = await screen.findByTestId('calx14-panneau')
    const batterie = within(panneau).getByTestId('calx14-batterie')

    const total = within(batterie).getByTestId('calx14-batterie-total')
    // La stratégie RETENUE vient du serveur, jamais traduite si le code n'est
    // pas reconnu (zéro affordance inventée) : affichée telle quelle.
    expect(within(total).getByText('autoconsommation')).toBeInTheDocument()
    // `formatNumber` insère une espace fine insécable dans les milliers : le
    // `.` du regex l'attrape quel que soit le caractère exact (piège banqué).
    expect(within(total).getByText(/2.400 kWh/)).toBeInTheDocument()

    const groupe = within(batterie).getByTestId('calx14-groupe')
    expect(within(groupe).getByText('BAT-ESSAI-1')).toBeInTheDocument()
    expect(within(groupe).getByText('autoconsommation')).toBeInTheDocument()
    expect(within(groupe).getByText(/2.400 kWh/)).toBeInTheDocument()

    const horsReseau = within(panneau).getByTestId('calx14-hors-reseau')
    const horsReseauTotal = within(horsReseau).getByTestId('calx14-hors-reseau-total')
    expect(within(horsReseauTotal).getByText(/250 kWh/)).toBeInTheDocument() // défaillance
    expect(within(horsReseauTotal).getByText('Décembre')).toBeInTheDocument() // pire mois = 12
    const banque = within(horsReseau).getByTestId('calx14-hors-reseau-banque')
    expect(within(banque).getByText('2 j')).toBeInTheDocument() // jours_autonomie
  })

  it('sans fiche batterie (bloc OMIS) : le motif du serveur, AUCUN chiffre', async () => {
    const donnees = donneesSimulees()
    donnees.batterie = {
      groupes: [], total: null, avertissements: [], motif_absence: MOTIF_SANS_STRATEGIE,
    }
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
    rendre()

    const panneau = await screen.findByTestId('calx14-panneau')
    expect(within(panneau).getByTestId('calx14-batterie-motif'))
      .toHaveTextContent(MOTIF_SANS_STRATEGIE)
    // Aucun chiffre : ni le bloc total, ni le tableau de groupes.
    expect(within(panneau).queryByTestId('calx14-batterie-total')).toBeNull()
    expect(within(panneau).queryByTestId('calx14-groupes')).toBeNull()
  })

  it('bloc hors_reseau absent (calepinage raccordé au réseau) : section masquée, motif affiché', async () => {
    const donnees = donneesSimulees()
    donnees.hors_reseau = {
      heures: null, consommation_kwh: null, production_kwh: null, servi_kwh: null,
      defaillance_kwh: null, heures_defaillantes: null, taux_defaillance: null,
      surplus_perdu_kwh: null, soc_minimal_pct: null, mois_le_plus_defavorable: null,
      par_mois: [], banque: null, quantiles_publiables: null, motif_quantiles: '',
      mentions: [], motif_absence: MOTIF_RACCORDE,
    }
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
    rendre()

    const panneau = await screen.findByTestId('calx14-panneau')
    expect(within(panneau).getByTestId('calx14-hors-reseau-motif'))
      .toHaveTextContent(MOTIF_RACCORDE)
    expect(within(panneau).queryByTestId('calx14-hors-reseau-total')).toBeNull()
    expect(within(panneau).queryByTestId('calx14-hors-reseau-par-mois')).toBeNull()
  })

  it('simulation périmée (CALX70) : le bandeau de péremption est affiché, aucun bloc chiffré', async () => {
    servir('exemple_perime')
    rendre()

    await screen.findByTestId('calx14-panneau')
    expect(screen.getByTestId('calx14-perime')).toHaveTextContent(
      'simulation périmée : le document a changé depuis le calcul du 19/09/2026',
    )
    expect(screen.queryByTestId('calx14-batterie')).toBeNull()
    expect(screen.queryByTestId('calx14-hors-reseau')).toBeNull()
  })

  it('non simulé : le motif du serveur et un bouton pour lancer/relancer la simulation', async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('calx14-panneau')
    expect(screen.getByTestId('calx14-non-simule')).toBeInTheDocument()
    expect(screen.getByTestId('calx14-relancer-bouton')).toBeInTheDocument()
    expect(screen.queryByTestId('calx14-batterie')).toBeNull()
  })

  /* CALX271 — « Comparer des capacités du stock » : la liste ORDONNÉE et son
     critère écrit en toutes lettres, lus EXACTEMENT dans
     `calepinage_simulation.json` (`batterie.capacites_candidates`), jamais
     un classement refait ici, jamais un prix. */
  it('CALX271 : le bouton déplie la liste ordonnée et son critère, motivation déclarée présélectionnée', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesSimulees() })
    rendre()

    const bouton = await screen.findByTestId('calx271-comparer')
    expect(bouton).toBeEnabled()
    expect(screen.queryByTestId('calx271-liste')).toBeNull()
    fireEvent.click(bouton)

    const contrat = exempleContrat('calepinage', 'calepinage_simulation')
      .batterie.capacites_candidates
    const autoconso = contrat.par_motivation.autoconso
    const liste = screen.getByTestId('calx271-liste')
    expect(within(liste).getByTestId('calx271-motivation-declaree'))
      .toHaveTextContent('Autoconsommation')
    expect(within(liste).getByTestId('calx271-critere')).toHaveTextContent(autoconso.critere)
    const lignes = within(liste).getAllByTestId('calx271-candidate')
    expect(lignes).toHaveLength(autoconso.candidates.length)
    // L'ORDRE est celui du serveur : la première ligne est son rang 1.
    expect(lignes[0]).toHaveTextContent(autoconso.candidates[0].libelle)
    expect(lignes[1]).toHaveTextContent(autoconso.candidates[1].libelle)
    // Aucun montant n'est affiché : ni « MAD », ni « prix ».
    expect(liste.textContent).not.toMatch(/\bMAD\b|prix/i)
  })

  it('CALX271 : changer de motivation change le critère ; une motivation incalculable affiche SON motif', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesSimulees() })
    rendre()

    fireEvent.click(await screen.findByTestId('calx271-comparer'))
    const contrat = exempleContrat('calepinage', 'calepinage_simulation')
      .batterie.capacites_candidates

    fireEvent.click(screen.getByTestId('calx271-motivation-couverture'))
    expect(screen.getByTestId('calx271-critere'))
      .toHaveTextContent(contrat.par_motivation.couverture.critere)

    fireEvent.click(screen.getByTestId('calx271-motivation-pointe'))
    expect(screen.getByTestId('calx271-motivation-motif'))
      .toHaveTextContent(contrat.par_motivation.pointe.motif_absence)
    expect(screen.queryByTestId('calx271-candidates')).toBeNull()
  })

  it('CALX271 : sans capacités au stock, le bouton est inactif et le motif est lisible', async () => {
    const donnees = donneesSimulees()
    const vide = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_vide')
      .batterie.capacites_candidates
    donnees.batterie = { ...donnees.batterie, capacites_candidates: vide }
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
    rendre()

    const bouton = await screen.findByTestId('calx271-comparer')
    expect(bouton).toBeDisabled()
    expect(screen.getByTestId('calx271-motif')).toHaveTextContent(vide.motif_absence)
    fireEvent.click(bouton)
    expect(screen.queryByTestId('calx271-liste')).toBeNull()
  })

  it('erreur réseau : message français, aucune valeur inventée', async () => {
    calepinageApi.calepinages.resultat.mockRejectedValue(new Error('boom'))
    rendre()

    expect(await screen.findByTestId('calx14-erreur')).toHaveTextContent(
      'Batterie indisponible.',
    )
  })
})
