import { ETAPES } from './parcoursGuide'

/* ============================================================================
   ACAL393 — LES CINQ BOUTONS D'ÉTAPE DU PARCOURS GUIDÉ.
   Lit `calepinageApi.calepinages.parcours(id)` (contrat
   `calepinage_parcours_guide.json`) : une pastille d'état par étape. La lecture
   est best-effort : sans réponse, les boutons restent là, sans pastille. Un
   clic ouvre l'étape via `onChoisir(cleEtape)` — le rail écrit l'URL.
   ========================================================================== */

const LIBELLE_ETAT = {
  a_faire: 'à faire', en_cours: 'en cours', fait: 'fait', bloque: 'bloqué',
}

export default function RailGuide({ etapeActive, etats, onChoisir }) {
  return (
    <nav aria-label="Étapes du calepinage" data-testid="cal-rail-etapes"
      className="mb-2 flex flex-wrap gap-1.5">
      {ETAPES.map((etape, rang) => {
        const etat = etats[etape.cle]
        const actif = etape.cle === etapeActive
        return (
          <button
            key={etape.cle}
            type="button"
            data-testid={`cal-etape-${etape.cle}`}
            data-etat={etat ?? ''}
            aria-current={actif ? 'step' : undefined}
            onClick={() => onChoisir(etape.cle)}
            className={`inline-flex items-center gap-1.5 border px-3 py-1.5 text-sm ${
              actif ? 'border-primary bg-primary/10 font-medium' : 'border-border'}`}
          >
            <span className="tech-label text-lune-faint">{rang + 1}</span>
            {etape.libelle}
            {etat && (
              <span data-testid={`cal-etape-${etape.cle}-etat`}
                className="text-xs text-lune-faint">
                {LIBELLE_ETAT[etat]}
              </span>
            )}
          </button>
        )
      })}
    </nav>
  )
}
