import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, within } from '@testing-library/react'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'
import { espions } from '../../../test/fixtures/calepinageApiMock'

/* ============================================================================
   CALX69 / ACAL133 — LES RÉGLAGES DE SIMULATION ET D'ÉLECTRIQUE, SAISISSABLES,
   TYPÉS PAR LE REGISTRE SERVI.
   ----------------------------------------------------------------------------
   Ce que ce test tient :
     * les lignes viennent EXCLUSIVEMENT du `registre` servi par le GET
       (contrat `parametres_calepinage.json`) : aucune copie locale, aucun
       repli — sans registre servi, un état d'erreur explicite ;
     * le type de chaque clé commande son champ (enum, booléen, bornes) ;
     * UN SEUL PUT `{simulation, electrique_societe}` ; un aller-retour sans
       geste renvoie les sections telles que servies ;
     * une clé entamée sans source est REFUSÉE avant tout envoi réseau, le
       champ fautif pointé et le bandeau le nomme (règle fondateur 08/09) ;
     * le refus 400 du serveur (nommé DANS sa section) atterrit SOUS la clé ;
     * une clé jamais entamée est OMISE de l'envoi — aucune valeur par défaut ;
     * « Tout recalculer » appelle l'endpoint et dit « N simulations relancées ».
   ========================================================================== */

const REGLAGES = exempleContrat('calepinage', 'parametres_calepinage')
const REGLAGES_VIDES = exempleContrat('calepinage', 'parametres_calepinage', 'exemple_vide')
const REGISTRE = REGLAGES.registre

// ACAL345 — la doublure partagée de `calepinageApi.parametres` et de la permission.
const mocks = espions
vi.mock('../../../api/calepinageApi', async () => (await import('../../../test/fixtures/calepinageApiMock')).apiParametres({ recalculer: true }))
vi.mock('../../../hooks/useHasPermission', async () => (await import('../../../test/fixtures/calepinageApiMock')).permissionMock())

const module_ = await import('./ReglagesSimulation')
const ReglagesSimulation = module_.default

const rendre = () => render(<ReglagesSimulation />)

const champValeur = (cle) => screen.getByTestId(`calx69-valeur-${cle}`).querySelector('input, select')
const champSource = (cle) => screen.getByTestId(`calx69-source-${cle}`).querySelector('select')
const champReference = (cle) => screen.getByTestId(`calx69-reference-${cle}`).querySelector('input')

beforeEach(() => {
  vi.clearAllMocks()
  mocks.hasPermission.mockReturnValue(true)
})
afterEach(() => { cleanup() })

