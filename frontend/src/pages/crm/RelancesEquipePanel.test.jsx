import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent, within } from '@testing-library/react'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* SUIVI-ÉQUIPE (fondateur, 29/10/2026) — la « Vue d'équipe » de l'écran
   « Suivi des relances ». Charge utile = l'exemple COMMITTÉ du contrat
   `controle_suivi` (`apps/crm/contract_samples/controle_suivi.json`, PACT10),
   jamais un objet retapé à la main : si le serveur change de forme, l'exemple
   change et ce test casse tout seul. Nouveau fichier car : nouveau composant. */
vi.mock('../../api/crmApi', () => ({ default: { getControleSuivi: vi.fn() } }))

import crmApi from '../../api/crmApi'
import RelancesEquipePanel from './RelancesEquipePanel'

const DONNEES = exempleContrat('crm', 'controle_suivi')
const PAR_COMMERCIAL = DONNEES.par_commercial

beforeEach(() => {
  crmApi.getControleSuivi.mockResolvedValue(reponseContrat('crm', 'controle_suivi'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

// Le sélecteur de période est un `Segmented` (role=radiogroup) : clic sur l'option.
const choisirPeriode = (name) => fireEvent.click(screen.getByRole('radio', { name }))
const ligne = (id) => screen.getByTestId(`equipe-ligne-${id}`)

describe('RelancesEquipePanel (SUIVI-ÉQUIPE)', () => {
  it('appelle le contrôle sur 14 jours par défaut sans owner, puis avec la période choisie et le responsable reçu', async () => {
    const { rerender } = render(<RelancesEquipePanel owner="" />)
    await waitFor(() => expect(crmApi.getControleSuivi).toHaveBeenCalledWith({ jours: 14 }))
    choisirPeriode('7 jours')
    await waitFor(() => expect(crmApi.getControleSuivi).toHaveBeenCalledWith({ jours: 7 }))
    rerender(<RelancesEquipePanel owner="7" />)
    await waitFor(() => expect(crmApi.getControleSuivi).toHaveBeenCalledWith({ jours: 7, owner: '7' }))
  })

  it('les quatre tuiles et les barres rendent les chiffres SERVIS, tels quels, dans l\'ordre servi', async () => {
    render(<RelancesEquipePanel owner="" />)
    await waitFor(() => expect(screen.getByTestId('equipe-tuiles')).toBeInTheDocument())
    expect(screen.getByTestId('equipe-tuile-retard'))
      .toHaveTextContent(String(DONNEES.exceptions.en_retard.total))
    expect(screen.getByTestId('equipe-tuile-a-temps')).toHaveTextContent(/85[,.]7/)
    expect(screen.getByTestId('equipe-tuile-a-temps')).toHaveTextContent(/78[,.]0/)
    expect(screen.getByTestId('equipe-tuile-reportees'))
      .toHaveTextContent(String(DONNEES.verdict.reportees))
    expect(screen.getByTestId('equipe-tuile-attente'))
      .toHaveTextContent(String(DONNEES.exceptions.taches_en_attente.total))

    // Une barre par ligne servie, dans l'ordre servi (le serveur trie).
    const lignes = screen.getAllByTestId(/^equipe-ligne-/)
    expect(lignes).toHaveLength(PAR_COMMERCIAL.length)
    expect(lignes.map((l) => within(l).getByRole('button').textContent))
      .toEqual(PAR_COMMERCIAL.map((c) => c.nom))

    // Segments depuis la base : le retard d'abord ; un compteur à 0 n'a pas de segment.
    const premiere = PAR_COMMERCIAL[0]
    const segments = [...lignes[0].querySelectorAll('[data-serie]')].map((s) => s.dataset.serie)
    expect(segments).toEqual(['ouvert', 'en_retard', 'a_temps', 'sautees'].filter((k) => premiere[k]))
    expect(lignes[0]).toHaveTextContent(`${premiere.en_retard_actuel} en retard`)
    expect(lignes[0]).toHaveTextContent(`${premiere.aujourdhui} aujourd'hui`)

    // La légende dit le MOT ; la frise a son tableau équivalent (ChartFrame).
    expect(screen.getByTestId('equipe-legende-commercial')).toHaveTextContent('Toujours en retard')
    expect(screen.getByTestId('equipe-legende-jours')).toHaveTextContent('Ouvertes, pas encore en retard')
    expect(screen.getByText(`Touches dues jour par jour sur ${DONNEES.periode_jours} jours`))
      .toBeInTheDocument()
  })

  it('cliquer un commercial borne la file à lui ; re-cliquer revient à toute l\'équipe', async () => {
    const onChoisirOwner = vi.fn()
    const premiere = PAR_COMMERCIAL[0]
    const { rerender } = render(<RelancesEquipePanel owner="" onChoisirOwner={onChoisirOwner} />)
    await waitFor(() => expect(ligne(premiere.id)).toBeInTheDocument())
    expect(within(ligne(premiere.id)).getByRole('button')).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(within(ligne(premiere.id)).getByRole('button'))
    expect(onChoisirOwner).toHaveBeenCalledWith(premiere.id)

    rerender(<RelancesEquipePanel owner={String(premiere.id)} onChoisirOwner={onChoisirOwner} />)
    await waitFor(() => expect(within(ligne(premiere.id)).getByRole('button'))
      .toHaveAttribute('aria-pressed', 'true'))
    fireEvent.click(within(ligne(premiere.id)).getByRole('button'))
    expect(onChoisirOwner).toHaveBeenLastCalledWith('')
  })

  it('société vide (`exemple_vide`) : le bloc le dit, aucun chiffre inventé', async () => {
    crmApi.getControleSuivi.mockResolvedValue(reponseContrat('crm', 'controle_suivi', 'exemple_vide'))
    render(<RelancesEquipePanel owner="" />)
    await waitFor(() => expect(screen.getByTestId('equipe-vide')).toBeInTheDocument())
    expect(screen.queryByTestId('equipe-tuiles')).not.toBeInTheDocument()
  })

  it('refus serveur : un message, jamais des barres vides qui mentent', async () => {
    crmApi.getControleSuivi.mockRejectedValue(new Error('500'))
    render(<RelancesEquipePanel owner="" />)
    await waitFor(() => expect(screen.getByText(/Vue d.équipe indisponible/)).toBeInTheDocument())
    expect(screen.queryByTestId('equipe-tuiles')).not.toBeInTheDocument()
  })
})
