/* ACAL154 — l'onglet « Décisions électriques ».

   Les réponses viennent de l'exemple COMMITTÉ `calepinage_entree_electrique.json` ; seule la
   façade `calepinageApi` est mockée, le composant ne l'est pas. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => {
  const lecture = vi.fn()
  const ecriture = vi.fn()
  const evaluation = vi.fn()
  return { default: { calepinages: { entreeElectrique: lecture, enregistrerEntreeElectrique: ecriture, evaluerElectrique: evaluation } } }
})

import calepinageApi from '../../../api/calepinageApi'
import DecisionsElectriques from './DecisionsElectriques'
import { corpsDeDecisions, depuisEntree } from './DecisionsElectriques.helpers'

const EXEMPLE = exempleContrat('calepinage', 'calepinage_entree_electrique')
const VIDE = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_vide')

const servir = (entree) => calepinageApi.calepinages.entreeElectrique
  .mockResolvedValue({ data: { ...EXEMPLE, entree } })
const rendre = () => render(
  <MemoryRouter><DecisionsElectriques calepinageId={5} /></MemoryRouter>,
)
const champ = (cle) => document.getElementById(`acal154-champ-${cle}`)
const poste = () => calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0][1]

// ACAL1973 — les questions du dossier viennent de l'évaluation servie (`protections.questions[]`, contrat
// `calepinage_evaluation_electrique.json`) ; corps VIDE, comme le verdict (on lit ce qui est enregistré).
const EVALUATION = exempleContrat('calepinage', 'calepinage_evaluation_electrique', 'exemple_vide')

beforeEach(() => {
  vi.clearAllMocks()
  calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data: EVALUATION })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DecisionsElectriques (ACAL154)', () => {
  it('T4-X7-011 — une décision enregistrée prévient l’écran (la liste « Prêt à envoyer ? » se relit)', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    servir(VIDE.entree)
    const surEnregistre = vi.fn()
    render(<MemoryRouter><DecisionsElectriques calepinageId={5} surEnregistre={surEnregistre} /></MemoryRouter>)
    await userEvent.click(await screen.findByTestId('acal154-enregistrer'))
    await waitFor(() => expect(surEnregistre).toHaveBeenCalledTimes(1))
  })

  it('écarter sans motif affiche le refus sous la ligne', async () => {
    servir(VIDE.entree)
    const message = 'Organe « PAC1 » écarté sans motif : écarter un organe exigé par une règle demande une justification écrite.'
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
      response: { status: 400, data: { 'protections.ecartes.motif': message } },
    })

    rendre()
    await userEvent.click(await screen.findByTestId('acal154-ajouter-ecarte'))
    await userEvent.type(champ('ecarte-0-repere'), 'PAC1')
    await userEvent.click(screen.getByTestId('acal154-enregistrer'))

    expect(await screen.findByTestId('acal154-ecarte-0-erreur')).toHaveTextContent(message)
    expect(poste().protections.ecartes).toEqual([{ repere: 'PAC1', motif: '' }])
  })

  it('écarter avec motif poste protections.ecartes (clé entière) et relit les décisions', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    calepinageApi.calepinages.entreeElectrique
      .mockResolvedValueOnce({ data: { ...EXEMPLE, entree: VIDE.entree } })
      .mockResolvedValueOnce({
        data: {
          ...EXEMPLE,
          entree: { ...VIDE.entree, protections: { ecartes: [{ repere: 'PAC1', motif: 'Liaison courte' }], ajouts: [] } },
        },
      })

    rendre()
    await userEvent.click(await screen.findByTestId('acal154-ajouter-ecarte'))
    await userEvent.type(champ('ecarte-0-repere'), 'PAC1')
    await userEvent.type(champ('ecarte-0-motif'), 'Liaison courte')
    await userEvent.click(screen.getByTestId('acal154-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalledTimes(1))
    expect(poste().protections).toEqual({ ecartes: [{ repere: 'PAC1', motif: 'Liaison courte' }], ajouts: [] })
    // La relecture du GET : la décision stockée est ce que l'écran montre.
    await waitFor(() => expect(calepinageApi.calepinages.entreeElectrique).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(champ('ecarte-0-motif')).toHaveValue('Liaison courte'))
  })

  it('un organe ajouté poste désignation, quantité et motif', async () => {
    servir(VIDE.entree)
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })

    rendre()
    await userEvent.click(await screen.findByTestId('acal154-ajouter-ajout'))
    await userEvent.type(champ('ajout-0-designation'), 'Parafoudre AC')
    await userEvent.type(champ('ajout-0-quantite'), '2')
    await userEvent.type(champ('ajout-0-motif'), 'Exigence du bureau')
    await userEvent.click(screen.getByTestId('acal154-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalled())
    expect(poste().protections.ajouts).toEqual([
      { designation: 'Parafoudre AC', motif: 'Exigence du bureau', quantite: 2 },
    ])
  })

  it('terre sans date refusée sous le champ date', async () => {
    servir(VIDE.entree)
    const message = 'Mesure saisie sans sa date de mesure.'
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
      response: { status: 400, data: { 'terre.date_mesure_prise': message } },
    })

    rendre()
    await screen.findByTestId('acal154-formulaire')
    await userEvent.type(champ('point_mesure_prise'), 'Piquet nord')
    await userEvent.click(champ('justification_continuite'))
    await userEvent.click(screen.getByTestId('acal154-enregistrer'))

    expect(await screen.findByTestId('acal154-erreur-date_mesure_prise')).toHaveTextContent(message)
    expect(poste().terre).toEqual({ justification_continuite: true, point_mesure_prise: 'Piquet nord' })
  })

  it('polystring poste groupes {mppt, pans}', async () => {
    servir(VIDE.entree)
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })

    rendre()
    await userEvent.click(await screen.findByTestId('acal154-ajouter-groupe'))
    await userEvent.type(champ('groupe-0-mppt'), '1')
    await userEvent.type(champ('groupe-0-pans'), 'PAN-A, PAN-B')
    await userEvent.click(screen.getByTestId('acal154-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalled())
    expect(poste().polystring).toEqual([{ mppt: 1, pans: ['PAN-A', 'PAN-B'] }])
  })

  it('un refus de groupe se pose sous la ligne du groupe visé', async () => {
    servir(VIDE.entree)
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
      response: { status: 400, data: { 'groupes.0.mppt': 'Entrée MPPT 9 absente de la fiche.' } },
    })

    rendre()
    await userEvent.click(await screen.findByTestId('acal154-ajouter-groupe'))
    await userEvent.type(champ('groupe-0-mppt'), '9')
    await userEvent.click(screen.getByTestId('acal154-enregistrer'))

    expect(await screen.findByTestId('acal154-groupe-0-erreur')).toHaveTextContent('Entrée MPPT 9 absente de la fiche.')
  })

  it('une entrée stockée se renvoie à l identique, une absente n est pas inventée', () => {
    const stockee = {
      protections: { ecartes: [{ repere: 'PAC1', motif: 'Liaison courte' }], ajouts: [] },
      terre: { justification_continuite: true, resistance_ohm: 20 },
      polystring: [{ mppt: 1, pans: ['PAN-A', 'PAN-B'] }],
    }
    expect(corpsDeDecisions(depuisEntree(stockee), stockee)).toEqual(stockee)
    expect(corpsDeDecisions(depuisEntree({}), {})).toEqual({})
  })

  it('ACAL1550 : répondre « oui » à l’arrêt rapide s’enregistre dans protections.exigences.arret_rapide et se relit', async () => {
    servir(VIDE.entree)
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })

    rendre()
    await userEvent.selectOptions(await screen.findByLabelText(/arrêt rapide exigé/), 'oui')
    await userEvent.click(screen.getByTestId('acal154-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalled())
    expect(poste().protections.exigences).toEqual({ arret_rapide: 'oui' })
    cleanup()
    servir({ protections: { ecartes: [], ajouts: [], exigences: { arret_rapide: 'oui', paratonnerre: { present: 'non' } } } })
    rendre()
    expect(await screen.findByLabelText(/arrêt rapide exigé/)).toHaveValue('oui')
    expect(corpsDeDecisions(depuisEntree({ protections: { exigences: { arret_rapide: 'non' } } }), {}))
      .toEqual({ protections: { ecartes: [], ajouts: [], exigences: { arret_rapide: 'non' } } })
  })

  it('ACAL1973 : l’étiquette de l’arrêt rapide est la question SERVIE (`protections.questions[].question`), jamais un texte recopié', async () => {
    servir(VIDE.entree)
    const question = 'Le dossier exige-t-il la coupure rapide côté DC ?'
    const questions = [{ ...EVALUATION.protections.questions[0], question }]
    calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data: { ...EVALUATION, protections: { questions } } })

    rendre()

    expect(await screen.findByLabelText(question)).toBeInTheDocument()
    expect(calepinageApi.calepinages.evaluerElectrique).toHaveBeenCalledWith(5, {})
    expect(screen.queryByText(/Coupure d’urgence DC/)).toBeNull()
  })

  it('une lecture en panne le DIT', async () => {
    calepinageApi.calepinages.entreeElectrique.mockRejectedValue(new Error('boum'))

    rendre()

    expect(await screen.findByTestId('acal154-erreur')).toBeInTheDocument()
  })
})
