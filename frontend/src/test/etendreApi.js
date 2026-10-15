/* Étend un module d'API réel pour un test (ENF19) : le module d'origine reste
   intact, `extras` remplace/ajoute des méthodes de son export par défaut. Usage :
     vi.mock('…/api/ventesApi', async (importOriginal) =>
       (await import('…/test/etendreApi')).etendreApi(importOriginal, { methode: vi.fn() })) */
export async function etendreApi(importOriginal, extras) {
  const actual = await importOriginal()
  return { ...actual, default: { ...actual.default, ...extras } }
}
