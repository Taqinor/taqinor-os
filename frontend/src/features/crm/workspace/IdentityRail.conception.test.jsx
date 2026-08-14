import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { initState } from './draftCore'
import IdentityRail from './IdentityRail'

/* PV22 — chip « conception 3D » du rail identité. Les données viennent du bloc
   `conception` {kwc, image_url} DÉJÀ servi par la fiche lead (PV78) : aucun
   appel réseau n'est ajouté. NULL-SAFE : sans conception, le chip n'existe pas
   — jamais un « 0 kWc », jamais une vignette vide. */

vi.mock('../../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => true,
}))
vi.mock('../../../api/crmApi', () => ({
  default: {
    getLeadDuplicates: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadClientMatch: vi.fn(() => Promise.resolve({ data: [] })),
    mergeLeads: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../../../components/AssigneePicker', () => ({
  default: () => <div data-testid="assignee" />,
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

const makeState = (over = {}) => initState({
  lead: {
    id: 7, nom: 'Karim', prenom: 'B.', ville: 'Agadir',
    telephone: '0612345678', is_archived: false,
    devis_auto: { pret: false, message: 'Renseignez la facture.' },
    ...over,
  },
  mode: 'edit',
})

describe('PV22 — chip conception 3D (IdentityRail)', () => {
  it('affiche les kWc conçus et la vignette du toit servis par la fiche', () => {
    render(
      <IdentityRail
        state={makeState({
          conception: { kwc: 7.7, image_url: 'https://minio.test/toit-7.png' },
        })}
        onAction={vi.fn()}
        users={[]}
      />,
    )
    const chip = screen.getByTestId('lw-chip-conception')
    expect(chip).toHaveTextContent('7,7 kWc conçus')
    const vignette = chip.querySelector('img')
    expect(vignette).toHaveAttribute('src', 'https://minio.test/toit-7.png')
    // Décorative : jamais annoncée deux fois par le lecteur d'écran.
    expect(vignette).toHaveAttribute('alt', '')
  })

  it('sans image : le chip reste, la vignette disparaît', () => {
    render(
      <IdentityRail
        state={makeState({ conception: { kwc: 12, image_url: '' } })}
        onAction={vi.fn()}
        users={[]}
      />,
    )
    const chip = screen.getByTestId('lw-chip-conception')
    expect(chip).toHaveTextContent('12 kWc conçus')
    expect(chip.querySelector('img')).toBeNull()
  })

  it('aucune conception (bloc absent, null, ou 0 kWc) : aucun chip', () => {
    const { rerender } = render(
      <IdentityRail state={makeState()} onAction={vi.fn()} users={[]} />)
    expect(screen.queryByTestId('lw-chip-conception')).toBeNull()

    rerender(
      <IdentityRail
        state={makeState({ conception: { kwc: null, image_url: '' } })}
        onAction={vi.fn()} users={[]} />)
    expect(screen.queryByTestId('lw-chip-conception')).toBeNull()

    rerender(
      <IdentityRail
        state={makeState({ conception: { kwc: 0, image_url: '' } })}
        onAction={vi.fn()} users={[]} />)
    expect(screen.queryByTestId('lw-chip-conception')).toBeNull()
  })
})
