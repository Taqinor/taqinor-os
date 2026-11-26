import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, within } from '@testing-library/react'
import { exempleContrat, reponseContrat, documentContrat } from '../../../test/fixtures/contractSamples'
import { espions } from '../../../test/fixtures/calepinageApiMock'
import albedoSurfaces from './albedoSurfaces.json'
import process from 'node:process'

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

describe('T4-X3-018 — une saisie non enregistrée ne se perd pas sans avertissement', () => {
  const quitter = () => {
    const evenement = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(evenement)
    return evenement.defaultPrevented
  }

  it('quitter après une saisie demande confirmation ; enregistrée ou rétablie, non', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES })
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')
    expect(quitter()).toBe(false)

    fireEvent.change(champValeur('cos_phi_par_defaut'), { target: { value: '0.9' } })
    expect(quitter()).toBe(true)
    // Revenir à la valeur servie : plus rien à perdre.
    fireEvent.change(champValeur('cos_phi_par_defaut'), { target: { value: '' } })
    expect(quitter()).toBe(false)

    fireEvent.change(champValeur('cos_phi_par_defaut'), { target: { value: '1' } })
    fireEvent.change(champSource('cos_phi_par_defaut'), { target: { value: 'societe' } })
    expect(quitter()).toBe(true)
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(quitter()).toBe(false))
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
    expect(screen.queryByTestId('acal947-erreurs-bouton')).not.toBeInTheDocument()
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
    // ACAL1736 : la frappe préremplit « Saisie » ; la source est ici RETIRÉE à la main.
    fireEvent.change(champSource('fenetre_annees'), { target: { value: '' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))

    const erreur = await screen.findByTestId('calx69-erreur-fenetre_annees')
    expect(erreur).toHaveTextContent('source')
    expect(screen.getByTestId('acal947-erreurs-bouton')).toHaveTextContent('années météo')
    expect(screen.getByTestId('acal947-erreurs-bouton').querySelector('a[href="#calx69-fenetre_annees"]'))
      .toBeTruthy()
    expect(mocks.putParametres).not.toHaveBeenCalled()
  })
})

