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

// EZ1 — le client `recordsApi` est RÉEL : seul le transport (axios) est simulé,
// pour lire l'endpoint et le corps réellement postés par l'objet de relance.
const { apiPost } = vi.hoisted(() => ({
  apiPost: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))
vi.mock('../../api/axios', () => ({ default: { post: apiPost } }))

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

/* VX87 — structure du journal : les issues proposées viennent de la table
   partagée `OUTCOME_LABELS` (hors la clé vide), les 4 délais de prochaine
   action posent J+0/1/3/7 en DATE LOCALE. Date figée (seule `Date` est
   simulée) pour que « aujourd'hui + N » soit exact. */
describe('VX87 — issues proposées et délais de prochaine action', () => {
  afterEach(() => { vi.useRealTimers() })

  it('propose exactement les issues d’OUTCOME_LABELS, sans la clé vide', () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    const groupe = screen.getByRole('group', { name: "Résultat de l'appel" })
    const attendues = Object.entries(OUTCOME_LABELS).filter(([cle]) => cle)
    const proposees = [...groupe.querySelectorAll('button')]
    expect(proposees.map((b) => b.dataset.outcome)).toEqual(attendues.map(([cle]) => cle))
    expect(proposees.map((b) => b.textContent)).toEqual(attendues.map(([, libelle]) => libelle))
  })

  it.each([
    ["Aujourd'hui", '2026-08-10'],
    ['Demain', '2026-08-11'],
    ['Dans 3 j', '2026-08-13'],
    ['Dans 7 j', '2026-08-17'],
  ])('« %s » pose la relance au %s, en date locale', async (libelle, attendu) => {
    vi.useFakeTimers({ toFake: ['Date'] })
    // 23 h 30 locales : un ISO UTC décalerait le jour.
    vi.setSystemTime(new Date(2026, 7, 10, 23, 30))
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} mode="planification" />)
    fireEvent.click(screen.getByText(libelle))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(42, { relance_date: attendu }))
  })
})

/* EZ1 — le popover EST le planificateur rapide : une relance déjà posée est
   AFFICHÉE et jamais écrasée sans choix explicite, une seule valeur de date,
   pas d'heure native (la date part en local), un objet crée une vraie activité. */
