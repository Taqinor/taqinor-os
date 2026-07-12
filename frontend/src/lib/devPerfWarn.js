// VX189(d) — avertissement DEV-ONLY sur les Long Animation Frames (LoAF, API
// PerformanceObserver `long-animation-frame`) : un script qui bloque le
// thread principal ≥ 50ms cause le jank que les utilisateurs ressentent
// (scroll saccadé, tap qui ne répond pas), mais rien ne le signalait pendant
// le développement — seul un profiler manuel le révélait après coup.
//
// Zéro octet en prod : ce module n'est JAMAIS importé statiquement — l'appelant
// (main.jsx) le charge par `import()` dynamique DERRIÈRE `if (import.meta.env.DEV)`.
// Vite remplace `import.meta.env.DEV` par le littéral `false` en build prod ;
// Rollup élimine alors la branche morte ET l'import dynamique qu'elle contient
// (aucune référence au module, aucun chunk généré pour lui en prod).
//
// Coordination VX61 (note, pas une tâche à part) : quand `vitals.js` se
// construit, utiliser `web-vitals/attribution` et inclure les
// `longAnimationFrameEntries` (top-3 scripts) dans le beacon — même fichier,
// amendement de son Done=.

// Résumé lisible des scripts responsables (top 3, triés par durée décroissante).
// Exportée (PURE, testable en node --test — zéro dépendance navigateur).
export function topScripts(entry, limit = 3) {
  const scripts = Array.isArray(entry.scripts) ? entry.scripts : []
  return scripts
    .slice()
    .sort((a, b) => (b.duration ?? 0) - (a.duration ?? 0))
    .slice(0, limit)
    .map((s) => ({
      nom: s.name || s.sourceURL || s.invoker || '(inconnu)',
      type: s.invokerType || s.entryType || '',
      duree_ms: Math.round((s.duration ?? 0) * 10) / 10,
    }))
}

/**
 * Installe l'observateur DEV. No-op silencieux si l'API n'est pas
 * disponible (navigateur non compatible) — ne doit JAMAIS faire échouer le
 * démarrage de l'app.
 */
export function installDevPerfWarn() {
  if (typeof PerformanceObserver === 'undefined') return
  if (!PerformanceObserver.supportedEntryTypes?.includes('long-animation-frame')) return

  try {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const duree = Math.round(entry.duration * 10) / 10
        // eslint-disable-next-line no-console -- avertissement DEV volontaire
        console.warn(`[perf] Long Animation Frame — ${duree} ms (seuil 50 ms)`)
        const scripts = topScripts(entry)
        if (scripts.length) {
          // eslint-disable-next-line no-console -- table DEV volontaire
          console.table(scripts)
        }
      }
    })
    observer.observe({ type: 'long-animation-frame', buffered: true })
  } catch {
    // API indisponible / navigateur non compatible — silencieux, jamais fatal.
  }
}

export default installDevPerfWarn
