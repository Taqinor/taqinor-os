/* ============================================================================
   ARC44 — Factory REST partagée + helper d'unwrap de réponse.
   ----------------------------------------------------------------------------
   La factory `{list,get,create,update,remove}` était re-déclarée localement
   dans chaque module `frontend/src/api/*.js` (ex. `comptaApi.js` `resource()`,
   `flotteApi.js`/`qhseApi.js` `crud()` — trois copies quasi identiques).
   `resource(client, path)` ci-dessous est le point unique : elle NE change
   aucune URL ni aucun verbe HTTP, elle centralise juste le code.

   Inventaire des variantes réelles d'unwrap de réponse (grep exhaustif de
   `frontend/src` au moment d'ARC44, 2026-07-10) — le backend n'a PAS encore
   d'enveloppe de pagination uniforme (YAPIC1, non construite) :
     1. Tableau brut               → `res.data` est déjà un Array.
     2. Paginé DRF standard        → `res.data` = `{results:[...], count, ...}`.
     3. Combiné (le plus courant)  → `Array.isArray(data) ? data : (data?.results ?? [])`
        vu dans TagChipInput.jsx, NcrChatter.jsx, EmployeList.jsx, KbPage.jsx,
        BlocInsertPicker.jsx, AppointmentBooker.jsx, CampagnesScreen.jsx, etc.
     4. Clé métier au lieu de `results` (rare) → `useQhseList.rowsFrom` gère
        aussi `data?.evenements` et `data?.items` pour 2 endpoints agrégés.
   `unwrapList()` couvre les cas 1–3 (l'écrasante majorité). Un appelant avec
   une clé métier dédiée (cas 4) garde sa propre petite fonction locale — ce
   n'est pas une régression, ces endpoints ne renvoient pas une liste de
   ressource générique.

   FUTURE INTENT (YAPIC1) : quand le backend expose une enveloppe de
   pagination uniforme, `unwrapList` est le SEUL endroit à faire évoluer —
   aucun call-site n'a à changer.
   ========================================================================== */

// Déballe une réponse axios en tableau, quelle que soit l'enveloppe actuelle.
export function unwrapList(res) {
  const data = res?.data
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  return []
}

// Fabrique CRUD REST standard sur `${basePath}/${path}/` via le client axios
// fourni (chaque module api/*.js a son propre `api` — préfixe /api/django).
// Signature volontairement identique aux factories qu'elle remplace :
// `resource(path)` liée à un client, ou `resource(client, basePath, path)`
// pour un usage direct — voir les deux formes ci-dessous.
export function makeResourceFactory(client, basePath) {
  const base = basePath.endsWith('/') ? basePath : `${basePath}/`
  return function resource(path) {
    const root = `${base}${path}/`
    return {
      list: (params) => client.get(root, { params }),
      get: (id) => client.get(`${root}${id}/`),
      create: (data) => client.post(root, data),
      update: (id, data) => client.patch(`${root}${id}/`, data),
      remove: (id) => client.delete(`${root}${id}/`),
    }
  }
}

export default makeResourceFactory
