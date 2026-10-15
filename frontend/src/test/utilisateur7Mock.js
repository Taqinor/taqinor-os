import { vi } from 'vitest'

/* `useSelector` mocké pour les suites qui ne lisent que `auth.user.id` (ENF19) :
   l'utilisateur connecté vaut 7, sans vrai Provider redux. Importer ce module
   enregistre le `vi.mock('react-redux')`. */
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: { user: { id: 7 } } }),
}))
