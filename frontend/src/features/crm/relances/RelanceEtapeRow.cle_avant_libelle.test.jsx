// PARAM-CADENCE (E8, décision fondateur 25/09/2026) — l'écran reconnaît une
// étape par sa CLÉ d'abord, son libellé ensuite : une société qui renomme ses
// barreaux (Paramètres → CRM, E5) ne doit jamais perdre les bonnes questions
// ni les boutons de l'étape « devis parti ». Étapes de départ = fixtures
// COMMITTÉES du contrat `relance_etape_v2.json` (PACT10), `cle`/`libelle`
// ajustés au cas par cas (même patron que les autres tests de cette ligne,
// ex. `RelanceEtapeRow.canaux.test.jsx` : un objet réel, un ou deux champs
// neutralisés/renommés — jamais un objet inventé de toutes pièces).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn(), toastSuccess: vi.fn(), toastError: vi.fn() }))
vi.mock('../../../api/crmApi', () => ({
  default: {
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
    enregistrerPieceRecue: vi.fn(),
  },
}))

afterEach(() => { cleanup(); vi.clearAllMocks(); window.sessionStorage.clear() })

function noop() {}

function ligne(etape, props = {}) {
  return render(
    <RelanceEtapeRow
      etape={etape} onFait={noop} onSauter={noop} onReporter={noop}
      onOuvrirMessage={noop} {...props}
    />,
  )
}

const GENERIQUE = exempleContrat('crm', 'relance_etape_v2', 'exemple_generique').results[0]
const DEBRIEF = exempleContrat('crm', 'relance_etape_v2', 'exemple_debrief_visite').results[0]

describe('PARAM-CADENCE — E8, la clé prime sur le libellé', () => {
  it('cle=\'devis\' + libellé renommé « Faire le devis » : boutons + étiquette « Devis envoyé — passer à la suite »', () => {
    // Renommé côté Paramètres (E5) : le libellé n'est PLUS un des
    // `LIBELLES_ETAPE_DEVIS` connus — seule `cle` permet encore de
    // reconnaître l'étape « devis parti ».
    ligne({ ...GENERIQUE, cle: 'devis', libelle: 'Faire le devis' })
    // Les deux actions de l'étape « devis parti » restent proposées.
    expect(screen.getByRole('link', { name: 'Créer le devis' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Planifier la visite' })).toBeInTheDocument()
    // « Fait » reformule l'issue neutre en « Devis envoyé… », jamais
    // « Fait — passer à la suite » (qui mentirait sur l'effet réel).
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByRole('button', { name: 'Devis envoyé — passer à la suite' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Fait — passer à la suite' })).not.toBeInTheDocument()
  })

  it('cle=\'debrief\' + libellé renommé garde les questions du débrief', () => {
    // Renommé côté Paramètres (E5) : le libellé n'est plus une clé de
    // `QUESTIONS_VISITE` — sans reconnaissance par `cle`, l'écran retomberait
    // sur la question générique de la cadence `apres_devis`.
    ligne({ ...DEBRIEF, cle: 'debrief', libelle: 'Rappeler après la visite (renommé)' })
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByText('La visite a-t-elle eu lieu ?')).toBeInTheDocument()
    expect(screen.queryByText('Réponse du client sur la proposition ?')).not.toBeInTheDocument()
  })

  it('une ancienne touche sans `cle`, au libellé par défaut, se comporte comme avant', () => {
    // `cle` VIDE (barreau du protocole / étape posée avant PARAM-CADENCE,
    // notes.cle du contrat) : le repli par libellé continue de fonctionner à
    // l'identique — aucune régression du comportement CAD2 existant.
    ligne({ ...DEBRIEF, cle: '' })
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByText('La visite a-t-elle eu lieu ?')).toBeInTheDocument()
  })
})
