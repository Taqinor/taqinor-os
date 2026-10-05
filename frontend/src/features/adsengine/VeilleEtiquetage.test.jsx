import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react'
import { documentContrat } from '../../test/fixtures/contractSamples'

/* VEIL32 — Étiquetage à l'aveugle. Charges utiles = contrats committés
   veille_annonceur.json et veille_echantillon.json (PACT13). L'annonceur est
   volontairement servi AVEC son verdict machine : l'écran ne doit RIEN en
   montrer. */

const ANNONCEUR = documentContrat('adsengine', 'veille_annonceur').exemple
const ECHANTILLON = documentContrat('adsengine', 'veille_echantillon').exemple
const TAILLE_TEST = ECHANTILLON.test.length

const etat = { restants: TAILLE_TEST }
const mocks = vi.hoisted(() => ({ annonceurs: vi.fn(), echantillon: vi.fn(), etiquette: vi.fn() }))
vi.mock('./adsengineApi', () => ({ default: { veille: mocks } }))

import VeilleEtiquetage from './VeilleEtiquetage'

beforeEach(() => {
  vi.clearAllMocks()
  etat.restants = TAILLE_TEST
  mocks.annonceurs.mockImplementation((params) => Promise.resolve({
    data: params.sans_etiquette
      ? { count: etat.restants, results: etat.restants ? [ANNONCEUR] : [] }
      : { count: TAILLE_TEST, results: [ANNONCEUR] },
  }))
  mocks.echantillon.mockResolvedValue({ data: ECHANTILLON })
  mocks.etiquette.mockImplementation(() => {
    etat.restants -= 1
    return Promise.resolve({ data: { ...ANNONCEUR, classe: null, verdict: null } })
  })
})

describe('VeilleEtiquetage', () => {
  it('mode aveugle : ni classe machine ni motif dans le DOM', async () => {
    const { container } = render(<VeilleEtiquetage decouverteId={17} />)
    expect(await screen.findByTestId('ae-veille-etiquetage-fiche')).toBeTruthy()
    expect(container.textContent).not.toContain(ANNONCEUR.verdict.motif_fr)
    expect(container.textContent).not.toContain('décidé par')
    expect(mocks.annonceurs).toHaveBeenCalledWith(expect.objectContaining({
      decouverte: 17, jeu: 'test', aveugle: '1', sans_etiquette: '1' }))
    // aucune classe pré-sélectionnée
    expect(screen.getByTestId('ae-veille-etiquetage-enregistrer').disabled).toBe(true)
  })

  it('compteur servi par le serveur, étiquette par etiquette/ (jamais verdict/)', async () => {
    render(<VeilleEtiquetage decouverteId={17} />)
    expect((await screen.findByTestId('ae-veille-etiquetage-compteur')).textContent)
      .toBe(`0 / ${TAILLE_TEST}`)
    fireEvent.click(screen.getByTestId('ae-veille-etiquetage-classe-hors_sujet'))
    fireEvent.click(screen.getByTestId('ae-veille-etiquetage-drop-non'))
    fireEvent.click(screen.getByTestId('ae-veille-etiquetage-enregistrer'))
    await waitFor(() => expect(mocks.etiquette).toHaveBeenCalledWith(
      ANNONCEUR.id, { classe: 'hors_sujet', dropshipper: 'non' }))
    await waitFor(() => expect(screen.getByTestId('ae-veille-etiquetage-compteur').textContent)
      .toBe(`1 / ${TAILLE_TEST}`))
  })

  it('reprise après fermeture de l’onglet au bon compteur', async () => {
    etat.restants = TAILLE_TEST - 3
    render(<VeilleEtiquetage decouverteId={17} />)
    await screen.findByTestId('ae-veille-etiquetage-compteur')
    cleanup()
    render(<VeilleEtiquetage decouverteId={17} />)
    expect((await screen.findByTestId('ae-veille-etiquetage-compteur')).textContent)
      .toBe(`3 / ${TAILLE_TEST}`)
  })

  it('tirage : tailles obligatoires, puis appel echantillon/', async () => {
    render(<VeilleEtiquetage decouverteId={17} />)
    fireEvent.click(await screen.findByTestId('ae-veille-etiquetage-tirer'))
    expect(await screen.findByTestId('ae-veille-etiquetage-erreur')).toBeTruthy()
    expect(mocks.echantillon).not.toHaveBeenCalled()
    fireEvent.change(screen.getByTestId('ae-veille-etiquetage-taille-etalonnage'), { target: { value: '5' } })
    fireEvent.change(screen.getByTestId('ae-veille-etiquetage-taille-test'), { target: { value: '10' } })
    fireEvent.click(screen.getByTestId('ae-veille-etiquetage-tirer'))
    await waitFor(() => expect(mocks.echantillon).toHaveBeenCalledWith(17, {
      taille_etalonnage: 5, taille_test: 10 }))
    expect((await screen.findByTestId('ae-veille-etiquetage-message')).textContent)
      .toContain(`${ECHANTILLON.etalonnage.length} + ${ECHANTILLON.test.length}`)
  })
})
