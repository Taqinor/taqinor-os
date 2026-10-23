import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act, render, screen, cleanup } from '@testing-library/react'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'

/* AGQ25 (C-AGQ-024) — le devis automatique lancé depuis le GÉNÉRATEUR
   transmet `onAlertes` : le journal `alertes` du serveur (articles « prix à
   renseigner » omis, PVGIS, alertes internes) est conservé par le hook et
   rendu par LE composant de la fiche lead (`AlertesDevisAuto`).
   Nouveau fichier car : le hook n'avait aucun module de test (chemin réel
   `pages/ventes/generator/hooks/`, la ligne du plan citait `pages/crm/leads/`).
   Test-du-test : retirer `onAlertes: setAlertesAuto` de `runAutoQuote` fait
   repasser « journal_affiche_apres_creation » au rouge. */

const createAutoQuote = vi.fn()
vi.mock('../../../../features/ventes/autoQuote', () => ({
  LEAD_TYPE_TO_MODE: { residentiel: 'residentiel', agricole: 'agricole' },
  createAutoQuote: (...a) => createAutoQuote(...a),
}))
vi.mock('../../../../api/crmApi', () => ({ default: { getLead: vi.fn(() => new Promise(() => {})) } }))
vi.mock('../../../../api/ventesApi', () => ({ default: { getPrefillSite: vi.fn(() => new Promise(() => {})) } }))

const { useLeadClientEcran } = await import('./useLeadClientEcran')
const { default: AlertesDevisAuto } = await import('../../../crm/leads/AlertesDevisAuto')

afterEach(() => { cleanup(); vi.clearAllMocks() })

const ctx = () => ({
  leads: [], structuresCatalogue: [], setSaving: vi.fn(), setErrors: vi.fn(),
  dispatchSizing: vi.fn(), finish: vi.fn(), leadId: '', setLeadId: vi.fn(),
  clientId: '', setClientId: vi.fn(), setFHiver: vi.fn(), setFEte: vi.fn(),
  setMonthly: vi.fn(), setConsoMensuelle: vi.fn(), setHorsReseau: vi.fn(),
  horsReseauTouched: false, setPompeCv: vi.fn(), setPompeHmt: vi.fn(),
  setPompeDebit: vi.fn(), appliquerEntreesPompage: vi.fn(),
  facturesProtegeesRef: { current: false }, reinitialiserFactures: vi.fn(),
  setAvisFactures: vi.fn(), consoMensuelle: '', pompeCv: '', pompeHmt: '',
  pompeDebit: '', baremeSociete: null,
})

describe('alertes', () => {
  it('test_journal_affiche_apres_creation', async () => {
    const alertes = exempleContrat('ventes', 'etude_ci_preview').alertes
    createAutoQuote.mockImplementation(async ({ onAlertes }) => {
      onAlertes?.(alertes)
      return 615
    })
    const contexte = ctx()
    const { result } = renderHook(() => useLeadClientEcran(contexte))
    await act(async () => {
      await result.current.runAutoQuote({ id: 91, type_installation: 'agricole' }, '0')
    })
    expect(typeof createAutoQuote.mock.calls[0][0].onAlertes).toBe('function')
    expect(contexte.finish).toHaveBeenCalledWith(615)
    expect(result.current.alertesAuto).toEqual(alertes)

    render(<AlertesDevisAuto alertes={result.current.alertesAuto} />)
    const bloc = screen.getByTestId('ldp-alertes-auto')
    for (const a of alertes) expect(bloc).toHaveTextContent(a.message)
    expect(screen.queryAllByTestId('ldp-alerte-interne'))
      .toHaveLength(alertes.filter((a) => a.interne === true).length)
  })

  it('aucune alerte : rien n’est rendu', () => {
    const { container } = render(<AlertesDevisAuto alertes={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
