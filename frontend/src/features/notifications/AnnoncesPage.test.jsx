import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* WIR177 — écran destinataire des annonces internes (XKB5/XKB6).

   Ce que ce module PROUVE :
     - la liste demande bien les annonces ACTIVES (`{ active: 1 }`) ;
     - `?annonce=<pk>` — le motif que les deux `link=` de
       `apps/notifications/services.py` posent — remonte l'annonce visée EN
       TÊTE (la publication et la relance ouvrent donc la bonne annonce) ;
     - « J'ai lu et compris » appelle `accuserLectureAnnonce(<pk>)` (l'accusé
       qui alimente le rapport de conformité XKB6) et l'écran bascule sur la
       confirmation ;
     - le bouton n'apparaît QUE sur une annonce à lecture obligatoire.

   PACT10/PACT13 — la charge utile n'est PAS écrite ici : elle est importée de
   l'exemple committé `apps/notifications/contract_samples/annonces_actives.json`,
   le même fichier que le test backend
   (`tests_wir177_lien_annonces.ContratAnnoncesActivesTests`) affirme contre la
   réponse RÉELLE du serveur. Si le serveur change de forme, l'exemple change et
   ce test casse tout seul. */

const { getAnnonces, accuserLectureAnnonce } = vi.hoisted(() => ({
  getAnnonces: vi.fn(),
  accuserLectureAnnonce: vi.fn(() => Promise.resolve({ data: { lu: true } })),
}))
vi.mock('../../api/notificationsApi', () => ({
  default: { getAnnonces, accuserLectureAnnonce },
}))
vi.mock('../../ui/Toaster', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}))

import AnnoncesPage from './AnnoncesPage'

const APP = 'notifications'
const CONTRAT = 'annonces_actives'
const ANNONCES = exempleContrat(APP, CONTRAT).results
// L'annonce à lecture obligatoire (celle qui porte le bouton d'accusé) et une
// annonce ordinaire — repérées PAR LEUR CONTENU, jamais par un id codé en dur.
const OBLIGATOIRE = ANNONCES.find((a) => a.lecture_obligatoire)
const ORDINAIRE = ANNONCES.find((a) => !a.lecture_obligatoire)

function renderPage(search = '') {
  return render(
    <MemoryRouter initialEntries={[`/annonces${search}`]}>
      <AnnoncesPage />
    </MemoryRouter>,
  )
}

describe('AnnoncesPage (WIR177)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // L'enveloppe paginée COMPLÈTE du contrat (count/next/previous/results),
    // telle que le serveur la renvoie — pas seulement le tableau.
    getAnnonces.mockResolvedValue(reponseContrat(APP, CONTRAT))
  })

  it('l’exemple de contrat porte bien les deux cas dont l’écran a besoin', () => {
    // Garde-fou : si l'exemple committé perd l'un des deux, les tests
    // ci-dessous testeraient autre chose que ce qu'ils annoncent.
    expect(OBLIGATOIRE).toBeTruthy()
    expect(ORDINAIRE).toBeTruthy()
  })

  it('liste les annonces ACTIVES de la société', async () => {
    renderPage()
    expect(await screen.findByText(ORDINAIRE.titre)).toBeInTheDocument()
    expect(screen.getByText(OBLIGATOIRE.titre)).toBeInTheDocument()
    expect(getAnnonces).toHaveBeenCalledWith({ active: 1 })
  })

  it('sans `?annonce=`, l’annonce ÉPINGLÉE passe devant', async () => {
    // Référence de l'ordre par défaut — sans elle, le test de ciblage
    // ci-dessous pourrait être vert pour la mauvaise raison.
    expect(OBLIGATOIRE.epinglee).toBe(true)
    expect(ORDINAIRE.epinglee).toBe(false)
    renderPage()
    await screen.findByText(ORDINAIRE.titre)
    const cartes = screen.getAllByTestId(/^annonce-\d+$/)
    expect(cartes[0]).toHaveAttribute('data-testid', `annonce-${OBLIGATOIRE.id}`)
  })

  it('`?annonce=<pk>` remonte l’annonce visée en tête', async () => {
    // On cible l'annonce NON épinglée : sans le motif `?annonce=`, elle
    // arriverait EN DERNIER — la remontée prouve donc bien le ciblage (c'est
    // le lien que posent les deux notifications d'annonce).
    renderPage(`?annonce=${ORDINAIRE.id}`)
    await screen.findByText(ORDINAIRE.titre)
    const cartes = screen.getAllByTestId(/^annonce-\d+$/)
    expect(cartes[0]).toHaveAttribute('data-testid', `annonce-${ORDINAIRE.id}`)
  })

  it('« J’ai lu et compris » enregistre l’accusé et affiche la confirmation', async () => {
    renderPage()
    const bouton = await screen.findByText('J’ai lu et compris')
    await userEvent.click(bouton)
    await waitFor(() => expect(accuserLectureAnnonce)
      .toHaveBeenCalledWith(OBLIGATOIRE.id))
    expect(await screen.findByTestId(`annonce-lue-${OBLIGATOIRE.id}`))
      .toBeInTheDocument()
    // Un seul accusé posé : le bouton a laissé place à la confirmation
    // (le POST reste idempotent côté serveur — cf. `acknowledge_annonce`).
    expect(screen.queryByText('J’ai lu et compris')).toBeNull()
    expect(accuserLectureAnnonce).toHaveBeenCalledTimes(1)
  })

  it('aucun bouton d’accusé sur une annonce sans lecture obligatoire', async () => {
    getAnnonces.mockResolvedValue({
      data: { ...exempleContrat(APP, CONTRAT), count: 1, results: [ORDINAIRE] },
    })
    renderPage()
    await screen.findByText(ORDINAIRE.titre)
    expect(screen.queryByText('J’ai lu et compris')).toBeNull()
  })

  it('état vide quand aucune annonce active', async () => {
    // L'AUTRE ÉTAT du serveur, committé lui aussi — jamais un `{}` inventé.
    getAnnonces.mockResolvedValue(reponseContrat(APP, CONTRAT, 'exemple_vide'))
    renderPage()
    expect(await screen.findByText('Aucune annonce')).toBeInTheDocument()
  })
})
