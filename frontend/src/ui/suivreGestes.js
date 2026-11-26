// R5A-N5 — SUIVI DU PREMIER GESTE DE L'UTILISATEUR, partagé par l'atelier calepinage (ACAL1661) et le générateur de devis.
/* ACAL1661 — « AUCUN GESTE DE L'UTILISATEUR DEPUIS L'OUVERTURE ». Ouvrir un calepinage sans y toucher ne peut rien avoir à
   enregistrer : ce que l'outil réécrit ensuite tout seul (pose recalculée, kWh servis, accès solaire) n'est pas une
   modification. Tant qu'aucun geste n'a eu lieu, la référence de « modifié ? » suit donc la scène ; AU PREMIER geste
   (pointeur, clavier, saisie, collage, dépôt — capture, donc AVANT que le geste n'agisse) la référence est figée à
   l'état d'avant le geste, et tout ce qui change ensuite se voit — y compris dans la première seconde et par un panneau
   latéral qui ne passe par aucun historique du constructeur. Cliquer un ONGLET (`role="tab"`) ne change aucun document : il
   n'est pas un geste. R5A-N5 (2) — naviguer n'est pas non plus éditer : un clic dans une barre de navigation intra-page
   (`<nav>`, `role="navigation"`, `role="tablist"` : les puces « Technique », « Lignes »… du générateur de devis, qui ne font
   que défiler jusqu'à une carte) et les touches qui ne font que déplacer le focus (Tab, Maj, Ctrl, Alt, Méta) ne figent pas la
   référence — sinon tout ce que l'écran pose ensuite tout seul (relectures du lead, conception, réglages société) devenait
   une « modification » dès le premier clic de navigation. `auPremierGeste` est appelé une seule fois. */
export const EVENEMENTS_DE_GESTE = Object.freeze(['pointerdown', 'keydown', 'touchstart', 'input', 'change', 'paste', 'drop'])

const NAVIGATION_INTRA_PAGE = 'nav, [role="navigation"], [role="tablist"]'
const TOUCHES_DE_FOCUS = Object.freeze(['Tab', 'Shift', 'Control', 'Alt', 'Meta'])

export function suivreGestes(cible, auPremierGeste) {
  let geste = false
  const lire = (e) => {
    if (geste) return
    if (e?.target?.closest?.('[role="tab"]')) return
    if (e?.target?.closest?.(NAVIGATION_INTRA_PAGE)) return
    if (e?.type === 'keydown' && TOUCHES_DE_FOCUS.includes(e.key)) return
    geste = true
    auPremierGeste?.()
  }
  EVENEMENTS_DE_GESTE.forEach((nom) => cible.addEventListener(nom, lire, { capture: true }))
  return {
    aGeste: () => geste,
    arreter: () => EVENEMENTS_DE_GESTE.forEach((nom) => cible.removeEventListener(nom, lire, { capture: true })),
  }
}
