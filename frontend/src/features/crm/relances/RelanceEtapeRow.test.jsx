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

// CAD10 — la liste des motifs de perte (Paramètres → CRM), lue au premier
// refus choisi. Forme du `MotifPerteSerializer` (id, nom, archived, est_junk).
vi.mock('../../../api/crmApi', () => ({
  default: {
    getMotifsPerte: vi.fn(() => Promise.resolve({
      data: [
        { id: 1, nom: 'Prix', archived: false, est_junk: false },
        { id: 2, nom: 'Numéro invalide', archived: false, est_junk: true },
        { id: 3, nom: 'Ancien motif', archived: true, est_junk: false },
      ],
    })),
  },
}))

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

  it('« Répondeur » envoie l’issue SERVEUR non_joint avec sa précision en note (réconciliation CKP2↔CKP4 : le serveur ne connaît que LeadActivity.OUTCOMES)', async () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    render(
      <RelanceEtapeRow etape={ETAPE_APPEL} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Répondeur' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_APPEL.id, { outcome: 'non_joint', note: 'Répondeur' }))
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

// CAD5 — « Ne plus me contacter » sur TOUTES les cadences. Les deux touches du
// contrat committé `relance_etape_v2.json` servent de départ : la première est
// un appel de prise de contact, la seconde un WhatsApp du suivi de proposition.
const ETAPE_APRES_DEVIS = exempleContrat('crm', 'relance_etape_v2').results[1]

// CAD4 — « Client joint » est LE mot des trois cadences : une seule issue
// serveur (`joint`), jamais une seconde étiquette pour le même effet moteur.
describe('CAD4 RelanceEtapeRow — un seul mot pour « je l’ai eu »', () => {
  const ETAPE_REVEIL = { ...ETAPE_APPEL, cadence: 'reveil', ordre: 1, libelle: 'Réveil J30' }

  it.each([
    ['prise de contact', ETAPE_APPEL],
    ['suivi de proposition', ETAPE_APRES_DEVIS],
    ['réveil', ETAPE_REVEIL],
  ])('%s : « Client joint » envoie l’issue `joint`, aucune seconde étiquette', async (_nom, etape) => {
    const onFait = vi.fn(() => Promise.resolve({}))
    render(
      <RelanceEtapeRow etape={etape} onFait={onFait} onSauter={noop} onReporter={noop}
        onOuvrirMessage={noop} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    // L'ancienne seconde étiquette (écrite en motif : le mot lui-même ne doit
    // plus apparaître dans ce dossier, hors historique).
    expect(screen.queryByRole('button', { name: /^Int.ress.$/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Client joint' }))
    // Touche message du suivi : la confirmation « sans ouverture » n'est pas
    // demandée (message ouvert dans le contrat) — le geste part directement.
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      etape.id, expect.objectContaining({ outcome: 'joint' })))
  })
})

function ouvrirFait(etape, props = {}) {
  render(
    <RelanceEtapeRow etape={etape} onFait={noop} onSauter={noop} onReporter={noop}
      onOuvrirMessage={noop} {...props} />,
  )
  fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
}

describe('CAD5 RelanceEtapeRow — « Ne plus me contacter »', () => {
  it('la réponse est proposée sur une touche de prise de contact ET sur le suivi de proposition', () => {
    ouvrirFait(ETAPE_APPEL)
    expect(screen.getByRole('button', { name: 'Ne plus me contacter' })).toBeInTheDocument()
    cleanup()
    ouvrirFait(ETAPE_APRES_DEVIS)
    expect(screen.getByRole('button', { name: 'Ne plus me contacter' })).toBeInTheDocument()
  })

  it('envoie la CLÉ de réponse (jamais une issue inventée côté écran)', async () => {
    const onFait = vi.fn(() => Promise.resolve({ prochaine_touche: null }))
    ouvrirFait(ETAPE_APPEL, { onFait })
    fireEvent.click(screen.getByRole('button', { name: 'Ne plus me contacter' }))
    expect(screen.getByTestId('suite-reponse')).toHaveTextContent(/sans étape de décision/)
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_APPEL.id, { reponse: 'ne_plus_contacter' }))
  })

  it('propose ensuite l’accusé « stop_contact » dans la modale d’aperçu (jamais envoyé seul)', async () => {
    const onFait = vi.fn(() => Promise.resolve({ prochaine_touche: null }))
    const onOuvrirMessage = vi.fn()
    ouvrirFait(ETAPE_APPEL, { onFait, onOuvrirMessage })
    fireEvent.click(screen.getByRole('button', { name: 'Ne plus me contacter' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onOuvrirMessage).toHaveBeenCalledWith(
      { ...ETAPE_APPEL, message_cle: 'stop_contact' }))
  })

  it('un refus serveur {erreurs: {reponse}} s’affiche SOUS les réponses', async () => {
    const erreur = {
      response: { status: 400, data: { erreurs: { reponse: 'Cette touche est déjà traitée.' } } },
    }
    const onFait = vi.fn(() => Promise.reject(erreur))
    ouvrirFait(ETAPE_APPEL, { onFait })
    fireEvent.click(screen.getByRole('button', { name: 'Ne plus me contacter' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByTestId('erreur-outcome'))
      .toHaveTextContent('Cette touche est déjà traitée.')
  })
})

// CAD6 — « Plus tard — pas maintenant » : date convenue obligatoire, la CLÉ
// part (jamais l'issue), puis le texte `rappel_plus_tard` est PROPOSÉ.
describe('CAD6 RelanceEtapeRow — « Plus tard — pas maintenant »', () => {
  afterEach(() => { vi.useRealTimers() })

  it('est proposée sur la prise de contact ET le suivi de proposition', () => {
    ouvrirFait(ETAPE_APPEL)
    expect(screen.getByRole('button', { name: 'Plus tard — pas maintenant' })).toBeInTheDocument()
    cleanup()
    ouvrirFait(ETAPE_APRES_DEVIS)
    expect(screen.getByRole('button', { name: 'Plus tard — pas maintenant' })).toBeInTheDocument()
  })

  it('exige la date convenue puis envoie {reponse, rappel_le} et propose le texte', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-09-23T09:00:00Z'))
    const onFait = vi.fn(() => Promise.resolve({ prochaine_touche: null }))
    const onOuvrirMessage = vi.fn()
    ouvrirFait(ETAPE_APPEL, { onFait, onOuvrirMessage })
    fireEvent.click(screen.getByRole('button', { name: 'Plus tard — pas maintenant' }))
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Rappeler le'), { target: { value: '2026-10-14' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_APPEL.id, { reponse: 'plus_tard', rappel_le: '2026-10-14' }))
    await waitFor(() => expect(onOuvrirMessage).toHaveBeenCalledWith(
      { ...ETAPE_APPEL, message_cle: 'rappel_plus_tard' }))
  })
})

// CAD7 — « Question de prix » : seulement sur le suivi de proposition ; la
// CLÉ part, et aucun texte n'est proposé (l'offre du fondateur attend sa
// décision).
describe('CAD7 RelanceEtapeRow — « Question de prix — veut négocier »', () => {
  it('n’existe que sur le suivi de proposition', () => {
    ouvrirFait(ETAPE_APPEL)
    expect(screen.queryByRole('button', { name: 'Question de prix — veut négocier' }))
      .not.toBeInTheDocument()
    cleanup()
    ouvrirFait(ETAPE_APRES_DEVIS)
    expect(screen.getByRole('button', { name: 'Question de prix — veut négocier' }))
      .toBeInTheDocument()
  })

  it('envoie la clé et ne propose AUCUN message', async () => {
    const onFait = vi.fn(() => Promise.resolve({ prochaine_touche: null }))
    const onOuvrirMessage = vi.fn()
    ouvrirFait(ETAPE_APRES_DEVIS, { onFait, onOuvrirMessage })
    fireEvent.click(screen.getByRole('button', { name: 'Question de prix — veut négocier' }))
    expect(screen.getByTestId('suite-reponse')).toHaveTextContent(/aucun message ne part/)
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_APRES_DEVIS.id, { reponse: 'question_prix' }))
    expect(onOuvrirMessage).not.toHaveBeenCalled()
  })
})

// CAD8 — « Demande un devis modifié » : atteignable sur toute touche du
// suivi de proposition (plus seulement après une visite).
describe('CAD8 RelanceEtapeRow — « Demande un devis modifié »', () => {
  it('est proposée sur le suivi de proposition, jamais en prise de contact', () => {
    ouvrirFait(ETAPE_APPEL)
    expect(screen.queryByRole('button', { name: 'Demande un devis modifié' }))
      .not.toBeInTheDocument()
    cleanup()
    ouvrirFait(ETAPE_APRES_DEVIS)
    expect(screen.getByRole('button', { name: 'Demande un devis modifié' })).toBeInTheDocument()
  })

  it('envoie la clé de réponse', async () => {
    const onFait = vi.fn(() => Promise.resolve({ prochaine_touche: null }))
    ouvrirFait(ETAPE_APRES_DEVIS, { onFait })
    fireEvent.click(screen.getByRole('button', { name: 'Demande un devis modifié' }))
    expect(screen.getByTestId('suite-reponse')).toHaveTextContent(/Préparer le devis modifié/)
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_APRES_DEVIS.id, { reponse: 'devis_modifie' }))
  })
})

