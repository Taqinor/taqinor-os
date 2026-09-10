// CKP4/CKP6 (fondateur 2026-09-10) — un canal APPEL clôturé « Fait » exige
// TOUJOURS une issue (Joint/Pas de réponse existantes + Répondeur/Occupé
// ajoutées) ; un 400 `{erreurs: {outcome}}` s'affiche SOUS le contrôle ; le
// message de confirmation vient de LA RÉPONSE serveur, jamais calculé ici ;
// les badges « Sautée · qui · quand » et « Annulée (moteur) · motif » ne se
// confondent jamais (vérité des sautées, CKP1). Étape de départ = le premier
// résultat du contrat COMMITTÉ `relance_etape_v2.json` (canal appel) —
// jamais un objet retapé à la main.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn() }))
import { toastInfo } from '../../../lib/toast'

const ETAPE_APPEL = exempleContrat('crm', 'relance_etape_v2').results[0]

afterEach(() => { cleanup(); vi.clearAllMocks() })

function noop() {}

describe('CKP4 RelanceEtapeRow — issue obligatoire sur un appel', () => {
  it('un canal appel propose Joint/Pas de réponse (existants) ET Répondeur/Occupé (ajoutés)', () => {
    render(
      <RelanceEtapeRow etape={ETAPE_APPEL} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByRole('button', { name: 'Client joint' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pas de réponse' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Répondeur' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Occupé' })).toBeInTheDocument()
  })

  it('Confirmer reste désactivé tant qu\'aucune issue n\'est choisie (obligatoire)', () => {
    render(
      <RelanceEtapeRow etape={ETAPE_APPEL} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
  })

  it('« Répondeur »/« Occupé » envoient leur propre outcome', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    render(
      <RelanceEtapeRow etape={ETAPE_APPEL} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Répondeur' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(ETAPE_APPEL.id, { outcome: 'repondeur' }))
  })

  it('une réponse 400 {erreurs: {outcome}} s\'affiche SOUS le contrôle, jamais un toast générique', async () => {
    const erreur = {
      response: { status: 400, data: { erreurs: { outcome: 'Une issue est requise pour un appel.' } } },
    }
    const onFait = vi.fn(() => Promise.reject(erreur))
    render(
      <RelanceEtapeRow etape={ETAPE_APPEL} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Client joint' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByTestId('erreur-outcome'))
      .toHaveTextContent('Une issue est requise pour un appel.')
    expect(toastInfo).not.toHaveBeenCalled()
  })

  it('le message de confirmation vient de la RÉPONSE serveur (prochaine_touche.due_at), jamais calculé localement', async () => {
    const onFait = vi.fn(() => Promise.resolve({
      prochaine_touche: { due_at: '2026-09-12T09:00:00Z', canal: 'appel' },
    }))
    render(
      <RelanceEtapeRow etape={ETAPE_APPEL} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Pas de réponse' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(toastInfo).toHaveBeenCalled())
    expect(toastInfo.mock.calls[0][0]).toMatch(/Prochain appel programmé le/)
  })

  it('sans prochaine_touche dans la réponse (dernière touche, cadence arrêtée) : aucun message inventé', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    render(
      <RelanceEtapeRow etape={ETAPE_APPEL} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Client joint' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalled())
    expect(toastInfo).not.toHaveBeenCalled()
  })
})

describe('CKP1/CKP4 RelanceEtapeRow — badges honnêtes (sautée ≠ annulée)', () => {
  it('« sautee » affiche « Sautée · qui · HH:MM » (auteur ET heure visibles)', () => {
    const etape = {
      ...ETAPE_APPEL, statut: 'sautee', traite_par_nom: 'meryem', traite_le: '2026-09-10T09:05:00Z',
    }
    render(
      <RelanceEtapeRow etape={etape} onFait={noop} onSauter={noop} onReporter={noop}
        onOuvrirMessage={noop} showStatut readOnly />,
    )
    expect(screen.getByText(/^Sautée · meryem · \d{2}:\d{2}$/)).toBeInTheDocument()
  })

  it('« annulee » affiche « Annulée (moteur) · motif », jamais un auteur', () => {
    const etape = { ...ETAPE_APPEL, statut: 'annulee', note: 'devis accepté', traite_par_nom: '' }
    render(
      <RelanceEtapeRow etape={etape} onFait={noop} onSauter={noop} onReporter={noop}
        onOuvrirMessage={noop} showStatut readOnly />,
    )
    expect(screen.getByText('Annulée (moteur) · devis accepté')).toBeInTheDocument()
    expect(screen.queryByText(/Sautée/)).not.toBeInTheDocument()
  })
})
