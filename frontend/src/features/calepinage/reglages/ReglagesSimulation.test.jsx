import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   CALX69 — LES RÉGLAGES DE SIMULATION ET D'ÉLECTRIQUE, ENFIN SAISISSABLES.
   ----------------------------------------------------------------------------
   Ce que ce test tient :
     * une ligne par clé du registre (`REGISTRE_SIMULATION`,
       `REGISTRE_ELECTRIQUE_SOCIETE`), avec son libellé, son unité, son champ
       « valeur », son sélecteur « source » et son champ « référence » ;
     * les valeurs SERVIES (contrat committé) remplissent les champs, mais le
       REPÈRE doctrinal du registre (les valeurs citées des concurrents) reste
       une simple aide sous la ligne — jamais recopié dans « valeur » ;
     * une clé entamée sans source est REFUSÉE avant tout envoi réseau, le
       champ fautif pointé et le bandeau le nomme (règle fondateur 08/09) ;
     * le refus 400 du serveur (qui nomme la clé) atterrit SOUS la même clé ;
     * une clé jamais entamée est OMISE de l'envoi — aucune valeur par défaut
       n'est écrite.
   ========================================================================== */

const REGLAGES = exempleContrat('calepinage', 'parametres_calepinage')
const REGLAGES_VIDES = exempleContrat('calepinage', 'parametres_calepinage', 'exemple_vide')

const mocks = vi.hoisted(() => ({
  getParametres: vi.fn(),
  putParametres: vi.fn(),
  hasPermission: vi.fn(),
}))

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    parametres: {
      get: (...a) => mocks.getParametres(...a),
      update: (...a) => mocks.putParametres(...a),
    },
  },
}))

vi.mock('../../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => mocks.hasPermission(code),
}))

const {
  default: ReglagesSimulation, REGISTRE_SIMULATION, REGISTRE_ELECTRIQUE_SOCIETE,
} = await import('./ReglagesSimulation')

const rendre = () => render(<ReglagesSimulation />)

const champValeur = (cle) => screen.getByTestId(`calx69-valeur-${cle}`).querySelector('input')
const champSource = (cle) => screen.getByTestId(`calx69-source-${cle}`).querySelector('select')
const champReference = (cle) => screen.getByTestId(`calx69-reference-${cle}`).querySelector('input')

beforeEach(() => {
  vi.clearAllMocks()
  mocks.hasPermission.mockReturnValue(true)
})
afterEach(() => { cleanup() })

describe('CALX69 — une ligne par clé du registre, dans les deux sections', () => {
  it('monte une ligne par clé de `simulation` et `electrique_societe`', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()

    for (const [cle] of REGISTRE_SIMULATION) {
      expect(await screen.findByTestId(`calx69-ligne-${cle}`)).toBeInTheDocument()
      expect(champValeur(cle)).toBeInTheDocument()
      expect(champSource(cle)).toBeInTheDocument()
      expect(champReference(cle)).toBeInTheDocument()
    }
    for (const [cle] of REGISTRE_ELECTRIQUE_SOCIETE) {
      expect(screen.getByTestId(`calx69-ligne-${cle}`)).toBeInTheDocument()
    }
  })

  it('remplit les champs depuis le contrat committé, jamais depuis le repère doctrinal', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    // Valeurs SERVIES par le contrat (`exemple.simulation.mode_meteo`).
    expect(champValeur('mode_meteo').value).toBe(REGLAGES.simulation.mode_meteo.valeur)
    expect(champSource('mode_meteo').value).toBe(REGLAGES.simulation.mode_meteo.source)
    expect(champReference('mode_meteo').value).toBe(REGLAGES.simulation.mode_meteo.reference)
    expect(champValeur('cos_phi_par_defaut').value).toBe(
      String(REGLAGES.electrique_societe.cos_phi_par_defaut.valeur),
    )

    // Une clé JAMAIS saisie (ex. `fenetre_annees`, absente du contrat) reste
    // VIDE — son repère doctrinal (aide) ne se retrouve PAS dans « valeur ».
    expect(champValeur('fenetre_annees').value).toBe('')
    const aide = screen.getByTestId('calx69-aide-fenetre_annees')
    expect(aide).toHaveTextContent('PVGIS')
    expect(champValeur('fenetre_annees').value).not.toContain('PVGIS')
  })
})

describe('CALX69 — une clé entamée sans source est refusée AVANT tout envoi', () => {
  it('pointe le champ fautif, le bandeau le nomme, et n’appelle jamais le serveur', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide'))
    rendre()
    await screen.findByTestId('calx69-ligne-fenetre_annees')

    fireEvent.change(champValeur('fenetre_annees'), { target: { value: '10' } })
    // Aucune source choisie.
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))

    const erreur = await screen.findByTestId('calx69-erreur-fenetre_annees')
    expect(erreur).toHaveTextContent('source')
    expect(screen.getByTestId('calx69-bandeau')).toHaveTextContent('Fenêtre d’années météo')
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
})

describe('CALX69 — aucune clé non saisie n’est envoyée, aucune valeur par défaut', () => {
  it('enregistre une section vide sans rien inventer quand rien n’est tapé', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES_VIDES })
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    fireEvent.click(screen.getByTestId('calx69-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(2))
    expect(mocks.putParametres).toHaveBeenNthCalledWith(1, { simulation: {} })
    expect(mocks.putParametres).toHaveBeenNthCalledWith(2, { electrique_societe: {} })
    expect(screen.queryByTestId('calx69-bandeau')).not.toBeInTheDocument()
  })

  it('envoie les deux sections dans l’ordre `simulation` puis `electrique_societe` quand une clé de chaque est saisie', async () => {
    mocks.getParametres.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage', 'exemple_vide'))
    mocks.putParametres.mockResolvedValue({ data: REGLAGES })
    rendre()
    await screen.findByTestId('calx69-ligne-mode_meteo')

    fireEvent.change(champValeur('mode_meteo'), { target: { value: 'pluriannuel' } })
    fireEvent.change(champSource('mode_meteo'), { target: { value: 'societe' } })
    fireEvent.change(champValeur('cos_phi_par_defaut'), { target: { value: '1' } })
    fireEvent.change(champSource('cos_phi_par_defaut'), { target: { value: 'societe' } })
    fireEvent.click(screen.getByTestId('calx69-enregistrer'))

    await waitFor(() => expect(mocks.putParametres).toHaveBeenCalledTimes(2))
    expect(mocks.putParametres.mock.calls[0][0]).toEqual({
      simulation: { mode_meteo: { valeur: 'pluriannuel', source: 'societe', reference: '' } },
    })
    expect(mocks.putParametres.mock.calls[1][0]).toEqual({
      electrique_societe: { cos_phi_par_defaut: { valeur: 1, source: 'societe', reference: '' } },
    })
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