// CAD9 — « Décision à plusieurs » : deux nuances sur le suivi de proposition,
// chacune sous sa propre CLÉ (la note typée est composée côté serveur).
describe('CAD9 RelanceEtapeRow — « Décision à plusieurs »', () => {
  it('propose la famille ET le propriétaire sur le suivi de proposition', () => {
    ouvrirFait(ETAPE_APRES_DEVIS)
    expect(screen.getByRole('button', { name: 'Décision à plusieurs — en famille' }))
      .toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Décision à plusieurs — le propriétaire' }))
      .toBeInTheDocument()
  })

  it('envoie la clé de la nuance choisie', async () => {
    const onFait = vi.fn(() => Promise.resolve({ prochaine_touche: null }))
    ouvrirFait(ETAPE_APRES_DEVIS, { onFait })
    fireEvent.click(screen.getByRole('button', { name: 'Décision à plusieurs — le propriétaire' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_APRES_DEVIS.id, { reponse: 'decision_proprietaire' }))
  })
})

// CAD10 — le motif de refus, FACULTATIF, proposé au seul moment où il est
// connu : le refus sans motif passe toujours ; le motif choisi part avec lui.
describe('CAD10 RelanceEtapeRow — motif de refus facultatif', () => {
  it('le refus propose la liste paramétrée (sans les archivés) et passe sans motif', async () => {
    const onFait = vi.fn(() => Promise.resolve({ prochaine_touche: null }))
    ouvrirFait(ETAPE_APPEL, { onFait })
    fireEvent.click(screen.getByRole('button', { name: 'Refus' }))
    expect(screen.getByLabelText('Motif du refus (facultatif)')).toBeInTheDocument()
    expect(await screen.findByRole('option', { name: 'Prix' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Ancien motif' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_APPEL.id, { outcome: 'refuse' }))
  })

  it('le motif choisi part avec le refus', async () => {
    const onFait = vi.fn(() => Promise.resolve({ prochaine_touche: null }))
    ouvrirFait(ETAPE_APRES_DEVIS, { onFait })
    fireEvent.click(screen.getByRole('button', { name: 'Refuse la proposition' }))
    await screen.findByRole('option', { name: 'Prix' })
    fireEvent.change(screen.getByLabelText('Motif du refus (facultatif)'), { target: { value: 'Prix' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_APRES_DEVIS.id, { outcome: 'refuse', motif_refus: 'Prix' }))
  })

  it('aucune liste n’est proposée hors refus', () => {
    ouvrirFait(ETAPE_APPEL)
    fireEvent.click(screen.getByRole('button', { name: 'Pas de réponse' }))
    expect(screen.queryByLabelText('Motif du refus (facultatif)')).not.toBeInTheDocument()
  })
})

// CAD11 — « Numéro invalide / a bloqué » : raccourci sur une touche APPEL
// (patron Répondeur/Occupé, aucune nouvelle issue), « perdu, motif junk »
// proposé en un clic, et `lead_est_junk` (contrat committé) visible.
describe('CAD11 RelanceEtapeRow — numéro invalide et junk', () => {
  it('le raccourci apparaît sur une touche appel, pas sur un WhatsApp', () => {
    ouvrirFait(ETAPE_APPEL)
    expect(screen.getByRole('button', { name: 'Numéro invalide' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'A bloqué / signalé' })).toBeInTheDocument()
    cleanup()
    ouvrirFait(ETAPE_APRES_DEVIS)
    expect(screen.queryByRole('button', { name: 'Numéro invalide' })).not.toBeInTheDocument()
  })

  it('sans la case, seule l’issue non_joint + la note typée partent', async () => {
    const onFait = vi.fn(() => Promise.resolve({ prochaine_touche: null }))
    ouvrirFait(ETAPE_APPEL, { onFait })
    fireEvent.click(screen.getByRole('button', { name: 'Numéro invalide' }))
    await screen.findByTestId('proposition-perdu-junk')
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(
      ETAPE_APPEL.id, { outcome: 'non_joint', note: 'Numéro invalide' }))
  })

  it('la case cochée propose « perdu, motif junk » en un clic', async () => {
    const onFait = vi.fn(() => Promise.resolve({ prochaine_touche: null }))
    ouvrirFait(ETAPE_APPEL, { onFait })
    fireEvent.click(screen.getByRole('button', { name: 'Numéro invalide' }))
    await screen.findByTestId('proposition-perdu-junk')
    fireEvent.click(screen.getByRole('checkbox', { name: /Marquer le lead perdu/ }))
    // Seuls les motifs JUNK de la liste sont proposés.
    expect(screen.queryByRole('option', { name: 'Prix' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(ETAPE_APPEL.id, {
      outcome: 'non_joint', note: 'Numéro invalide', perdu_junk: 'Numéro invalide',
    }))
  })

  it('`lead_est_junk` du contrat est visible sur la touche', () => {
    render(
      <RelanceEtapeRow etape={{ ...ETAPE_APPEL, lead_est_junk: true }} onFait={noop}
        onSauter={noop} onReporter={noop} onOuvrirMessage={noop} readOnly showStatut />,
    )
    expect(screen.getByText('Junk')).toBeInTheDocument()
    cleanup()
    render(
      <RelanceEtapeRow etape={ETAPE_APPEL} onFait={noop} onSauter={noop}
        onReporter={noop} onOuvrirMessage={noop} readOnly showStatut />,
    )
    expect(ETAPE_APPEL.lead_est_junk).toBe(false)
    expect(screen.queryByText('Junk')).not.toBeInTheDocument()
  })
})

// CAD26 — « Reporter » offre DEUX gestes ; au-delà de 7 jours, la mise en
// veille est proposée d'elle-même. Horloge figée (seul `Date` est simulé) :
// mercredi 23/09/2026 à Casablanca.
describe('CAD26 RelanceEtapeRow — décaler ou mettre en veille', () => {
  afterEach(() => { vi.useRealTimers() })

  function ouvrirReporter(onReporter) {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-09-23T09:00:00Z'))
    render(
      <RelanceEtapeRow etape={ETAPE_APPEL} onFait={noop} onSauter={noop}
        onReporter={onReporter} onOuvrirMessage={noop} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Reporter/ }))
  }

  it('un report de quelques jours reste un décalage (corps inchangé)', async () => {
    const onReporter = vi.fn(() => Promise.resolve({}))
    ouvrirReporter(onReporter)
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: '2026-09-25' } })
    expect(screen.queryByTestId('veille-proposee')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onReporter).toHaveBeenCalledWith(
      ETAPE_APPEL.id, { rappel_le: '2026-09-25', rappel_heure: '09:00' }))
  })

  it('au-delà de 7 jours, la veille est proposée et part avec mode=veille', async () => {
    const onReporter = vi.fn(() => Promise.resolve({ ...ETAPE_APPEL, due_date: '2026-10-14' }))
    ouvrirReporter(onReporter)
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: '2026-10-14' } })
    expect(screen.getByTestId('veille-proposee')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Mettre en veille/ }))
      .toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onReporter).toHaveBeenCalledWith(
      ETAPE_APPEL.id, { rappel_le: '2026-10-14', rappel_heure: '09:00', mode: 'veille' }))
    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith(
      'Dossier en veille : la cadence reprendra à cette même touche.'))
  })

  // CAD27 — une date passée est REFUSÉE par l'écran (champ borné, message qui
  // nomme le champ, Confirmer désactivé).
  it('CAD27 — « Reporter au » refuse hier et le dit sous le champ', () => {
    const onReporter = vi.fn()
    ouvrirReporter(onReporter)
    expect(screen.getByLabelText('Reporter au')).toHaveAttribute('min', '2026-09-23')
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: '2026-09-22' } })
    expect(screen.getByTestId('erreur-report-date')).toHaveTextContent('« Reporter au »')
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(onReporter).not.toHaveBeenCalled()
  })

  it('CAD27 — « À rappeler le… » refuse hier ; aujourd’hui reste accepté', () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-09-23T09:00:00Z'))
    ouvrirFait(ETAPE_APPEL)
    fireEvent.click(screen.getByRole('button', { name: 'À rappeler le…' }))
    fireEvent.change(screen.getByLabelText('Rappeler le'), { target: { value: '2026-09-22' } })
    expect(screen.getByTestId('erreur-rappel-le')).toHaveTextContent('« Rappeler le »')
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Rappeler le'), { target: { value: '2026-09-23' } })
    expect(screen.queryByTestId('erreur-rappel-le')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeEnabled()
  })

  it('CAD27 — le refus serveur {erreurs: {rappel_le}} s’affiche sous le champ', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-09-23T09:00:00Z'))
    const refus = '« Rappeler le » : le 22/09/2026 est déjà passé — choisissez aujourd’hui ou une date à venir.'
    const onFait = vi.fn(() => Promise.reject({
      response: { status: 400, data: { erreurs: { rappel_le: refus } } },
    }))
    ouvrirFait(ETAPE_APPEL, { onFait })
    fireEvent.click(screen.getByRole('button', { name: 'À rappeler le…' }))
    fireEvent.change(screen.getByLabelText('Rappeler le'), { target: { value: '2026-09-24' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByTestId('erreur-rappel-le')).toHaveTextContent(refus)
  })

  it('le choix explicite « Décaler ce rappel » prime sur la proposition', async () => {
    const onReporter = vi.fn(() => Promise.resolve({}))
    ouvrirReporter(onReporter)
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: '2026-10-14' } })
    fireEvent.click(screen.getByRole('button', { name: 'Décaler ce rappel' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(onReporter).toHaveBeenCalledWith(
      ETAPE_APPEL.id, { rappel_le: '2026-10-14', rappel_heure: '09:00' }))
  })
})
