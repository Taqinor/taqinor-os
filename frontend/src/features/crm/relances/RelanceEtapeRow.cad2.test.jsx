// CAD2 — les quatre gestes de VISITE (rendez-vous technique) portent tous la
// cadence `apres_devis` (VISITE-CADENCE, pour vivre dans la même frise) mais
// AUCUN n'est un barreau du suivi de proposition : avant ce correctif,
// l'écran choisissait ses questions PAR CADENCE et proposait « Visite
// acceptée » / « Refuse la proposition » sur un débrief déjà tenu — la
// réponse naturelle « client joint » faisait même redémarrer le suivi de
// proposition depuis son barreau 1 (moitié serveur : commit bd98d0dd).
//
// La nature d'une touche se lit désormais sur son LIBELLÉ
// (`QUESTIONS_VISITE`) : chaque geste pose SA question, sur les issues
// EXISTANTES de `relance_etape_v2` (jamais une valeur d'énumération neuve,
// jamais « Intéressé », retiré par CAD4). Étape de départ = l'état COMMITTÉ
// du contrat (`exemple_debrief_visite`) — jamais un objet retapé à la main
// (PACT10) ; les trois autres libellés dérivent du MÊME objet (même forme),
// seul le libellé change, pour rester des états plausibles du serveur.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import RelanceEtapeRow from './RelanceEtapeRow'

vi.mock('../../../lib/toast', () => ({ toastInfo: vi.fn() }))
// CAD10 — un clic sur une réponse « Refuse » charge les motifs de perte.
vi.mock('../../../api/crmApi', () => ({
  default: { getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })) },
}))

const ETAPE_DEBRIEF = exempleContrat('crm', 'relance_etape_v2', 'exemple_debrief_visite').results[0]
// PARAM-CADENCE (25/09/2026) — l'écran reconnaît une étape par sa CLÉ d'abord
// (E8) : la ligne du contrat porte `cle: 'debrief'`, donc chaque variante ci-dessous
// pose aussi la clé qui va avec son libellé (vide pour un barreau du protocole).

afterEach(() => { cleanup(); vi.clearAllMocks() })

function noop() {}

function ouvrirFait(etape) {
  render(
    <RelanceEtapeRow etape={etape} onFait={noop} onSauter={noop} onReporter={noop} onOuvrirMessage={noop} />,
  )
  fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
}

describe('CAD2 — « Débrief visite » pose SA question, jamais celle du suivi de proposition', () => {
  it('question dédiée, « Intéressé » absent, « Visite acceptée » absent', () => {
    ouvrirFait(ETAPE_DEBRIEF)
    expect(screen.getByText('La visite a-t-elle eu lieu ?')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Intéressé' })).not.toBeInTheDocument()
    // « Visite acceptée » n'a de sens que sur le geste qui CALE la date
    // (« Planifier la visite technique convenue ») — jamais sur un débrief.
    expect(screen.queryByRole('button', { name: 'Visite acceptée' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Oui, client joint après la visite' })).toBeInTheDocument()
  })

  it('« Client joint » envoie l’issue serveur EXISTANTE `joint`, jamais un code inventé', () => {
    const onFait = vi.fn(() => Promise.resolve({}))
    render(
      <RelanceEtapeRow etape={ETAPE_DEBRIEF} onFait={onFait} onSauter={noop} onReporter={noop} onOuvrirMessage={noop} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Oui, client joint après la visite' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(onFait).toHaveBeenCalledWith(ETAPE_DEBRIEF.id, { outcome: 'joint' })
  })

  it('les réponses du CLIENT de la cadence après-devis restent proposées (question de prix, devis modifié…)', () => {
    ouvrirFait(ETAPE_DEBRIEF)
    expect(screen.getByRole('button', { name: 'Question de prix — veut négocier' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Demande un devis modifié' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ne plus me contacter' })).toBeInTheDocument()
  })
})

describe('CAD2 — les trois autres gestes de visite ont chacun leur propre question', () => {
  it('« Planifier la visite technique convenue » : caler la date, « Visite acceptée » proposé', () => {
    const filet = { ...ETAPE_DEBRIEF, cle: 'planifier', libelle: 'Planifier la visite technique convenue' }
    ouvrirFait(filet)
    expect(screen.getByText('La date du rendez-vous a-t-elle été calée ?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Oui, la date est calée' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Intéressé' })).not.toBeInTheDocument()
  })

  it('« Confirmer la visite (veille) » : le rendez-vous tient-il, jamais « Intéressé »', () => {
    const confirmation = { ...ETAPE_DEBRIEF, cle: 'confirmation', libelle: 'Confirmer la visite (veille)', canal: 'whatsapp' }
    ouvrirFait(confirmation)
    expect(screen.getByText('Le rendez-vous de demain est-il confirmé ?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmé — le rendez-vous tient' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Intéressé' })).not.toBeInTheDocument()
  })

  it('« Préparer le devis modifié — rappeler le client » : sa propre question', () => {
    const devisModifie = { ...ETAPE_DEBRIEF, cle: 'devis_modifie', libelle: 'Préparer le devis modifié — rappeler le client' }
    ouvrirFait(devisModifie)
    expect(screen.getByText('Le devis modifié est prêt : le client est-il rappelé ?')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Intéressé' })).not.toBeInTheDocument()
  })

  it('une touche du suivi de proposition ORDINAIRE (barreau) garde son jeu de questions par cadence', () => {
    const barreau = { ...ETAPE_DEBRIEF, cle: '', libelle: 'Preuve — installation comparable' }
    ouvrirFait(barreau)
    expect(screen.getByText('Réponse du client sur la proposition ?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Visite acceptée' })).toBeInTheDocument()
  })
})
