// SUIVI-REFUS (30/09/2026) — « Sauter » et « Reporter » DISENT leur refus,
// comme « Fait ». Incident : sur un double clic (deux onglets, liste périmée),
// le serveur répond 400 `{erreurs: {etape: "Cette étape est déjà traitée — …"}}`
// (SUIVI E8). Le parent avalait l'erreur de ces deux gestes (seul « Fait » la
// relançait) : le panneau « Reporter » se refermait « comme réussi » et seul un
// toast générique « Action impossible pour le moment. » passait. Règle fondateur
// du 08/09 : l'erreur NOMME le champ, SOUS le champ — jamais un toast seul.
//
// Ces tests montent la ligne SEULE avec un parent qui rejette ; le cockpit, la
// frise de la fiche et l'écran de suivi ont leurs propres cas (monter le vrai
// parent est ce qui prouve que l'erreur arrive bien jusqu'à la ligne). Étape de
// départ = le premier résultat du contrat COMMITTÉ `relance_etape_v2.json`.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn() }))
vi.mock('../../../api/crmApi', () => ({
  default: { getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { toastInfo } from '../../../lib/toast'

const ETAPE_APPEL = exempleContrat('crm', 'relance_etape_v2').results[0]

// Le message EXACT du serveur (`views.MESSAGE_ETAPE_DEJA_TRAITEE`).
const DEJA_TRAITEE = 'Cette étape est déjà traitée — rechargez la liste.'
const MESSAGE_ROLE = 'Votre rôle ne permet pas de traiter les relances (responsable ou administrateur requis).'
const MESSAGE_RESEAU = 'Pas de connexion au serveur — vérifiez le réseau et réessayez.'
const MESSAGE_SERVEUR = 'Le serveur n’a pas pu enregistrer la réponse — réessayez dans un instant.'

// CAD27 — l'écran REFUSE un report dans le passé : la date des tests de report
// est DEMAIN à Casablanca, jamais une date figée qui finit par passer.
const DEMAIN = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(new Date(Date.now() + 24 * 3600 * 1000))

afterEach(() => { cleanup(); vi.clearAllMocks() })

const refus = (status, data) => ({ response: { status, data } })
const refus400 = (erreurs) => refus(400, { erreurs })

function monter({ onSauter, onReporter, ...props } = {}) {
  return render(
    <RelanceEtapeRow
      etape={ETAPE_APPEL} onFait={vi.fn()} onSauter={onSauter ?? vi.fn()}
      onReporter={onReporter ?? vi.fn()} onOuvrirMessage={vi.fn()} {...props}
    />,
  )
}

function ouvrirReporter() {
  fireEvent.click(screen.getByRole('button', { name: /Reporter/ }))
  fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: DEMAIN } })
}
function ouvrirSauter(note = '') {
  fireEvent.click(screen.getByRole('button', { name: /Sauter/ }))
  if (note) {
    fireEvent.change(screen.getByPlaceholderText(/Note \(optionnelle\)/), { target: { value: note } })
  }
}
const confirmer = () => fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))

