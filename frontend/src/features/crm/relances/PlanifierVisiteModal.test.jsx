// VISCAD3 — modale « Planifier la visite technique », partagée par les trois
// points d'entrée (panneau de coaching, SectionVisite, issue « Visite
// acceptée »). Contrat FIXÉ (backend construit en parallèle sur EXACTEMENT
// cette forme) :
//   POST /api/django/crm/leads/<id>/visites/planifier/
//   body {date_prevue, commercial?, notes?} -> 201 {visite: {...}}
//   erreurs de validation : {date_prevue: ["…"]} (objet de champs).
import {
  describe, it, expect, vi, afterEach,
} from 'vitest'
import {
  render, screen, cleanup, fireEvent, waitFor,
} from '@testing-library/react'

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({
      data: [{ id: 7, username: 'meryem' }, { id: 9, username: 'karim' }],
    })),
    planifierVisiteLead: vi.fn(),
  },
}))
vi.mock('../../../lib/toast', () => ({ toastSuccess: vi.fn() }))

import crmApi from '../../../api/crmApi'
import { toastSuccess } from '../../../lib/toast'
import PlanifierVisiteModal from './PlanifierVisiteModal'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function monter(props = {}) {
  const onOpenChange = vi.fn()
  const onPlanifie = vi.fn()
  const utils = render(
    <PlanifierVisiteModal
      leadId={1489} open onOpenChange={onOpenChange} onPlanifie={onPlanifie}
      {...props}
    />,
  )
  return { ...utils, onOpenChange, onPlanifie }
}

describe('VISCAD3 PlanifierVisiteModal', () => {
  it('charge les commerciaux assignables à l\'ouverture (même source que le sélecteur Responsable)', async () => {
    monter()
    await waitFor(() => expect(crmApi.getAssignableUsers).toHaveBeenCalled())
    expect(await screen.findByRole('option', { name: 'meryem' })).toBeInTheDocument()
  })

  it('succès : appelle planifierVisiteLead avec le payload EXACT, toast, ferme, rappelle onPlanifie', async () => {
    crmApi.planifierVisiteLead.mockResolvedValue({
      data: { visite: { id: 55, statut: 'brouillon', statut_libelle: 'Planifiée' } },
    })
    const { onOpenChange, onPlanifie } = monter()
    // Attend le chargement des commerciaux AVANT de saisir — le formulaire se
    // réinitialise à l'ouverture (`queueMicrotask`, voir le composant) : saisir
    // puis attendre effacerait la date au moment même où ce `await` la laisse
    // s'exécuter.
    await waitFor(() => expect(screen.getByRole('option', { name: 'meryem' })).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Date prévue'), { target: { value: '2026-09-20' } })
    fireEvent.change(screen.getByLabelText('Commercial assigné'), { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText('Note (optionnelle)'), { target: { value: 'Toit difficile d’accès' } })
    fireEvent.click(screen.getByRole('button', { name: 'Planifier la visite' }))
    await waitFor(() => expect(crmApi.planifierVisiteLead).toHaveBeenCalledWith(1489, {
      date_prevue: '2026-09-20', commercial: 7, notes: 'Toit difficile d’accès',
    }))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith(
      'Visite planifiée — relances décalées après la visite'))
    await waitFor(() => expect(onPlanifie).toHaveBeenCalledWith(
      { id: 55, statut: 'brouillon', statut_libelle: 'Planifiée' }))
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
  })

  it('succès sans commercial/note : le payload ne porte QUE date_prevue', async () => {
    crmApi.planifierVisiteLead.mockResolvedValue({ data: { visite: { id: 56 } } })
    monter()
    fireEvent.change(screen.getByLabelText('Date prévue'), { target: { value: '2026-09-21' } })
    fireEvent.click(screen.getByRole('button', { name: 'Planifier la visite' }))
    await waitFor(() => expect(crmApi.planifierVisiteLead).toHaveBeenCalledWith(
      1489, { date_prevue: '2026-09-21' }))
  })

  it('erreur 400 de champ : message EXACT sous le champ + bandeau qui nomme le champ', async () => {
    crmApi.planifierVisiteLead.mockRejectedValue({
      response: { status: 400, data: { date_prevue: ['Cette date est déjà passée.'] } },
    })
    monter()
    fireEvent.change(screen.getByLabelText('Date prévue'), { target: { value: '2026-09-20' } })
    fireEvent.click(screen.getByRole('button', { name: 'Planifier la visite' }))
    // Sous le champ — id déterministe posé par FormField (`${id}-error`) ;
    // `toHaveTextContent` ignore le préfixe sr-only « Champ requis : ».
    await waitFor(() => expect(document.getElementById('pv-date-prevue-error'))
      .toHaveTextContent('Cette date est déjà passée.'))
    // Bandeau — nomme le champ EN FRANÇAIS, jamais la clé technique brute.
    expect(screen.getByText('Date prévue : Cette date est déjà passée.')).toBeInTheDocument()
  })

  it('erreur inattendue (réseau/500) : une phrase claire, jamais « Non enregistré »', async () => {
    crmApi.planifierVisiteLead.mockRejectedValue(new Error('boom'))
    monter()
    fireEvent.change(screen.getByLabelText('Date prévue'), { target: { value: '2026-09-20' } })
    fireEvent.click(screen.getByRole('button', { name: 'Planifier la visite' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'La planification de la visite a échoué — réessayez.')
  })

  it('le formulaire se réinitialise à chaque RÉOUVERTURE (jamais la saisie d\'un lead précédent)', async () => {
    const { rerender } = render(
      <PlanifierVisiteModal leadId={1489} open onOpenChange={vi.fn()} onPlanifie={vi.fn()} />,
    )
    fireEvent.change(screen.getByLabelText('Date prévue'), { target: { value: '2026-09-20' } })
    expect(screen.getByLabelText('Date prévue').value).toBe('2026-09-20')
    rerender(<PlanifierVisiteModal leadId={1489} open={false} onOpenChange={vi.fn()} onPlanifie={vi.fn()} />)
    rerender(<PlanifierVisiteModal leadId={1489} open onOpenChange={vi.fn()} onPlanifie={vi.fn()} />)
    // Le reset part d'un `queueMicrotask` (même patron que
    // `ToucheMessageDialog.jsx`) — jamais une lecture synchrone immédiate.
    await waitFor(() => expect(screen.getByLabelText('Date prévue').value).toBe(''))
  })
})
