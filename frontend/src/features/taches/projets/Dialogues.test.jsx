import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/tachesApi', async (original) => ({
  ...(await original()),
  decalerProjet: vi.fn(),
  supprimerProjet: vi.fn(),
  terminerProjet: vi.fn(),
  listerTousLesProjets: vi.fn(),
  listerProjets: vi.fn(),
  rouvrirProjet: vi.fn(),
}))

const api = await import('../../../api/tachesApi')
const { DialogueDecaler, DialogueSupprimer, DialogueTerminer } = await import('./Dialogues')
const { default: ProjetsArchive } = await import('../../../pages/taches/ProjetsArchive')

/* TCH92 — Supprimer (« … et ses N tâches ? »), Décaler (aperçu avant d'écrire, refus « avant aujourd'hui »),
   Terminer (issue, bilan, tâches ouvertes) sur `decalage.json` et `projet_ecrit.json` ; l'écran Archive. */

const AUJOURDHUI = '2026-11-17'
const projet = (suite = {}) => ({ ...exempleContrat('taches', 'projet'), ...suite })
const utilisateur = () => userEvent.setup()

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-11-17T09:00:00'))
})
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks() })

describe('TCH92 — Supprimer le projet', () => {
  it('« Supprimer « Ventes » et ses 20 tâches ? » puis Supprimer appelle l\'API et rend la main', async () => {
    api.supprimerProjet.mockResolvedValue({ data: {} })
    const onFait = vi.fn()
    render(<DialogueSupprimer projet={projet()} onFait={onFait} onFermer={() => {}} />)
    const dialogue = screen.getByRole('dialog', { name: 'Supprimer le projet' })
    expect(within(dialogue).getByText('Supprimer « Ventes » et ses 20 tâches ?')).toBeInTheDocument()
    expect(within(dialogue).getByText('Ils restent 30 jours dans Supprimées récemment.')).toBeInTheDocument()
    await utilisateur().click(within(dialogue).getByRole('button', { name: 'Supprimer' }))
    expect(api.supprimerProjet).toHaveBeenCalledWith(3)
    await waitFor(() => expect(onFait).toHaveBeenCalledTimes(1))
  })

  it('Fermer n\'écrit rien ; un échec est dit dans le dialogue et le projet reste', async () => {
    api.supprimerProjet.mockRejectedValue(new Error('Network Error'))
    const onFermer = vi.fn()
    const onFait = vi.fn()
    render(<DialogueSupprimer projet={projet()} onFait={onFait} onFermer={onFermer} />)
    const user = utilisateur()
    await user.click(screen.getByRole('button', { name: 'Supprimer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Connexion perdue')
    expect(onFait).not.toHaveBeenCalled()
    await user.click(screen.getAllByRole('button', { name: 'Fermer' }).at(-1))
    expect(onFermer).toHaveBeenCalled()
  })
})

describe('TCH92 — Décaler les dates', () => {
  const noms = { taches: { 41: 'Poser la structure' }, sections: {} }

  it('+1 semaine montre l\'aperçu (rien écrit) ; Appliquer écrit avec apercu:false', async () => {
    api.decalerProjet.mockResolvedValue(reponseContrat('taches', 'decalage'))
    const onFait = vi.fn()
    render(<DialogueDecaler projet={projet()} noms={noms} aujourdhui={AUJOURDHUI} onFait={onFait} onFermer={() => {}} />)
    const user = utilisateur()
    expect(screen.getByRole('button', { name: 'Appliquer' })).toBeDisabled()
    await user.click(screen.getByRole('radio', { name: '+1 semaine' }))
    expect(api.decalerProjet).toHaveBeenCalledWith(3, { delta_jours: 7, apercu: true })
    expect(await screen.findByText('1 date change.')).toBeInTheDocument()
    const ligne = screen.getByText('Poser la structure').closest('li')
    expect(ligne).toHaveTextContent('ven. 20')
    expect(ligne).toHaveTextContent('ven. 27')
    expect(onFait).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Appliquer' }))
    expect(api.decalerProjet).toHaveBeenLastCalledWith(3, { delta_jours: 7, apercu: false })
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(expect.objectContaining({ changements: expect.any(Array) })))
  })

  it('« 2 tâches passeraient avant aujourd\'hui » s\'affiche sous le champ et Appliquer reste fermé', async () => {
    api.decalerProjet.mockRejectedValue({ response: { status: 400, data: { delta_jours: ['2 tâches passeraient avant aujourd\'hui.'] } } })
    render(<DialogueDecaler projet={projet()} noms={noms} aujourdhui={AUJOURDHUI} onFait={() => {}} onFermer={() => {}} />)
    const user = utilisateur()
    await user.click(screen.getByRole('radio', { name: 'Choisir' }))
    await user.type(screen.getByLabelText('Nombre de jours (− pour avancer)'), '-2')
    expect(await screen.findByRole('alert')).toHaveTextContent('2 tâches passeraient avant aujourd\'hui.')
    expect(screen.getByLabelText('Nombre de jours (− pour avancer)')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('button', { name: 'Appliquer' })).toBeDisabled()
  })
})

describe('TCH92 — Terminer le projet', () => {
  it('sans issue, le serveur répond « Atteint ou abandonné ? » sous le champ', async () => {
    api.terminerProjet.mockRejectedValue({ response: { status: 400, data: { issue: ['Atteint ou abandonné ?'] } } })
    render(<DialogueTerminer projet={projet()} onFait={() => {}} onFermer={() => {}} />)
    await utilisateur().click(screen.getByRole('button', { name: 'Terminer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Atteint ou abandonné ?')
    expect(api.terminerProjet).toHaveBeenCalledWith(3, { issue: '', bilan: '', taches_ouvertes: 'boite', projet_cible_id: null })
  })

  it('Atteint + bilan + « Les remettre dans À trier » : le corps de projet_ecrit.json est rendu', async () => {
    api.terminerProjet.mockResolvedValue(reponseContrat('taches', 'projet_ecrit'))
    const onFait = vi.fn()
    render(<DialogueTerminer projet={projet()} onFait={onFait} onFermer={() => {}} />)
    const user = utilisateur()
    expect(screen.getByText('Ses 8 tâches encore ouvertes :')).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: 'Atteint' }))
    await user.type(screen.getByLabelText('Bilan (facultatif)'), 'Signé')
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(api.terminerProjet).toHaveBeenCalledWith(3, { issue: 'atteint', bilan: 'Signé', taches_ouvertes: 'boite', projet_cible_id: null })
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(expect.objectContaining({ deplacees: 3, geste_id: 86 })))
  })

  it('« Les déplacer vers… » propose les autres projets actifs et envoie le projet cible', async () => {
    const autre = { ...projet(), id: 5, nom: 'Site web' }
    api.listerTousLesProjets.mockResolvedValue([projet(), autre])
    api.terminerProjet.mockResolvedValue(reponseContrat('taches', 'projet_ecrit'))
    render(<DialogueTerminer projet={projet()} onFait={() => {}} onFermer={() => {}} />)
    const user = utilisateur()
    await user.click(screen.getByRole('radio', { name: 'Atteint' }))
    await user.click(screen.getByRole('radio', { name: 'Les déplacer vers…' }))
    const choix = await screen.findByLabelText('Projet de destination')
    expect(within(choix).queryByRole('option', { name: 'Ventes' })).toBeNull()
    await user.selectOptions(choix, 'Site web')
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(api.terminerProjet).toHaveBeenCalledWith(3, { issue: 'atteint', bilan: '', taches_ouvertes: 'deplacer', projet_cible_id: 5 })
  })

  it('Raccord F2 — « Les abandonner » envoie `taches_ouvertes: annuler`, la valeur que le serveur accepte', async () => {
    api.terminerProjet.mockResolvedValue(reponseContrat('taches', 'projet_ecrit'))
    render(<DialogueTerminer projet={projet()} onFait={() => {}} onFermer={() => {}} />)
    const user = utilisateur()
    await user.click(screen.getByRole('radio', { name: 'Abandonné' }))
    await user.click(screen.getByRole('radio', { name: 'Les abandonner' }))
    await user.click(screen.getByRole('button', { name: 'Terminer' }))
    expect(api.terminerProjet).toHaveBeenCalledWith(3, { issue: 'abandonne', bilan: '', taches_ouvertes: 'annuler', projet_cible_id: null })
  })

  it('un projet sans tâche ouverte ne pose pas la question des tâches ouvertes', () => {
    render(<DialogueTerminer projet={projet({ compteurs: { ouvertes: 0, faites: 12 } })} onFait={() => {}} onFermer={() => {}} />)
    expect(screen.queryByText(/encore ouvertes/)).toBeNull()
  })
})