describe('SUIVI-REFUS — « Reporter » refusé par le serveur', () => {
  it('double clic (400 erreurs.etape) : le panneau RESTE ouvert et le message exact est sous le geste', async () => {
    const onReporter = vi.fn(() => Promise.reject(refus400({ etape: DEJA_TRAITEE })))
    monter({ onReporter })
    ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
    expect(onReporter).toHaveBeenCalledTimes(1)
    // Jamais refermé « comme réussi » : la date saisie et « Confirmer » restent.
    expect(screen.getByLabelText('Reporter au')).toHaveValue(DEMAIN)
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Fait$/ })).not.toBeInTheDocument()
    expect(toastInfo).not.toHaveBeenCalled()
  })

  it('le refus de DATE du serveur (erreurs.rappel_le) s’affiche SOUS « Reporter au » et s’efface à la retouche de la date', async () => {
    const refusDate = '« Reporter au » : le 22/09/2026 est déjà passé — choisissez aujourd’hui ou une date à venir.'
    const onReporter = vi.fn(() => Promise.reject(refus400({ rappel_le: refusDate })))
    monter({ onReporter })
    ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-report-date')).toHaveTextContent(refusDate)
    expect(screen.getByLabelText('Reporter au')).toHaveAttribute('aria-invalid', 'true')
    // La date refusée n'est pas une erreur « générale » : un seul message.
    expect(screen.queryByTestId('erreur-outcome')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: '2099-03-02' } })
    expect(screen.queryByTestId('erreur-report-date')).not.toBeInTheDocument()
  })

  it('403 : le message de rôle est en clair sous le geste', async () => {
    monter({ onReporter: vi.fn(() => Promise.reject(refus(403, { detail: 'Interdit.' }))) })
    ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(MESSAGE_ROLE)
    expect(screen.getByLabelText('Reporter au')).toBeInTheDocument()
  })

  it('400 avec detail (hors erreurs) : le detail du serveur est affiché tel quel', async () => {
    monter({ onReporter: vi.fn(() => Promise.reject(refus(400, { detail: 'Report impossible ce jour-là.' }))) })
    ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent('Report impossible ce jour-là.')
  })

  it('erreur réseau : phrase claire sous le geste, panneau ouvert', async () => {
    monter({ onReporter: vi.fn(() => Promise.reject(new Error('Network Error'))) })
    ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(MESSAGE_RESEAU)
    expect(screen.getByLabelText('Reporter au')).toHaveValue(DEMAIN)
  })

  it('500 : phrase claire sous le geste, panneau ouvert', async () => {
    monter({ onReporter: vi.fn(() => Promise.reject(refus(500, {}))) })
    ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(MESSAGE_SERVEUR)
  })

  it('une clé d’erreur que l’écran ne connaît pas (mode) n’est JAMAIS muette', async () => {
    const message = 'Geste inconnu : « x ». Choisir « decaler » ou « veille ».'
    monter({ onReporter: vi.fn(() => Promise.reject(refus400({ mode: message }))) })
    ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(message)
  })

  it('un 2e envoi efface le refus du 1er ; le succès referme le panneau', async () => {
    const onReporter = vi.fn()
      .mockRejectedValueOnce(refus400({ etape: DEJA_TRAITEE }))
      .mockResolvedValueOnce({})
    monter({ onReporter })
    ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
    confirmer()
    await waitFor(() => expect(onReporter).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByLabelText('Reporter au')).not.toBeInTheDocument())
    expect(screen.queryByTestId('erreur-outcome')).not.toBeInTheDocument()
  })

  it('succès : le panneau se referme et les gestes reviennent (comportement inchangé)', async () => {
    const onReporter = vi.fn(() => Promise.resolve({}))
    monter({ onReporter })
    ouvrirReporter()
    confirmer()
    await waitFor(() => expect(onReporter).toHaveBeenCalledWith(
      ETAPE_APPEL.id, { rappel_le: DEMAIN, rappel_heure: '09:00' }))
    await waitFor(() => expect(screen.queryByLabelText('Reporter au')).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Reporter/ })).toBeInTheDocument()
    expect(screen.queryByTestId('erreur-outcome')).not.toBeInTheDocument()
  })

  it('« Annuler » referme le panneau ET efface le refus affiché', async () => {
    monter({ onReporter: vi.fn(() => Promise.reject(refus400({ etape: DEJA_TRAITEE }))) })
    ouvrirReporter()
    confirmer()
    await screen.findByTestId('erreur-outcome')
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(screen.queryByTestId('erreur-outcome')).not.toBeInTheDocument()
    // Rouvert : plus aucune trace du refus précédent.
    fireEvent.click(screen.getByRole('button', { name: /Reporter/ }))
    expect(screen.queryByTestId('erreur-outcome')).not.toBeInTheDocument()
  })
})

