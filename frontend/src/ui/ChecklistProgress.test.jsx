import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import ChecklistProgress from './ChecklistProgress'

/* APX31 — UN composant d'avancement de checklist, DEUX panneaux.
   État vérifié avant : `pages/sav/TicketChecklistPanel.jsx` affichait
   « X/Y points » en texte plat, alors que `pages/installations/
   ChantierChecklist.jsx` avait déjà une `Progress` + le pourcentage — deux
   réponses différentes à la même question sur deux écrans du même ERP. */

afterEach(() => { cleanup() })

describe('ChecklistProgress (APX31)', () => {
  it('rend la barre ET le compte lisible (la couleur n’est jamais seule)', () => {
    render(<ChecklistProgress done={3} total={8} />)
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
    expect(screen.getByText('3/8 points · 38%')).toBeInTheDocument()
  })

  it('accorde le nom de l’unité comptée (« point » / « étape »)', () => {
    render(<ChecklistProgress done={1} total={1} noun="étape" show="count" />)
    expect(screen.getByText('1/1 étape')).toBeInTheDocument()
  })

  it('une checklist vide n’affiche AUCUN avancement (0/0 n’a pas de sens)', () => {
    const { container } = render(<ChecklistProgress done={0} total={0} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('borne un compte incohérent au lieu de rendre 150 %', () => {
    render(<ChecklistProgress done={99} total={4} show="percent" />)
    expect(screen.getByText('100%')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
  })

  it('accepte un pourcentage IMPOSÉ (le chantier reçoit le sien du serveur)', () => {
    // Adopter le composant partagé ne doit PAS changer le nombre que le
    // panneau chantier affichait : il passe `completion` tel quel.
    render(<ChecklistProgress percent={62} show="percent" />)
    expect(screen.getByText('62%')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '62')
  })

  it('porte un nom accessible qui dit l’avancement', () => {
    render(<ChecklistProgress done={2} total={5} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute(
      'aria-label', 'Avancement : 2/5 points',
    )
  })
})
