// QAH-PROP — petit moteur de tests par PROPRIÉTÉS, sans dépendance (la règle du
// dépôt interdit `fast-check` : il n'est pas installé, on n'en ajoute pas).
//
// Un PRNG SEEDÉ (mulberry32) + un `forAll` qui rejoue N cas déterministes et,
// au premier échec, RAPPORTE le cas minimal trouvé (réduction gloutonne par
// `shrink`) avec la graine — un échec est donc toujours REJOUABLE à
// l'identique. Aucun `Math.random()` : deux exécutions = les mêmes cas.
//
// Ce fichier est un HELPER (pas de `.test.` dans son nom) : aucun runner ne le
// collecte comme suite, il est seulement importé par `*.properties.test.mjs`.

export function mulberry32(seed) {
  let a = seed >>> 0
  return function rand() {
    a |= 0
    a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function creerGen(seed) {
  const rand = mulberry32(seed)
  const g = {
    rand,
    int: (min, max) => Math.floor(rand() * (max - min + 1)) + min,
    float: (min, max) => min + rand() * (max - min),
    // Flottant « arrondi » au pas donné — pour les valeurs saisies au clavier.
    saisi: (min, max, pas = 1) => Math.round((min + rand() * (max - min)) / pas) * pas,
    pick: (arr) => arr[Math.floor(rand() * arr.length)],
    bool: (p = 0.5) => rand() < p,
    // Échelle LOG-uniforme : couvre petit ET énorme sans que les grands
    // nombres écrasent tout (les factures réelles sont log-réparties).
    logFloat: (min, max) => Math.exp(Math.log(min) + rand() * (Math.log(max) - Math.log(min))),
  }
  return g
}

// Réduction gloutonne : pour un cas (objet JSON) qui échoue, essaie de
// remplacer chaque champ numérique par 0 / sa moitié / son arrondi, et chaque
// tableau par un préfixe plus court, tant que la propriété échoue encore.
export function reduire(cas, echoue, maxPas = 200) {
  // `echoue(c)` rend le MESSAGE d'échec ou null : on n'accepte une réduction
  // que si l'échec reste de la MÊME classe (message aux chiffres près), sinon
  // la réduction dériverait vers un autre défaut (ex. une entrée dégénérée).
  const classe = (m) => String(m).replace(/-?\d+(?:\.\d+)?(?:e[-+]?\d+)?/gi, '#')
  const cible = classe(echoue(cas))
  let courant = JSON.parse(JSON.stringify(cas))
  const candidats = (v) => {
    if (typeof v === 'number' && Number.isFinite(v)) {
      const out = []
      if (v !== 0) out.push(0)
      if (Math.abs(v) > 1) out.push(Math.round(v))
      if (Math.abs(v) > 2) out.push(v / 2)
      return out
    }
    if (Array.isArray(v) && v.length > 1) {
      return [v.slice(0, Math.ceil(v.length / 2)), v.slice(0, v.length - 1)]
    }
    return []
  }
  let pas = 0
  let progres = true
  while (progres && pas < maxPas) {
    progres = false
    for (const cle of Object.keys(courant)) {
      for (const alt of candidats(courant[cle])) {
        pas += 1
        const essai = { ...courant, [cle]: alt }
        const m = echoue(essai)
        if (m !== null && classe(m) === cible) { courant = essai; progres = true; break }
      }
    }
  }
  return courant
}

// forAll : `gen(g)` fabrique UN cas ; `verifie(cas)` LÈVE (assert) ou rend une
// chaîne d'erreur quand la propriété est violée. Rend `null` si tout passe,
// sinon { cas, cas_minimal, message, seed, essai } — l'appelant décide s'il
// lève (propriété attendue vraie) ou s'il vérifie que la violation CONNUE
// persiste (KNOWN_VIOLATIONS).
export function forAll({ seed, runs = 200, gen, verifie }) {
  const g = creerGen(seed)
  const viole = (c) => {
    try {
      const r = verifie(c)
      return typeof r === 'string' && r.length ? r : null
    } catch (e) {
      return e && e.message ? e.message : String(e)
    }
  }
  for (let i = 0; i < runs; i++) {
    const cas = gen(g)
    const message = viole(cas)
    if (message) {
      const minimal = reduire(cas, viole)
      return { cas, cas_minimal: minimal, message: viole(minimal) || message, seed, essai: i }
    }
  }
  return null
}

export function assertPropriete(nom, params) {
  const echec = forAll(params)
  if (echec) {
    throw new Error(
      `PROPRIÉTÉ VIOLÉE « ${nom} » (seed=${echec.seed}, essai=${echec.essai}) : ${echec.message}\n`
      + `cas minimal : ${JSON.stringify(echec.cas_minimal)}`)
  }
}

// Balaye récursivement une valeur et rend le premier chemin dont le nombre
// n'est pas fini (NaN / ±Infinity), ou null. Sert au contrat « aucun NaN/inf
// nulle part dans les sorties ».
export function premierNonFini(valeur, chemin = '') {
  if (typeof valeur === 'number') return Number.isFinite(valeur) ? null : `${chemin}=${valeur}`
  if (Array.isArray(valeur)) {
    for (let i = 0; i < valeur.length; i++) {
      const r = premierNonFini(valeur[i], `${chemin}[${i}]`)
      if (r) return r
    }
    return null
  }
  if (valeur && typeof valeur === 'object') {
    for (const [k, v] of Object.entries(valeur)) {
      const r = premierNonFini(v, chemin ? `${chemin}.${k}` : k)
      if (r) return r
    }
  }
  return null
}
