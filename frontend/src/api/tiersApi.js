import api from './axios'
import { makeResourceFactory } from './resource'

/* ============================================================================
   WIR152 — Client de l'app fondation `tiers` (`/api/django/tiers/`).
   ----------------------------------------------------------------------------
   `TiersViewSet` (ARC17, CRUD complet + recherche nom/email/ice/rc/if/cin)
   n'était consommé qu'en resolver de nom par deux écrans compta
   (`CockpitPage.jsx`/`EngagementsPage.jsx`, appel `api.get('/tiers/tiers/')`
   direct) — aucun écran répertoire, et l'action `doublons` (ARC20,
   admin-only) n'avait aucun appelant. `axios` préfixe déjà `/api/django` :
   on n'écrit ici que `/tiers/…`.
   ========================================================================== */

const crud = makeResourceFactory(api, '/tiers')

const tiersApi = {
  tiers: crud('tiers'),
  // ARC20 — rapport LECTURE SEULE des doublons (même ICE/email sur
  // plusieurs fiches Tiers), admin-only côté backend.
  doublons: () => api.get('/tiers/tiers/doublons/'),
}

export default tiersApi