describe('ACAL1736 — la source vaut « Saisie » par défaut, et les tables se lisent en lignes', () => {
  beforeEach(() => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES_VIDES })
  })

  it('une valeur tapée préremplit « Saisie » (modifiable) ; vidée, la ligne redevient non entamée et omise', async () => {
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')
    expect(champSource('mode_meteo').value).toBe('') // jamais entamée : rien de prérempli
    fireEvent.change(champValeur('mode_meteo'), { target: { value: 'pluriannuel' } })
    expect(champSource('mode_meteo').value).toBe('saisie')
    fireEvent.change(champSource('mode_meteo'), { target: { value: 'societe' } })
    fireEvent.change(champValeur('sigma_modele_pct'), { target: { value: '3' } })
    fireEvent.change(champValeur('sigma_modele_pct'), { target: { value: '' } })
    expect(champSource('sigma_modele_pct').value).toBe('')
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    const { simulation } = mocks.putParametres.mock.calls[0][0]
    expect(simulation.mode_meteo).toEqual({ valeur: 'pluriannuel', source: 'societe', reference: '' })
    expect(simulation).not.toHaveProperty('sigma_modele_pct')
  })

  it('« arrêts » et « Uc / Uv » : des lignes lisibles, jamais « Table structurée (JSON) » ; la source préremplie part avec', async () => {
    rendre()
    await screen.findByTestId('calx69-ligne-indisponibilite_fenetres')
    for (const cle of ['indisponibilite_fenetres', 'thermique_par_pose']) {
      expect(screen.getByTestId(`acal133-type-${cle}`)).not.toHaveTextContent('JSON')
      expect(screen.getByTestId(`calx69-table-${cle}`).textContent).not.toMatch(/[{}"]/)
    }
    fireEvent.click(screen.getByTestId('calx69-table-indisponibilite_fenetres-ajouter'))
    fireEvent.change(screen.getByTestId('calx69-indisponibilite_fenetres-0-debut'), { target: { value: '2026-01-05' } })
    fireEvent.change(screen.getByTestId('calx69-indisponibilite_fenetres-0-fin'), { target: { value: '2026-01-07' } })
    expect(champSource('indisponibilite_fenetres').value).toBe('saisie')
    expect(screen.getByTestId('calx69-table-indisponibilite_fenetres').textContent).not.toMatch(/[{}"]/)
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0].simulation.indisponibilite_fenetres).toEqual({
      valeur: [{ debut: '2026-01-05', fin: '2026-01-07' }], source: 'saisie', reference: '',
    })
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

describe('T4-X3-019 — les tables se saisissent en champs lisibles, pas en JSON brut', () => {
  const servirTable = (simulation) => {
    const servi = reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide')
    servi.data.simulation = simulation
    mocks.getParametres.mockResolvedValue(servi)
    mocks.putParametres.mockResolvedValue({ data: REGLAGES_VIDES })
  }

  it('LID : une ligne par technologie, la frappe écrit la MÊME forme JSON que l’API attend', async () => {
    servirTable({})
    rendre()
    await screen.findByTestId('calx69-ligne-lid_par_techno')
    const table = screen.getByTestId('calx69-table-lid_par_techno')
    expect(table).toHaveTextContent('Cellules PERC')
    expect(table).toHaveTextContent('Cellules TOPCon')
    expect(table.textContent).not.toMatch(/[{}"]/)
    const pct = screen.getByTestId('calx69-lid_par_techno-perc-pct')
    expect(pct).toHaveAttribute('step', 'any')
    expect(pct).not.toHaveAttribute('min')
    fireEvent.change(pct, { target: { value: '1.5' } })
    fireEvent.change(screen.getByTestId('calx69-lid_par_techno-perc-source'), { target: { value: 'Fiche fabricant' } })
    fireEvent.change(champSource('lid_par_techno'), { target: { value: 'texte' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0].simulation.lid_par_techno).toEqual({
      valeur: { perc: { pct: 1.5, source: 'Fiche fabricant' } }, source: 'texte', reference: '',
    })
  })

  it('une table servie se lit en champs remplis ; un aller-retour sans geste renvoie la valeur servie', async () => {
    const servie = { dos_isole: { source: 'texte', uc_w_m2k: 15 }, pose_libre: { source: 'texte', uc_w_m2k: 29, uv_w_m3sk: 0 } }
    servirTable({ thermique_par_pose: { valeur: servie, source: 'texte', reference: '' } })
    rendre()
    await screen.findByTestId('calx69-ligne-thermique_par_pose')
    expect(screen.getByTestId('calx69-thermique_par_pose-dos_isole-uc_w_m2k')).toHaveValue(15)
    expect(screen.getByTestId('calx69-thermique_par_pose-pose_libre-uc_w_m2k')).toHaveValue(29)
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0].simulation.thermique_par_pose.valeur).toEqual(servie)
  })

  it('fenêtres d’arrêt : ajouter une ligne écrit une liste [{debut, fin, motif}]', async () => {
    servirTable({})
    rendre()
    await screen.findByTestId('calx69-ligne-indisponibilite_fenetres')
    fireEvent.click(screen.getByTestId('calx69-table-indisponibilite_fenetres-ajouter'))
    fireEvent.change(screen.getByTestId('calx69-indisponibilite_fenetres-0-debut'), { target: { value: '2026-01-05' } })
    fireEvent.change(screen.getByTestId('calx69-indisponibilite_fenetres-0-fin'), { target: { value: '2026-01-07' } })
    fireEvent.change(screen.getByTestId('calx69-indisponibilite_fenetres-0-motif'), { target: { value: 'Maintenance' } })
    fireEvent.change(champSource('indisponibilite_fenetres'), { target: { value: 'saisie' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0].simulation.indisponibilite_fenetres.valeur)
      .toEqual([{ debut: '2026-01-05', fin: '2026-01-07', motif: 'Maintenance' }])
  })

  it('une valeur illisible dans la forme attendue reste sur l’éditeur JSON', async () => {
    servirTable({ lid_par_techno: { valeur: [1, 2], source: 'texte', reference: '' } })
    rendre()
    await screen.findByTestId('calx69-ligne-correspondances_nomenclature')
    expect(screen.queryByTestId('calx69-table-lid_par_techno')).toBeNull()
    expect(champValeur('lid_par_techno')).toHaveValue('[1,2]')
  })

  it('correspondances de nomenclature : une ligne par correspondance, forme servie renvoyée à l’identique sans geste', async () => {
    const servie = { rails: 12, coffret_dc: 'REF-7' }
    const servi = reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide')
    servi.data.electrique_societe = { correspondances_nomenclature: { valeur: servie, source: 'texte', reference: '' } }
    mocks.getParametres.mockResolvedValue(servi)
    mocks.putParametres.mockResolvedValue({ data: REGLAGES_VIDES })
    rendre()
    await screen.findByTestId('calx69-ligne-correspondances_nomenclature')
    expect(screen.getByTestId('calx69-table-correspondances_nomenclature')).toBeInTheDocument()
    expect(screen.getByTestId('calx69-correspondances_nomenclature-0-cle')).toHaveValue('rails')
    expect(screen.getByTestId('calx69-correspondances_nomenclature-0-valeur')).toHaveValue('12')
    expect(screen.getByTestId('calx69-correspondances_nomenclature-1-valeur')).toHaveValue('REF-7')
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    const envoye = mocks.putParametres.mock.calls[0][0].electrique_societe.correspondances_nomenclature.valeur
    expect(envoye).toEqual(servie)
    expect(JSON.stringify(envoye)).toBe(JSON.stringify(servie))
    expect(typeof envoye.rails).toBe('number')
  })

  it('correspondances : ajouter une ligne laissée à moitié est refusé sous le champ, complétée elle part', async () => {
    const servi = reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide')
    servi.data.electrique_societe = {}
    mocks.getParametres.mockResolvedValue(servi)
    mocks.putParametres.mockResolvedValue({ data: REGLAGES_VIDES })
    rendre()
    await screen.findByTestId('calx69-ligne-correspondances_nomenclature')
    fireEvent.click(screen.getByTestId('calx69-table-correspondances_nomenclature-ajouter'))
    fireEvent.change(screen.getByTestId('calx69-correspondances_nomenclature-0-cle'), { target: { value: 'rails' } })
    fireEvent.change(champSource('correspondances_nomenclature'), { target: { value: 'texte' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    expect(await screen.findByTestId('calx69-erreur-correspondances_nomenclature')).toHaveTextContent('à moitié remplie')
    expect(mocks.putParametres).not.toHaveBeenCalled()
    fireEvent.change(screen.getByTestId('calx69-correspondances_nomenclature-0-valeur'), { target: { value: '45' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0].electrique_societe.correspondances_nomenclature.valeur).toEqual({ rails: 45 })
  })

  it('chaque table convertie monte son ancre #calx69-<clé> (liens « Renseigner »), focalisable, sans doublon d’id', async () => {
    servirTable({})
    rendre()
    await screen.findByTestId('calx69-ligne-lid_par_techno')
    for (const cle of ['lid_par_techno', 'thermique_par_pose', 'indisponibilite_fenetres', 'regle_bom_structure', 'consigne_dc_plan_cablage', 'correspondances_nomenclature']) {
      const ancres = document.querySelectorAll(`[id="calx69-${cle}"]`)
      expect(ancres.length, cle).toBe(1)
      expect(ancres[0], cle).toHaveAttribute('tabindex', '-1')
    }
  })

  it('lecture seule : tous les champs de table sont désactivés', async () => {
    mocks.hasPermission.mockReturnValue(false)
    servirTable({ lid_par_techno: { valeur: { perc: { pct: 1.5, source: 'texte' } }, source: 'texte', reference: '' } })
    rendre()
    await screen.findByTestId('calx69-ligne-lid_par_techno')
    expect(screen.getByTestId('calx69-lid_par_techno-perc-pct')).toBeDisabled()
    expect(screen.getByTestId('calx69-lid_par_techno-perc-pct')).toHaveValue(1.5)
    expect(screen.getByTestId('calx69-regle_bom_structure-rails_par_module')).toBeDisabled()
  })
})

describe('D-ACAL-104 — « gérer » sans « approuver » : les réglages de la société se lisent seulement', () => {
  it('une phrase, saisie désactivée, aucun bouton d’enregistrement ni de réinitialisation', async () => {
    mocks.hasPermission.mockImplementation((code) => code === 'calepinage_gerer')
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    expect(screen.getByTestId('cal-reglages-lecture-seule')).toHaveTextContent(
      'Ces réglages de la société se lisent ici : seules les personnes qui peuvent approuver un calepinage peuvent les changer.')
    expect(champValeur('mode_meteo')).toBeDisabled()
    expect(screen.queryByTestId('calx69-enregistrer')).not.toBeInTheDocument()
    // « Tout recalculer » suit le droit DE SA ROUTE (`calepinage_gerer`), pas la lecture seule des champs.
    expect(screen.getByTestId('acal133-tout-recalculer')).toBeInTheDocument()
  })

  it('sans « gérer » ni « approuver » : ni enregistrer, ni tout recalculer', async () => {
    mocks.hasPermission.mockReturnValue(false)
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')
    expect(screen.queryByTestId('calx69-enregistrer')).toBeNull()
    expect(screen.queryByTestId('acal133-tout-recalculer')).toBeNull()
  })

  it('un approbateur ne voit pas la phrase et enregistre', async () => {
    mocks.hasPermission.mockImplementation((code) => code === 'calepinage_approuver')
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')
    expect(screen.queryByTestId('cal-reglages-lecture-seule')).toBeNull()
    expect(screen.getByTestId('calx69-enregistrer')).toBeInTheDocument()
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

describe('ACAL289 — cartes « Historique » et « Rapport d’étude » (fin de page)', () => {
  it('la carte Historique envoie presets.versions_conservees et la carte Rapport documents.rapport_etude.sections', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES })
    rendre()
    const historique = await screen.findByTestId('acal289-historique')
    const champ = within(historique).getByLabelText('Versions conservées')
    expect(champ).toHaveValue(String(REGLAGES.presets.versions_conservees))
    // Rien de changé : rien n'est envoyé.
    expect(screen.getByTestId('acal289-enregistrer-historique')).toBeDisabled()
    fireEvent.change(champ, { target: { value: '5' } })
    fireEvent.click(screen.getByTestId('acal289-enregistrer-historique'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0]).toEqual({ presets: { versions_conservees: 5 } })

    fireEvent.click(screen.getByTestId('acal289-section-pertes'))
    fireEvent.click(screen.getByTestId('acal289-enregistrer-rapport'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(2))
    expect(mocks.putParametres.mock.calls[1][0]).toEqual({
      documents: { rapport_etude: { sections: ['synthese', 'production'], langue: null } },
    })
  })

  it('vider le champ remet la purge à OFF (null)', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES_VIDES })
    rendre()
    const champ = within(await screen.findByTestId('acal289-historique')).getByLabelText('Versions conservées')
    fireEvent.change(champ, { target: { value: '' } })
    fireEvent.click(screen.getByTestId('acal289-enregistrer-historique'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0]).toEqual({ presets: { versions_conservees: null } })
  })

  it('ENF15 — le catalogue servi, DÉRIVÉ de rapport_etude.json, s’affiche section par section', async () => {
    // Le serveur (`views/parametres.py::_catalogue_rapport`) sert `catalogue_rapport`
    // = `{code, titre, obligatoire}` de CHAQUE section du contrat
    // `apps/calepinage/contract_samples/rapport_etude.json` (CALX292), dans son
    // ordre : la carte doit les montrer toutes, obligatoires verrouillées, et
    // renvoyer les codes dans l'ordre du contrat.
    const sections = exempleContrat('calepinage', 'rapport_etude').sections
    const catalogue = sections.map(({ code, titre, obligatoire }) => ({ code, titre, obligatoire: Boolean(obligatoire) }))
    mocks.getParametres.mockResolvedValue({ data: {
      ...REGLAGES, documents: { rapport_etude: null, catalogue_rapport: catalogue } } })
    mocks.putParametres.mockResolvedValue({ data: REGLAGES })
    rendre()
    const carte = await screen.findByTestId('acal289-rapport')
    sections.forEach(({ code, titre, obligatoire }) => {
      const caseSection = screen.getByTestId(`acal289-section-${code}`)
      expect(caseSection).toBeChecked()
      if (obligatoire) expect(caseSection).toBeDisabled()
      else expect(caseSection).toBeEnabled()
      expect(carte).toHaveTextContent(titre)
    })
    const facultative = sections.find((s) => !s.obligatoire)
    fireEvent.click(screen.getByTestId(`acal289-section-${facultative.code}`))
    fireEvent.click(screen.getByTestId('acal289-enregistrer-rapport'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0]).toEqual({ documents: { rapport_etude: {
      sections: sections.map((s) => s.code).filter((c) => c !== facultative.code), langue: null } } })
  })

  it('une section obligatoire n’est pas décochable', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()
    const obligatoire = await screen.findByTestId('acal289-section-synthese')
    expect(obligatoire).toBeChecked()
    expect(obligatoire).toBeDisabled()
  })

  it('un 400 est affiché mot pour mot', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    mocks.putParametres.mockRejectedValue({ response: { status: 400, data: {
      presets: 'versions_conservees : un entier supérieur à 0 est attendu.' } } })
    rendre()
    const champ = within(await screen.findByTestId('acal289-historique')).getByLabelText('Versions conservées')
    fireEvent.change(champ, { target: { value: '7' } })
    fireEvent.click(screen.getByTestId('acal289-enregistrer-historique'))
    expect(await screen.findByTestId('acal289-erreur-historique'))
      .toHaveTextContent('versions_conservees : un entier supérieur à 0 est attendu.')
  })
})

/* ACAL405 — « Démarrage rapide » : les valeurs publiées du profil de départ
   (contrat `calepinage_profil_depart.json`, ACAL403), jamais écrites par l'écran. */
describe('ACAL405 — Démarrage rapide', () => {
  const PROFIL = exempleContrat('calepinage', 'calepinage_profil_depart')
  const APPLICATION = documentContrat('calepinage', 'calepinage_profil_depart').exemple_application
  const CLE = PROFIL.valeurs[0].cle

  const servirReglages = (simulation) => {
    const servi = reponseContrat('calepinage', 'parametres_calepinage')
    servi.data.simulation = simulation
    mocks.getParametres.mockResolvedValue(servi)
    return servi
  }

  const profilA = (etat) => ({ ...PROFIL, valeurs: [{ ...PROFIL.valeurs[0], etat }] })

  it('l’état affiché est celui que le serveur sert, ligne par ligne', async () => {
    mocks.profilDepart.mockResolvedValue({ data: PROFIL })
    servirReglages({})
    rendre()
    expect(await screen.findByTestId(`acal405-etat-${CLE}`)).toHaveTextContent('Vide')
    expect(screen.getByTestId(`acal405-valeur-${CLE}`)).toHaveTextContent(PROFIL.valeurs[0].url)
    expect(screen.getByTestId('acal405-sans-source')).toHaveTextContent(PROFIL.sans_source[0].motif)
    for (const [etat, libelle] of [['posee_par_profil', 'Posée par le profil (retirable)'],
      ['deja_saisie', 'Déjà renseigné par vous']]) {
      cleanup()
      mocks.profilDepart.mockResolvedValue({ data: profilA(etat) })
      servirReglages({})
      rendre()
      expect(await screen.findByTestId(`acal405-etat-${CLE}`)).toHaveTextContent(libelle)
    }
  })

  it('sans `etat` servi, une clé saisie se lit « déjà saisie » sur les réglages', async () => {
    mocks.profilDepart.mockResolvedValue({ data: profilA(undefined) })
    servirReglages({ [CLE]: { valeur: 0.07, source: 'texte', reference: 'saisie' } })
    rendre()
    expect(await screen.findByTestId(`acal405-etat-${CLE}`))
      .toHaveTextContent('Déjà renseigné par vous (0,07) — conservé')
  })

  /* Maquette « Démarrage rapide » : des mots de tous les jours, un tableau à cinq colonnes. */
  describe('maquette — tableau Remplir · Réglage · Valeur proposée · Source · État', () => {
    const LIGNE = (cle, valeur, extra = {}) => ({
      ...PROFIL.valeurs[0], cle, valeur, etat: 'a_appliquer', unite: '', ...extra,
    })
    const PROFIL_RICHE = {
      ...PROFIL,
      valeurs: [
        LIGNE('b0_iam', 0.05),
        LIGNE('mismatch_fabricant_pct', 2, { unite: '%' }),
        LIGNE('resolution_minutes', 60, { unite: 'minutes' }),
        LIGNE('modele_iam', 'fresnel'),
        LIGNE('thermique_par_pose', {
          pose_libre: { uc_w_m2k: 29, uv_w_m3sk: 0 }, dos_isole: { uc_w_m2k: 15, uv_w_m3sk: 0 },
        }, { unite: 'W/m²K et W/m³sK' }),
        { ...LIGNE('albedo_mensuel', 0.2), etat: 'deja_saisie' },
      ],
    }

    it('le tableau : cinq colonnes, un nom français par réglage, sa valeur avec son unité', async () => {
      mocks.profilDepart.mockResolvedValue({ data: PROFIL_RICHE })
      servirReglages({})
      rendre()
      await screen.findByTestId('acal405-valeur-b0_iam')
      const tableau = screen.getByRole('region', { name: 'Réglages proposés' })
      for (const colonne of ['Remplir', 'Réglage', 'Valeur proposée', 'Source', 'État']) {
        expect(within(tableau).getAllByText(colonne).length).toBeGreaterThan(0)
      }
      const ligne = (cle) => screen.getByTestId(`acal405-valeur-${cle}`)
      expect(ligne('b0_iam')).toHaveTextContent('Reflets du verre')
      expect(ligne('b0_iam')).toHaveTextContent('0,05')
      expect(ligne('mismatch_fabricant_pct')).toHaveTextContent('Écarts entre panneaux')
      expect(ligne('mismatch_fabricant_pct')).toHaveTextContent('2 %')
      expect(ligne('resolution_minutes')).toHaveTextContent('60 minutes')
      expect(ligne('modele_iam')).toHaveTextContent('Fresnel')
      expect(ligne('thermique_par_pose')).toHaveTextContent('29 · 15 W/m²K')
      expect(ligne('thermique_par_pose')).toHaveTextContent('Pose libre · dos isolé')
    })

    it('ACAL1968 — « Qualité des panneaux » dit qu’elle lit la tolérance de la fiche du module et que, sans tolérance, le tri usuel 0 % à +3 % est supposé (D-ACAL-98)', async () => {
      mocks.profilDepart.mockResolvedValue({ data: { ...PROFIL, valeurs: [LIGNE('regle_qualite_module', 'quart_pvsyst')] } })
      servirReglages({})
      rendre()
      const ligne = await screen.findByTestId('acal405-valeur-regle_qualite_module')
      expect(ligne).toHaveTextContent('Qualité des panneaux à la sortie d’usine')
      expect(ligne).toHaveTextContent('Un quart de l’écart, comme PVsyst')
      expect(ligne).toHaveTextContent('tolérance de puissance de la fiche du module')
      expect(ligne).toHaveTextContent('sans tolérance publiée, le tri usuel 0 % à +3 % est supposé')
    })

    it('jamais de JSON ni de clé technique à l’écran', async () => {
      mocks.profilDepart.mockResolvedValue({ data: PROFIL_RICHE })
      servirReglages({})
      rendre()
      await screen.findByTestId('acal405-valeur-b0_iam')
      const carte = screen.getByTestId('acal405-demarrage')
      // Les lignes de valeur ne montrent ni accolade, ni clé du registre.
      for (const v of PROFIL_RICHE.valeurs) {
        const texte = screen.getByTestId(`acal405-valeur-${v.cle}`).textContent
        expect(texte, v.cle).not.toMatch(/[{}[\]"]/)
        expect(texte, v.cle).not.toContain(v.cle)
      }
      expect(carte.textContent).not.toContain('"uc_w_m2k"')
      // Les clés laissées sans valeur sont nommées en français, jamais par leur clé.
      for (const s of PROFIL.sans_source) {
        expect(screen.getByTestId('acal405-sans-source').textContent).not.toContain(s.cle)
      }
    })

    it('la table LID du profil se lit « 1,5 · 1 · 1 · 1,5 % » avec ses cellules, jamais « Plusieurs valeurs »', async () => {
      const { valeurLisible, precisionValeur } = await import('./profilDepart')
      const lid = { perc: { pct: 1.5 }, topcon: { pct: 1 }, hjt: { pct: 1 }, inconnue: { pct: 1.5 } }
      expect(valeurLisible(lid, '%')).toBe('1,5 · 1 · 1 · 1,5 %')
      expect(precisionValeur(lid)).toBe('Cellules PERC · TOPCon · HJT · autre')
      expect(valeurLisible({ pose_libre: { uc_w_m2k: 29 }, dos_isole: { uc_w_m2k: 15 } }, 'W/m²K')).toBe('29 · 15 W/m²K')
    })

    it('toute clé « sans source » servie par le contrat a son nom français', async () => {
      const { LIBELLES_SANS_SOURCE, nomSansSource, estSansSource, libelleReglage } = await import('./profilDepart')
      // L'écran des résultats incomplets lit cette même liste (« Remplir » ne remplit pas ces réglages).
      for (const cle of ['indisponibilite_fenetres', 'modele_degradation']) expect(estSansSource(cle), cle).toBe(true)
      // D-ACAL-82 : salissure, LID, indisponibilité forfaitaire et câbles ont une valeur de départ.
      for (const cle of ['salissure_mensuelle_pct', 'lid_par_techno', 'indisponibilite_forfait_pct', 'ohmique_dc_conception_pct', 'ohmique_ac_conception_pct']) {
        expect(estSansSource(cle), cle).toBe(false)
        expect(libelleReglage(cle).nom, cle).not.toBe('Autre réglage')
      }
      for (const v of PROFIL.valeurs) expect(estSansSource(v.cle), v.cle).toBe(false)
      const libellesRegistre = Object.fromEntries(
        Object.values(REGISTRE).flat().map((r) => [r.cle, r.libelle]))
      for (const s of PROFIL.sans_source) {
        expect(nomSansSource(s.cle), s.cle).not.toBe('Autre réglage')
      }
      // Le nom français d'une clé sans source EST le libellé du registre servi (apostrophes typographiques mises à part).
      for (const [cle, nom] of Object.entries(LIBELLES_SANS_SOURCE)) {
        if (libellesRegistre[cle]) {
          expect(nom.replace(/’/g, "'"), cle).toBe(libellesRegistre[cle].replace(/’/g, "'"))
        }
      }
    })

    it('la source : l’éditeur en clair + « ouvrir » vers la MÊME adresse ; la citation complète reste dans la ligne', async () => {
      mocks.profilDepart.mockResolvedValue({ data: PROFIL })
      servirReglages({})
      rendre()
      const ligne = await screen.findByTestId(`acal405-valeur-${CLE}`)
      expect(ligne).toHaveTextContent('PVsyst')
      const lien = within(ligne).getByRole('link', { name: /Ouvrir la source/ })
      expect(lien).toHaveAttribute('href', PROFIL.valeurs[0].url)
      expect(lien).toHaveAttribute('target', '_blank')
      // La citation intégrale (anglais, adresse entière) : en infobulle et pour les lecteurs d'écran, plus de
      // ligne dépliable (la rangée garde la hauteur de la maquette).
      expect(ligne.querySelector('details')).toBeNull()
      expect(within(ligne).getByTestId(`acal405-citation-${CLE}`)).toHaveTextContent(PROFIL.valeurs[0].reference)
      expect(ligne.querySelector('[title]')).toHaveAttribute('title', expect.stringContaining(PROFIL.valeurs[0].url))
    })

    it('ACAL1826 — la valeur servie au style v2 : texte inchangé, pastille dorée sur une publication, aucune sur une valeur SUPPOSÉE', async () => {
      const publiee = { ...PROFIL.valeurs[0], cle: 'b0_iam', valeur: 0.05, unite: '' }
      const supposee = { ...PROFIL.valeurs[0], cle: 'salissure_mensuelle_pct', valeur: 3, unite: '%',
        reference: 'Profil de départ — valeur de départ SUPPOSÉE, acceptée par le fondateur' }
      mocks.profilDepart.mockResolvedValue({ data: { ...PROFIL, valeurs: [publiee, supposee] } })
      servirReglages({})
      rendre()
      const pastille = (ligne) => ligne.querySelector('.rounded-full.bg-\\[var\\(--cal-action\\)\\]')
      const lignePubliee = await screen.findByTestId('acal405-valeur-b0_iam')
      expect(lignePubliee).toHaveTextContent('0,05')
      expect(pastille(lignePubliee)).not.toBeNull()
      const ligneSupposee = screen.getByTestId('acal405-valeur-salissure_mensuelle_pct')
      expect(ligneSupposee).toHaveTextContent('3 %')
      expect(pastille(ligneSupposee)).toBeNull()
    })

    it('« Remplir les N réglages vides » : N = les lignes vides réellement servies', async () => {
      mocks.profilDepart.mockResolvedValue({ data: PROFIL_RICHE })
      servirReglages({})
      rendre()
      // 6 lignes dont 1 déjà renseignée : 5 vides.
      await waitFor(() => expect(screen.getByTestId('acal405-appliquer')).toHaveTextContent('Remplir les 5 réglages vides'))
      expect(screen.getByRole('link', { name: 'Tout saisir à la main' })).toHaveAttribute(
        'href', '/calepinage/reglages#calx69-section-simulation')
    })

    it('ACAL2002 — « Remplir… » est le bouton doré v2 (mêmes jetons que le bouton d’étape)', async () => {
      const { readFileSync } = await import('node:fs')
      const { resolve } = await import('node:path')
      const style = document.createElement('style')
      style.textContent = ['49-jetons-v2.css', '50-coque-atelier.css']
        .map((f) => readFileSync(resolve(process.cwd(), `src/styles/calepinage/${f}`), 'utf8')).join('\n')
      document.head.appendChild(style)
      try {
        mocks.profilDepart.mockResolvedValue({ data: PROFIL_RICHE })
        servirReglages({})
        rendre()
        const bouton = await screen.findByTestId('acal405-appliquer')
        await waitFor(() => expect(bouton).toBeEnabled())
        expect(bouton).toHaveClass('cal-bouton-or', 'cal-bouton-or-grand')
        expect(bouton.closest('.cal-reglages')).not.toBeNull()
        const cs = getComputedStyle(bouton)
        expect(cs.background).toContain('--cal-action')
        expect(cs.height).toBe('52px')
        expect(cs.borderRadius).toBe('var(--cal-rayon-pile)')
        expect(cs.boxShadow).toBe('var(--cal-action-ombre)')
      } finally { style.remove() }
    })

    it('rien à remplir : le bouton le dit et se désactive', async () => {
      mocks.profilDepart.mockResolvedValue({ data: profilA('deja_saisie') })
      servirReglages({})
      rendre()
      const bouton = await screen.findByTestId('acal405-appliquer')
      // Le profil est lu d'abord (le bouton n'annonce rien pendant la lecture), puis il le dit.
      await waitFor(() => expect(bouton).toHaveTextContent('Aucun réglage à remplir'))
      expect(bouton).toBeDisabled()
    })

    it('les cases « Remplir » : cochées d’office sur un réglage vide, décochables ; une valeur en place n’a pas de case active', async () => {
      mocks.profilDepart.mockResolvedValue({ data: PROFIL_RICHE })
      servirReglages({})
      rendre()
      await screen.findByTestId('acal405-valeur-b0_iam')
      const a = within(screen.getByTestId('acal405-valeur-b0_iam')).getByRole('checkbox')
      const b = within(screen.getByTestId('acal405-valeur-albedo_mensuel')).getByRole('checkbox')
      expect(a).toBeChecked()
      expect(b).not.toBeChecked()
      expect(a).toBeEnabled()
      expect(b).toBeDisabled() // déjà renseignée : jamais remplacée
      fireEvent.click(a)
      expect(a).not.toBeChecked()
      expect(screen.getByTestId('acal405-appliquer')).toHaveTextContent('Remplir les 4 réglages cochés')
    })

    it('« Remplir » n’envoie que les clés cochées (`cles`) ; tout décoché : bouton éteint', async () => {
      mocks.profilDepart.mockResolvedValue({ data: PROFIL_RICHE })
      mocks.appliquerProfilDepart.mockResolvedValue({ data: APPLICATION })
      servirReglages({})
      rendre()
      await screen.findByTestId('acal405-valeur-b0_iam')
      fireEvent.click(within(screen.getByTestId('acal405-valeur-b0_iam')).getByRole('checkbox'))
      fireEvent.click(screen.getByTestId('acal405-appliquer'))
      await screen.findByTestId('acal405-message')
      const cles = mocks.appliquerProfilDepart.mock.calls[0][0]
      expect(cles).toHaveLength(4)
      expect(cles).not.toContain('b0_iam')
      expect(cles).not.toContain('albedo_mensuel') // déjà renseignée
    })

    it('pendant la lecture : lignes grises, boutons éteints, AUCUNE annonce ; un échec dit simplement et propose « Réessayer »', async () => {
      let rejeter
      mocks.profilDepart.mockReturnValueOnce(new Promise((_, ko) => { rejeter = ko }))
      servirReglages({})
      rendre()
      expect((await screen.findAllByTestId('acal405-ligne-en-lecture')).length).toBeGreaterThan(0)
      const bouton = screen.getByTestId('acal405-appliquer')
      expect(bouton).toBeDisabled()
      expect(bouton).not.toHaveTextContent('Aucun réglage')
      expect(screen.getByTestId('acal405-retirer')).toBeDisabled()
      rejeter(new Error('lent'))
      expect(await screen.findByTestId('acal405-echec-lecture')).toHaveTextContent('n’ont pas pu être lus')
      expect(screen.queryAllByTestId('acal405-ligne-en-lecture')).toHaveLength(0)
      mocks.profilDepart.mockResolvedValue({ data: PROFIL })
      fireEvent.click(screen.getByTestId('acal405-reessayer'))
      expect(await screen.findByTestId(`acal405-etat-${CLE}`)).toBeInTheDocument()
      expect(screen.queryByTestId('acal405-echec-lecture')).toBeNull()
    }, 60000)

    it('une valeur déjà en place : case éteinte mais visible, jamais remplacée (D-ACAL-31) ; « ouvrir » souligné', async () => {
      mocks.profilDepart.mockResolvedValue({ data: PROFIL_RICHE })
      servirReglages({})
      rendre()
      const ligne = await screen.findByTestId('acal405-valeur-albedo_mensuel')
      expect(within(ligne).getByRole('checkbox', { name: /Déjà en place, non remplacé/ })).toBeDisabled()
      expect(within(ligne).getByRole('link', { name: /Ouvrir la source/ }).className).toMatch(/(^| )underline( |$)/)
    })

    it('la ligne « Saisir » : les réglages sans valeur publiée mènent à leur saisie', async () => {
      mocks.profilDepart.mockResolvedValue({ data: PROFIL })
      servirReglages({})
      rendre()
      const lien = await screen.findByTestId('acal405-saisir')
      expect(lien).toHaveTextContent('Saisir')
      expect(lien).toHaveAttribute('href', '/calepinage/reglages#calx69-section-simulation')
    })

    it('ACAL1344 — seul sur sa route : la carte s’arrête au bas du CONTENU du défilant (marge incluse), la page ne défile plus', async () => {
      window.history.replaceState(null, '', '/calepinage/reglages/demarrage-rapide')
      const rect = Element.prototype.getBoundingClientRect
      const hauteurFenetre = window.innerHeight
      try {
        window.innerHeight = 900
        // Le cadre de l'ERP : un défilant de 848 px (de 52 à 900) qui garde 32 px de marge basse ; la carte part à 150.
        Element.prototype.getBoundingClientRect = function mesure() {
          const r = (top, bottom) => ({ top, bottom, left: 0, right: 0, width: 0, height: bottom - top, x: 0, y: top, toJSON() {} })
          if (this.dataset?.testid === 'acal405-demarrage') return r(150, 150)
          if (this.dataset?.testid === 'cadre-defilant') return r(52, 900)
          return rect.call(this)
        }
        mocks.profilDepart.mockResolvedValue({ data: PROFIL })
        servirReglages({})
        const { default: DemarrageRapide } = await import('./DemarrageRapide')
        render(<div data-testid="cadre-defilant" style={{ overflowY: 'auto', paddingBottom: '32px' }}><DemarrageRapide /></div>)
        const carte = await screen.findByTestId('acal405-demarrage')
        // 900 − 32 (marge basse du cadre) − 150 (haut de la carte) = 718 : le bas de la carte tombe sur le bas utile.
        expect(carte.style.height).toBe('718px')
      } finally {
        Element.prototype.getBoundingClientRect = rect
        window.innerHeight = hauteurFenetre
        window.history.replaceState(null, '', '/')
      }
    })

    // ACAL1908 (rejeu T3-VAGUEC : 11 px de défilement restants, relevés au navigateur) — CAUSE : chaque ligne du tableau porte une
    // citation `sr-only` (`position: absolute`). Le tableau défile dans une section `overflow: auto` NON positionnée : le bloc
    // conteneur de ces spans était `.layout-content` (positionné par le shell), qui les comptait dans SON défilement à
    // leur position de ligne — le dépassement dépend du nombre de lignes, jamais de la hauteur de la carte (relevé au
    // navigateur : 1 159 px de défilement pour 848, 0 dès que la section est positionnée). La section est donc elle-même le
    // bloc conteneur : tout élément absolu du tableau a un ancêtre positionné DANS la section.
    it('ACAL1908 — le défilement du tableau retient ses éléments absolus : chaque citation `sr-only` a la section pour bloc conteneur', async () => {
      window.history.replaceState(null, '', '/calepinage/reglages/demarrage-rapide')
      try {
        mocks.profilDepart.mockResolvedValue({ data: PROFIL })
        servirReglages({})
        const { default: DemarrageRapide } = await import('./DemarrageRapide')
        render(<DemarrageRapide />)
        const section = await screen.findByRole('region', { name: 'Réglages proposés' })
        await waitFor(() => expect(section.querySelectorAll('.sr-only').length).toBeGreaterThan(0))
        const positionne = (n) => ['relative', 'absolute', 'fixed', 'sticky'].some((c) => n.classList.contains(c))
        const conteneur = (n) => { let p = n.parentElement; while (p && !positionne(p)) p = p.parentElement; return p }
        for (const span of section.querySelectorAll('.sr-only')) {
          const bloc = conteneur(span)
          expect(bloc, 'ancêtre positionné d’une citation sr-only').not.toBeNull()
          expect(section.contains(bloc), 'le bloc conteneur est dans la section qui défile').toBe(true)
        }
      } finally {
        window.history.replaceState(null, '', '/')
      }
    })

    // T4-B4-003 — arrivée depuis Résultats (« Remplir 2 des … réglages vides ») : seuls CES réglages sont cochés, la page
    // annonce le même nombre ; les autres réglages vides de la société restent là, décochés, cochables.
    it('`?reglages=` (venu de Résultats) : seuls ces réglages sont cochés, le bouton dit le même nombre', async () => {
      window.history.replaceState(null, '', '/calepinage/reglages/demarrage-rapide?reglages=b0_iam,modele_iam')
      try {
        mocks.profilDepart.mockResolvedValue({ data: PROFIL_RICHE })
        servirReglages({})
        const { default: DemarrageRapide } = await import('./DemarrageRapide')
        render(<DemarrageRapide />)
        await screen.findByTestId('acal405-valeur-b0_iam')
        const caseDe = (cle) => within(screen.getByTestId(`acal405-valeur-${cle}`)).getByRole('checkbox')
        expect(caseDe('b0_iam')).toBeChecked()
        expect(caseDe('modele_iam')).toBeChecked()
        expect(caseDe('mismatch_fabricant_pct')).not.toBeChecked()
        expect(caseDe('mismatch_fabricant_pct')).toBeEnabled()
        await waitFor(() => expect(screen.getByTestId('acal405-appliquer')).toHaveTextContent('Remplir les 2 réglages cochés'))
        fireEvent.click(caseDe('mismatch_fabricant_pct'))
        expect(screen.getByTestId('acal405-appliquer')).toHaveTextContent('Remplir les 3 réglages cochés')
      } finally {
        window.history.replaceState(null, '', '/')
      }
    })

    it('seul sur sa route : titre de page 28 px, sans second fil d’Ariane (la page en porte déjà un) ; `autonome` le rend', async () => {
      window.history.replaceState(null, '', '/calepinage/reglages/demarrage-rapide')
      try {
        mocks.profilDepart.mockResolvedValue({ data: PROFIL })
        servirReglages({})
        const { default: DemarrageRapide } = await import('./DemarrageRapide')
        render(<DemarrageRapide />)
        expect(await screen.findByRole('heading', { level: 1, name: 'Démarrage rapide' })).toBeInTheDocument()
        expect(screen.queryByRole('navigation', { name: 'Fil d’Ariane' })).toBeNull()
        // Sans appelant, le droit est celui de la personne connectée (doublure : accordé).
        expect(screen.getByTestId('acal405-appliquer')).toBeInTheDocument()
      } finally {
        window.history.replaceState(null, '', '/')
      }
    })
  })

  it('le clic appelle POST puis relit les réglages', async () => {
    mocks.profilDepart.mockResolvedValue({ data: PROFIL })
    mocks.appliquerProfilDepart.mockResolvedValue({ data: APPLICATION })
    servirReglages({})
    rendre()
    // Le bouton reste éteint tant que le profil n'est pas lu (aucun N à annoncer).
    await waitFor(() => expect(screen.getByTestId('acal405-appliquer')).toBeEnabled())
    fireEvent.click(screen.getByTestId('acal405-appliquer'))
    expect(await screen.findByTestId('acal405-message'))
      .toHaveTextContent(`${APPLICATION.appliquees.length} valeurs appliquées`)
    expect(mocks.appliquerProfilDepart).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(mocks.getParametres).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(mocks.profilDepart).toHaveBeenCalledTimes(2))
  })

  it('« Retirer le profil » appelle DELETE', async () => {
    mocks.profilDepart.mockResolvedValue({ data: PROFIL })
    mocks.retirerProfilDepart.mockResolvedValue({ data: { retirees: [{ cle: CLE }], gardees: [] } })
    servirReglages({})
    rendre()
    // Éteint pendant la lecture du profil : le geste n'est offert qu'une fois les réglages lus.
    const retirer = await screen.findByTestId('acal405-retirer')
    await waitFor(() => expect(retirer).toBeEnabled())
    fireEvent.click(retirer)
    expect(await screen.findByTestId('acal405-message')).toHaveTextContent('1 valeurs retirées')
    expect(mocks.retirerProfilDepart).toHaveBeenCalledTimes(1)
  })

  it('sans le droit, pas de bouton', async () => {
    mocks.hasPermission.mockReturnValue(false)
    mocks.profilDepart.mockResolvedValue({ data: PROFIL })
    servirReglages({})
    rendre()
    await screen.findByTestId(`acal405-etat-${CLE}`)
    expect(screen.queryByTestId('acal405-appliquer')).toBeNull()
    expect(screen.queryByTestId('acal405-retirer')).toBeNull()
  })

  it('le préfixe écrit côté écran est celui du contrat, et les références du profil le portent', async () => {
    const { PREFIXE_PROFIL_DEPART } = await import('./profilDepart')
    const contrat = documentContrat('calepinage', 'calepinage_profil_depart')
    expect(PREFIXE_PROFIL_DEPART).toBe(contrat.prefixe_reference)
    for (const v of PROFIL.valeurs) expect(v.reference.startsWith(PREFIXE_PROFIL_DEPART)).toBe(true)
  })
})

describe('ACAL397 — « ce qui manque » → /calepinage/reglages#norme : le champ de la norme existe et prend le focus', () => {
  afterEach(() => { window.history.replaceState(null, '', '/') })

  it('#norme : le sélecteur de la norme est montré, rempli de la section servie, et focalisé', async () => {
    window.history.replaceState(null, '', '/calepinage/reglages#norme')
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()
    const champ = await screen.findByLabelText('Norme applicable')
    expect(champ.id).toBe('norme')
    expect(champ).toHaveValue(REGLAGES.norme_electrique.norme)
    await waitFor(() => expect(document.activeElement).toBe(champ))
  })

  it('enregistrer la norme : un PUT `norme_electrique` qui garde les coefficients servis', async () => {
    const servi = reponseContrat('calepinage', 'parametres_calepinage')
    mocks.getParametres.mockResolvedValue(servi)
    mocks.putParametres.mockResolvedValue({ data: {} })
    rendre()
    fireEvent.change(await screen.findByLabelText('Norme applicable'), { target: { value: '' } })
    fireEvent.click(screen.getByTestId('acal397-norme-enregistrer'))
    await screen.findByTestId('acal397-norme-message')
    const corps = mocks.putParametres.mock.calls[0][0]
    expect(Object.keys(corps)).toEqual(['norme_electrique'])
    expect(corps.norme_electrique.norme).toBeNull()
    expect(corps.norme_electrique.coefficients).toEqual(servi.data.norme_electrique.coefficients)
  })
})

describe('ACAL770 — les valeurs que le serveur ne sait pas honorer sont grisées avec leur motif', () => {
  it('« martin_ruiz » : option désactivée « — indisponible », motif visible ; « tmy » est servie (ACAL1715)', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    // ACAL1715 — l'année type PVGIS est transposée : l'option n'est plus grisée, aucun motif.
    const optionTmy = Array.from(champValeur('mode_meteo').querySelectorAll('option'))
      .find((o) => o.value === 'tmy')
    expect(optionTmy.disabled).toBe(false)
    expect(optionTmy.textContent).toBe('Année type (TMY)')
    expect(screen.queryByTestId('acal770-motif-mode_meteo-tmy')).toBeNull()
    const optionPluri = Array.from(champValeur('mode_meteo').querySelectorAll('option'))
      .find((o) => o.value === 'pluriannuel')
    expect(optionPluri.disabled).toBe(false)

    const optionMartin = Array.from(champValeur('modele_iam').querySelectorAll('option'))
      .find((o) => o.value === 'martin_ruiz')
    expect(optionMartin.disabled).toBe(true)
    expect(optionMartin.textContent).toContain('— indisponible')
    const motif = screen.getByTestId('acal770-motif-modele_iam-martin_ruiz')
    expect(motif).toHaveAttribute('role', 'status')
    expect(motif).toHaveTextContent('Fresnel')
    // une ligne sans valeur non servie ne change pas
    expect(screen.queryByTestId('acal770-motif-attenuation_horizon-true')).toBeNull()
  })

  it('une valeur déjà enregistrée reste affichée et son motif devient un avertissement', async () => {
    // La valeur non servie qui reste au registre : « martin_ruiz » (ACAL1715 a retiré « tmy »).
    const servi = reponseContrat('calepinage', 'parametres_calepinage')
    servi.data.simulation.modele_iam = { valeur: 'martin_ruiz', source: 'societe', reference: '' }
    mocks.getParametres.mockResolvedValue(servi)
    rendre()
    await screen.findByTestId('calx69-ligne-modele_iam')
    expect(champValeur('modele_iam').value).toBe('martin_ruiz')
    expect(screen.getByTestId('acal770-motif-modele_iam-martin_ruiz')).toHaveTextContent('Valeur enregistrée')
  })
})

describe('ACAL947 — toutes les erreurs de réglage d’un coup, sous le bouton', () => {
  it('un 400 à plusieurs clés : une ligne par réglage, sous « Enregistrer », la saisie reste', async () => {
    const multiple = exempleContrat('calepinage', 'parametres_calepinage', 'exemple_refus_multiple')
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    mocks.putParametres.mockRejectedValue({ response: { status: 400, data: multiple } })
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    fireEvent.change(champValeur('sigma_modele_pct'), { target: { value: 'abc' } })
    fireEvent.change(champSource('sigma_modele_pct'), { target: { value: 'societe' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))

    const liste = await screen.findByTestId('acal947-erreurs-bouton')
    const attendues = Object.values(multiple).flatMap((section) => Object.keys(section))
    expect(attendues).toHaveLength(4)
    for (const cle of attendues) {
      const ligne = within(liste).getByTestId(`acal947-erreur-${cle}`)
      expect(ligne.querySelector(`a[href="#calx69-${cle}"]`)).toBeTruthy()
    }
    // la liste est SOUS le bouton « Enregistrer », la saisie n'est pas perdue
    const bouton = screen.getByTestId('calx69-enregistrer')
    expect(bouton.compareDocumentPosition(liste) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(champValeur('sigma_modele_pct').value).toBe('abc')
  })
})

describe('ACAL964 — les listes montrent des mots français et envoient la valeur technique', () => {
  it('« Année type (TMY) » s’affiche pour tmy ; une valeur hors liste reste telle quelle', async () => {
    const servi = reponseContrat('calepinage', 'parametres_calepinage')
    servi.data.simulation.modele_degradation = { valeur: 'inconnu', source: 'societe', reference: '' }
    mocks.getParametres.mockResolvedValue(servi)
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    const options = Array.from(champValeur('mode_meteo').querySelectorAll('option'))
    const tmy = options.find((o) => o.value === 'tmy')
    expect(tmy.textContent).toContain('Année type (TMY)')
    expect(options.find((o) => o.value === 'pluriannuel').textContent).toBe('Plusieurs années réelles')
    // plus aucun mot à tiret bas dans les listes des enums du registre
    for (const ligne of servi.data.registre.simulation.filter((r) => r.type === 'enum')) {
      for (const o of champValeur(ligne.cle).querySelectorAll('option')) {
        if (o.value) expect(o.textContent).not.toMatch(/_/)
      }
    }
    // la valeur stockée hors liste reste affichée telle quelle
    expect(champValeur('modele_degradation').value).toBe('inconnu')
  })

  it('l’aller-retour envoie la clé technique, jamais le libellé', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    mocks.putParametres.mockResolvedValue({ data: {} })
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')
    fireEvent.change(champValeur('mode_meteo'), { target: { value: 'pluriannuel' } })
    fireEvent.change(champSource('mode_meteo'), { target: { value: 'societe' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    expect(mocks.putParametres.mock.calls[0][0].simulation.mode_meteo.valeur).toBe('pluriannuel')
  })
})

describe('ACAL572 — l’écran « Lestage »', () => {
  const lestageServi = () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES })
  }
  const champLestage = (cle) => document.getElementById(`lestage-${cle}`)

  it('la carte porte id="lestage" et chaque ligne id="lestage-<cle>" ; aucune constante physique', async () => {
    lestageServi()
    rendre()
    await screen.findByTestId('acal572-lestage')
    expect(document.getElementById('lestage')).toBe(screen.getByTestId('acal572-lestage'))
    const lignes = REGISTRE.lestage
    // Le nombre de lignes est celui servi — jamais un nombre figé ici.
    expect(lignes.length).toBeGreaterThan(0)
    for (const r of lignes) expect(champLestage(r.cle)).not.toBeNull()
    expect(champLestage('acceleration_pesanteur_m_s2')).toBeNull()
    expect(champLestage('masse_volumique_air_kg_m3')).toBeNull()
    expect(screen.getAllByTestId(/^acal572-ligne-/)).toHaveLength(lignes.length)
  })

  it('saisie ⇒ la section lestage ENTIÈRE est renvoyée, zones intactes', async () => {
    lestageServi()
    rendre()
    await screen.findByTestId('acal572-lestage')

    fireEvent.change(champLestage('largeur_bande_rive_m'), { target: { value: '1.2' } })
    fireEvent.change(screen.getByTestId('acal572-source-largeur_bande_rive_m'), { target: { value: 'notice K2' } })
    fireEvent.click(screen.getByTestId('acal572-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    const corps = mocks.putParametres.mock.calls[0][0]
    expect(Object.keys(corps)).toEqual(['lestage'])
    expect(corps.lestage.zones).toEqual(REGLAGES.lestage.zones)
    expect(corps.lestage.zone_par_defaut).toBe(REGLAGES.lestage.zone_par_defaut)
    expect(corps.lestage.zones_de_pose).toEqual({ largeur_bande_rive_m: { valeur: 1.2, source: 'notice K2' } })
    expect(corps.lestage.vitesse_vent_reference_m_s).toEqual(REGLAGES.lestage.vitesse_vent_reference_m_s)
    expect(await screen.findByTestId('acal572-message')).toBeInTheDocument()
  })

  it('une ligne vide n’est pas envoyée', async () => {
    lestageServi()
    rendre()
    await screen.findByTestId('acal572-lestage')
    fireEvent.click(screen.getByTestId('acal572-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    const { lestage } = mocks.putParametres.mock.calls[0][0]
    expect(lestage.zones_de_pose).toBeUndefined()
    expect(lestage.largeur_coin_m).toBeUndefined()
  })

  it('une valeur sans source : le message serveur s’affiche sous sa ligne', async () => {
    const MOTIF = '« Largeur de la bande de rive » doit porter la RÉFÉRENCE du texte d’où elle vient.'
    lestageServi()
    mocks.putParametres.mockRejectedValue({
      response: { status: 400, data: { 'zones_de_pose.largeur_bande_rive_m': MOTIF } },
    })
    rendre()
    await screen.findByTestId('acal572-lestage')

    fireEvent.change(champLestage('largeur_bande_rive_m'), { target: { value: '1.2' } })
    fireEvent.click(screen.getByTestId('acal572-enregistrer'))

    const erreur = await screen.findByTestId('acal572-erreur-largeur_bande_rive_m')
    expect(erreur).toHaveTextContent(MOTIF)
    expect(within(screen.getByTestId('acal572-ligne-largeur_bande_rive_m')).getByRole('alert')).toBe(erreur)
  })

  it('un nombre illisible est refusé avant tout envoi, sous sa ligne', async () => {
    lestageServi()
    rendre()
    await screen.findByTestId('acal572-lestage')
    const champ = champLestage('largeur_coin_m')
    champ.type = 'text'
    fireEvent.change(champ, { target: { value: 'abc' } })
    fireEvent.click(screen.getByTestId('acal572-enregistrer'))
    expect(await screen.findByTestId('acal572-erreur-largeur_coin_m')).toHaveTextContent('doit être un nombre')
    expect(mocks.putParametres).not.toHaveBeenCalled()
  })

  it('sans le droit de gérer : lecture seule, aucun bouton', async () => {
    mocks.hasPermission.mockReturnValue(false)
    lestageServi()
    rendre()
    await screen.findByTestId('acal572-lestage')
    expect(screen.queryByTestId('acal572-enregistrer')).toBeNull()
    expect(champLestage('largeur_bande_rive_m')).toBeDisabled()
  })
})

describe('ACAL561 — retraits par type d’arête', () => {
  it('la section degagements ENTIÈRE est renvoyée, la ligne égout ajoutée avec sa source', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES })
    rendre()
    await screen.findByTestId('acal561-carte')
    // Servie par le contrat : « égout 0,40 m — notice X ».
    expect(screen.getByTestId('acal561-retrait-egout')).toHaveValue(0.4)
    fireEvent.change(screen.getByTestId('acal561-retrait-rive'), { target: { value: '0.25' } })
    fireEvent.change(screen.getByTestId('acal561-source-rive'), { target: { value: 'notice Y' } })
    fireEvent.click(screen.getByTestId('acal561-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    const corps = mocks.putParametres.mock.calls[0][0]
    expect(Object.keys(corps)).toEqual(['degagements'])
    expect(corps.degagements.retrait_rive_m).toBe(REGLAGES.degagements.retrait_rive_m)
    expect(corps.degagements.allee_technique_m).toBe(REGLAGES.degagements.allee_technique_m)
    expect(corps.degagements.retraits_par_arete).toEqual([
      { type: 'egout', retrait_m: 0.4, source: 'notice X', reference: '' },
      { type: 'rive', retrait_m: 0.25, source: 'notice Y', reference: '' },
    ])
  })

  it('le refus serveur nommé se pose sous la ligne envoyée à ce rang', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    mocks.putParametres.mockRejectedValue({ response: { status: 400, data: {
      'degagements.retraits_par_arete[0].source': 'la source manque' } } })
    rendre()
    await screen.findByTestId('acal561-carte')
    fireEvent.click(screen.getByTestId('acal561-enregistrer'))
    expect(await screen.findByTestId('acal561-erreur-egout')).toHaveTextContent('la source manque')
  })
})

/* ACAL747 — la table des albédos : seules les valeurs UNIQUES imprimées par la page. */
describe('albedoSurfaces.json (ACAL747)', () => {
  it('chaque surface : valeur numérique unique, url https, date ISO ; ecartees ne recoupe pas surfaces', () => {
    expect(albedoSurfaces.surfaces.length).toBeGreaterThan(0)
    for (const s of albedoSurfaces.surfaces) {
      expect(typeof s.valeur, s.surface).toBe('number')
      expect(s.valeur).toBeGreaterThan(0)
      expect(s.valeur).toBeLessThanOrEqual(1)
      expect(s.url).toMatch(/^https:\/\//)
      expect(s.date_lecture).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    }
    const retenues = new Set(albedoSurfaces.surfaces.map((s) => s.surface))
    for (const e of albedoSurfaces.ecartees) {
      expect(retenues.has(e.surface), e.surface).toBe(false)
      expect(e.motif).toBeTruthy()
    }
  })
})

/* ACAL748 — « Remplir depuis une surface (valeur publiée) » sur la ligne albédo. */
describe('ACAL748 — choix d\'une surface pour l\'albédo', () => {
  it('choisir une surface remplit valeur, source et référence ; aucun PUT avant Enregistrer', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES_VIDES })
    rendre()
    await screen.findByTestId('calx69-ligne-albedo_mensuel')
    const surface = albedoSurfaces.surfaces[0]
    const choix = screen.getByTestId('acal748-choix-albedo_mensuel').querySelector('select')
    fireEvent.change(choix, { target: { value: surface.surface } })

    expect(champValeur('albedo_mensuel').value).toBe(String(surface.valeur))
    expect(champSource('albedo_mensuel').value).toBe('texte')
    expect(champReference('albedo_mensuel').value).toBe(
      `PVsyst — Albedo usual coefficients — ${surface.surface} — ${surface.url} — lu le ${surface.date_lecture} — valeur publiée, non mesurée`)
    expect(mocks.putParametres).not.toHaveBeenCalled()

    fireEvent.click(screen.getByTestId('calx69-enregistrer'))
    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(1))
    const envoye = mocks.putParametres.mock.calls[0][0].simulation.albedo_mensuel
    expect(envoye.source).toBe('texte')
    expect(envoye.reference).toContain(surface.url)
  })
})
