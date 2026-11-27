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
import { render, screen, cleanup, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, fichierContrat, reponseContrat } from '../../../test/fixtures/contractSamples'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import userEvent from '@testing-library/user-event'
import { formatNumber } from '../../../lib/format'
import { chiffresSansGrandeur } from '../commun/useExplications'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      resultat: vi.fn(), simuler: vi.fn(),
      entreeElectrique: vi.fn(() => Promise.resolve({ data: { entree: {} } })),
      enregistrerEntreeElectrique: vi.fn(),
      exportCsv: vi.fn(),
      explications: vi.fn(),
    },
    moteur: { resultat: vi.fn() },
  },
}))

/* ACAL125 — le bouton de calcul est sous `calepinage_gerer` (doublure : pas de Provider Redux). */
vi.mock('../../../hooks/useHasPermission', () => ({ useHasPermission: () => true }))

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
      'simulation périmée : le document ou un réglage de la société a changé depuis le calcul du 19/09/2026',
    )
    expect(screen.queryByTestId('calx14-batterie')).toBeNull()
    expect(screen.queryByTestId('calx14-hors-reseau')).toBeNull()
  })

  it('non simulé : le motif du serveur et un bouton pour lancer/relancer la simulation', async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('calx14-panneau')
    expect(screen.getByTestId('calx14-non-simule')).toBeInTheDocument()
    expect(screen.getByTestId('calx48-lancer-bouton')).toBeInTheDocument()
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

/* ACAL167 — la déclaration de la batterie et du mode hors réseau. Les réponses viennent de
   l'exemple COMMITTÉ `calepinage_entree_electrique.json` (jamais d'un objet tapé à la main). */
describe('PanneauBatterie — déclarer la batterie (ACAL167)', () => {
  const VIDE = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_vide')
  const poste = () => calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0][1]
  const champ = (cle) => document.getElementById(`acal167-${cle}`)

  beforeEach(() => {
    calepinageApi.calepinages.entreeElectrique
      .mockResolvedValue({ data: { entree: VIDE.entree } })
    servir('exemple')
  })

  it('saisir une stratégie poste {batterie:{strategie, packs}} et relit la valeur serveur', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    calepinageApi.calepinages.entreeElectrique
      .mockResolvedValueOnce({ data: { entree: VIDE.entree } })
      .mockResolvedValueOnce({ data: { entree: { ...VIDE.entree, batterie: { strategie: 'autoconso', packs: 2 } } } })
    rendre()

    await screen.findByTestId('acal167-declaration')
    fireEvent.change(champ('strategie'), { target: { value: 'autoconso' } })
    fireEvent.change(champ('packs'), { target: { value: '2' } })
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))

    await screen.findByTestId('acal167-message')
    expect(poste()).toEqual({ batterie: { strategie: 'autoconso', packs: 2 } })
    // La valeur relue du serveur est celle affichée.
    expect(champ('strategie')).toHaveValue('autoconso')
    expect(champ('packs')).toHaveValue(2)
    expect(calepinageApi.calepinages.entreeElectrique).toHaveBeenCalledTimes(2)
  })

  it('paramètre de stratégie manquant refusé sous son champ', async () => {
    const message = '« seuil_effacement_kw » : saisissez un nombre positif ou nul.'
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
      response: { status: 400, data: { 'batterie.seuil_effacement_kw': message } },
    })
    rendre()

    await screen.findByTestId('acal167-declaration')
    fireEvent.change(champ('strategie'), { target: { value: 'peak_shaving' } })
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))

    expect(await screen.findByTestId('acal167-erreur-seuil_effacement_kw')).toHaveTextContent(message)
  })

  it('hors réseau poste jours_autonomie', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    rendre()

    await screen.findByTestId('acal167-declaration')
    fireEvent.click(champ('actif'))
    fireEvent.change(champ('jours'), { target: { value: '2' } })
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))

    await screen.findByTestId('acal167-message')
    expect(poste()).toEqual({ hors_reseau: { actif: true, jours_autonomie: 2 } })
  })

  it('une déclaration jamais touchée et absente du stock n’envoie rien d’inventé', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    rendre()

    await screen.findByTestId('acal167-declaration')
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))

    await screen.findByTestId('acal167-message')
    expect(poste()).toEqual({})
  })

  it('ACAL125 — suit queued → running → done (statuts réels) puis relit le résultat, sans refus', async () => {
    const accuse = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_accepte')
    servir('exemple')
    calepinageApi.calepinages.simuler.mockResolvedValue({ data: accuse })
    calepinageApi.moteur.resultat
      .mockResolvedValueOnce({ data: { ...accuse, statut: 'queued' } })
      .mockResolvedValueOnce({ data: { ...accuse, statut: 'running' } })
      .mockResolvedValue({ data: { ...accuse, statut: 'done', progress_pct: 100 } })
    render(<MemoryRouter><PanneauBatterie calepinageId={1} intervalleMs={5} /></MemoryRouter>)

    await screen.findByTestId('calx14-panneau')
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))

    await waitFor(() => expect(calepinageApi.moteur.resultat).toHaveBeenCalledTimes(3))
    await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalledTimes(2))
    expect(screen.queryByTestId('calx48-refus')).toBeNull()
    // Résultat frais : « Recalculer » envoie forcer:true.
    expect(calepinageApi.calepinages.simuler).toHaveBeenCalledWith(1, { forcer: true })
  })

  it('« Enregistrer et relancer » enchaîne la relance de la simulation (forcer: true)', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    calepinageApi.calepinages.simuler.mockResolvedValue({ data: {} })
    rendre()

    await screen.findByTestId('acal167-declaration')
    fireEvent.change(champ('strategie'), { target: { value: 'autoconso' } })
    fireEvent.click(screen.getByTestId('acal167-enregistrer-relancer'))

    await vi.waitFor(() => expect(calepinageApi.calepinages.simuler).toHaveBeenCalledWith(1, { forcer: true }))
    expect(poste()).toEqual({ batterie: { strategie: 'autoconso' } })
  })

  describe('ACAL788 — appareils à tenir pendant une coupure', () => {
    const SECOURS = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_secours').batterie
    const saisir = (rang, cle, valeur) => fireEvent.change(
      document.getElementById(`acal788-${rang}-${cle}`), { target: { value: String(valeur) } })

    it('deux appareils et 4 h postent le corps attendu puis affichent la réserve servie', async () => {
      calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
      const energie = SECOURS.appareils.reduce(
        (somme, a) => somme + a.puissance_continue_kw * a.quantite, 0) * SECOURS.duree_secours_h
      const donnees = donneesSimulees()
      donnees.batterie.total.reserve_secours = {
        energie_kwh: energie, duree_h: SECOURS.duree_secours_h, detail: SECOURS.appareils,
      }
      calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
      // La relecture après l'enregistrement rend l'entrée telle que le serveur la garde.
      calepinageApi.calepinages.entreeElectrique
        .mockResolvedValueOnce({ data: { entree: VIDE.entree } })
        .mockResolvedValueOnce({ data: { entree: { ...VIDE.entree, batterie: SECOURS } } })
      rendre()

      await screen.findByTestId('acal167-declaration')
      expect(screen.queryByTestId('acal788-secours')).toBeNull()
      fireEvent.change(champ('strategie'), { target: { value: 'backup' } })
      fireEvent.click(screen.getByTestId('acal788-ajouter'))
      fireEvent.click(screen.getByTestId('acal788-ajouter'))
      SECOURS.appareils.forEach((a, rang) => {
        saisir(rang, 'nom', a.nom)
        saisir(rang, 'puissance_continue_kw', a.puissance_continue_kw)
        saisir(rang, 'puissance_pointe_kw', a.puissance_pointe_kw)
        saisir(rang, 'quantite', a.quantite)
      })
      fireEvent.change(document.getElementById('acal788-duree'), { target: { value: String(SECOURS.duree_secours_h) } })
      fireEvent.click(screen.getByTestId('acal167-enregistrer'))

      await screen.findByTestId('acal167-message')
      expect(poste()).toEqual({
        batterie: {
          strategie: 'backup',
          appareils: SECOURS.appareils,
          duree_secours_h: SECOURS.duree_secours_h,
          reserve_backup_kwh: null,
        },
      })
      expect(typeof poste().batterie.duree_secours_h).toBe('number')
      expect(champ('reserve_backup_kwh')).toBeDisabled()
      expect(screen.getByTestId('acal788-reserve')).toHaveTextContent(
        `Réserve déduite : ${formatNumber(energie)} kWh pour 2 appareils pendant ${SECOURS.duree_secours_h} h`)
    })

    it('un refus du serveur se lit sous la durée', async () => {
      const motif = 'La durée de coupure à tenir est SAISIE (heures).'
      calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
        response: { status: 400, data: { 'batterie.duree_secours_h': motif } },
      })
      rendre()

      await screen.findByTestId('acal167-declaration')
      fireEvent.change(champ('strategie'), { target: { value: 'backup' } })
      fireEvent.click(screen.getByTestId('acal167-enregistrer'))

      expect(await screen.findByTestId('acal788-duree-erreur')).toHaveTextContent(motif)
    })
  })

  describe('ACAL799 — les coupures : trois questions, énergie non fournie et heures tenues', () => {
    const COUPURES = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_secours').batterie.coupures
    const SERVI = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute').batterie.total.secours
    const rendreExpert = (expert = true) => render(
      <MemoryRouter initialEntries={[expert ? '/?mode=expert' : '/']}><PanneauBatterie calepinageId={1} /></MemoryRouter>,
    )
    const declaration = () => screen.findByTestId('acal167-declaration', {}, { timeout: 10_000 })
    const servirSecours = (secours) => {
      const donnees = donneesSimulees()
      donnees.batterie.total.secours = secours
      calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
    }

    it('trois réponses postent `batterie.coupures` ; énergie non fournie et heures tenues de l’exemple s’affichent', async () => {
      calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
      calepinageApi.calepinages.entreeElectrique
        .mockResolvedValueOnce({ data: { entree: VIDE.entree } })
        .mockResolvedValueOnce({ data: { entree: { ...VIDE.entree, batterie: { strategie: 'backup', coupures: COUPURES } } } })
      servirSecours(SERVI)
      rendreExpert()
      await declaration()
      fireEvent.change(champ('strategie'), { target: { value: 'backup' } })
      for (const cle of ['nombre_par_an', 'duree_h', 'heure_debut']) {
        const saisie = document.getElementById(`acal799-${cle}`)
        expect(saisie.value, `${cle} jamais prérempli`).toBe('')
        fireEvent.change(saisie, { target: { value: String(COUPURES[cle]) } })
      }
      fireEvent.click(screen.getByTestId('acal167-enregistrer'))
      await screen.findByTestId('acal167-message')
      expect(poste().batterie.coupures).toEqual(COUPURES)

      expect(screen.getByTestId('acal799-energie')).toHaveTextContent(
        `Énergie non fournie attendue : ${formatNumber(SERVI.coupures.energie_non_fournie_kwh)} kWh par an `
        + `(la pire coupure : ${formatNumber(SERVI.coupures.energie_non_fournie_par_coupure_pire_kwh)} kWh)`)
      const lignes = screen.getAllByTestId('acal799-appareil')
      expect(lignes).toHaveLength(SERVI.appareils.length)
      SERVI.appareils.forEach((a, i) => expect(lignes[i])
        .toHaveTextContent(`${a.nom} : tient ${formatNumber(a.heures_tenues)} h`))
    })

    it('`secours` nul : « non calculé » et le motif servi, jamais 0', async () => {
      const vide = exempleContrat('calepinage', 'calepinage_simulation').batterie.total.secours
      servirSecours(vide)
      rendreExpert()
      await declaration()
      fireEvent.change(champ('strategie'), { target: { value: 'backup' } })
      expect(screen.getByTestId('acal799-energie')).toHaveTextContent(`non calculé : ${vide.motif_coupures}`)
      expect(screen.getByTestId('acal799-appareils-motif')).toHaveTextContent(`non calculé : ${vide.motif_appareils}`)
      expect(screen.getByTestId('acal799-energie')).not.toHaveTextContent(/\b0 kWh/)
    })

    it('hors mode expert : la section Coupures n’existe pas', async () => {
      servirSecours(SERVI)
      rendreExpert(false)
      await declaration()
      fireEvent.change(champ('strategie'), { target: { value: 'backup' } })
      expect(screen.getByTestId('acal788-secours')).toBeTruthy()
      expect(screen.queryByTestId('acal799-coupures')).toBeNull()
    })
  })
})

