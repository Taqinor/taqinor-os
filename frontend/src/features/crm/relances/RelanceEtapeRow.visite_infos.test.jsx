// PARAM-CADENCE (E7, décision fondateur 25/09/2026) — sous le libellé d'un
// geste de visite, la date de la visite technique du lead et, quand le
// retour terrain est saisi, un lien direct vers son écran. Étape de départ =
// `exemple_debrief_visite` du contrat COMMITTÉ `relance_etape_v2.json`
// (PACT10, seule variante qui porte `visite_prevue_le`/`visite_id`/
// `visite_retour_disponible`) — jamais un objet retapé à la main ; les cas
// négatifs réutilisent cette même fixture, un seul champ neutralisé à la
// fois (même patron que les autres tests de cette ligne, ex.
// `RelanceEtapeRow.canaux.test.jsx`).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { formatDate } from '../../../lib/format'
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

const TOUCHE_DEBRIEF = exempleContrat('crm', 'relance_etape_v2', 'exemple_debrief_visite').results[0]
const TOUCHE_ORDINAIRE = exempleContrat('crm', 'relance_etape_v2').results[0]

describe('PARAM-CADENCE — E7, la visite sur la ligne', () => {
  it('affiche « Visite prévue le JJ/MM/AAAA » et le lien « Ouvrir le retour »', () => {
    ligne(TOUCHE_DEBRIEF)
    expect(screen.getByTestId('visite-infos')).toHaveTextContent(
      `Visite prévue le ${formatDate(TOUCHE_DEBRIEF.visite_prevue_le)}`)
    const lien = screen.getByRole('link', { name: 'Ouvrir le retour' })
    expect(lien).toHaveAttribute('href', `/visites/${TOUCHE_DEBRIEF.visite_id}`)
  })

  it('le lien navigue via `navigate` (même repli que « Créer le devis »), aucun Router requis', () => {
    const navigate = vi.fn()
    ligne(TOUCHE_DEBRIEF, { navigate })
    fireEvent.click(screen.getByRole('link', { name: 'Ouvrir le retour' }))
    expect(navigate).toHaveBeenCalledWith(`/visites/${TOUCHE_DEBRIEF.visite_id}`)
  })

  it('un geste de visite SANS retour disponible n’affiche que la date, aucun lien', () => {
    ligne({ ...TOUCHE_DEBRIEF, visite_retour_disponible: false, visite_id: null })
    expect(screen.getByTestId('visite-infos')).toHaveTextContent(
      `Visite prévue le ${formatDate(TOUCHE_DEBRIEF.visite_prevue_le)}`)
    expect(screen.queryByRole('link', { name: 'Ouvrir le retour' })).not.toBeInTheDocument()
  })

  it('un geste de visite sans aucune info de visite servie : rien ne s’affiche', () => {
    ligne({
      ...TOUCHE_DEBRIEF, visite_prevue_le: null, visite_id: null, visite_retour_disponible: false,
    })
    expect(screen.queryByTestId('visite-infos')).not.toBeInTheDocument()
  })

  it('une touche ORDINAIRE (pas un geste de visite) n’affiche rien, même avec des infos de visite servies', () => {
    ligne({
      ...TOUCHE_ORDINAIRE, visite_prevue_le: '2026-09-27', visite_id: 5, visite_retour_disponible: true,
    })
    expect(screen.queryByTestId('visite-infos')).not.toBeInTheDocument()
  })
})
