import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { formatCote, milieu } from './plan2d'
// CALX111 câblage — étiquettes de NUMÉRO de module en vue plan. Le module est le MÊME que
// celui du builder (alias `@roofpro`, résolu sur le fichier de `apps/web`), donc c'est la
// mémoire de l'atelier qui est lue — jamais une numérotation recalculée ici.
import { etiquettesPlan, registreAtelier } from '@roofpro/numerotation'

/* ============================================================================
   CAL104 — VUE 2D PLAN ORTHOGRAPHIQUE + PLEIN ÉCRAN.
   ----------------------------------------------------------------------------
   Constat : la scène était exclusivement une vue 3D sur carte, et aucun mode
   plein écran n'existait — l'atelier restait coincé dans une colonne étroite de
   l'ERP. Cet onglet ajoute les deux.

   COTES ET COMPTE IDENTIQUES À LA 3D — par CONSTRUCTION, pas par recalcul : le
   plan est la PROJECTION (`projectPlanView`, `scene3d.ts`) de ce que la 3D a
   déjà posé. Le contour et les rectangles de modules viennent du document
   sérialisé par le builder lui-même ; cet écran ne pave rien et ne compte rien.

   PLEIN ÉCRAN RÉVERSIBLE, SANS RIEN PERDRE : on passe l'ÉLÉMENT en plein écran
   (API Fullscreen) — le composant n'est jamais démonté et le builder n'est jamais
   re-booté, donc ni la sélection ni l'historique ne bougent. Sortie par Échap ou
   par le bouton : l'état revient tel quel. Navigateur sans Fullscreen ⇒ repli en
   plein cadre CSS, même réversibilité.

   ATTEIGNABLE : monté comme ONGLET dans son écran parent (`ToitureDesign`), à
   côté de la 3D — pas une route orpheline qu'il faudrait deviner.
   ========================================================================== */

const VUE_W = 900
const VUE_H = 560

/**
 * @param {object} plan  résultat de `projectPlanView` (déjà projeté), ou null.
 * @param {number} compte3d  compte de modules AFFICHÉ par la 3D — sert de contrôle :
 *                           s'il diverge du plan, on le DIT au lieu de choisir.
 * @param {string} [panId]   CALX111 — identifiant du pan dont on dessine le plan. Absent
 *                           (défaut) : AUCUNE étiquette de numéro, rendu d'aujourd'hui à
 *                           l'identique. Fourni : les numéros STABLES du document sont
 *                           posés sur les modules, si la bascule « Numéroter » est
 *                           allumée et que l'échelle les rend lisibles.
 */