/* ACAL447 — la semaine 8 à 14 de mars, lue dans le CSV horaire. Les états de
   charge viennent du contrat `calepinage_serie_horaire.json` (jamais tapés). */
describe('PanneauBatterie — le « ? » de chaque tuile (ACAL875)', () => {
  // Le registre RÉEL (`data/explications.json`, servi tel quel par ACAL871).
  const registre = JSON.parse(readFileSync(
    join(fichierContrat('calepinage', 'x'), '..', '..', 'data', 'explications.json'), 'utf8'))

  it('chaque tuile a son « ? » ; la capacité utile cite la profondeur servie', async () => {
    calepinageApi.calepinages.explications.mockResolvedValue({ data: registre })
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesSimulees() })
    rendre()
    const panneau = await screen.findByTestId('calx14-panneau')
    const tuiles = ['calx14-batterie-total', 'calx14-batterie-energie',
      'calx14-hors-reseau-total', 'calx14-hors-reseau-banque'].map((t) => within(panneau).getByTestId(t))
    tuiles.forEach((bloc) => expect(chiffresSansGrandeur(bloc)).toEqual([]))
    const boutons = tuiles.flatMap((bloc) => within(bloc).getAllByRole('button', { name: 'Pourquoi ce chiffre ?' }))
    expect(boutons).toHaveLength(22)
    const connues = new Set(registre.entrees.map((e) => e.cle))
    boutons.forEach((b) => expect(connues.has(b.dataset.grandeur)).toBe(true))

    const banque = within(panneau).getByTestId('calx14-hors-reseau-banque')
    await userEvent.click(within(banque).getAllByRole('button', { name: 'Pourquoi ce chiffre ?' })[0])
    const dod = donneesSimulees().hors_reseau.banque.dod_pct
    expect(await screen.findByText(new RegExp(`profondeur de décharge publiée, ${formatNumber(dod)} %`)))
      .toBeInTheDocument()
  })
})

