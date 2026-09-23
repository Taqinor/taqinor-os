import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import CallLogPopover from './CallLogPopover'

/* VX87 — CallLogPopover : journal d'appel en un geste (issue + note +
   prochaine relance), 1 requête logInteraction + 1 requête updateLead
   optionnelle. */

vi.mock('../../api/crmApi', () => ({
  default: {
    logInteraction: vi.fn(() => Promise.resolve({ data: {} })),
    updateLead: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../lib/toast', () => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

import crmApi from '../../api/crmApi'
import { OUTCOME_LABELS } from '../../components/ChatterTimeline'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import PHRASES from './relances/suite_phrases.json'
import { phraseEffet } from './relances/suite'

afterEach(() => { cleanup(); vi.clearAllMocks() })

// CAD15 — le journal d'appel de la fiche ne clôt aucune touche, mais les
// récepteurs du moteur réagissent à l'issue : chaque issue AFFICHE sa
// conséquence, tirée de la MÊME table de phrases que le panneau « Fait »
// (`relances/suite_phrases.json`, clé `journal`, gardée égale au calcul
// serveur et rejouée par `apps/crm/tests_cad17_parite_promesse_effet.py`).
describe('CAD15 CallLogPopover — chaque issue dit ce qu’elle déclenche', () => {
  const ISSUES = Object.entries(OUTCOME_LABELS).filter(([cle]) => cle)

  it.each(ISSUES)('« %s » affiche sa phrase de conséquence', (cle, libelle) => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    expect(screen.queryByTestId('clp-suite')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText(libelle))
    const attendu = PHRASES.journal[cle].map(phraseEffet).join(' ')
    expect(attendu.length).toBeGreaterThan(0)
    expect(screen.getByTestId('clp-suite')).toHaveTextContent(attendu)
  })

  it('le « Refus » dit la MÊME phrase d’arrêt que le panneau « Fait » d’une touche', () => {
    const [touche] = exempleContrat('crm', 'relance_etape_v2').results
    const arretPanneau = phraseEffet(touche.suites.refuse[0])
    expect(arretPanneau).toBe(phraseEffet('relances_arretees'))
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    fireEvent.click(screen.getByText('Refus'))
    expect(screen.getByTestId('clp-suite')).toHaveTextContent(arretPanneau)
  })

  it('en planification pure (aucun appel), aucune conséquence n’est annoncée', () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} mode="planification" />)
    expect(screen.queryByTestId('clp-suite')).not.toBeInTheDocument()
  })
})

describe('CallLogPopover (VX87)', () => {
  it('ouvre le popover au clic sur le déclencheur par défaut', () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    expect(screen.getByText('Journaliser un appel')).toBeInTheDocument()
  })

  it('propose les 5 issues + un champ note + 4 délais de prochaine action', () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    expect(screen.getByText('Joint')).toBeInTheDocument()
    expect(screen.getByText('Non joint')).toBeInTheDocument()
    expect(screen.getByText('À rappeler')).toBeInTheDocument()
    expect(screen.getByText('Refus')).toBeInTheDocument()
    expect(screen.getByText('Intéressé')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Note (facultative)…')).toBeInTheDocument()
    expect(screen.getByText("Aujourd'hui")).toBeInTheDocument()
    expect(screen.getByText('Demain')).toBeInTheDocument()
  })

  it('« Enregistrer » reste désactivé tant qu\'aucune issue n\'est choisie', () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeDisabled()
  })

  it('journalise en 1 requête logInteraction (issue seule, sans prochaine action)', async () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    fireEvent.click(screen.getByText('Joint'))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.logInteraction).toHaveBeenCalledWith(
      42, expect.objectContaining({ kind: 'appel', outcome: 'joint' }),
    ))
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })

  it('pose la relance dans le MÊME geste quand une prochaine action est choisie', async () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    fireEvent.click(screen.getByText('À rappeler'))
    fireEvent.click(screen.getByText('Dans 3 j'))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(
      42, expect.objectContaining({ relance_date: expect.any(String) }),
    ))
  })

  it('appelle onLogged après journalisation réussie', async () => {
    const onLogged = vi.fn()
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} onLogged={onLogged} />)
    fireEvent.click(screen.getByText('Intéressé'))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(onLogged).toHaveBeenCalled())
  })
})
