import { vi } from 'vitest'

/* `useSelector` mocké pour les suites qui ne lisent que `auth.user.id` (ENF19) :
   l'utilisateur connecté vaut 7, sans vrai Provider redux. Importer ce module
   enregistre le `vi.mock('react-redux')`. `portee` : comme tout profil servi par
   `/auth/me/` (ADRG122 — sans elle, le profil vaut « pas encore chargé »). */
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: { user: { id: 7, portee: 'interne' } } }),
}))
