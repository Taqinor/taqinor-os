import { describe, it, expect } from 'vitest'
import {
  selectModulesDesactives,
  isModuleDisabled,
  filterNavSections,
  estAutoriseEntree,
  porteUnCodeDuModule,
  REPLI_ROLES,
} from './moduleGating'
import { moduleConfigs } from './moduleRoutes'
import { registrePermissions } from '../test/fixtures/contractSamples'

describe('ODX6 — moduleGating (gating par module actif/désactivé)', () => {
  it('selectModulesDesactives : repli [] si absent', () => {
    expect(selectModulesDesactives({ auth: {} })).toEqual([])
    expect(selectModulesDesactives({ auth: { modulesDesactives: ['flotte'] } }))
      .toEqual(['flotte'])
  })

  it('isModuleDisabled : clé désactivée → true ; clé absente/nulle → false', () => {
    expect(isModuleDisabled(['flotte'], 'flotte')).toBe(true)
    expect(isModuleDisabled(['flotte'], 'stock')).toBe(false)
    // Section globale sans clé : jamais désactivée.
    expect(isModuleDisabled(['flotte'], null)).toBe(false)
    expect(isModuleDisabled(['flotte'], undefined)).toBe(false)
    expect(isModuleDisabled([], 'flotte')).toBe(false)
  })

  it('filterNavSections : liste vide de désactivés → sections INCHANGÉES (même référence)', () => {
    const sections = [{ key: 'stock' }, { label: 'ADMIN' }]
    // Chemin par défaut : aucune copie, byte-identique.
    expect(filterNavSections(sections, [])).toBe(sections)
    expect(filterNavSections(sections, undefined)).toBe(sections)
  })

  it('filterNavSections : retire la section du module désactivé, garde les autres et les globales', () => {
    const sections = [
      { label: null },                 // globale (Dashboard) sans clé
      { key: 'stock', label: 'STOCK' },
      { key: 'flotte', label: 'FLOTTE' },
      { label: 'ADMINISTRATION' },     // globale sans clé
    ]
    const out = filterNavSections(sections, ['flotte'])
    expect(out.map((s) => s.label)).toEqual([null, 'STOCK', 'ADMINISTRATION'])
    // La section flotte est bien absente.
    expect(out.find((s) => s.key === 'flotte')).toBeUndefined()
  })
})

/* T4-X8-016 (lot 8) — `permModule` : miroir EXACT de `LectureDuModule`
   (backend/django_core/authentication/permissions.py). Rôles et module des codes LUS du golden committé du
   registre (`apps/roles/golden/registre_permissions.json`, plancher vérifié par
   `apps/roles/tests_spl300_registre_golden.py`) — aucune liste de codes recopiée ici. */
describe('T4-X8-016 — permModule suit LectureDuModule, ni plus strict ni plus large', () => {
  const registre = registrePermissions()
  const moduleDe = registre.dicts.PERMISSION_MODULE
  const codesCrm = new Set(Object.keys(moduleDe).filter((c) => moduleDe[c] === 'crm'))
  const ENTREE = { roles: ['normal', 'responsable', 'admin'], permModule: 'crm', permRepliPalier: REPLI_ROLES }

  // Le palier de menu servi (`authentication/role_tiers.py::tier_for_role_fields`, permissions fournies).
  const palier = (perms) => (perms.includes('roles_gerer') ? 'admin'
    : perms.includes('users_voir') ? 'responsable' : 'normal')
  // `LectureDuModule.has_permission` pour une vue du module crm (aucun octroi crm dans OCTROIS_LECTURE).
  const serveur = ({ portee = 'interne', legacy = false, perms = [] }) => {
    if (portee !== 'interne') return false // IsAnyRole
    if (legacy || perms.includes('roles_gerer')) return true // compte hérité, is_admin_role
    return perms.some((c) => codesCrm.has(c))
  }

  // Verdict ATTENDU, écrit à la main : la table ne peut pas être fausse des deux côtés à la fois.
  const ATTENDU = {
    Directeur: true, Administrateur: true, 'Commercial responsable': true, Commercial: true,
    'Commercial terrain': false, 'Technicien responsable': false, Technicien: false, Viewer: true,
    Responsable: true, Utilisateur: true, 'Admin RH': false, 'Admin Ventes': true,
    'Portail client': false, 'Portail fournisseur': false, 'Portail partenaire': false,
  }
  const roles = registre.registres_roles.CANONICAL_SYSTEM_ROLES

  it('chaque rôle système du registre : verdict serveur = verdict front = verdict attendu', () => {
    expect(roles.map(([nom]) => nom).sort()).toEqual(Object.keys(ATTENDU).sort())
    for (const [nom, perms] of roles) {
      const portee = nom.startsWith('Portail') ? 'externe' : 'interne'
      const attendu = ATTENDU[nom]
      expect(serveur({ portee, perms }), `${nom} (serveur)`).toBe(attendu)
      expect(estAutoriseEntree(ENTREE, palier(perms), perms), `${nom} (front)`).toBe(attendu)
    }
  })

  it('rôle PERSONNALISÉ crm_creer seul (sans crm_voir) : lu par le serveur, ouvert par le front', () => {
    expect(serveur({ perms: ['crm_creer'] })).toBe(true)
    expect(estAutoriseEntree(ENTREE, 'normal', ['crm_creer'])).toBe(true)
    // … mais pas par la règle crm_voir des Leads.
    expect(estAutoriseEntree({ ...ENTREE, permModule: undefined, perm: 'crm_voir' }, 'normal', ['crm_creer']))
      .toBe(false)
  })

  it('compte LÉGACY (aucune permission servie) : lu par le serveur, ouvert par le front à chaque palier', () => {
    for (const tier of ['normal', 'responsable', 'admin']) {
      expect(serveur({ legacy: true })).toBe(true)
      expect(estAutoriseEntree(ENTREE, tier, []), tier).toBe(true)
    }
  })

  it('palier admin sans code crm (roles_gerer) : ouvert des deux côtés', () => {
    expect(serveur({ perms: ['roles_gerer'] })).toBe(true)
    expect(estAutoriseEntree(ENTREE, 'admin', ['roles_gerer'])).toBe(true)
  })

  it('les codes reconnus par le préfixe sont EXACTEMENT ceux du module au registre, pour chaque permModule déclaré', () => {
    const declares = moduleConfigs.flatMap((c) => [...(c.nav?.items ?? []), ...(c.routes ?? [])])
      .filter((e) => e.permModule)
    // Appliqué aujourd'hui aux seuls Défis, Parrainage et Profils site (menu + route).
    expect([...new Set(declares.map((e) => e.to ?? e.path))].sort())
      .toEqual(['/crm/defis', '/crm/parrainage', '/crm/profils-site'])
    expect(declares).toHaveLength(6)
    const tous = registre.listes.ALL_PERMISSIONS
    for (const module of new Set(declares.map((e) => e.permModule))) {
      const parPrefixe = tous.filter((c) => porteUnCodeDuModule([c], module)).sort()
      const auRegistre = Object.keys(moduleDe).filter((c) => moduleDe[c] === module).sort()
      expect(parPrefixe, module).toEqual(auRegistre)
    }
  })
})
