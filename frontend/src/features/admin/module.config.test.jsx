import { describe, it, expect } from 'vitest'

/* ODY23 — « Dashboard → app Tableau de bord ». `admin/module.config.jsx`
   gagne sa PREMIÈRE section `nav` (jusqu'ici routes-only) : un item unique
   vers `/dashboard` (route/page inchangées, propriété ODY27 — hors
   périmètre). Voir le commentaire de tête du fichier pour la justification
   du choix (pas de nouveau `features/dashboard/module.config.jsx`, hors
   périmètre ODY23). Les routes historiques (Utilisateurs/Rôles/Tenants/
   Sécurité/Gouvernance) restent inchangées ; leurs entrées de MENU vivent
   désormais dans `features/parametres/module.config.jsx` (app Paramètres). */
describe('admin — module.config (ODY23 Tableau de bord)', () => {
  it('déclare une nav "TABLEAU DE BORD" avec /dashboard en 1er (et unique) item', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('admin')
    expect(config.nav).toBeTruthy()
    expect(config.nav.label).toBe('TABLEAU DE BORD')
    expect(config.nav.items).toHaveLength(1)

    const navItem = config.nav.items[0]
    expect(navItem.to).toBe('/dashboard')
    expect(navItem.label).toBe('Tableau de bord')
    expect(navItem.roles).toEqual(['normal', 'responsable', 'admin'])
    expect(navItem.icon).toBeTruthy()
  })

  it('ne redéclare pas de route pour /dashboard (page ODY27, router/index.jsx inchangé)', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.routes.find((r) => r.path === '/dashboard')).toBeFalsy()
  })

  it('garde ses 5 routes Administration historiques inchangées', async () => {
    const { default: config } = await import('./module.config.jsx')
    const paths = config.routes.map((r) => r.path).sort()
    expect(paths).toEqual([
      '/admin/gouvernance-acces',
      '/admin/roles',
      '/admin/securite-identite',
      '/admin/tenants',
      '/admin/users',
    ])
  })
})