describe('TCH92 — Archive', () => {
  const archive = (suite = {}) => ({
    data: {
      count: 2, next: null, previous: null,
      results: [
        projet({ id: 11, nom: 'Chantier Salé', statut: 'termine', issue: 'atteint', termine_le: '2026-11-13T17:00:00+01:00', bilan: 'Mis en service.', compteurs: { ouvertes: 0, faites: 14 }, ...suite }),
        projet({ id: 12, nom: 'Site vitrine', statut: 'termine', issue: 'abandonne', termine_le: '2026-11-16T17:00:00+01:00', compteurs: { ouvertes: 6, faites: 3 } }),
      ],
    },
  })
  const monter = () => render(<MemoryRouter initialEntries={['/taches/projets/archive']}><ProjetsArchive /></MemoryRouter>)

  it('liste issue, date de fin, avancement et bilan ; la recherche filtre sans accents', async () => {
    api.listerProjets.mockResolvedValue(archive())
    monter()
    const salé = (await screen.findByText('Chantier Salé')).closest('.ligne')
    expect(api.listerProjets).toHaveBeenCalledWith({ statut: 'archive' })
    expect(salé).toHaveTextContent('Atteint')
    expect(salé).toHaveTextContent('ven. 13/11')
    expect(salé).toHaveTextContent('14 sur 14')
    expect(salé).toHaveTextContent('Mis en service.')
    expect(screen.getByText('Site vitrine').closest('.ligne')).toHaveTextContent('Abandonné')
    await utilisateur().type(screen.getByLabelText('Chercher un projet archivé'), 'sale')
    expect(screen.queryByText('Site vitrine')).toBeNull()
    expect(screen.getByText('Chantier Salé')).toBeInTheDocument()
  })

  it('Rouvrir retire la ligne sur place ; un refus la remet et le dit', async () => {
    api.listerProjets.mockResolvedValue(archive())
    api.rouvrirProjet.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Un projet « Chantier Salé » existe déjà.', code: 'nom_pris' } } })
    api.rouvrirProjet.mockResolvedValueOnce({ data: {} })
    monter()
    const user = utilisateur()
    await user.click(await screen.findByRole('button', { name: 'Rouvrir « Chantier Salé »' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Un projet « Chantier Salé » existe déjà.')
    expect(screen.getByText('Chantier Salé')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Rouvrir « Site vitrine »' }))
    await waitFor(() => expect(screen.queryByText('Site vitrine')).toBeNull())
    expect(api.rouvrirProjet).toHaveBeenLastCalledWith(12)
    expect(api.listerProjets).toHaveBeenCalledTimes(1)
  })

  it('aucun projet archivé : « Aucun projet archivé »', async () => {
    api.listerProjets.mockResolvedValue({ data: { count: 0, next: null, previous: null, results: [] } })
    monter()
    expect(await screen.findByText('Aucun projet archivé')).toBeInTheDocument()
  })
})