describe('PanneauBatterie — semaine d’état de charge (ACAL447)', () => {
  const socs = () => exempleContrat('calepinage', 'calepinage_serie_horaire', 'exemple_tronquee').serie_horaire.points
    .map((p) => p.batterie_soc_pct).filter((v) => v !== null)
  const csv = (lignes) => ['annee;mois;jour;heure;batterie_soc_pct', ...lignes].join('\r\n')
  const fr = (v) => String(v).replace('.', ',')

  it('la semaine de mars se trace depuis batterie_soc_pct ; sans batterie, aucune requête de série', async () => {
    const [a, b] = socs()
    calepinageApi.calepinages.exportCsv.mockResolvedValue({
      data: csv([`2020;3;8;10;${fr(a)}`, '2020;3;8;11;', `2020;3;9;10;${fr(b)}`]),
    })
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesSimulees() })
    rendre()

    const bloc = await screen.findByTestId('acal447-semaine')
    const titre = await within(bloc).findByTestId('acal447-titre')
    expect(calepinageApi.calepinages.exportCsv)
      .toHaveBeenCalledWith(1, 'horaire', 'annee,mois,jour,heure,batterie_soc_pct')
    expect(titre).toHaveTextContent('du 8 au 14 mars 2020 (année météo de la série, pas une moyenne)')
    // une heure sans valeur est un trou, jamais 0 (table équivalente du graphique)
    expect(bloc.textContent).not.toMatch(/\b0 %/)
    cleanup()

    // sans batterie dispatchée : le motif du panneau reste seul, aucune requête de série
    calepinageApi.calepinages.exportCsv.mockClear()
    const sansBatterie = donneesSimulees()
    sansBatterie.batterie = {
      groupes: [], total: null, avertissements: [], motif_absence: MOTIF_SANS_STRATEGIE,
    }
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: sansBatterie })
    rendre()
    await screen.findByTestId('calx14-batterie-motif')
    expect(screen.queryByTestId('acal447-semaine')).toBeNull()
    expect(calepinageApi.calepinages.exportCsv).not.toHaveBeenCalled()
  })

  it('série agrégée au jour : le motif nomme la cause, aucune courbe', async () => {
    calepinageApi.calepinages.exportCsv.mockResolvedValue({ data: csv(['2020;3;8;;55,0']) })
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesSimulees() })
    rendre()
    expect(await screen.findByTestId('acal447-motif'))
      .toHaveTextContent('courbe horaire indisponible : série agrégée au jour')
  })
})

