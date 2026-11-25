import { readFileSync } from 'node:fs'

/** T4-X7-010 — les règles `@media (pointer: coarse)` d'une feuille, posées SANS leur requête (jsdom ne lit pas
 * les @media). Aide de test partagée (AtelierPanneaux.test.jsx, EtapeResultats.test.jsx) : rend la balise
 * `<style>` posée, à retirer par l'appelant. */
export function feuilleAuDoigt(chemin) {
  const brut = document.createElement('style')
  brut.textContent = readFileSync(chemin, 'utf8')
  document.head.appendChild(brut)
  const regles = [...brut.sheet.cssRules]
  brut.remove()
  const style = document.createElement('style')
  style.textContent = regles.filter((r) => r.type === 4 && r.conditionText === '(pointer: coarse)')
    .flatMap((m) => [...m.cssRules].map((r) => r.cssText)).join(' ')
  document.head.appendChild(style)
  return style
}
