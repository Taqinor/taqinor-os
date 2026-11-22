// Coque (22/11) — groupe « outils » du DOM du constructeur, DÉPLACÉ VERBATIM depuis
// BuilderDom.jsx (move only) : la rangée Effacer / + Ajouter une zone / Parcelle / bascules /
// surface. `#rp9-add-area` est l'ANCRE des formes du toit et de « Créer le toit » (script).

export default function BuilderOutils({
  chipClass,
  photoToit,
  photoToitVisible,
  setPhotoToitVisible,
  setToitClientVisible,
  toitClientPresent,
  toitClientVisible,
}) {
  return (
    <>
          <div className="flex flex-wrap items-center gap-3 border-t border-border p-4">
            <button type="button" id="rp9-clear" className={chipClass}>Effacer</button>
            <button type="button" id="rp9-add-area" disabled className={chipClass}>+ Ajouter une zone</button>
            {/* ACAL233 — la parcelle du site (clé racine `parcelle`, plan de masse). */}
            <button type="button" id="rp9-parcelle" aria-pressed="false" className={chipClass}>Parcelle</button>
            <button type="button" id="rp9-parcelle-clear" hidden className={chipClass}>Effacer la parcelle</button>
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
            <p className="ml-auto text-sm text-muted-foreground"><span>Surface&nbsp;: </span><span id="rp9-area-value" className="text-foreground">—</span></p>
          </div>
    </>
  )
}