describe('PanneauBatterie — seuils de protection hors réseau (ACAL791)', () => {
  const VIDE = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_vide')
  const AVANCE = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_hors_reseau_avance').hors_reseau
  const poste = () => calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0][1]
  const rendreExpert = (expert = true) => render(
    <MemoryRouter initialEntries={[expert ? '/?mode=expert' : '/']}><PanneauBatterie calepinageId={1} /></MemoryRouter>,
  )

  beforeEach(() => {
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: { entree: VIDE.entree } })
    servir('exemple')
  })

  it('trois seuils saisis postent hors_reseau.seuils ; le refus du serveur se lit sous la veille', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValueOnce({ data: {} })
    calepinageApi.calepinages.entreeElectrique
      .mockResolvedValueOnce({ data: { entree: VIDE.entree } })
      .mockResolvedValueOnce({ data: { entree: { ...VIDE.entree, hors_reseau: { actif: true, seuils: AVANCE.seuils } } } })
    rendreExpert()
    await screen.findByTestId('acal167-declaration')
    expect(screen.queryByTestId('acal791-seuils')).toBeNull()
    fireEvent.click(document.getElementById('acal167-actif'))
    for (const [cle, valeur] of Object.entries(AVANCE.seuils)) {
      fireEvent.change(document.getElementById(`acal791-${cle}`), { target: { value: String(valeur) } })
    }
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))

    await screen.findByTestId('acal167-message')
    expect(poste()).toEqual({ hors_reseau: { actif: true, seuils: AVANCE.seuils } })

    const motif = 'Le seuil de veille est sous le seuil d’arrêt.'
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValueOnce({
      response: { status: 400, data: { 'hors_reseau.seuils.veille_pct': motif } },
    })
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))
    expect(await screen.findByTestId('acal791-veille_pct-erreur')).toHaveTextContent(motif)
  })

  it('trois champs vides sans seuil enregistré ne postent aucun seuil', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    rendreExpert()
    await screen.findByTestId('acal167-declaration')
    fireEvent.click(document.getElementById('acal167-actif'))
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))

    await screen.findByTestId('acal167-message')
    expect(poste()).toEqual({ hors_reseau: { actif: true } })
  })

  it('hors mode expert, ou site raccordé, les champs n’existent pas', async () => {
    rendreExpert(false)
    await screen.findByTestId('acal167-declaration')
    fireEvent.click(document.getElementById('acal167-actif'))
    expect(screen.queryByTestId('acal791-seuils')).toBeNull()
    cleanup()
    rendreExpert()
    await screen.findByTestId('acal167-declaration')
    expect(screen.queryByTestId('acal791-seuils')).toBeNull()
  })
})

