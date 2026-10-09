// ASAV61 — rôle « responsable » simulé pour les tests historiques qui exercent
// les gestes d'écriture eux-mêmes (sans store d'auth).
export function permissionsResponsable(actual) {
  return {
    ...actual,
    useIsAdminOrResponsable: () => true,
    useHasPermission: () => true,
  }
}
