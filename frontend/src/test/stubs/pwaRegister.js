// Stub de `virtual:pwa-register/react` (fourni par vite-plugin-pwa, absent de
// la config Vitest). Permet à `features/pwa/PwaPrompts.jsx` d'être transformé
// sans échec de résolution quand un test le tire transitivement — aucun test
// n'exerce le service worker.
export const useRegisterSW = () => ({
  needRefresh: [false, () => {}],
  offlineReady: [false, () => {}],
  updateServiceWorker: () => {},
})
export default { useRegisterSW }