describe('PanneauBatterie — groupe d’appoint hors réseau (ACAL803)', () => {
  const VIDE = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_vide')
  const GROUPE = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_hors_reseau_avance').hors_reseau.groupe
  const SERVI = exempleContrat('calepinage', 'calepinage_simulation').hors_reseau
  const poste = () => calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0][1]
  const declaration = () => screen.findByTestId('acal167-declaration', {}, { timeout: 10_000 })
  const rendreExpert = (expert = true) => render(
    <MemoryRouter initialEntries={[expert ? '/?mode=expert' : '/']}><PanneauBatterie calepinageId={1} /></MemoryRouter>,
  )
  // Même patron que les blocs plus haut : la charge part de donneesSimulees()
  // (contrat calepinage_resultat, qui sert bien `hors_reseau`).
  const servirHorsReseau = (horsReseau) => {
    const donnees = donneesSimulees()
    donnees.hors_reseau = horsReseau
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
  }

  beforeEach(() => {
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: { entree: VIDE.entree } })
  })

  it('le groupe saisi poste `hors_reseau.groupe` ; heures de marche et banque du mois chargé de l’exemple s’affichent', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValueOnce({ data: {} })
    calepinageApi.calepinages.entreeElectrique
      .mockResolvedValueOnce({ data: { entree: VIDE.entree } })
      .mockResolvedValueOnce({ data: { entree: { ...VIDE.entree, hors_reseau: { actif: true, groupe: GROUPE } } } })
    servirHorsReseau(SERVI)
    rendreExpert()
    await declaration()
    fireEvent.click(document.getElementById('acal167-actif'))
    expect(document.getElementById('acal803-puissance_kw')).toBeNull()
    fireEvent.click(document.getElementById('acal803-actif'))
    for (const cle of ['puissance_kw', 'soc_demarrage_pct', 'soc_arret_pct', 'heures_max_par_jour']) {
      const saisie = document.getElementById(`acal803-${cle}`)
      expect(saisie.value, `${cle} jamais prérempli`).toBe('')
      fireEvent.change(saisie, { target: { value: String(GROUPE[cle]) } })
    }
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))
    await screen.findByTestId('acal167-message')
    expect(poste()).toEqual({ hors_reseau: { actif: true, groupe: GROUPE } })

    const g = SERVI.groupe
    expect(screen.getByTestId('acal803-groupe')).toHaveTextContent(
      `Le groupe a tourné ${formatNumber(g.heures_de_marche)} h dans l’année (${formatNumber(g.energie_fournie_kwh, { decimals: 0 })} kWh fournis)`)
    expect(screen.getAllByTestId('acal803-groupe-mois')).toHaveLength(g.par_mois.length)
    const b = SERVI.banque_mois_charge
    expect(screen.getByTestId('acal803-banque-mois')).toHaveTextContent(
      `Pour le mois le plus chargé (Décembre) : banque de ${formatNumber(b.capacite_utile_kwh, { decimals: 0 })} kWh utiles, `
      + `défaillance ${formatNumber(b.defaillance_kwh, { decimals: 0 })} kWh`)

    const motif = 'Le groupe démarre batterie basse.'
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValueOnce({
      response: { status: 400, data: { 'hors_reseau.groupe.soc_demarrage_pct': motif } },
    })
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))
    expect(await screen.findByTestId('acal803-soc_demarrage_pct-erreur')).toHaveTextContent(motif)
  })

  it('case décochée et rien au stock : aucun groupe posté ; sans groupe servi, rien de nouveau', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    servirHorsReseau({ ...SERVI, groupe: null, banque_mois_charge: null, motif_banque_mois_charge: 'Mois non calculé.' })
    rendreExpert()
    await declaration()
    fireEvent.click(document.getElementById('acal167-actif'))
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))
    await screen.findByTestId('acal167-message')
    expect(poste()).toEqual({ hors_reseau: { actif: true } })
    expect(screen.queryByTestId('acal803-groupe')).toBeNull()
    expect(screen.getByTestId('acal803-banque-mois')).toHaveTextContent('non calculé : Mois non calculé.')
  })

  it('ACAL970 — la case hors réseau est un `Checkbox` de l’ERP, les listes portent `bg-card`', async () => {
    servirHorsReseau(SERVI)
    rendreExpert(false)
    await declaration()
    const caseHorsReseau = document.getElementById('acal167-actif')
    expect(caseHorsReseau.tagName).toBe('BUTTON')
    expect(caseHorsReseau).toHaveAttribute('role', 'checkbox')
    fireEvent.click(screen.getByText('Le site est hors réseau'))
    expect(caseHorsReseau).toHaveAttribute('data-state', 'checked')
    for (const cle of ['strategie', 'couplage']) {
      const liste = document.getElementById(`acal167-${cle}`)
      expect(liste).toHaveClass('bg-card', 'border-input', 'text-foreground', 'h-[var(--control-h)]')
      expect(liste).not.toHaveClass('bg-black/30')
    }
  })

  it('hors mode expert, l’interrupteur du groupe n’existe pas', async () => {
    servirHorsReseau(SERVI)
    rendreExpert(false)
    await declaration()
    fireEvent.click(document.getElementById('acal167-actif'))
    expect(document.getElementById('acal803-actif')).toBeNull()
  })
})

