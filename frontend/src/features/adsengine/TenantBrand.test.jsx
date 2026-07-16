import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import TenantBrand from './TenantBrand'
import { setTenantTheme, resetTenantTheme } from '../../design/tenantTheme'

/* ENG31 — le bandeau de marque tenant s'appuie sur core.TenantTheme (via le
   pub/sub design/tenantTheme) : logo + nom quand configuré, repli propre sinon. */

beforeEach(() => { resetTenantTheme() })
afterEach(() => { resetTenantTheme() })

describe('TenantBrand (ENG31)', () => {
  it('repli propre : nom produit par défaut, aucun logo', () => {
    render(<TenantBrand />)
    expect(screen.getByTestId('ae-tenant-name')).toHaveTextContent('TAQINOR')
    expect(screen.queryByTestId('ae-tenant-logo')).toBeNull()
  })

  it('thème configuré : logo + nom du tenant', () => {
    setTenantTheme({
      nom_affichage: 'SK Paysages',
      logo_url: 'https://cdn/logo.png',
      couleur_primaire: '#0a7', couleur_secondaire: '#053',
    })
    render(<TenantBrand />)
    expect(screen.getByTestId('ae-tenant-name')).toHaveTextContent('SK Paysages')
    const logo = screen.getByTestId('ae-tenant-logo')
    expect(logo).toHaveAttribute('src', 'https://cdn/logo.png')
    expect(logo).toHaveAttribute('alt', 'SK Paysages')
  })

  it('sous-titre optionnel affiché', () => {
    render(<TenantBrand subtitle="Brief hebdomadaire" />)
    expect(screen.getByText(/Brief hebdomadaire/)).toBeInTheDocument()
  })
})