describe('ACAL133 — les lignes viennent EXCLUSIVEMENT du registre servi', () => {
  it('lignes = registre servi, aucune copie locale', async () => {
    const servi = reponseContrat('calepinage', 'parametres_calepinage')
    // Une clé que le registre SERVI porte et qu'aucune table locale ne
    // connaît, et une clé du registre d'avant retirée du servi.
    servi.data.registre.simulation.push({
      cle: 'cle_servie_seulement', libelle: 'Clé servie seulement', unite: '', reference: 'servie',
      type: 'nombre',
    })
    servi.data.registre.simulation = servi.data.registre.simulation
      .filter((ligne) => ligne.cle !== 'attenuation_horizon')
    mocks.getParametres.mockResolvedValue(servi)
    rendre()

    for (const section of ['simulation', 'electrique_societe']) {
      for (const { cle } of servi.data.registre[section]) {
        expect(await screen.findByTestId(`calx69-ligne-${cle}`)).toBeInTheDocument()
      }
    }
    expect(screen.getByTestId('calx69-ligne-cle_servie_seulement')).toBeInTheDocument()
    expect(screen.queryByTestId('calx69-ligne-attenuation_horizon')).toBeNull()
    // La copie locale n'existe plus.
    expect(module_.REGISTRE_SIMULATION).toBeUndefined()
    expect(module_.REGISTRE_ELECTRIQUE_SOCIETE).toBeUndefined()
  })

  it('registre absent de la réponse : état d’erreur explicite, aucune ligne de repli', async () => {
    const sansRegistre = reponseContrat('calepinage', 'parametres_calepinage')
    delete sansRegistre.data.registre
    mocks.getParametres.mockResolvedValue(sansRegistre)
    rendre()

    expect(await screen.findByTestId('calx69-erreur-chargement'))
      .toHaveTextContent('Registre des réglages indisponible')
    expect(screen.queryByTestId('calx69-ligne-mode_meteo')).toBeNull()
  })

  it('affiche le libellé et la référence servis', async () => {
    const contratServi = reponseContrat('calepinage', 'parametres_calepinage')
    const ligneModeMeteo = contratServi.data.registre.simulation
      .find((ligne) => ligne.cle === 'mode_meteo')
    ligneModeMeteo.libelle = 'Mode météo (servi par le GET, jamais la table locale)'
    ligneModeMeteo.reference = 'référence servie par le GET, jamais celle codée en local'
    mocks.getParametres.mockResolvedValue(contratServi)
    rendre()

    const ligne = await screen.findByTestId('calx69-ligne-mode_meteo')
    expect(ligne).toHaveTextContent('Mode météo (servi par le GET, jamais la table locale)')
    expect(screen.getByTestId('calx69-aide-mode_meteo')).toHaveTextContent(
      'référence servie par le GET, jamais celle codée en local',
    )
  })

  it('remplit les champs depuis le contrat committé, jamais depuis le repère doctrinal', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    expect(champValeur('mode_meteo').value).toBe(REGLAGES.simulation.mode_meteo.valeur)
    expect(champSource('mode_meteo').value).toBe(REGLAGES.simulation.mode_meteo.source)
    expect(champReference('mode_meteo').value).toBe(REGLAGES.simulation.mode_meteo.reference)
    expect(champValeur('cos_phi_par_defaut').value).toBe(
      String(REGLAGES.electrique_societe.cos_phi_par_defaut.valeur),
    )
    expect(champValeur('fenetre_annees').value).toBe('')
    expect(screen.getByTestId('calx69-aide-fenetre_annees')).toHaveTextContent('PVGIS')
    expect(champValeur('fenetre_annees').value).not.toContain('PVGIS')
  })

  it('champs typés : liste fermée pour un enum, oui/non pour un booléen, bornes du registre', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    const enumServi = REGISTRE.simulation.find((r) => r.cle === 'mode_meteo')
    const select = champValeur('mode_meteo')
    expect(select.tagName).toBe('SELECT')
    const options = Array.from(select.querySelectorAll('option')).map((o) => o.value).filter(Boolean)
    expect(options).toEqual(enumServi.valeurs)

    expect(champValeur('attenuation_horizon').tagName).toBe('SELECT')
    expect(screen.getByTestId('acal133-type-sigma_modele_pct'))
      .toHaveTextContent('Pourcentage entre 0 et 100')
    // Aucune borne HTML : ce que l'on tape n'est jamais « sauté ».
    expect(champValeur('sigma_modele_pct')).not.toHaveAttribute('min')
    expect(champValeur('sigma_modele_pct')).not.toHaveAttribute('max')
  })

  it('dit qu’un poste saisi sur un calepinage prime sur le réglage société', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()
    expect(await screen.findByTestId('acal133-priorite'))
      .toHaveTextContent('prime sur ce réglage')
  })
})

describe('ACAL133 — un seul PUT pour les deux sections', () => {
  it('un seul PUT {simulation, electrique_societe}', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES })
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    fireEvent.change(champValeur('mode_meteo'), { target: { value: 'pluriannuel' } })
    fireEvent.change(champSource('mode_meteo'), { target: { value: 'societe' } })
    fireEvent.change(champValeur('cos_phi_par_defaut'), { target: { value: '1' } })
    fireEvent.change(champSource('cos_phi_par_defaut'), { target: { value: 'societe' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0]).toEqual({
      simulation: { mode_meteo: { valeur: 'pluriannuel', source: 'societe', reference: '' } },
      electrique_societe: { cos_phi_par_defaut: { valeur: 1, source: 'societe', reference: '' } },
    })
  })

  it('une section vide n’invente rien : un seul PUT de deux sections vides', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES_VIDES })
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    fireEvent.click(screen.getByTestId('calx69-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres).toHaveBeenCalledWith({ simulation: {}, electrique_societe: {} })
    expect(screen.queryByTestId('calx69-bandeau')).not.toBeInTheDocument()
  })

  it('aller-retour sans geste : les sections renvoyées sont celles servies, à l’octet', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES })
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0]).toEqual({
      simulation: REGLAGES.simulation,
      electrique_societe: REGLAGES.electrique_societe,
    })

    // Deuxième enregistrement, toujours sans toucher : identique.
    await screen.findByTestId('calx69-message')
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(2))
    expect(mocks.putParametres.mock.calls[1][0]).toEqual(mocks.putParametres.mock.calls[0][0])
  })

  it('un texte qui ressemble à un nombre n’en devient pas un sans geste', async () => {
    const servi = reponseContrat('calepinage', 'parametres_calepinage')
    servi.data.simulation = {
      mode_meteo: { valeur: '60', source: 'texte', reference: 'valeur texte' },
    }
    mocks.getParametres.mockResolvedValue(servi)
    mocks.putParametres.mockResolvedValue({ data: servi.data })
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0].simulation.mode_meteo.valeur).toBe('60')
  })
})

