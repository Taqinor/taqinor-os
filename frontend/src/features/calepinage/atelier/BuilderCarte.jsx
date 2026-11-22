// Coque (22/11) — groupe « carte » du DOM du constructeur, DÉPLACÉ VERBATIM depuis
// BuilderDom.jsx (move only) : la recherche d'adresse et l'enveloppe de la carte. Sous-arbre
// intact (le script cherche ses ids et le parent de « Terminer le tracé »). Toujours monté.
import { useContext, useEffect } from 'react'
import ToitClientOverlay from '../../ventes/ToitClientOverlay'
import { ContexteCoque } from './coque/contexteCoque'
import { Icone } from './coque/primitives'

// Maquette Main — les boutons de zoom de MapLibre portent des noms anglais (« Zoom in / Zoom out ») : dans la coque,
// ils prennent ceux de la maquette. Le script crée la carte (et ses contrôles) après le montage : quelques essais.
const NOMS_ZOOM = [['.maplibregl-ctrl-zoom-in', 'Zoomer'], ['.maplibregl-ctrl-zoom-out', 'Dézoomer']]
const ESSAIS_ZOOM_MS = [0, 1500, 4000, 8000]

function useZoomEnFrancais(actif, mapWrapRef) {
  useEffect(() => {
    if (!actif) return undefined
    const nommer = () => {
      for (const [sel, nom] of NOMS_ZOOM) {
        const b = mapWrapRef?.current?.querySelector?.(sel)
        if (b && b.getAttribute('aria-label') !== nom) { b.setAttribute('aria-label', nom); b.setAttribute('title', nom) }
      }
    }
    const minuteurs = ESSAIS_ZOOM_MS.map((delai) => window.setTimeout(nommer, delai))
    return () => minuteurs.forEach((m) => window.clearTimeout(m))
  }, [actif, mapWrapRef])
}

export default function BuilderCarte({
  basculerPleinEcran3d,
  chipClass,
  contourClientBrut,
  inputClass,
  mapWrapRef,
  photoToit,
  photoToitVisible,
  pleinEcran3d,
  toitClientVisible,
}) {
  // Maquette Main (22/11) — dans la coque, « Plein écran » rejoint la pile de zoom (pictogramme, nom accessible
  // inchangé) ; hors coque (mode lead), la puce texte d'avant, à l'octet près.
  const dansCoque = useContext(ContexteCoque) !== null
  const libellePleinEcran = pleinEcran3d ? 'Quitter le plein écran' : 'Plein écran'
  useZoomEnFrancais(dansCoque, mapWrapRef)
  return (
    <>
          <form id="rp9-search" className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row">
            <label htmlFor="rp9-address" className="sr-only">Adresse</label>
            <div className="relative flex-1">
              <input id="rp9-address" name="address" type="text" autoComplete="off"
                role="combobox" aria-autocomplete="list" aria-expanded="false"
                aria-controls="rp9-suggestions" aria-haspopup="listbox"
                placeholder="Adresse du client" className={inputClass} />
              <ul id="rp9-suggestions" role="listbox" aria-label="Suggestions d'adresses" hidden
                className="absolute left-0 right-0 top-full z-20 mt-1 max-h-72 overflow-auto border border-border bg-background"></ul>
            </div>
            <button type="submit" className="flex-none bg-brass-400 px-6 py-3 text-base font-bold text-azur-950">Localiser</button>
          </form>

          {/* L-MAP — enveloppe ADDITIVE autour de `#rp9-map` (jamais un enfant :
              le builder ne cherche que ses propres id, un parent ne lui change
              rien). `ToitClientOverlay` y flotte en calque de référence
              passif — voir roofbuilder.css `.rp9-map-wrap`/`.rp9-toit-client`.
              CALX129 — c'est cette MÊME enveloppe que la bascule plein écran
              cible (jamais `#rp9-map` : le builder ne cherche que ses propres
              id, une classe sur son parent ne le démonte ni ne le ré-amorce). */}
          <div
            ref={mapWrapRef}
            data-plein-ecran={pleinEcran3d ? '1' : '0'}
            data-testid="rp9-map-wrap"
            className={pleinEcran3d ? 'rp9-map-wrap fixed inset-0 z-[var(--z-overlay)] bg-background' : 'rp9-map-wrap'}
          >
            <div
              id="rp9-map"
              className={pleinEcran3d ? 'h-full w-full bg-muted' : 'h-[56vh] min-h-[360px] w-full bg-muted'}
              role="application" aria-label="Carte 3D pour dessiner le toit"
            >
              <div id="rp9-compass" className="rp9-compass" aria-hidden="true">
                <div id="rp9-compass-arrow" className="rp9-compass-arrow"><span>N</span><span>S</span></div>
              </div>
            </div>
            {/* VT13 — la photo RÉELLE du toit (visite terrain validée + calée)
                se drape en calque de FOND du contour, dans le même repère.
                Le builder vendored n'est pas touché : ce calque flotte
                au-dessus de sa carte, en `pointer-events: none`. */}
            <ToitClientOverlay
              contour={contourClientBrut}
              visible={toitClientVisible}
              photoToit={photoToit}
              photoVisible={photoToitVisible}
            />
            {/* CALX129 — reste À L'INTÉRIEUR de l'enveloppe (pas dans la barre
                d'outils plus bas) : en plein écran, tout ce qui est hors de
                cette enveloppe est recouvert — le bouton de sortie doit donc y
                vivre pour rester cliquable dans les deux états. */}
            <button
              type="button"
              onClick={basculerPleinEcran3d}
              data-testid="rp9-plein-ecran-toggle"
              className={`${chipClass} rp9-carte-puce${dansCoque ? ' cal-carte-plein-ecran' : ''}`}
            >
              {dansCoque ? <><Icone nom="pleinEcran" taille={18} epaisseur={2} /><span className="sr-only">{libellePleinEcran}</span></> : libellePleinEcran}
            </button>
            {/* ACAL954 — « Terminer le tracé » SUR la carte (centré en bas), plus sous la flottaison ;
                ids inchangés (lus par roof-tool-pro11.ts). Même fond opaque que la puce ACAL950,
                rangé dans le flux de ce bandeau (position statique). */}
            <div className="absolute bottom-10 left-1/2 z-10 flex -translate-x-1/2 gap-2">
              <button type="button" id="rp9-finish" disabled className={`${chipClass} rp9-carte-puce`} style={{ position: 'static' }}>Terminer le tracé</button>
              <button type="button" id="rp9-undo-point" hidden className={`${chipClass} rp9-carte-puce`} style={{ position: 'static' }}>Annuler le dernier point</button>
            </div>
          </div>
    </>
  )
}
