/* `window.matchMedia` factice PARTAGÉ des tests (jsdom ne l'implémente pas) :
   `matches` vaut la valeur passée (faux par défaut = écran « bureau »). */
export function mockMatchMedia(matches = false) {
  window.matchMedia = (query) => ({
    matches, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