describe('SUIVI-REFUS — « Sauter » refusé par le serveur', () => {
  it('400 erreurs.etape : le panneau RESTE ouvert (note conservée) et le message exact est sous le geste', async () => {
    const onSauter = vi.fn(() => Promise.reject(refus400({ etape: DEJA_TRAITEE })))
    monter({ onSauter })
    ouvrirSauter('Client en congé')
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
    expect(onSauter).toHaveBeenCalledWith(ETAPE_APPEL.id, 'Client en congé')
    // Panneau toujours là : phrase de suite, note saisie, bouton « Confirmer ».
    expect(screen.getByTestId('suite-sauter')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Note \(optionnelle\)/)).toHaveValue('Client en congé')
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeInTheDocument()
  })

  it('403 : le message de rôle est en clair sous le geste', async () => {
    monter({ onSauter: vi.fn(() => Promise.reject(refus(403, { detail: 'Interdit.' }))) })
    ouvrirSauter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(MESSAGE_ROLE)
  })

  it('erreur réseau : phrase claire sous le geste', async () => {
    monter({ onSauter: vi.fn(() => Promise.reject(new Error('Network Error'))) })
    ouvrirSauter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(MESSAGE_RESEAU)
  })

  it('500 : phrase claire sous le geste', async () => {
    monter({ onSauter: vi.fn(() => Promise.reject(refus(500, {}))) })
    ouvrirSauter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(MESSAGE_SERVEUR)
  })

  it('un 2e envoi efface le refus du 1er ; le succès referme le panneau', async () => {
    const onSauter = vi.fn()
      .mockRejectedValueOnce(refus400({ etape: DEJA_TRAITEE }))
      .mockResolvedValueOnce(undefined)
    monter({ onSauter })
    ouvrirSauter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
    confirmer()
    await waitFor(() => expect(onSauter).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByTestId('suite-sauter')).not.toBeInTheDocument())
    expect(screen.queryByTestId('erreur-outcome')).not.toBeInTheDocument()
  })

  // Avant, la ligne ne refermait pas elle-même le panneau « Sauter » : elle
  // comptait sur le parent (cockpit : ligne retirée ; suivi/fiche : relecture).
  // Sur une liste relue qui garde la touche `a_faire` (liste périmée), le
  // panneau restait alors ouvert avec « Confirmer » cliquable — comme « Reporter »
  // avant SUIVI-BLOCAGE. Les parents, eux, retirent/relisent toujours (cas
  // cockpit / suivi / fiche de leurs suites).
  it('succès : le panneau se referme et les gestes reviennent', async () => {
    const onSauter = vi.fn(() => Promise.resolve({}))
    monter({ onSauter })
    ouvrirSauter('Pas joignable')
    confirmer()
    await waitFor(() => expect(onSauter).toHaveBeenCalledWith(ETAPE_APPEL.id, 'Pas joignable'))
    await waitFor(() => expect(screen.queryByTestId('suite-sauter')).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Sauter/ })).toBeInTheDocument()
    expect(screen.queryByTestId('erreur-outcome')).not.toBeInTheDocument()
  })

  it('un parent qui ne renvoie pas de promesse (retour vide) referme quand même le panneau', async () => {
    const onSauter = vi.fn()
    monter({ onSauter })
    ouvrirSauter()
    confirmer()
    await waitFor(() => expect(screen.queryByTestId('suite-sauter')).not.toBeInTheDocument())
    expect(onSauter).toHaveBeenCalledTimes(1)
  })
})

describe('SUIVI-REFUS — « Fait » et le raccourci d’issue', () => {
  it('« Fait » : une clé d’erreur inconnue n’est plus muette non plus (le parent ne double plus le refus par un toast)', async () => {
    const message = 'Nouveau refus du serveur.'
    const onFait = vi.fn(() => Promise.reject(refus400({ nouvelle_cle: message })))
    monter({ onFait })
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Client joint' }))
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(message)
  })

  it('« Fait » : erreurs.etape (déjà traitée) reste affiché sous les réponses', async () => {
    const onFait = vi.fn(() => Promise.reject(refus400({ etape: DEJA_TRAITEE })))
    monter({ onFait })
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Client joint' }))
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
  })

  it('« Saisir l’issue de l’appel » n’hérite pas du refus d’un « Reporter » resté à l’écran', async () => {
    monter({
      onReporter: vi.fn(() => Promise.reject(refus400({ etape: DEJA_TRAITEE }))),
      panneauAppelInitial: true,
    })
    ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
    fireEvent.click(screen.getByRole('button', { name: /Saisir l’issue de l’appel/ }))
    // Le panneau « Fait » s'ouvre (ses réponses sont là) sans le refus périmé.
    expect(await screen.findByRole('button', { name: 'Client joint' })).toBeInTheDocument()
    expect(screen.queryByTestId('erreur-outcome')).not.toBeInTheDocument()
  })
})
