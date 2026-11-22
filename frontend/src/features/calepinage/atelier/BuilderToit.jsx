// Coque (22/11) — groupe « toit » du DOM du constructeur, DÉPLACÉ VERBATIM depuis
// BuilderDom.jsx (move only) : `#rp9-config` (type de toit, pente, face, obstacles, ombre,
// mesure, soleil). Sous-arbre intact : les hôtes `parentElement` du script y restent.
import HeureLegale from '../HeureLegale'

export default function BuilderToit({
  expert = false, // ACAL869 — le niveau expert (publié par le rail) : ouvre « Réglages avancés » d'office
  chipClass,
}) {
  return (
    <>
          {/* Contrôles de config (mode normal) */}
          <div id="rp9-config" hidden className="space-y-4 border-t border-border bg-card p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Type de toit</span>
              <button type="button" data-rooftype="flat" className={chipClass} aria-pressed="true">Toit plat</button>
              <button type="button" data-rooftype="pitched" className={chipClass} aria-pressed="false">Toit en pente / tuiles</button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" id="rp9-optimum" className={`${chipClass} text-primary-text`}>↺ Réinitialiser</button>
              <span id="rp9-optimum-note" className="min-w-0 flex-1 text-xs text-muted-foreground"></span>
            </div>
            <div id="rp9-flat-controls" className="space-y-4">
              <div id="rp9-flat-only" className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Orientation</span>
                  <button type="button" data-family="south" className={chipClass} aria-pressed="true">Plein sud<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-family="eastwest" className={chipClass} aria-pressed="false">Est-Ouest<span className="rp9-reco-badge" hidden> ✓</span></button>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Inclinaison</span>
                  <button type="button" data-tilt="reco" className={chipClass} aria-pressed="true">Recommandé<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-tilt="29" className={chipClass} aria-pressed="false">29°<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-tilt="15" className={chipClass} aria-pressed="false">15°<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-tilt="10" className={chipClass} aria-pressed="false">10°<span className="rp9-reco-badge" hidden> ✓</span></button>
                </div>
                <div className="flex items-center gap-3">
                  <label htmlFor="rp9-tilt-range" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground shrink-0">Inclinaison fine</label>
                  <input id="rp9-tilt-range" type="range" min="5" max="35" step="1" defaultValue="29" className="rp9-range min-w-0 flex-1" />
                  <span id="rp9-tilt-value" className="w-16 shrink-0 text-right text-sm font-semibold text-primary-text">29°</span>
                </div>
                <div id="rp9-azimuth-group" hidden className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Azimut</span>
                  <button type="button" data-azimuth="south" className={chipClass} aria-pressed="true">Plein sud<span className="rp9-reco-badge" hidden> ✓</span></button>
                  <button type="button" data-azimuth="aligned" className={chipClass} aria-pressed="false">Aligné toit<span className="rp9-reco-badge" hidden> ✓</span></button>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Panneaux</span>
                <button type="button" data-orient="auto" className={chipClass} aria-pressed="true">Auto</button>
                <button type="button" data-orient="portrait" className={chipClass} aria-pressed="false">Portrait<span className="rp9-reco-badge" hidden> ✓</span></button>
                <button type="button" data-orient="landscape" className={chipClass} aria-pressed="false">Paysage<span className="rp9-reco-badge" hidden> ✓</span></button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Marge de rive</span>
                <button type="button" data-margin="keep" className={chipClass} aria-pressed="true">Garder<span className="rp9-reco-badge" hidden> ✓</span></button>
                <button type="button" data-margin="remove" className={chipClass} aria-pressed="false">Pleine rive<span className="rp9-reco-badge" hidden> ✓</span></button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <label htmlFor="rp9-overhang-input" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Débord (m)</label>
                <input id="rp9-overhang-input" type="number" inputMode="decimal" step="any" min="0" defaultValue="0"
                  className="fig h-9 w-20 border border-border bg-background px-2 text-center text-base text-foreground outline-none focus:border-brass-400" />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <label htmlFor="rp9-seuil-acces" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Accès solaire minimal (%)</label>
                <input id="rp9-seuil-acces" type="text" inputMode="decimal" aria-describedby="rp9-seuil-acces-erreur rp9-seuil-acces-note"
                  className="fig h-11 w-20 border border-border bg-background px-2 text-center text-base text-foreground outline-none focus:border-brass-400" />
                <span id="rp9-seuil-acces-note" className="text-xs text-muted-foreground" />
                <span id="rp9-seuil-acces-erreur" role="alert" className="w-full text-xs text-destructive" />
              </div>
            </div>
            <div id="rp9-pitched-controls" hidden className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Pente</span>
                <button type="button" data-pitch="15" className={chipClass} aria-pressed="false">~15°</button>
                <button type="button" data-pitch="22" className={chipClass} aria-pressed="true">~22°</button>
                <button type="button" data-pitch="30" className={chipClass} aria-pressed="false">~30°</button>
                <button type="button" data-pitch="45" className={chipClass} aria-pressed="false">~45°</button>
              </div>
              <div className="flex items-center gap-3">
                <label htmlFor="rp9-pitch-range" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground shrink-0">Pente fine</label>
                <input id="rp9-pitch-range" type="range" min="5" max="45" step="1" defaultValue="22" className="rp9-range min-w-0 flex-1" />
                <span id="rp9-pitch-value" className="w-12 shrink-0 text-right text-sm font-semibold text-primary-text">22°</span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Face du pan</span>
                <button type="button" data-facing="180" className={chipClass} aria-pressed="true">Sud</button>
                <button type="button" data-facing="135" className={chipClass} aria-pressed="false">Sud-Est</button>
                <button type="button" data-facing="225" className={chipClass} aria-pressed="false">Sud-Ouest</button>
                <button type="button" data-facing="90" className={chipClass} aria-pressed="false">Est</button>
                <button type="button" data-facing="270" className={chipClass} aria-pressed="false">Ouest</button>
              </div>
              <p id="rp9-facing-note" className="min-h-[1rem] text-xs text-muted-foreground" aria-live="polite"></p>
              <div className="flex items-center gap-3">
                <label htmlFor="rp9-facing-range" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground shrink-0">Sens de la pente</label>
                <input id="rp9-facing-range" type="range" min="0" max="359" step="any" defaultValue="180" className="rp9-range min-w-0 flex-1" />
                <span id="rp9-facing-value" className="w-28 shrink-0 text-right text-sm font-semibold text-primary-text">Sud · 180°</span>
              </div>
              <p id="rp9-pitched-note" className="min-h-[1.25rem] text-xs text-foreground" aria-live="polite"></p>
            </div>

            {/* CAL107 — bloc « Obstacles », porté de apps/web/src/pages/preview/
                toiture-3d-pro-11.astro (mêmes ids : obstaclesUi.ts les cherche par id,
                indépendamment de la page qui les héberge). Ce contrôle manquait dans
                l'ERP — la pose d'obstacle n'était donc reachable QUE sur la page de
                préview publique, jamais depuis le poste d'un commercial. */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Obstacles</span>
              <button type="button" id="rp9-obstacle" className={chipClass}>Ajouter un obstacle (cheminée…)</button>
              <button type="button" id="rp9-obstacle-clear" className={chipClass}>Tout effacer</button>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Marquez les obstacles (climatiseur, cheminée, lanterneau, citerne…) — on
              n'y posera pas de panneaux. Glissez sur le toit pour dessiner un
              rectangle ; touchez-le pour le redimensionner.
            </p>
            <div id="rp9-obs-edit" hidden className="border border-border bg-background/40 p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs font-semibold uppercase tracking-wide text-primary-text">Obstacle sélectionné</span>
                <button type="button" id="rp9-obs-delete"
                  className="border border-alert-300/60 px-3 py-2 text-sm font-semibold text-destructive transition-colors hover:bg-alert-300/10">
                  × Supprimer
                </button>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="block text-sm text-foreground">
                  Longueur (m)
                  <input id="rp9-obs-length" type="text" inputMode="decimal" step="any"
                    className="fig mt-1 h-9 w-full border border-border bg-background px-2 text-center text-base text-foreground outline-none focus:border-brass-400" />
                </label>
                <label className="block text-sm text-foreground">
                  Largeur (m)
                  <input id="rp9-obs-width" type="text" inputMode="decimal" step="any"
                    className="fig mt-1 h-9 w-full border border-border bg-background px-2 text-center text-base text-foreground outline-none focus:border-brass-400" />
                </label>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Taille</span>
                <button type="button" id="rp9-obs-minus" aria-label="Réduire l'obstacle"
                  className="h-11 w-11 border border-border text-xl font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text">−</button>
                <button type="button" id="rp9-obs-plus" aria-label="Agrandir l'obstacle"
                  className="h-11 w-11 border border-border text-xl font-bold text-foreground transition-colors hover:border-brass-400 hover:text-primary-text">+</button>
                <span id="rp9-obs-dims" className="fig text-sm text-foreground">—</span>
              </div>
              {/* ACAL493 — hauteur saisie (obstaclesUi.ts : `rp9-obs-height`, au `change`, vide = retirée). */}
              <label className="mt-3 block text-sm text-foreground">
                Hauteur (m)
                <input id="rp9-obs-height" type="text" inputMode="decimal" step="any"
                  className="fig mt-1 h-11 w-full border border-border bg-background px-2 text-center text-base text-foreground outline-none focus:border-brass-400" />
              </label>
              <p className="mt-1 text-xs text-muted-foreground">
                Laissez vide si vous ne la connaissez pas : l'obstacle ne fera alors aucune ombre.
              </p>
              {/* ACAL1032 — duplication (CAL73) et trame ; ids lus par obstaclesUi.ts. */}
              <button type="button" id="rp9-obs-duplicate" className={`${chipClass} mt-3 min-h-11`}>Dupliquer</button>
              <details className="mt-3">
                <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-foreground">Poser en série</summary>
                <div className="grid grid-cols-3 gap-3">
                  {[['spacing', 'Pas (m)'], ['cols', 'Colonnes'], ['rows', 'Lignes']].map(([k, nom]) => (
                    <label key={k} className="block text-sm text-foreground">
                      {nom}
                      <input id={`rp9-obs-grid-${k}`} type="text" inputMode="decimal" step="any"
                        className="fig mt-1 h-11 w-full border border-border bg-background px-2 text-center text-base text-foreground outline-none focus:border-brass-400 aria-[invalid=true]:border-destructive" />
                    </label>
                  ))}
                </div>
                <button type="button" id="rp9-obs-grid-place" className={`${chipClass} mt-3 min-h-11`}>Poser en série</button>
              </details>
            </div>
            {/* ACAL493 — bandeau « Compte NON engageable » (CAL72), visible même sans sélection. */}
            <p id="rp9-obs-engage" role="status" hidden className="border border-alert-300/60 bg-background/40 p-3 text-sm text-foreground"></p>

            {/* ACAL497 — « Mesurer une hauteur par son ombre » (shadingUi.ts, WJ19) : niveau expert, replié d'office. */}
            <details id="rp9-shade-bloc" open={!!expert} className="border border-border p-3">
              <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-foreground">Ombre d'un voisin ou d'un arbre</summary>
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" id="rp9-shade-add" aria-pressed="false" className={`${chipClass} min-h-11`}>Mesurer une hauteur par son ombre</button>
                <button type="button" id="rp9-shade-clear" className={`${chipClass} min-h-11`}>Effacer les ombres</button>
              </div>
              <label className="mt-3 block text-sm text-foreground">
                Heure solaire de l'image
                <input id="rp9-shade-hour" type="text" inputMode="decimal" step="any"
                  className="fig mt-1 h-11 w-full border border-border bg-background px-2 text-center text-base text-foreground outline-none focus:border-brass-400" />
              </label>
              <p id="rp9-shade-hour-value" className="mt-1 text-xs text-muted-foreground"></p>
              <p className="mt-1 text-xs text-muted-foreground">Midi solaire = 12 h, ce n'est pas l'heure de la montre.</p>
              {/* ACAL504 — hauteur du bâtiment : shadingUi.ts accroche le panneau « Bâtiment » (rp11-batiment) à ce conteneur. */}
              <div id="rp9-shade-batiment" className="mt-3">
                <label className="block text-sm text-foreground">
                  Hauteur du bâtiment (m)
                  <input id="rp9-shade-height" type="text" inputMode="decimal" step="any"
                    className="fig mt-1 h-11 w-full border border-border bg-background px-2 text-center text-base text-foreground outline-none focus:border-brass-400" />
                </label>
                <p id="rp9-shade-height-note" aria-live="polite" className="mt-1 text-xs text-muted-foreground"></p>
              </div>
              <div id="rp9-shade-list" className="mt-2 space-y-2"></div>
              <p id="rp9-shade-note" aria-live="polite" className="mt-2 text-xs text-muted-foreground"></p>
            </details>

            {/* CAL102 — outil de MESURE (distance/surface/angle), annotation persistée avec
                le calepinage (roofPro11/mesureUi.ts). Un genre choisi, des taps posent les
                points, « Terminer la mesure » la pose (refusée tant qu'elle est
                géométriquement invalide pour son genre), « Annuler » abandonne la session. */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Mesurer</span>
              <button type="button" data-mesure-kind="distance" id="rp9-mesure-distance" className={chipClass} aria-pressed="false">Distance</button>
              <button type="button" data-mesure-kind="area" id="rp9-mesure-area" className={chipClass} aria-pressed="false">Surface</button>
              <button type="button" data-mesure-kind="angle" id="rp9-mesure-angle" className={chipClass} aria-pressed="false">Angle</button>
              <button type="button" id="rp9-mesure-finish" hidden className={chipClass}>Terminer la mesure</button>
              <button type="button" id="rp9-mesure-cancel" hidden className={chipClass}>Annuler</button>
            </div>
            <p id="rp9-mesure-note" className="min-h-[1rem] text-xs text-muted-foreground" aria-live="polite"></p>
            <ul id="rp9-mesure-list" className="space-y-1 text-xs text-foreground"></ul>

            {/* ACAL434 — barre du soleil (ids lus par roof-tool-pro11.ts ; le script y crée
                lui-même la date rp9-sun-date et les boutons de lecture jour/année). */}
            <div id="rp9-sun-controls" className="space-y-3 border border-border bg-muted p-3">
              <div className="flex items-center gap-3">
                <label htmlFor="rp9-sun-hour" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground shrink-0">Heure du soleil</label>
                <input id="rp9-sun-hour" type="range" min="6" max="18" step="1" defaultValue="12" className="rp9-range min-w-0 flex-1"
                  aria-label="Heure solaire (6 h à 18 h, midi solaire = 12 h)" />
                <span id="rp9-sun-hour-value" className="w-12 shrink-0 text-right text-sm font-semibold text-primary-text">12 h</span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Saison</span>
                <button type="button" data-sun-season="winter" className={chipClass} aria-pressed="true">Hiver (pire cas)</button>
                <button type="button" data-sun-season="summer" className={chipClass} aria-pressed="false">Été</button>
              </div>
              {/* ACAL436 — carte d'accès solaire (ids lus par shadingUi.ts, qui crée lui-même le mois, le bloc chiffré et les heures masquées dans ce parent). */}
              <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mr-1">Accès solaire</span>
                <button type="button" id="rp9-heatmap-toggle" className={chipClass} aria-pressed="false">Carte d'accès solaire</button>
                <p id="rp9-heatmap-note" className="w-full text-xs text-muted-foreground" />
              </div>
            </div>
            <HeureLegale />
          </div>
    </>
  )
}
