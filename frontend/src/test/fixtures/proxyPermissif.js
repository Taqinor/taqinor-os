/* Doublure PERMISSIVE d'un module d'API (ENF19) : n'importe quel appel rend une
   promesse résolue `{ data: {} }`, donc aucun panneau ne tombe sur une méthode
   absente — un rouge désigne l'écran testé, jamais une doublure oubliée.
   À utiliser depuis une fabrique `vi.mock` :
     vi.mock('…/api/calepinageApi', async () =>
       (await import('…/test/fixtures/proxyPermissif')).moduleApiPermissif())
   `surcharge` remplace des propriétés de premier niveau (ex. `{ get: espion }`). */
const reponse = () => Promise.resolve({ data: {} })

const doublure = () => new Proxy(function appel() { return reponse() }, {
  // `then` DOIT rester absent : un proxy « thenable » serait attendu comme
  // une promesse par `await` et bloquerait le test.
  get: (_cible, prop) => (typeof prop === 'symbol' || prop === 'then'
    ? undefined
    : doublure()),
  apply: () => reponse(),
})

export function moduleApiPermissif(surcharge = {}) {
  const racine = new Proxy(function appel() { return reponse() }, {
    get: (_cible, prop) => {
      if (Object.hasOwn(surcharge, prop)) return surcharge[prop]
      return typeof prop === 'symbol' || prop === 'then' ? undefined : doublure()
    },
    apply: () => reponse(),
  })
  return { default: racine }
}