describe('PanneauBatterie — réglages propres à la stratégie (ACAL792)', () => {
  const VIDE = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_vide')
  const poste = () => calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0][1]
  const regler = (id, valeur) => fireEvent.change(document.getElementById(id), { target: { value: String(valeur) } })
  const rendreExpert = (expert = true) => render(
    <MemoryRouter initialEntries={[expert ? '/?mode=expert' : '/']}><PanneauBatterie calepinageId={1} /></MemoryRouter>,
  )

  beforeEach(() => {
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: { entree: VIDE.entree } })
    servir('exemple')
  })

  it('« charger de 10 h à 14 h jusqu’à 80 % » poste les fenêtres et met les listes d’heures à null', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    rendreExpert()
    await screen.findByTestId('acal167-declaration')
    fireEvent.change(document.getElementById('acal167-strategie'), { target: { value: 'decalage' } })
    fireEvent.click(screen.getByTestId('acal792-ajouter-charge'))
    fireEvent.click(screen.getByTestId('acal792-ajouter-decharge'))
    regler('acal792-charge-0-debut', 10)
    regler('acal792-charge-0-fin', 14)
    regler('acal792-charge-0-soc', 80)
    regler('acal792-decharge-0-debut', 18)
    regler('acal792-decharge-0-fin', 22)
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))

    await screen.findByTestId('acal167-message')
    expect(poste()).toEqual({
      batterie: {
        strategie: 'decalage',
        fenetres: {
          charge: [{ heures: [10, 11, 12, 13], soc_cible_pct: 80 }],
          decharge: [{ heures: [18, 19, 20, 21], soc_cible_pct: null }],
        },
        heures_charge: null,
        heures_decharge: null,
      },
    })
  })

  it('« Ajouter une fenêtre » se désactive à 3 ; un recouvrement refusé se lit sous la fenêtre fautive', async () => {
    const motif = 'La fenêtre « fenetres.decharge[0] » recouvre une fenêtre de charge.'
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
      response: { status: 400, data: { 'batterie.fenetres.decharge[0]': motif } },
    })
    rendreExpert()
    await screen.findByTestId('acal167-declaration')
    fireEvent.change(document.getElementById('acal167-strategie'), { target: { value: 'decalage' } })
    for (let i = 0; i < 3; i += 1) fireEvent.click(screen.getByTestId('acal792-ajouter-charge'))
    expect(screen.getByTestId('acal792-ajouter-charge')).toBeDisabled()
    expect(screen.getByTestId('acal792-ajouter-decharge')).not.toBeDisabled()
    fireEvent.click(screen.getByTestId('acal792-ajouter-decharge'))
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))

    expect(await screen.findByTestId('acal792-decharge-0-erreur')).toHaveTextContent(motif)
  })

  it('« Effacement de pointe » : part et plafond effaçables postés, vides = rien', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    calepinageApi.calepinages.entreeElectrique
      .mockResolvedValueOnce({ data: { entree: VIDE.entree } })
      .mockResolvedValueOnce({ data: { entree: { ...VIDE.entree, batterie: { strategie: 'peak_shaving' } } } })
    rendreExpert()
    await screen.findByTestId('acal167-declaration')
    fireEvent.change(document.getElementById('acal167-strategie'), { target: { value: 'peak_shaving' } })
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))
    await screen.findByTestId('acal167-message')
    expect(poste()).toEqual({ batterie: { strategie: 'peak_shaving' } })

    calepinageApi.calepinages.enregistrerEntreeElectrique.mockClear()
    regler('acal792-part', 60)
    regler('acal792-plafond', 5)
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))
    await vi.waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalled())
    expect(poste()).toEqual({ batterie: { strategie: 'peak_shaving', part_effacable_pct: 60, plafond_effacable_kw: 5 } })
  })

  it('hors mode expert, aucun de ces réglages n’existe', async () => {
    rendreExpert(false)
    await screen.findByTestId('acal167-declaration')
    fireEvent.change(document.getElementById('acal167-strategie'), { target: { value: 'decalage' } })
    expect(screen.queryByTestId('acal792-fenetres')).toBeNull()
    fireEvent.change(document.getElementById('acal167-strategie'), { target: { value: 'peak_shaving' } })
    expect(screen.queryByTestId('acal792-pointe')).toBeNull()
  })
})

describe('PanneauBatterie — détails du mode expert (ACAL789)', () => {
  const rendreExpert = (expert = true) => render(
    <MemoryRouter initialEntries={[expert ? '/?mode=expert' : '/']}><PanneauBatterie calepinageId={1} /></MemoryRouter>,
  )

  it('l’exemple du contrat : cycles lus, « non calculé » + motif servi pour le reste', async () => {
    const donnees = donneesSimulees()
    const { vieillissement } = donnees.batterie.total
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
    rendreExpert()

    const details = await screen.findByTestId('acal789-details')
    expect(within(details).getByTestId('acal789-cycles'))
      .toHaveTextContent(`Cycles par an : ${formatNumber(vieillissement.cycles_annuels)} (en moyenne`)
    expect(within(details).getByTestId('acal789-capacite'))
      .toHaveTextContent(`non calculé : ${vieillissement.motif_absence}`)
    // Jamais 0 pour une valeur absente : la pointe est nulle hors « peak_shaving ».
    expect(within(details).getByTestId('acal789-pointe')).toHaveTextContent('Pointe : non calculé')
    expect(within(details).getByTestId('acal789-pointe')).not.toHaveTextContent(/0 kW/)
    expect(within(details).getByTestId('acal789-depassements')).toHaveTextContent('Dépassements restants : non calculé')
  })

  it('les valeurs servies se lisent : capacité par année, pointe avant/après, dépassements', async () => {
    const donnees = donneesSimulees()
    Object.assign(donnees.batterie.total, {
      pointe_avant_kw: 9.5, pointe_apres_kw: 6.5, nombre_depassements_residuels: 12,
    })
    donnees.batterie.total.vieillissement.annees = [
      { annee: 1, cycles_cumules: 240, capacite_batterie_pct: 100, au_dela_fiche: false },
      { annee: 2, cycles_cumules: 480, capacite_batterie_pct: null, au_dela_fiche: true },
    ]
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
    rendreExpert()

    const details = await screen.findByTestId('acal789-details')
    expect(within(details).getByTestId('acal789-capacite'))
      .toHaveTextContent(`année 1 ${formatNumber(100, { decimals: 1 })} %, année 2 —`)
    expect(within(details).getByTestId('acal789-pointe')).toHaveTextContent(
      `${formatNumber(9.5, { decimals: 1 })} kW avant, ${formatNumber(6.5, { decimals: 1 })} kW après`)
    expect(within(details).getByTestId('acal789-depassements')).toHaveTextContent('12 heures par an')
  })

  it('hors mode expert le bloc n’existe pas', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesSimulees() })
    rendreExpert(false)

    await screen.findByTestId('calx14-batterie')
    expect(screen.queryByTestId('acal789-details')).toBeNull()
  })
})