describe('EZ1 — la relance existante n’est jamais écrasée en silence', () => {
  const frFr = (annee, mois, jour) => new Date(annee, mois - 1, jour).toLocaleDateString('fr-FR')

  afterEach(() => { vi.useRealTimers() })

  function ouvrirAvecRelance(relanceActuelle) {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 7, 10, 9, 0))
    return render(
      <CallLogPopover
        leadId={42} open onOpenChange={() => {}} relanceActuelle={relanceActuelle}
      />,
    )
  }

  it('sans relance existante, la date choisie s’écrit directement (aucun conflit à trancher)', async () => {
    ouvrirAvecRelance(null)
    fireEvent.click(screen.getByText('Joint'))
    fireEvent.click(screen.getByText('Demain'))
    expect(screen.queryByRole('group', { name: 'Relance déjà planifiée' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(42, { relance_date: '2026-08-11' }))
  })

  it('une relance existante différente est AFFICHÉE avec les deux choix, « Garder » par défaut', () => {
    ouvrirAvecRelance('2026-08-20')
    fireEvent.click(screen.getByText('Demain'))
    const groupe = screen.getByRole('group', { name: 'Relance déjà planifiée' })
    expect(groupe).toHaveTextContent(`Une relance est déjà prévue le ${frFr(2026, 8, 20)}`)
    const garder = screen.getByRole('button', { name: `Garder le ${frFr(2026, 8, 20)}` })
    const remplacer = screen.getByRole('button', { name: `Remplacer par le ${frFr(2026, 8, 11)}` })
    expect(garder).toHaveAttribute('aria-pressed', 'true')
    expect(remplacer).toHaveAttribute('aria-pressed', 'false')
  })

  it('le défaut ne détruit RIEN : l’appel est journalisé mais la relance existante reste', async () => {
    ouvrirAvecRelance('2026-08-20')
    fireEvent.click(screen.getByText('Joint'))
    fireEvent.click(screen.getByText('Demain'))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.logInteraction).toHaveBeenCalled())
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })

  it('« Remplacer » est le seul chemin vers l’écriture de la nouvelle date', async () => {
    ouvrirAvecRelance('2026-08-20')
    fireEvent.click(screen.getByText('Joint'))
    fireEvent.click(screen.getByText('Demain'))
    fireEvent.click(screen.getByRole('button', { name: `Remplacer par le ${frFr(2026, 8, 11)}` }))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(42, { relance_date: '2026-08-11' }))
  })

  it('re-choisir la MÊME date n’est pas un conflit : écriture idempotente, aucune décision', async () => {
    ouvrirAvecRelance('2026-08-11')
    fireEvent.click(screen.getByText('Joint'))
    fireEvent.click(screen.getByText('Demain'))
    expect(screen.queryByRole('group', { name: 'Relance déjà planifiée' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(42, { relance_date: '2026-08-11' }))
  })

  it('aucune date choisie = aucune écriture de relance (la relance existante n’est même pas proposée)', async () => {
    ouvrirAvecRelance('2026-08-20')
    fireEvent.click(screen.getByText('Joint'))
    expect(screen.queryByRole('group', { name: 'Relance déjà planifiée' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(crmApi.logInteraction).toHaveBeenCalled())
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })
})

describe('EZ1 — une seule valeur de date, des chips qui la REMPLISSENT', () => {
  afterEach(() => { vi.useRealTimers() })

  it('un chip remplit la date libre, un second clic la vide, « Effacer » aussi', () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 7, 10, 9, 0))
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} mode="planification" />)
    const champ = screen.getByRole('button', { name: 'Date de relance' })
    expect(champ).toHaveTextContent('jj/mm/aaaa')
    fireEvent.click(screen.getByText('Demain'))
    expect(champ).toHaveTextContent(new Date(2026, 7, 11).toLocaleDateString('fr-FR'))
    fireEvent.click(screen.getByText('Demain'))
    expect(champ).toHaveTextContent('jj/mm/aaaa')
    fireEvent.click(screen.getByText('Dans 3 j'))
    fireEvent.click(screen.getByRole('button', { name: 'Effacer la date' }))
    expect(champ).toHaveTextContent('jj/mm/aaaa')
  })

  it('PAS D’HEURE NATIVE : aucun champ datetime-local ; l’heure promise n’existe qu’avec une date', () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} />)
    expect(document.querySelector('input[type="datetime-local"]')).toBeNull()
    expect(screen.queryByLabelText('Heure promise (facultative)')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Demain'))
    expect(screen.getByLabelText('Heure promise (facultative)')).toHaveAttribute('type', 'time')
    expect(document.querySelector('input[type="datetime-local"]')).toBeNull()
  })
})

describe('EZ1 — un OBJET crée une vraie activité datée (zéro backend)', () => {
  afterEach(() => { vi.useRealTimers() })

  function planifier(objet) {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 7, 10, 9, 0))
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} mode="planification" />)
    fireEvent.click(screen.getByText('Demain'))
    if (objet) {
      fireEvent.change(screen.getByLabelText('Objet (facultatif)'), { target: { value: objet } })
    }
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
  }

  it('POST /records/activities/ sur crm.lead avec l’objet nettoyé et la date de relance', async () => {
    planifier('  Rappeler après le devis  ')
    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/records/activities/', {
      model: 'crm.lead', id: 42, summary: 'Rappeler après le devis', due_date: '2026-08-11',
    }))
    expect(crmApi.updateLead).toHaveBeenCalledWith(42, { relance_date: '2026-08-11' })
  })

  it('sans objet, aucune activité n’est créée (une relance suffit souvent)', async () => {
    planifier('')
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalled())
    expect(apiPost).not.toHaveBeenCalled()
  })
})

describe('EZ1 — planification pure : ni issue demandée ni exigée', () => {
  it('pas de choix d’issue ; « Enregistrer » exige une date, pas une issue ; rien n’est journalisé', async () => {
    render(<CallLogPopover leadId={42} open onOpenChange={() => {}} mode="planification" />)
    expect(screen.getByText('Planifier une relance')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: "Résultat de l'appel" })).not.toBeInTheDocument()
    expect(screen.queryByPlaceholderText('Note (facultative)…')).not.toBeInTheDocument()
    const enregistrer = screen.getByRole('button', { name: 'Enregistrer' })
    expect(enregistrer).toBeDisabled()
    fireEvent.click(screen.getByText('Demain'))
    expect(enregistrer).toBeEnabled()
    fireEvent.click(enregistrer)
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalled())
    expect(crmApi.logInteraction).not.toHaveBeenCalled()
  })
})
