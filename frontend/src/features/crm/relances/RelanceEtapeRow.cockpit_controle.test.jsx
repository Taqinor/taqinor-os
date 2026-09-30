// COCKPIT-CONTRÔLE F3 — « la ligne d'étape dit ce qu'elle est ».
//   · le badge de tête affiche la FAMILLE du type lue dans la table du parcours
//     (`typeEtape(etape).famille`), plus la cadence stockée (« Générique » pour
//     une tâche devis posée par le filet) ;
//   · un badge « Tâche » quand la table dit que le type en est une ;
//   · un badge « Reportée N× » (titre : l'échéance d'origine) quand
//     `nb_reports >= 1`.
// Lignes = exemples COMMITTÉS de `relance_etape_v2.json` (PACT10), qui portent
// désormais `type_etape`, `est_tache`, `nb_reports`, `due_initial_at` ; un test
// ne change que le champ qu'il éprouve, jamais la forme.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'
import { PARCOURS, typeEtape } from './parcours'

vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn() }))
vi.mock('../../../api/crmApi', () => ({
  default: { getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })) },
}))

const V2 = exempleContrat('crm', 'relance_etape_v2')
const APPEL = V2.results[0] // contact_appel, cadence contact
const MESSAGE_SUIVI = V2.results[1] // suivi_message, cadence apres_devis
const GENERIQUE = exempleContrat('crm', 'relance_etape_v2', 'exemple_generique').results
const PREMIER_RAPPEL = GENERIQUE[0] // generique, pas une tâche
const DECIDER = GENERIQUE[1] // decider_suite, cadence generique, TÂCHE
const REVEIL = exempleContrat('crm', 'relance_etape_v2', 'exemple_dernier_reveil').results[0]
const DEBRIEF = exempleContrat('crm', 'relance_etape_v2', 'exemple_debrief_visite').results[0]

const famille = (typeId) => PARCOURS.etapes.find((t) => t.id === typeId).famille

afterEach(() => { cleanup(); vi.clearAllMocks() })

function noop() {}

function monter(etape) {
  return render(
    <RelanceEtapeRow
      etape={etape} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop}
    />,
  )
}

describe('F3 — badge de tête : la famille du type, lue dans la table', () => {
  it.each([
    ['contact_appel', APPEL],
    ['suivi_message', MESSAGE_SUIVI],
    ['generique', PREMIER_RAPPEL],
    ['decider_suite', DECIDER],
    ['reveil_message', REVEIL],
    ['debrief', DEBRIEF],
  ])('%s : le badge affiche la famille de la table', (typeId, etape) => {
    // Le contrat sert bien ce type, et la table le retrouve comme l'écran.
    expect(etape.type_etape).toBe(typeId)
    expect(typeEtape(etape).id).toBe(typeId)
    monter(etape)
    expect(screen.getByTestId('badge-famille')).toHaveTextContent(famille(typeId))
  })

  it('une tâche posée par le filet (cadence stockée « generique ») ne dit plus « Générique »', () => {
    expect(DECIDER.cadence).toBe('generique')
    monter(DECIDER)
    expect(screen.queryByText('Générique')).not.toBeInTheDocument()
    expect(screen.getByTestId('badge-famille')).toHaveTextContent(famille('decider_suite'))
  })

  it('les anciens libellés de cadence (« Contact », « Après devis », « Réveil ») ne sont plus affichés', () => {
    monter(MESSAGE_SUIVI)
    const ligne = screen.getByTestId('relance-etape-row')
    expect(within(ligne).queryByText('Après devis')).not.toBeInTheDocument()
    expect(within(ligne).queryByText('Contact')).not.toBeInTheDocument()
    expect(within(ligne).queryByText('Réveil')).not.toBeInTheDocument()
  })

  it('rien d\'autre ne change dans la ligne : canal, heure et boutons restent', () => {
    monter(APPEL)
    const ligne = screen.getByTestId('relance-etape-row')
    expect(within(ligne).getByText('Appel')).toBeInTheDocument()
    expect(within(ligne).getByRole('button', { name: /^Fait$/ })).toBeInTheDocument()
    expect(within(ligne).getByRole('button', { name: /Reporter/ })).toBeInTheDocument()
  })
})

describe('F3 — badge « Tâche »', () => {
  it('présent quand la table dit que le type est une tâche (decider_suite)', () => {
    expect(DECIDER.est_tache).toBe(true)
    monter(DECIDER)
    expect(screen.getByTestId('badge-tache')).toHaveTextContent('Tâche')
  })

  it('présent aussi pour une étape « Préparer le devis » posée avec une cadence d\'appel', () => {
    monter({ ...DECIDER, type_etape: 'devis', cle: 'devis', libelle: 'Préparer et envoyer le devis (ou fixer un rappel)' })
    expect(screen.getByTestId('badge-tache')).toBeInTheDocument()
    expect(screen.getByTestId('badge-famille')).toHaveTextContent(famille('devis'))
  })

  it.each([
    ['un appel de prise de contact', APPEL],
    ['un message de suivi', MESSAGE_SUIVI],
    ['une étape générique', PREMIER_RAPPEL],
    ['un débrief de visite', DEBRIEF],
  ])('absent sur %s', (unused, etape) => {
    monter(etape)
    expect(screen.queryByTestId('badge-tache')).not.toBeInTheDocument()
  })
})

describe('F3 — badge « Reportée N× »', () => {
  it('absent tant que l\'échéance n\'a jamais été repoussée (nb_reports = 0)', () => {
    expect(APPEL.nb_reports).toBe(0)
    monter(APPEL)
    expect(screen.queryByTestId('badge-reportee')).not.toBeInTheDocument()
    expect(screen.queryByText(/Reportée/)).not.toBeInTheDocument()
  })

  it('« Reportée 2× », avec l\'échéance d\'origine en titre (JJ/MM à Casablanca)', () => {
    monter({ ...APPEL, nb_reports: 2, due_initial_at: '2026-09-03T09:00:00Z' })
    const badge = screen.getByTestId('badge-reportee')
    expect(badge).toHaveTextContent('Reportée 2×')
    expect(badge).toHaveAttribute('title', 'Prévue à l\'origine le 03/09')
  })

  it('« Reportée 1× » dès le premier report', () => {
    monter({ ...APPEL, nb_reports: 1, due_initial_at: '2026-09-30T08:00:00Z' })
    expect(screen.getByTestId('badge-reportee')).toHaveTextContent('Reportée 1×')
  })

  it('l\'échéance d\'origine se lit à l\'heure de Casablanca, pas en UTC (23:30 UTC = le lendemain)', () => {
    monter({ ...APPEL, nb_reports: 3, due_initial_at: '2026-09-03T23:30:00Z' })
    expect(screen.getByTestId('badge-reportee')).toHaveAttribute('title', 'Prévue à l\'origine le 04/09')
  })

  it('sans échéance d\'origine servie : le badge reste, sans titre inventé', () => {
    monter({ ...APPEL, nb_reports: 2, due_initial_at: null })
    const badge = screen.getByTestId('badge-reportee')
    expect(badge).toHaveTextContent('Reportée 2×')
    expect(badge).not.toHaveAttribute('title')
  })

  it('tâche reportée : les deux badges cohabitent', () => {
    monter({ ...DECIDER, nb_reports: 2, due_initial_at: '2026-09-20T09:00:00Z' })
    expect(screen.getByTestId('badge-tache')).toBeInTheDocument()
    expect(screen.getByTestId('badge-reportee')).toHaveTextContent('Reportée 2×')
  })
})
