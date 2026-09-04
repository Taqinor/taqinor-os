/* SOL12 — quels codes de permission afficher, selon les modules de la société.
   ----------------------------------------------------------------------------
   L'éditeur de rôles montrait TOUTES les cases `<app>_voir` / `<app>_gerer` de
   `ALL_PERMISSIONS`, y compris celles d'apps que la société n'a pas : module
   désactivé (ODX6), hors plan de licence (SOL9), ou vertical parqué par
   l'édition (SOL6). L'admin cochait alors des droits sans effet, sur des écrans
   qui n'existent pas chez lui — et la matrice était illisible.

   SOURCE DE LA CORRESPONDANCE code → module : le serveur, champ `modules` de
   `/roles/permissions-disponibles` (`apps.roles.models.PERMISSION_MODULE`).
   JAMAIS un préfixe deviné ici : `installation_*` appartient à `installations`,
   `equipement_*` à `sav`, `projet_*` à `gestion_projet`… une heuristique de
   préfixe se tromperait, et masquer une permission par erreur retire un droit
   à l'admin sans qu'il comprenne pourquoi.

   PORTÉE — AFFICHAGE UNIQUEMENT, jamais une frontière de sécurité :
     • le backend continue de servir tous les codes ;
     • un code DÉJÀ porté par le rôle en cours d'édition reste AFFICHÉ même si
       son module est éteint — sinon l'enregistrement du formulaire le
       supprimerait en silence, et réactiver le module ne le rendrait pas ;
     • un code sans module connu n'est jamais masqué (fondation, données
       sensibles, portée d'enregistrements…). */

/**
 * Filtre les codes de permission à AFFICHER.
 *
 * @param {string[]} codes            tous les codes servis par le backend
 * @param {Object}   modulesParCode   { code: clé_de_module } servi par le backend
 * @param {string[]} modulesDesactives clés indisponibles pour la société
 * @param {string[]} codesDejaPortes  codes du rôle en cours d'édition (gardés)
 * @returns {string[]} sous-ensemble ordonné (ordre d'entrée conservé)
 */
export function filtrerCodesAffichables(
  codes, modulesParCode, modulesDesactives, codesDejaPortes = [],
) {
  const eteints = new Set(modulesDesactives || [])
  if (eteints.size === 0) return codes ?? []
  const table = modulesParCode || {}
  const portes = new Set(codesDejaPortes || [])
  return (codes ?? []).filter((code) => {
    if (portes.has(code)) return true
    const module = table[code]
    return !module || !eteints.has(module)
  })
}

/**
 * Vrai si `code` appartient à un module indisponible pour la société.
 * (Utile pour signaler un code hérité plutôt que le masquer.)
 */
export function codeDUnModuleEteint(code, modulesParCode, modulesDesactives) {
  const module = (modulesParCode || {})[code]
  return !!module && (modulesDesactives || []).includes(module)
}
