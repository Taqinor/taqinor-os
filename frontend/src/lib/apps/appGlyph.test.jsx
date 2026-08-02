// ODY34 — LE garde-fou du portail : deux apps ne portent JAMAIS le même dessin.
// ----------------------------------------------------------------------------
// Ce que ce fichier empêche de revenir (constat fondateur du 2026-08-02, capture
// du portail à l'appui) : 43 des 44 module.config ne déclaraient pas d'icône
// d'app, `useInstalledApps()` retombait sur `nav.items[0].icon`, et l'écran
// affichait une dizaine de doublons — cinq apps avec le carré 2×2 de
// `LayoutDashboard` (leur premier écran est un cockpit), Flotte et Logistique
// avec le même camion, QHSE et Conformité avec le même bouclier…
//
// Deux invariants, testés sur le REGISTRE RÉEL (jamais une liste recopiée, qui
// dériverait) :
//   1. toute app déclare `nav.icon` — sinon son glyphe dépend de l'ORDRE de ses
//      items, donc peut changer sans que personne ne touche à l'iconographie ;
//   2. les glyphes des apps sont deux à deux DIFFÉRENTS.
//
// Une app AJOUTÉE plus tard sans glyphe propre, ou avec un glyphe déjà pris,
// fait échouer ce test — c'est exactement le but.
import { describe, it, expect } from 'vitest'
import { moduleConfigs } from '../../router/moduleRoutes'
import { buildInstalledApps } from './useInstalledApps'
import { appGlyph, APP_GLYPH_PROPS } from './appGlyph'

/* Un module est une APP s'il a une section de nav non vide — même règle que
   `buildInstalledApps` (les modules routes-only comme `ao` n'en sont pas). */
const apps = moduleConfigs.filter((c) => c?.nav?.items?.length > 0)

/* Nom lisible d'un composant d'icône lucide (forwardRef → displayName). */
const nomDuGlyphe = (n) => n?.type?.displayName || n?.type?.name || String(n?.type)

describe('ODY34 — glyphes d’app', () => {
  it('le portail compte bien toutes les apps du registre', () => {
    // Repère de vigilance : si ce nombre bouge, une app est née ou morte — et
    // les deux tests ci-dessous doivent l'avoir couverte.
    expect(apps.length).toBeGreaterThanOrEqual(42)
  })

  it('CHAQUE app déclare son glyphe (`nav.icon`) — jamais l’icône du 1er écran', () => {
    const sans = apps.filter((c) => !c.nav.icon).map((c) => c.key)
    expect(sans, `modules sans nav.icon : ${sans.join(', ')}`).toEqual([])
  })

  it('AUCUN doublon de glyphe sur tout le portail', () => {
    const parGlyphe = new Map()
    for (const c of apps) {
      const nom = nomDuGlyphe(c.nav.icon)
      parGlyphe.set(nom, [...(parGlyphe.get(nom) ?? []), c.key])
    }
    const doublons = [...parGlyphe.entries()]
      .filter(([, cles]) => cles.length > 1)
      .map(([nom, cles]) => `${nom} → ${cles.join(' + ')}`)
    expect(doublons, `glyphes partagés : ${doublons.join(' | ')}`).toEqual([])
    expect(parGlyphe.size).toBe(apps.length)
  })

  it('le glyphe RÉELLEMENT rendu par les 4 surfaces ODY9 est celui du module', () => {
    // `buildInstalledApps` est la source unique des quatre surfaces : c'est SON
    // résultat qu'il faut vérifier sans doublon, pas seulement les configs.
    const rendues = buildInstalledApps(moduleConfigs, { role: 'admin', permissions: [] })
    expect(rendues.length).toBe(apps.length)
    const noms = rendues.map((a) => nomDuGlyphe(a.icon))
    expect(new Set(noms).size, `doublons rendus : ${noms.join(', ')}`).toBe(noms.length)
  })

  it('appGlyph() pose les props du kit de nav', () => {
    const Faux = () => null
    const noeud = appGlyph(Faux)
    expect(noeud.type).toBe(Faux)
    expect(noeud.props).toMatchObject(APP_GLYPH_PROPS)
  })
})
