import { describe, it, expect, vi } from 'vitest'

/* Vérifie que le graphe d'imports de CHAQUE écran RH se résout (composant par
   défaut exporté) — filet anti-régression contre un import cassé, sans monter
   les composants (qui exigeraient redux/router selon les cas). */

vi.mock('../../api/rhApi', () => ({ default: {} }))

describe('RH — résolution des imports de tous les écrans', () => {
  it('charge chaque module d’écran + la config sans erreur', async () => {
    // Écrans + config : tous doivent exporter un défaut (composant ou config).
    const withDefault = await Promise.all([
      import('./RhCockpit.jsx'),
      import('./EmployeList.jsx'),
      import('./EmployeDetail.jsx'),
      import('./Conges.jsx'),
      import('./Temps.jsx'),
      import('./Competences.jsx'),
      import('./Recrutement.jsx'),
      import('./Hse.jsx'),
      import('./Portail.jsx'),
      import('./module.config.jsx'),
    ])
    withDefault.forEach((m) => expect(m.default).toBeTruthy())
    // Les constantes exportent des pastilles nommées (pas de défaut).
    const constants = await import('./constants.jsx')
    expect(constants.StatutEmploye).toBeTruthy()
  }, 30000)

  it('la config RH expose la clé, la nav et les routes attendues', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('rh')
    expect(config.order).toBe(40)
    expect(config.nav.label).toBe('RH')
    // Le portail (UX28) est ouvert à tous les rôles → route SANS clé `roles`.
    const portail = config.routes.find((r) => r.path === '/rh/portail')
    expect(portail).toBeTruthy()
    expect(portail.roles).toBeUndefined()
    // Les écrans back-office sont gatés Responsable/Admin.
    const cockpit = config.routes.find((r) => r.path === '/rh')
    expect(cockpit.roles).toEqual(['responsable', 'admin'])
  })
})
