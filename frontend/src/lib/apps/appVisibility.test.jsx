// ODY27 — `useAppVisibility()` : LE prédicat unique « cette app / ce chemin
// est-il visible ? » consommé par les surfaces TRANSVERSES (palette ⌘K,
// recherche globale, cloche, Dashboard). Adossé à `useInstalledApps()` (ODY1) :
// aucune de ces surfaces ne tient de liste d'apps locale.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { useAppVisibility } from './ActiveAppContext'

function makeStore({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: { auth: (s = { role, permissions, modulesDesactives, user: null }) => s },
  })
}

function Probe({ paths = [], apps = [] }) {
  const { isAppVisible, isPathVisible } = useAppVisibility()
  return (
    <div>
      {paths.map((p) => (
        <span key={p} data-testid={`path:${p}`}>{isPathVisible(p) ? 'oui' : 'non'}</span>
      ))}
      {apps.map((k) => (
        <span key={k} data-testid={`app:${k}`}>{isAppVisible(k) ? 'oui' : 'non'}</span>
      ))}
    </div>
  )
}

function renderProbe(props, storeOpts) {
  return render(
    <Provider store={makeStore(storeOpts)}>
      <MemoryRouter><Probe {...props} /></MemoryRouter>
    </Provider>,
  )
}

const verdict = (testId) => screen.getByTestId(testId).textContent

describe('ODY27 — useAppVisibility', () => {
  it('par défaut (rien de désactivé, rôle admin) tout est visible', () => {
    renderProbe(
      { paths: ['/ventes/devis', '/crm/leads', '/stock'], apps: ['ventes', 'crm'] },
    )
    expect(verdict('path:/ventes/devis')).toBe('oui')
    expect(verdict('path:/crm/leads')).toBe('oui')
    expect(verdict('path:/stock')).toBe('oui')
    expect(verdict('app:ventes')).toBe('oui')
    expect(verdict('app:crm')).toBe('oui')
  })

  it('une app désactivée pour la société (ODX6) devient invisible — et elle SEULE', () => {
    renderProbe(
      { paths: ['/ventes/devis', '/ventes/factures', '/crm/leads'], apps: ['ventes', 'crm'] },
      { modulesDesactives: ['ventes'] },
    )
    expect(verdict('path:/ventes/devis')).toBe('non')
    expect(verdict('path:/ventes/factures')).toBe('non')
    expect(verdict('path:/crm/leads')).toBe('oui')
    expect(verdict('app:ventes')).toBe('non')
    expect(verdict('app:crm')).toBe('oui')
  })

  it('une app dont AUCUN écran n’est autorisé au rôle est invisible (ARC47)', () => {
    // Tous les items de nav de l'app Paramètres exigent responsable/admin.
    renderProbe({ paths: ['/parametres', '/crm/leads'] }, { role: 'normal' })
    expect(verdict('path:/parametres')).toBe('non')
    expect(verdict('path:/crm/leads')).toBe('oui')
  })

  it('un chemin TRANSVERSE (hors de toute app) reste toujours visible', () => {
    // Le filtre ne masque QUE ce qui appartient à une app absente : il ne
    // masque jamais par défaut (un nouveau type/écran n'est pas avalé).
    renderProbe({ paths: ['/apps', '/chemin-inconnu'] }, { modulesDesactives: ['ventes', 'crm'] })
    expect(verdict('path:/apps')).toBe('oui')
    expect(verdict('path:/chemin-inconnu')).toBe('oui')
  })

  it('tolère une clé/chemin vide (jamais un masquage accidentel)', () => {
    renderProbe({ paths: [''], apps: [''] })
    expect(verdict('path:')).toBe('oui')
    expect(verdict('app:')).toBe('oui')
  })

  it('la query string n’empêche pas la résolution de l’app', () => {
    renderProbe({ paths: ['/ventes/devis?devis=42'] }, { modulesDesactives: ['ventes'] })
    expect(verdict('path:/ventes/devis?devis=42')).toBe('non')
  })
})