describe('PanneauBatterie — garde-fou, faits de la série et verdict (ACAL795)', () => {
  const rendreExpert = (expert = true) => render(
    <MemoryRouter initialEntries={[expert ? '/?mode=expert' : '/']}><PanneauBatterie calepinageId={1} /></MemoryRouter>,
  )
  const pct = (v) => `${formatNumber(v * 100, { decimals: 0 })} %`
  const n = (v) => formatNumber(v, { decimals: 0 })

  it('les trois faits, le garde-fou et le mot se lisent ; sans verdict le motif remplace le mot', async () => {
    // Même patron que servirHorsReseau : contrat calepinage_resultat, qui sert `batterie`.
    const haute = donneesSimulees()
    haute.batterie = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute').batterie
    const f = haute.batterie.total.faits_serie
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: haute })
    const premier = rendreExpert()
    const bloc = await screen.findByTestId('acal795-faits')
    expect(within(bloc).getByTestId('acal795-garde-fou')).toHaveTextContent(
      `Votre production est déjà consommée à ${pct(f.taux_autoconsommation_sans_batterie)} sans batterie`)
    expect(within(bloc).getByTestId('acal795-pleine'))
      .toHaveTextContent(`La batterie atteint 100 % ${n(f.jours_pleine)} jours sur ${n(f.jours_total)}`)
    expect(within(bloc).getByTestId('acal795-vide'))
      .toHaveTextContent(`Elle est vide avant l’aube ${n(f.nuits_au_plancher)} nuits sur ${n(f.jours_total)}`)
    expect(within(bloc).getByTestId('acal795-surplus'))
      .toHaveTextContent(`${pct(f.part_surplus_injecte)} du surplus part encore sur le réseau`)
    expect(within(bloc).getByTestId('acal795-mot')).toHaveTextContent('Adaptée à votre consommation')
    expect(within(bloc).queryByTestId('acal795-sans-verdict')).toBeNull()
    premier.unmount()

    const sansVerdict = donneesSimulees()
    expect(sansVerdict.batterie.total.verdict).toBeNull()
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: sansVerdict })
    rendreExpert()
    const bloc2 = await screen.findByTestId('acal795-faits')
    expect(within(bloc2).queryByTestId('acal795-mot')).toBeNull()
    expect(within(bloc2).getByTestId('acal795-sans-verdict'))
      .toHaveTextContent(`Pas de verdict : ${sansVerdict.batterie.total.motif_verdict}`)
    expect(within(bloc2).getByTestId('acal795-pleine')).toHaveTextContent(n(f.jours_pleine))
  })

  it('un fait absent se lit « non calculé », jamais 0', async () => {
    const donnees = donneesSimulees()
    donnees.batterie.total.faits_serie = { ...donnees.batterie.total.faits_serie, part_surplus_injecte: null }
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
    rendreExpert()
    expect(await screen.findByTestId('acal795-surplus')).toHaveTextContent('non calculé')
  })

  it('hors mode expert : rien', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesSimulees() })
    rendreExpert(false)
    await screen.findByTestId('calx14-batterie')
    expect(screen.queryByTestId('acal795-faits')).toBeNull()
  })
})

