// SPL216 — DOM complet du builder (rp9-*), déplacé VERBATIM depuis
// pages/ventes/ToitureDesign.jsx (move only : le JSX est inchangé ; seuls
// l'enveloppe du composant et les imports sont ajoutés, l'état arrive en props
// NOMMÉES). Mêmes ids, MÊME ORDRE des enfants (consommés par roofPro11/layoutEditor.ts).
import ToitClientOverlay from '../../ventes/ToitClientOverlay'

export default function BuilderDom({
  basculerPleinEcran3d,
  chipClass,
  contourClientBrut,
  inputClass,
  mapWrapRef,
  photoToit,
  photoToitVisible,
  pleinEcran3d,
  setPhotoToitVisible,
  setToitClientVisible,
  toitClientPresent,
  toitClientVisible,
}) {
  return (
    <>
        {/* BUILDER — DOM complet (mêmes ids que la preview pro-11). */}
        <div className="cine-card mt-6 overflow-hidden">
          <form id="rp9-search" className="flex flex-col gap-3 border-b border-white/10 p-4 sm:flex-row">
            <label htmlFor="rp9-address" className="sr-only">Adresse</label>
            <div className="relative flex-1">
              <input id="rp9-address" name="address" type="text" autoComplete="off"
                role="combobox" aria-autocomplete="list" aria-expanded="false"
                aria-controls="rp9-suggestions" aria-haspopup="listbox"
                placeholder="Adresse du client" className={inputClass} />
              <ul id="rp9-suggestions" role="listbox" aria-label="Suggestions d'adresses" hidden
                className="absolute left-0 right-0 top-full z-20 mt-1 max-h-72 overflow-auto border border-white/15 bg-nuit-900"></ul>
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
            className={pleinEcran3d ? 'rp9-map-wrap fixed inset-0 z-[var(--z-overlay)] bg-nuit-900' : 'rp9-map-wrap'}
          >
            <div
              id="rp9-map"
              className={pleinEcran3d ? 'h-full w-full bg-nuit-700' : 'h-[56vh] min-h-[360px] w-full bg-nuit-700'}
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
              className={`${chipClass} absolute right-3 top-3 z-10`}
            >
              {pleinEcran3d ? 'Quitter le plein écran' : 'Plein écran'}
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-white/10 p-4">
            <button type="button" id="rp9-finish" disabled className={chipClass}>Terminer le tracé</button>
            <button type="button" id="rp9-undo-point" hidden className={chipClass}>Annuler le dernier point</button>
            <button type="button" id="rp9-clear" className={chipClass}>Effacer</button>
            <button type="button" id="rp9-add-area" disabled className={chipClass}>+ Ajouter une zone</button>
            {/* L-MAP — bascule du calque de référence, seulement quand un
                contour client existe (rien à basculer sinon). */}
            {toitClientPresent && (
              <button
                type="button"
                className={chipClass}
                aria-pressed={toitClientVisible}
                onClick={() => setToitClientVisible((v) => !v)}
                data-testid="rp9-toit-client-toggle"
              >
                {toitClientVisible ? 'Toit dessiné : affiché' : 'Toit dessiné : masqué'}
              </button>
            )}
            {/* VT13 — bascule de la photo réelle, seulement quand une visite
                terrain validée en a calé une (rien à basculer sinon). */}
            {photoToit && (
              <button
                type="button"
                className={chipClass}
                aria-pressed={photoToitVisible}
                onClick={() => setPhotoToitVisible((v) => !v)}
                data-testid="rp9-photo-toit-toggle"
              >
                {photoToitVisible ? 'Photo réelle : affichée' : 'Photo réelle : masquée'}
              </button>
            )}
            <p className="ml-auto text-sm text-lune-faint"><span>Surface&nbsp;: </span><span id="rp9-area-value" className="text-white">—</span></p>
          </div>

          {/* Contrôles de config (mode normal) */}
          <div id="rp9-config" hidden className="space-y-4 border-t border-white/10 bg-nuit-800 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="tech-label mr-1 text-lune-faint">Type de toit</span>
              <button type="button" data-rooftype="flat" className={chipClass} aria-pressed="true">Toit plat</button>
              <button type="button" data-rooftype="pitched" className={chipClass} aria-pressed="false">Toit en pente / tuiles</button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" id="rp9-optimum" className={`${chipClass} text-brass-300`}>↺ Réinitialiser</button>
              <span id="rp9-optimum-note" className="min-w-0 flex-1 text-xs text-lune-faint"></span>
            </div>
            <div id="rp9-flat-controls" className="space-y-4">
              <div id="rp9-flat-only" className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="tech-label mr-1 text-lune-faint">Orientation</span>
                  <button type="button" data-family="south" className={chipClass} aria-pressed="true">Plein sud<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-family="eastwest" className={chipClass} aria-pressed="false">Est-Ouest<span className="rp9-reco-badge" hidden> ✓</span></button>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="tech-label mr-1 text-lune-faint">Inclinaison</span>
                  <button type="button" data-tilt="reco" className={chipClass} aria-pressed="true">Recommandé<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-tilt="29" className={chipClass} aria-pressed="false">29°<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-tilt="15" className={chipClass} aria-pressed="false">15°<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-tilt="10" className={chipClass} aria-pressed="false">10°<span className="rp9-reco-badge" hidden> ✓</span></button>
                </div>
                <div className="flex items-center gap-3">
                  <label htmlFor="rp9-tilt-range" className="tech-label shrink-0 text-lune-faint">Inclinaison fine</label>
                  <input id="rp9-tilt-range" type="range" min="5" max="35" step="1" defaultValue="29" className="rp9-range min-w-0 flex-1" />
                  <span id="rp9-tilt-value" className="w-16 shrink-0 text-right text-sm font-semibold text-brass-300">29°</span>
                </div>
                <div id="rp9-azimuth-group" hidden className="flex flex-wrap items-center gap-2">
                  <span className="tech-label mr-1 text-lune-faint">Azimut</span>
                  <button type="button" data-azimuth="south" className={chipClass} aria-pressed="true">Plein sud<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-azimuth="aligned" className={chipClass} aria-pressed="false">Aligné toit<span className="rp9-reco-badge" hidden> ✓</span></button>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="tech-label mr-1 text-lune-faint">Panneaux</span>
                <button type="button" data-orient="auto" className={chipClass} aria-pressed="true">Auto</button>
                <button type="button" data-orient="portrait" className={chipClass} aria-pressed="false">Portrait<span className="rp9-reco-badge" hidden> ✓</span></button>
                <button type="button" data-orient="landscape" className={chipClass} aria-pressed="false">Paysage<span className="rp9-reco-badge" hidden> ✓</span></button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="tech-label mr-1 text-lune-faint">Marge de rive</span>
                <button type="button" data-margin="keep" className={chipClass} aria-pressed="true">Garder<span className="rp9-reco-badge" hidden> ✓</span></button>
                <button type="button" data-margin="remove" className={chipClass} aria-pressed="false">Pleine rive<span className="rp9-reco-badge" hidden> ✓</span></button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <label htmlFor="rp9-overhang-input" className="tech-label mr-1 text-lune-faint">Débord (m)</label>
                <input id="rp9-overhang-input" type="number" inputMode="decimal" step="any" min="0" defaultValue="0"
                  className="fig h-9 w-20 border border-white/20 bg-nuit-900 px-2 text-center text-base text-white outline-none focus:border-brass-400" />
              </div>
            </div>
            <div id="rp9-pitched-controls" hidden className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="tech-label mr-1 text-lune-faint">Pente</span>
                <button type="button" data-pitch="15" className={chipClass} aria-pressed="false">~15°</button>
                <button type="button" data-pitch="22" className={chipClass} aria-pressed="true">~22°</button>
                <button type="button" data-pitch="30" className={chipClass} aria-pressed="false">~30°</button>
                <button type="button" data-pitch="45" className={chipClass} aria-pressed="false">~45°</button>
              </div>
              <div className="flex items-center gap-3">
                <label htmlFor="rp9-pitch-range" className="tech-label shrink-0 text-lune-faint">Pente fine</label>
                <input id="rp9-pitch-range" type="range" min="5" max="45" step="1" defaultValue="22" className="rp9-range min-w-0 flex-1" />
                <span id="rp9-pitch-value" className="w-12 shrink-0 text-right text-sm font-semibold text-brass-300">22°</span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="tech-label mr-1 text-lune-faint">Face du pan</span>
                <button type="button" data-facing="180" className={chipClass} aria-pressed="true">Sud</button>
                <button type="button" data-facing="135" className={chipClass} aria-pressed="false">Sud-Est</button>
                <button type="button" data-facing="225" className={chipClass} aria-pressed="false">Sud-Ouest</button>
                <button type="button" data-facing="90" className={chipClass} aria-pressed="false">Est</button>
                <button type="button" data-facing="270" className={chipClass} aria-pressed="false">Ouest</button>
              </div>
              <p id="rp9-facing-note" className="min-h-[1rem] text-xs text-lune-faint" aria-live="polite"></p>
              <div className="flex items-center gap-3">
                <label htmlFor="rp9-facing-range" className="tech-label shrink-0 text-lune-faint">Sens de la pente</label>
                <input id="rp9-facing-range" type="range" min="0" max="359" step="any" defaultValue="180" className="rp9-range min-w-0 flex-1" />
                <span id="rp9-facing-value" className="w-28 shrink-0 text-right text-sm font-semibold text-brass-300">Sud · 180°</span>
              </div>
              <p id="rp9-pitched-note" className="min-h-[1.25rem] text-xs text-lune-soft" aria-live="polite"></p>
            </div>

            {/* CAL107 — bloc « Obstacles », porté de apps/web/src/pages/preview/
                toiture-3d-pro-11.astro (mêmes ids : obstaclesUi.ts les cherche par id,
                indépendamment de la page qui les héberge). Ce contrôle manquait dans
                l'ERP — la pose d'obstacle n'était donc reachable QUE sur la page de
                préview publique, jamais depuis le poste d'un commercial. */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="tech-label mr-1 text-lune-faint">Obstacles</span>
              <button type="button" id="rp9-obstacle" className={chipClass}>Ajouter un obstacle (cheminée…)</button>
              <button type="button" id="rp9-obstacle-clear" className={chipClass}>Tout effacer</button>
            </div>
            <p className="text-xs leading-relaxed text-lune-faint">
              Marquez les obstacles (climatiseur, cheminée, lanterneau, citerne…) — on
              n'y posera pas de panneaux. Glissez sur le toit pour dessiner un
              rectangle ; touchez-le pour le redimensionner.
            </p>
            <div id="rp9-obs-edit" hidden className="border border-white/15 bg-nuit-900/40 p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="tech-label text-brass-300">Obstacle sélectionné</span>
                <button type="button" id="rp9-obs-delete"
                  className="border border-alert-300/60 px-3 py-2 text-sm font-semibold text-alert-300 transition-colors hover:bg-alert-300/10">
                  × Supprimer
                </button>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="block text-sm text-lune-soft">
                  Longueur (m)
                  <input id="rp9-obs-length" type="text" inputMode="decimal" step="any"
                    className="fig mt-1 h-9 w-full border border-white/20 bg-nuit-900 px-2 text-center text-base text-white outline-none focus:border-brass-400" />
                </label>
                <label className="block text-sm text-lune-soft">
                  Largeur (m)
                  <input id="rp9-obs-width" type="text" inputMode="decimal" step="any"
                    className="fig mt-1 h-9 w-full border border-white/20 bg-nuit-900 px-2 text-center text-base text-white outline-none focus:border-brass-400" />
                </label>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <span className="tech-label text-lune-faint">Taille</span>
                <button type="button" id="rp9-obs-minus" aria-label="Réduire l'obstacle"
                  className="h-11 w-11 border border-white/25 text-xl font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300">−</button>
                <button type="button" id="rp9-obs-plus" aria-label="Agrandir l'obstacle"
                  className="h-11 w-11 border border-white/25 text-xl font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300">+</button>
                <span id="rp9-obs-dims" className="fig text-sm text-lune-soft">—</span>
              </div>
            </div>

            {/* CAL102 — outil de MESURE (distance/surface/angle), annotation persistée avec
                le calepinage (roofPro11/mesureUi.ts). Un genre choisi, des taps posent les
                points, « Terminer la mesure » la pose (refusée tant qu'elle est
                géométriquement invalide pour son genre), « Annuler » abandonne la session. */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="tech-label mr-1 text-lune-faint">Mesurer</span>
              <button type="button" data-mesure-kind="distance" id="rp9-mesure-distance" className={chipClass} aria-pressed="false">Distance</button>
              <button type="button" data-mesure-kind="area" id="rp9-mesure-area" className={chipClass} aria-pressed="false">Surface</button>
              <button type="button" data-mesure-kind="angle" id="rp9-mesure-angle" className={chipClass} aria-pressed="false">Angle</button>
              <button type="button" id="rp9-mesure-finish" hidden className={chipClass}>Terminer la mesure</button>
              <button type="button" id="rp9-mesure-cancel" hidden className={chipClass}>Annuler</button>
            </div>
            <p id="rp9-mesure-note" className="min-h-[1rem] text-xs text-lune-faint" aria-live="polite"></p>
            <ul id="rp9-mesure-list" className="space-y-1 text-xs text-lune-soft"></ul>
          </div>

          {/* W69 — « Personnaliser la disposition » : porté de apps/web/toiture-3d-pro-11.astro
              (bloc rp9-layout-window/rp9-layout-panel, lignes 478-632) — DEUX modes d'édition
              manuelle des panneaux (▦ Emplacements validés / ✥ Placement libre), pilotés par le
              module partagé roofPro11/layoutEditor.ts. Ids/data-* STRICTEMENT identiques à
              l'astro : le moteur les cherche par id, un id renommé = bouton mort silencieux. */}
          <div id="rp9-layout-window" hidden className="border-t border-white/10 bg-nuit-800 p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
              <p className="tech-label text-brass-300">Personnaliser la disposition</p>
              <button type="button" id="rp9-layout-toggle" aria-pressed="false"
                className="border border-brass-400 bg-brass-400/10 px-4 py-2 text-sm font-bold text-brass-300 transition-colors hover:bg-brass-400/20">
                Déplacer les panneaux
              </button>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-lune-faint">
              Activez, puis dans le <strong className="text-lune-soft">plan tactile</strong> ci-dessous
              touchez un panneau (bleu) puis un emplacement libre (vert) pour l'y déplacer — ou
              utilisez <strong className="text-lune-soft">+ / −</strong>. Vous pouvez aussi glisser un
              panneau directement sur la 3D. Les panneaux se calent toujours sur des emplacements
              valides (jamais hors toit, hors retrait ou sur un obstacle) ; le nombre, la puissance,
              la production et les économies se recalculent.
            </p>

            <div id="rp9-layout-panel" hidden className="mt-5 space-y-5">
              {/* PV30 — DEUX MODES d'édition, côte à côte et explicites. « Emplacements
                  validés » (le défaut) ne déplace un panneau que d'une cellule calculée à
                  une autre : sûr, mais impossible d'y gagner de la place. « Placement
                  libre » déplace au centimètre et laisse RÉGLER le retrait de rive et
                  l'écart entre panneaux — les seules limites qui restent sont physiques
                  (contour du toit, chevauchement, obstacle), et les distances réelles
                  s'affichent pendant le geste. */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="tech-label text-lune-faint">Mode d’édition</span>
                <button type="button" id="rp9-layout-mode-lattice" aria-pressed="true"
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300 aria-pressed:border-brass-400">
                  ▦ Emplacements validés
                </button>
                <button type="button" id="rp9-layout-mode-free" aria-pressed="false"
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300">
                  ✥ Placement libre
                </button>
              </div>

              <div id="rp9-free-controls" hidden className="space-y-3 border border-brass-400/30 bg-brass-400/5 p-3">
                <p className="text-xs leading-relaxed text-lune-soft">
                  En placement libre, ces deux marges sont les vôtres : les baisser fait tenir
                  plus de panneaux. Les <strong className="text-lune-soft">distances réellement
                  mesurées</strong> s’affichent pendant le déplacement — rien n’est réduit dans
                  votre dos. Le contour du toit, les chevauchements et les obstacles restent,
                  eux, infranchissables.
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <label htmlFor="rp9-free-setback" className="text-sm text-lune-soft">Retrait de rive (cm)</label>
                  <input id="rp9-free-setback" name="freeSetback" type="text" inputMode="decimal" step="any"
                    className="w-24 border border-white/25 bg-nuit-900 px-3 py-2 text-sm text-white" />
                  <label htmlFor="rp9-free-gap" className="text-sm text-lune-soft">Écart entre panneaux (cm)</label>
                  <input id="rp9-free-gap" name="freeGap" type="text" inputMode="decimal" step="any"
                    className="w-24 border border-white/25 bg-nuit-900 px-3 py-2 text-sm text-white" />
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <button type="button" id="rp9-free-add" aria-pressed="false"
                    className="border border-brass-400 bg-brass-400/10 px-4 py-2.5 text-sm font-bold text-brass-300 transition-colors hover:bg-brass-400/20">
                    ＋ Ajouter un panneau
                  </button>
                  <span id="rp9-free-measure" className="fig text-sm text-brass-300" aria-live="polite"></span>
                </div>
              </div>

              <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
                <div>
                  <dd id="rp9-layout-count" className="fig text-lg text-white sm:text-xl">—</dd>
                  <dt className="tech-label mt-0.5 text-lune-faint">Panneaux posés</dt>
                </div>
                <div>
                  <dd id="rp9-layout-kwc" className="fig text-lg text-white sm:text-xl">—</dd>
                  <dt className="tech-label mt-0.5 text-lune-faint">Puissance</dt>
                </div>
                <div>
                  <dd id="rp9-layout-free" className="fig text-lg text-white sm:text-xl">—</dd>
                  <dt className="tech-label mt-0.5 text-lune-faint">Emplacements libres</dt>
                </div>
                <div>
                  <dd id="rp9-layout-cover" className="fig text-lg text-brass-300 sm:text-xl">—</dd>
                  <dt className="tech-label mt-0.5 text-lune-faint">Couverture besoin</dt>
                </div>
              </dl>

              {/* Boutons +/− (touch + mouvement réduit, sans glissé fin) */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="tech-label text-lune-faint">Ajouter / retirer</span>
                <button type="button" id="rp9-layout-minus" aria-label="Retirer un panneau"
                  className="h-11 w-11 border border-white/25 text-2xl font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300 disabled:cursor-not-allowed disabled:opacity-40">−</button>
                <button type="button" id="rp9-layout-plus" aria-label="Ajouter un panneau"
                  className="h-11 w-11 border border-white/25 text-2xl font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300 disabled:cursor-not-allowed disabled:opacity-40">+</button>
                <button type="button" id="rp9-layout-fill"
                  className="border border-brass-400 bg-brass-400/10 px-4 py-2.5 text-sm font-bold text-brass-300 transition-colors hover:bg-brass-400/20 disabled:cursor-not-allowed disabled:opacity-40">
                  ⤢ Remplir automatiquement
                </button>
                <button type="button" id="rp9-layout-reset"
                  className="ml-auto border border-brass-400 bg-brass-400/10 px-4 py-2.5 text-sm font-bold text-brass-300 transition-colors hover:bg-brass-400/20">
                  ↺ Réinitialiser la disposition optimale
                </button>
              </div>

              {/* PV25 — sélection MULTIPLE (marquee au glissé + Maj, ou mode sélection au
                  doigt), déplacement du groupe / de la rangée entière, et nudge d'azimut.
                  Chaque déplacement reste « tout ou rien » : si un seul panneau du groupe
                  n'a pas d'emplacement valide, rien ne bouge.
                  PV34 — les gestes SANS modificateur sont désormais les principaux : glisser
                  sur le toit encadre, double-cliquer prend la rangée. Ces boutons restent le
                  repli tactile (et le mode rangée), et le compteur dit en permanence combien
                  de panneaux sont tenus. */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="tech-label text-lune-faint">Sélection &amp; rangée</span>
                <button type="button" id="rp9-layout-select" aria-pressed="false"
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300">
                  ▭ Sélection multiple
                </button>
                <button type="button" id="rp9-layout-row" aria-pressed="false"
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300">
                  ⇔ Déplacer la rangée
                </button>
                <button type="button" id="rp9-layout-clear-sel"
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300 disabled:cursor-not-allowed disabled:opacity-40">
                  ✕ Effacer la sélection
                </button>
                <span id="rp9-layout-selcount" data-rp9-selcount="0" aria-live="polite"
                  className="text-sm font-semibold text-brass-300">
                  Aucun panneau sélectionné
                </span>
              </div>
              <p className="text-xs leading-relaxed text-lune-soft">
                Sur la 3D : <strong className="text-lune-soft">glissez sur le toit, à côté des
                panneaux</strong>, pour encadrer un groupe ou une rangée ·{' '}
                <strong className="text-lune-soft">double-clic</strong> sur un panneau = toute sa
                rangée · <strong className="text-lune-soft">Ctrl (⌘) + clic</strong> ajoute ou
                retire un panneau · <strong className="text-lune-soft">Maj + glissé</strong> ajoute
                un cadre au groupe · <strong className="text-lune-soft">Échap</strong> lâche la
                sélection. Glissez ensuite n’importe quel panneau sélectionné : tout le groupe
                suit le curseur.
              </p>

              {/* PV26 — annuler / rétablir (Ctrl+Z / Ctrl+Y, ou ⌘). Les flèches du
                  clavier déplacent le panneau (ou le groupe) d'un emplacement. */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="tech-label text-lune-faint">Historique</span>
                <button type="button" id="rp9-layout-undo" disabled
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300 disabled:cursor-not-allowed disabled:opacity-40">
                  ↶ Annuler <span className="text-lune-faint">(Ctrl+Z)</span>
                </button>
                <button type="button" id="rp9-layout-redo" disabled
                  className="border border-white/25 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300 disabled:cursor-not-allowed disabled:opacity-40">
                  ↷ Rétablir <span className="text-lune-faint">(Ctrl+Y)</span>
                </button>
                <span className="text-xs text-lune-soft">Flèches ← ↑ ↓ → : déplacer d’un emplacement</span>
              </div>

              {/* Nudge d'AZIMUT : n'a de sens que sur un toit en PENTE (la face du pan est
                  imposée par la toiture ; sur toit plat l'azimut est un axe de l'optimiseur).
                  Masqué en toit plat. */}
              <div id="rp9-layout-azimuth" hidden className="flex flex-wrap items-center gap-3">
                <span className="tech-label text-lune-faint">Azimut du pan</span>
                <button type="button" id="rp9-layout-az-minus" aria-label="Diminuer l’azimut d’un degré"
                  className="h-11 w-11 border border-white/25 text-2xl font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300">−</button>
                <span id="rp9-layout-az-value" className="fig text-lg text-white">—</span>
                <button type="button" id="rp9-layout-az-plus" aria-label="Augmenter l’azimut d’un degré"
                  className="h-11 w-11 border border-white/25 text-2xl font-bold text-white transition-colors hover:border-brass-400 hover:text-brass-300">+</button>
              </div>

              {/* Repli tactile : tap-sélection d'un panneau → tap-cible d'un emplacement vide.
                  Une mini-carte des cellules (occupées / libres) rend l'interaction code-vérifiable
                  et fonctionne sans glissé fin ni mouvement. */}
              <div>
                <p className="tech-label text-lune-faint">Plan des emplacements (tactile) — touchez un panneau, puis un emplacement libre</p>
                <div id="rp9-layout-grid" className="rp9-layout-grid mt-3" role="group" aria-label="Plan des emplacements de panneaux"></div>
                <p id="rp9-layout-note" className="mt-2 min-h-[1.25rem] text-xs leading-relaxed text-lune-soft" aria-live="polite"></p>
              </div>
            </div>
          </div>

          <p id="rp9-status" className="border-t border-white/10 px-4 py-3 text-sm text-lune-faint" aria-live="polite">Chargement…</p>
        </div>
    </>
  )
}