describe('ACAL133 — Tout recalculer', () => {
  it('Tout recalculer appelle l’endpoint et affiche « N simulations relancées »', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    mocks.recalculer.mockResolvedValue({ data: { soumis: 3, jobs: [], reste: 0 } })
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    fireEvent.click(screen.getByTestId('acal133-tout-recalculer'))

    expect(await screen.findByTestId('calx69-message')).toHaveTextContent('3 simulations relancées')
    expect(mocks.recalculer).toHaveBeenCalledTimes(1)
  })

  it('sans le droit de gérer : le bouton n’est pas proposé', async () => {
    mocks.hasPermission.mockReturnValue(false)
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    expect(screen.queryByTestId('acal133-tout-recalculer')).toBeNull()
  })
})

describe('CALX69 — une clé entamée sans source est refusée AVANT tout envoi', () => {
  it('pointe le champ fautif, le bandeau le nomme, et n’appelle jamais le serveur', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide'))
    rendre()
    await screen.findByTestId('calx69-ligne-fenetre_annees')

    fireEvent.change(champValeur('fenetre_annees'), { target: { value: '10' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))

    const erreur = await screen.findByTestId('calx69-erreur-fenetre_annees')
    expect(erreur).toHaveTextContent('source')
    expect(screen.getByTestId('calx69-bandeau')).toHaveTextContent('années météo')
    expect(screen.getByTestId('calx69-bandeau').querySelector('a[href="#calx69-fenetre_annees"]'))
      .toBeTruthy()
    expect(mocks.putParametres).not.toHaveBeenCalled()
  })
})

describe('CALX69 — le refus 400 du serveur atterrit SOUS la bonne clé', () => {
  it('une clé valide envoyée, refusée par le serveur, porte son message', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide'))
    mocks.putParametres.mockRejectedValueOnce({
      response: { data: { mode_meteo: ['« Mode météo » : provenance « ailleurs » inconnue.'] } },
    })
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    fireEvent.change(champValeur('mode_meteo'), { target: { value: 'pluriannuel' } })
    fireEvent.change(champSource('mode_meteo'), { target: { value: 'societe' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))

    expect(await screen.findByTestId('calx69-erreur-mode_meteo')).toHaveTextContent('inconnue')
    expect(mocks.putParametres).toHaveBeenCalledTimes(1)
  })

  it('400 nommé affiché sur la ligne (contrat `exemple_refus_type`, nommé DANS sa section)', async () => {
    const refus = exempleContrat('calepinage', 'parametres_calepinage', 'exemple_refus_type')
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide'))
    mocks.putParametres.mockRejectedValueOnce({ response: { data: refus } })
    rendre()
    await screen.findByTestId('calx69-ligne-sigma_modele_pct')

    // « 2,5 » est envoyé TEL QUEL : le serveur normalise et refuse en nommant.
    fireEvent.change(champValeur('sigma_modele_pct'), { target: { value: '2,5' } })
    fireEvent.change(champSource('sigma_modele_pct'), { target: { value: 'saisie' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))

    const ligne = await screen.findByTestId('calx69-ligne-sigma_modele_pct')
    expect(within(ligne).getByTestId('calx69-erreur-sigma_modele_pct'))
      .toHaveTextContent(refus.simulation.sigma_modele_pct)
    expect(mocks.putParametres.mock.calls[0][0].simulation.sigma_modele_pct.valeur).toBe('2,5')
  })
})

describe('CALX69 — lecture seule sans le droit de gérer', () => {
  it('affiche « Lecture seule », désactive la saisie, et ne propose pas d’enregistrer', async () => {
    mocks.hasPermission.mockReturnValue(false)
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    expect(screen.getByTestId('calx69-lecture-seule')).toBeInTheDocument()
    expect(champValeur('mode_meteo')).toBeDisabled()
    expect(screen.queryByTestId('calx69-enregistrer')).not.toBeInTheDocument()
  })
})

describe('ACAL132 — le PUT fusionne : une clé stockée puis vidée part à `null`', () => {
  it('envoie `null` pour la clé vidée et garde les autres clés servies', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES })
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    fireEvent.change(champValeur('mode_meteo'), { target: { value: '' } })
    fireEvent.change(champSource('mode_meteo'), { target: { value: '' } })
    fireEvent.change(champReference('mode_meteo'), { target: { value: '' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalled())
    const envoi = mocks.putParametres.mock.calls[0][0].simulation
    expect(envoi.mode_meteo).toBeNull()
    expect(envoi.resolution_minutes).toEqual(REGLAGES.simulation.resolution_minutes)
    expect('fenetre_annees' in envoi).toBe(false)
  })
})