export default function Vue2DPlan({ plan, compte3d, titre, panId }) {
  const boiteRef = useRef(null)
  const [pleinEcran, setPleinEcran] = useState(false)

  // Le plein écran peut être quitté par Échap : on suit l'état du document, on ne
  // suppose jamais que notre bouton est la seule sortie.
  useEffect(() => {
    const onChange = () => {
      const el = typeof document !== 'undefined' ? document.fullscreenElement : null
      if (!el) setPleinEcran((p) => (p && boiteRef.current?.dataset.replicss === '1' ? p : false))
    }
    document?.addEventListener?.('fullscreenchange', onChange)
    return () => document?.removeEventListener?.('fullscreenchange', onChange)
  }, [])

  const basculerPleinEcran = useCallback(async () => {
    const el = boiteRef.current
    if (!el) return
    if (pleinEcran) {
      el.dataset.replicss = '0'
      try {
        if (document.fullscreenElement && document.exitFullscreen) await document.exitFullscreen()
      } catch {
        /* sortie refusée : le repli CSS ci-dessous suffit */
      }
      setPleinEcran(false)
      return
    }
    try {
      if (el.requestFullscreen) {
        await el.requestFullscreen()
        el.dataset.replicss = '0'
      } else {
        el.dataset.replicss = '1' // repli CSS : même réversibilité, sans l'API
      }
    } catch {
      el.dataset.replicss = '1'
    }
    setPleinEcran(true)
  }, [pleinEcran])

  const divergence = useMemo(() => {
    if (!plan || compte3d == null) return null
    return plan.panelCount === compte3d ? null : compte3d
  }, [plan, compte3d])

  // CALX111 câblage — la DÉCISION est prise par `etiquettesPlan` (pure) : bascule éteinte,
  // échelle trop petite, ou modules et projection qui ne se correspondent pas ⇒ liste vide
  // et plan identique à celui d'aujourd'hui. Rien n'est numéroté ici.
  const etiquettes = useMemo(() => {
    if (!plan || !panId) return []
    return etiquettesPlan(plan, registreAtelier.modules(panId), registreAtelier.convention(panId))
  }, [plan, panId])

  return (
    <section
      ref={boiteRef}
      data-testid="v2d-boite"
      data-plein-ecran={pleinEcran ? '1' : '0'}
      className={pleinEcran ? 'fixed inset-0 z-[var(--z-overlay)] overflow-auto bg-nuit-900 p-4' : 'border border-white/10 bg-nuit-800 p-3'}
      aria-label="Vue 2D plan"
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="tech-label text-lune-faint">{titre ?? 'Vue 2D — plan orthographique, nord en haut'}</h3>
        <button type="button" className="rp9-chip ml-auto" data-testid="v2d-plein-ecran" onClick={basculerPleinEcran}>
          {pleinEcran ? 'Quitter le plein écran' : 'Plein écran'}
        </button>
      </div>

      {!plan && (
        <p className="text-sm text-lune-faint" data-testid="v2d-vide">
          Aucun contour fermé — tracez le toit dans la vue 3D, le plan suivra.
        </p>
      )}

      {plan && (
        <>
          <p className="mb-2 text-sm" data-testid="v2d-resume">
            <span data-testid="v2d-compte">{plan.panelCount}</span> module(s) — emprise{' '}
            {formatCote(plan.spanEastWestM)} (E-O) × {formatCote(plan.spanNorthSouthM)} (N-S).
          </p>
          {divergence != null && (
            <p className="mb-2 text-sm text-alert-300" data-testid="v2d-divergence">
              La vue 3D affiche {divergence} module(s) : le plan n’a pas été reprojeté depuis le
              dernier calcul — rouvrez la 3D pour resynchroniser.
            </p>
          )}
          <svg
            data-testid="v2d-svg"
            viewBox={`0 0 ${VUE_W} ${VUE_H}`}
            width="100%"
            role="img"
            aria-label={`Plan orthographique — ${plan.panelCount} modules`}
          >
            <polygon
              data-testid="v2d-contour"
              points={plan.outline.map((p) => p.join(',')).join(' ')}
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            />
            {plan.panels.map((q, i) => (
              <polygon
                key={i}
                data-testid="v2d-module"
                points={q.map((p) => p.join(',')).join(' ')}
                fill="currentColor"
                fillOpacity="0.25"
                stroke="currentColor"
                strokeWidth="0.75"
              />
            ))}
            {/* CALX111 — numéros de module, posés au centre du rectangle projeté. */}
            {etiquettes.map((e) => (
              <text
                key={`num-${e.index}`}
                data-testid="v2d-numero"
                x={e.x}
                y={e.y}
                fontSize="10"
                textAnchor="middle"
                dominantBaseline="middle"
                fill="currentColor"
              >
                {e.texte}
              </text>
            ))}
            {plan.cotes.map((c, i) => {
              const [mx, my] = milieu(c.from, c.to)
              return (
                <text key={i} data-testid="v2d-cote" x={mx} y={my} fontSize="12" textAnchor="middle" fill="currentColor">
                  {formatCote(c.lengthM)}
                </text>
              )
            })}
          </svg>
        </>
      )}
    </section>
  )
}
