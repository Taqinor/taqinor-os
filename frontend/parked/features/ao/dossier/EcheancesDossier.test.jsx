import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* AOF178 — échéances et jalons du dossier.
   Les dates sont RELATIVES à `Date.now()` et les libellés attendus sont
   calculés avec les MÊMES fonctions pures que l'écran (`ui/module/urgency.js`) :
   c'est ce qui prouve la « source unique » — et c'est aussi ce qui empêche la
   dérive d'horloge de faire rougir le test à minuit. */

const mocks = vi.hoisted(() => ({ update: vi.fn() }))

vi.mock('../../../api/aoApi', () => ({
  default: { affaires: { update: mocks.update } },
}))

import { daysUntil, urgencyLabel } from '../../../ui/module'
import { formatDate } from '../../../lib/format'
import EcheancesDossier from './EcheancesDossier'

const JOUR = 24 * 60 * 60 * 1000
const dans = (n) => new Date(Date.now() + n * JOUR).toISOString()

const LIMITE = dans(3)          // urgent (≤ 7 j)
const OUVERTURE = dans(45)      // ok (> 30 j)
const RETARD = dans(-2)         // en retard

const ECHEANCES = [
  { id: 1, libelle: 'Remise des plis', date_echeance: LIMITE, rappel_date: dans(1) },
  { id: 2, libelle: 'Ouverture des plis', date_echeance: OUVERTURE, rappel_date: dans(43) },
  { id: 3, libelle: 'Réponse aux questions', date_echeance: RETARD, rappel_date: dans(-4) },
]

const JALONS = [
  { id: 10, type: 'visite_site', date: dans(-2), fait: true },
  { id: 11, type: 'questions_mo', date: dans(2), fait: false },
  { id: 12, type: 'prorogation', libelle: 'Prorogation obtenue', date: dans(5), fait: false },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.update.mockResolvedValue({ data: {} })
})

describe('EcheancesDossier (AOF178)', () => {
  it('le compte à rebours et les échéances utilisent les MÊMES libellés d’urgence que la liste des affaires', () => {
    render(<EcheancesDossier affaireId={4} dateLimite={LIMITE} echeances={ECHEANCES} jalons={JALONS} />)
    // Un seul jeu de seuils : ceux de `ui/module/urgency.js`.
    expect(screen.getAllByText(urgencyLabel(daysUntil(LIMITE))).length).toBeGreaterThan(0)
    expect(screen.getByText(urgencyLabel(daysUntil(OUVERTURE)))).toBeInTheDocument()
    expect(screen.getByText(urgencyLabel(daysUntil(RETARD)))).toBeInTheDocument()
    // « En retard (J+N) » : le seuil « dépassé » est celui du socle partagé.
    expect(urgencyLabel(daysUntil(RETARD))).toMatch(/^En retard/)
  })

  it('affiche la date limite de remise des plis et les jalons du cycle réel', () => {
    render(<EcheancesDossier affaireId={4} dateLimite={LIMITE} echeances={ECHEANCES} jalons={JALONS} />)
    expect(screen.getByText('Date limite de remise des plis')).toBeInTheDocument()
    expect(screen.getByText(formatDate(LIMITE))).toBeInTheDocument()
    expect(screen.getByText('Visite de site')).toBeInTheDocument()
    expect(screen.getByText("Questions au maître d'ouvrage")).toBeInTheDocument()
    expect(screen.getByText('Prorogation obtenue')).toBeInTheDocument()
    expect(screen.getByText('Fait')).toBeInTheDocument()
  })

  it('affiche le rappel de chaque échéance (généré par le serveur, jamais recalculé ici)', () => {
    render(<EcheancesDossier affaireId={4} dateLimite={LIMITE} echeances={ECHEANCES} />)
    expect(screen.getByText(`Rappel le ${formatDate(ECHEANCES[0].rappel_date)}`)).toBeInTheDocument()
    expect(screen.getAllByText(/^Rappel le /)).toHaveLength(3)
  })

  it('la prorogation exige une référence ÉCRITE avant d’être enregistrable', () => {
    render(<EcheancesDossier affaireId={4} dateLimite={LIMITE} echeances={ECHEANCES} />)
    const bouton = screen.getByRole('button', { name: 'Enregistrer la prorogation' })
    expect(bouton).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/Nouvelle date limite/), { target: { value: '2026-09-30' } })
    expect(bouton).toBeDisabled() // date seule : insuffisant
    fireEvent.change(screen.getByLabelText(/Référence du courrier/), {
      target: { value: 'avis de prorogation n° 12/2026' },
    })
    expect(bouton).toBeEnabled()
  })

  it('enregistrer une prorogation écrite DÉCALE les rappels (le serveur les déplace, il n’en crée pas)', async () => {
    const onProrogee = vi.fn()
    const { rerender } = render(
      <EcheancesDossier affaireId={4} dateLimite={LIMITE} echeances={ECHEANCES} onProrogee={onProrogee} />,
    )
    fireEvent.change(screen.getByLabelText(/Nouvelle date limite/), { target: { value: '2026-09-30' } })
    fireEvent.change(screen.getByLabelText(/Référence du courrier/), {
      target: { value: 'avis de prorogation n° 12/2026' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la prorogation' }))

    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(4, {
      prorogation_date: '2026-09-30',
      prorogation_reference: 'avis de prorogation n° 12/2026',
    }))
    await waitFor(() => expect(onProrogee).toHaveBeenCalled())

    // Le serveur renvoie l'échéancier RECALCULÉ : mêmes rappels, décalés.
    const DECALEES = ECHEANCES.map((e) => ({ ...e, rappel_date: dans(20) }))
    rerender(<EcheancesDossier affaireId={4} dateLimite={dans(25)} echeances={DECALEES} />)
    expect(screen.getAllByText(`Rappel le ${formatDate(dans(20))}`)).toHaveLength(3)
    // Aucun rappel SUPPLÉMENTAIRE : ils ont été déplacés, pas dupliqués.
    expect(screen.getAllByText(/^Rappel le /)).toHaveLength(3)
  })

  it('un `onProroger` injecté remplace l’appel par défaut (aucun endpoint inventé)', async () => {
    const onProroger = vi.fn().mockResolvedValue({})
    render(<EcheancesDossier affaireId={4} dateLimite={LIMITE} onProroger={onProroger} />)
    fireEvent.change(screen.getByLabelText(/Nouvelle date limite/), { target: { value: '2026-10-05' } })
    fireEvent.change(screen.getByLabelText(/Référence du courrier/), { target: { value: 'courrier 3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la prorogation' }))
    await waitFor(() => expect(onProroger).toHaveBeenCalledWith({
      date: '2026-10-05', reference: 'courrier 3',
    }))
    expect(mocks.update).not.toHaveBeenCalled()
  })
})
