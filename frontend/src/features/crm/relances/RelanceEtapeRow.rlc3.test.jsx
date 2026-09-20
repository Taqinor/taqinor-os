// RLC3 (relevé fondateur du 08/09/2026) — « Fait » conditionné à l'action
// RÉELLE sur une touche message : le panneau rappelle si le message a été
// ouvert (activité « WhatsApp ouvert », servie par le serveur dans
// `message_ouvert_le`) et, sinon, demande une confirmation EXPLICITE — jamais
// un blocage dur (Meryem peut avoir écrit depuis son téléphone).
//
// Étapes de départ = les deux résultats du contrat COMMITTÉ
// `relance_etape_v2.json` (le premier : canal appel, message_ouvert_le null ;
// le second : canal whatsapp, message ouvert) — jamais un objet retapé.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn() }))

const [ETAPE_APPEL, ETAPE_MESSAGE] = exempleContrat('crm', 'relance_etape_v2').results

afterEach(() => { cleanup(); vi.clearAllMocks() })

function noop() {}

const monter = (etape, onFait = noop) => render(
  <RelanceEtapeRow
    etape={etape} onFait={onFait} onSauter={noop} onReporter={noop}
    onOuvrirMessage={noop}
  />,
)

const heureCasablanca = (iso) => new Intl.DateTimeFormat('fr-FR', {
  hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Casablanca',
}).format(new Date(iso))

describe('RLC3 — rappel « message ouvert ? » sur une touche message', () => {
  it('message OUVERT : le panneau le rappelle avec son heure, et ne demande rien de plus', () => {
    monter(ETAPE_MESSAGE)
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByTestId('rappel-message-ouvert')).toHaveTextContent(
      heureCasablanca(ETAPE_MESSAGE.message_ouvert_le))
    expect(screen.queryByTestId('confirmer-sans-ouverture')).toBeNull()
  })

  it('message NON ouvert : la confirmation explicite est exigée avant Confirmer', () => {
    monter({ ...ETAPE_MESSAGE, message_ouvert_le: null })
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByTestId('confirmer-sans-ouverture')).toBeInTheDocument()
    // Une issue choisie NE suffit pas : la question reste posée.
    fireEvent.click(screen.getByRole('button', { name: 'Intéressé' }))
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
  })

  it('la confirmation cochée débloque le geste et le TRACE (jamais un blocage dur)', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    monter({ ...ETAPE_MESSAGE, message_ouvert_le: null }, onFait)
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Intéressé' }))
    fireEvent.click(screen.getByRole('checkbox'))
    const confirmer = screen.getByRole('button', { name: 'Confirmer' })
    expect(confirmer).not.toBeDisabled()
    fireEvent.click(confirmer)
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_MESSAGE.id,
      {
        outcome: 'interesse',
        body: 'Marquée faite sans ouverture du message depuis l’ERP.',
      }))
  })

  it('message ouvert : le geste part SANS mention de non-ouverture', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    monter(ETAPE_MESSAGE, onFait)
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Intéressé' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_MESSAGE.id, { outcome: 'interesse' }))
  })

  it('une touche APPEL ne pose jamais la question (son issue est déjà obligatoire)', () => {
    monter(ETAPE_APPEL)
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.queryByTestId('rappel-message-ouvert')).toBeNull()
    expect(screen.queryByTestId('confirmer-sans-ouverture')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Client joint' }))
    expect(screen.getByRole('button', { name: 'Confirmer' })).not.toBeDisabled()
  })
})
