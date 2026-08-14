// Stub de `@roofpro/captureBoot` (AOF82, `RepriseCarte.jsx`) — le plugin
// `roofbuilder-ts-transpile` qui transpile ce fichier TS n'est monté que dans
// `vite.config.js`, pas dans la config Vitest (même garde que le stub
// `@roofbuilder` ci-dessus). Sans lui, `import('@roofpro/captureBoot')`
// échoue à la résolution au transform — `RepriseCarte.jsx` DÉGRADE déjà
// proprement vers le tracé manuel quand le montage échoue (try/catch), donc
// ce stub sans `bootCaptureOnly` exerce exactement cette branche dans les
// tests, sans jamais embarquer le lecteur de cartes réel.
export default {}