/* ACAL1644 — champs touchables (≥ 44 px, un par ligne) et refus nommés en mots, par le vrai formulaire. */
describe('PanneauBatterie — champs lisibles et refus en mots (ACAL1644)', () => {
  const VIDE = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_vide')
  const regler = (id, valeur) => fireEvent.change(document.getElementById(id), { target: { value: String(valeur) } })
  const champReserve = () => document.getElementById('acal167-reserve_backup_kwh')
  const rendreExpert = () => render(
    <MemoryRouter initialEntries={['/?mode=expert']}><PanneauBatterie calepinageId={1} /></MemoryRouter>,
  )

  beforeEach(() => {
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: { entree: VIDE.entree } })
    servir('exemple')
  })

  it('un refus sur −1 se lit sous le champ, en mots, sans chemin technique', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
      response: {
        status: 400,
        data: { 'batterie.appareils[0].puissance_continue_kw': 'Batterie.appareils[0].puissance continue kw : « Appareil 1 » : est à saisir' },
      },
    })
    rendreExpert()
    await screen.findByTestId('acal167-declaration')
    fireEvent.change(document.getElementById('acal167-strategie'), { target: { value: 'backup' } })
    fireEvent.click(screen.getByTestId('acal788-ajouter'))
    regler('acal788-0-puissance_continue_kw', -1)
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))

    expect(await screen.findByTestId('acal788-0-puissance_continue_kw-erreur'))
      .toHaveTextContent('Puissance en marche de l’appareil 1 : saisissez un nombre positif')
    expect(document.body.textContent).not.toMatch(/Batterie\.appareils|puissance continue kw/)
  })

  it('une fenêtre refusée est nommée « La 2e fenêtre de charge », sans chemin technique', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
      response: { status: 400, data: { 'batterie.fenetres.charge[1]': 'Batterie.fenetres.charge[1] : recouvre une fenêtre de décharge.' } },
    })
    rendreExpert()
    await screen.findByTestId('acal167-declaration')
    fireEvent.change(document.getElementById('acal167-strategie'), { target: { value: 'decalage' } })
    fireEvent.click(screen.getByTestId('acal792-ajouter-charge'))
    fireEvent.click(screen.getByTestId('acal792-ajouter-charge'))
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))

    expect(await screen.findByTestId('acal792-charge-1-erreur'))
      .toHaveTextContent('La 2e fenêtre de charge : recouvre une fenêtre de décharge.')
    expect(document.body.textContent).not.toMatch(/Batterie\.fenetres/)
  })

  it('ACAL1666 — stratégie changée : appareils, durée et fenêtres masqués ne sont plus postés, mais restent à l’écran', async () => {
    const SECOURS = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_secours').batterie
    const stocke = { ...VIDE.entree, batterie: { ...SECOURS, strategie: 'backup', fenetres: { charge: [{ heures: [10, 11], soc_cible_pct: 80 }], decharge: [] } } }
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: { entree: stocke } })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    rendreExpert()
    await screen.findByTestId('acal167-declaration')
    expect(document.getElementById('acal788-0-nom')).toHaveValue(SECOURS.appareils[0].nom)
    fireEvent.change(document.getElementById('acal167-strategie'), { target: { value: 'peak_shaving' } })
    regler('acal167-seuil_effacement_kw', 1.2)
    expect(champReserve()).not.toBeDisabled()
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))
    await screen.findByTestId('acal167-message')
    const { batterie } = calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0][1]
    expect(batterie.strategie).toBe('peak_shaving')
    expect(batterie.seuil_effacement_kw).toBe(1.2)
    ;['appareils', 'duree_secours_h', 'coupures', 'fenetres'].forEach((cle) => expect(batterie[cle]).toBeNull())
    // Revenir à « Secours » retrouve les appareils, gardés à l'écran.
    fireEvent.change(document.getElementById('acal167-strategie'), { target: { value: 'backup' } })
    expect(document.getElementById('acal788-0-nom')).toHaveValue(SECOURS.appareils[0].nom)
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))
    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalledTimes(2))
    expect(calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[1][1].batterie.appareils).toEqual(SECOURS.appareils)
  })

  it('ACAL1668 — sans devis lié, la liste des batteries du stock (celle du comparateur) pose batterie.produit', async () => {
    const donnees = donneesSimulees()
    const stock = donnees.batterie.capacites_candidates.capacites_stock
    expect(stock.length).toBeGreaterThan(1)
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    rendreExpert()
    await screen.findByTestId('acal167-declaration', {}, { timeout: 8000 })
    const liste = document.getElementById('acal167-produit')
    const options = Array.from(liste.querySelectorAll('option')).slice(1)
    expect(options.map((o) => o.value)).toEqual(stock.map((s) => String(s.produit)))
    expect(options[1]).toHaveTextContent(stock[1].libelle)
    fireEvent.change(liste, { target: { value: String(stock[1].produit) } })
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))
    await screen.findByTestId('acal167-message')
    expect(calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0][1])
      .toEqual({ batterie: { produit: stock[1].produit } })
  })

  it('ACAL1668 — sans choix de produit, rien n’est posté (la ligne du devis lié reste le défaut)', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesSimulees() })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    rendreExpert()
    await screen.findByTestId('acal167-declaration', {}, { timeout: 8000 })
    expect(document.getElementById('acal167-produit')).toHaveValue('')
    fireEvent.click(screen.getByTestId('acal167-enregistrer'))
    await screen.findByTestId('acal167-message')
    expect(calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0][1]).toEqual({})
  })

  it('chaque champ fait au moins 44 px (min-h-11) et s’empile sur une colonne', async () => {
    rendreExpert()
    await screen.findByTestId('acal167-declaration')
    fireEvent.change(document.getElementById('acal167-strategie'), { target: { value: 'backup' } })
    fireEvent.click(screen.getByTestId('acal788-ajouter'))
    fireEvent.click(document.getElementById('acal167-actif'))
    fireEvent.click(await screen.findByLabelText('Il y a un groupe sur le site'))
    const ids = ['acal788-0-puissance_continue_kw', 'acal788-duree', 'acal791-veille_pct', 'acal803-puissance_kw']
    ids.forEach((id) => expect(document.getElementById(id).className).toContain('min-h-11'))
    expect(screen.getByTestId('acal788-appareil').className).toContain('grid-cols-1')
    expect(screen.getByTestId('acal788-appareil').className).not.toMatch(/sm:grid-cols/)
    expect(document.getElementById('acal803-actif').className).toContain('size-5')
  })
})
