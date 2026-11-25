import { ZOOM_MAX_CADRAGE_ATELIER, hauteurCouverteParTiroir } from '../useAtelierBoot'

/* Le cadrage du toit dans la zone LIBRE de la carte (déplacé tel quel de CoqueAtelier.jsx, ACAL1801), partagé par la coque
   (entrée d'une étape à carte) et par la bascule plein écran (useAtelierVues.js, T4-X5-017). */

const pixels = (v) => (Number.isFinite(v) && v > 0 ? Math.round(v) : 0)

/** ACAL1801 — la carte est le décor (maquettes v2) : les pixels de `#rp9-map` COUVERTS par les pièces qui flottent
    dessus — bandeau (haut), rail vertical (gauche), panneau d'étape (droite), barre d'outils ou tiroir (bas). Le toit se
    cadre dans la zone LIBRE. Tout à 0 sans DOM, carte masquée, ou quand une pièce n'est pas posée SUR la carte.
    T4-X5-017 — carte en PLEIN ÉCRAN : aucune pièce ne la couvre (elles restent dans la page, sous l'élément plein
    écran) ⇒ tout à 0 : le toit se cadre sur tout l'écran, y compris aux re-cadrages tardifs de l'entrée d'étape. */
export function margesCouvertes(racine = typeof document !== 'undefined' ? document : null) {
  const zero = { haut: 0, bas: 0, gauche: 0, droite: 0 }
  const elCarte = racine?.getElementById?.('rp9-map')
  if (elCarte?.closest?.('[data-plein-ecran="1"]')) return zero
  const carte = elCarte?.getBoundingClientRect?.()
  if (!carte || !(carte.width > 0 && carte.height > 0)) return zero
  const boite = (sel) => {
    const el = racine.querySelector(sel)
    return el && !el.closest('[hidden]') ? el.getBoundingClientRect() : null
  }
  const rail = boite('[data-testid="cal-rail-etapes"]')
  return {
    haut: pixels(boite('[data-testid="cal-barre-projet"]')?.bottom - carte.top),
    gauche: rail && rail.height > rail.width ? pixels(rail.right - carte.left) : 0,
    droite: pixels(carte.right - boite('#rp9-studio-inspecteur:not([data-tiroir="1"])')?.left),
    bas: Math.max(pixels(carte.bottom - boite('[data-testid="cal-barre-outils-carte"]')?.top),
      hauteurCouverteParTiroir(racine)),
  }
}

/** Cadre le toit au-dessus des pièces du bas (`basPx`, lu par le moteur) ; les quatre marges partent aussi en
    `margesPx` pour centrer dans la zone libre (demande croisée au moteur de dessin, `cadrageToit.ts`). */
export function cadrerDansZoneLibre(builder) {
  if (typeof builder?.cadrerToit !== 'function') return false
  const marges = margesCouvertes()
  const couvre = marges.haut + marges.gauche + marges.droite + marges.bas > 0
  return builder.cadrerToit({ zoomMax: ZOOM_MAX_CADRAGE_ATELIER, basPx: marges.bas, ...(couvre ? { margesPx: marges } : {}) })
}
