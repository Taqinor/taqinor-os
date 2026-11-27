import { ETAPES, aReglerDeLEtape } from '../atelier/parcoursGuide'
import { Icone } from '../atelier/coque/primitives'
import { useAReglerPret } from './lecturePretAEnvoyer'
import { useRefusPublie } from '../production/refusPublie'

/* ============================================================================
   ACAL393 — LES CINQ BOUTONS D'ÉTAPE DU PARCOURS GUIDÉ.
   Lit `calepinageApi.calepinages.parcours(id)` (contrat
   `calepinage_parcours_guide.json`) : une pastille d'état par étape. La lecture
   est best-effort : sans réponse, les boutons restent là, sans pastille. Un
   clic ouvre l'étape via `onChoisir(cleEtape)` — le rail écrit l'URL.
   Coque (maquettes 22/11) — `vertical` : le RAIL DE GAUCHE de l'atelier plein écran
   (pictogramme + libellé empilés ; ACAL1802 : l'étape active dans une tuile BLEU NUIT, une étape `fait` porte la
   pastille verte cochée, « N à régler » une pastille or — styles de 50-coque-atelier.css sur `data-etat` /
   `aria-current` ; « Avancé » en bas, ligne « N à régler » lue sur `manque` servi par le parcours).
   ========================================================================== */

const LIBELLE_ETAT = {
  a_faire: 'à faire', en_cours: 'en cours', fait: 'fait', bloque: 'bloqué',
}

function RailVertical({ calepinageId, etapeActive, etats, manque, onChoisir, avance, onAvance, cache }) {
  // T4-B4-010 — quand « Prêt à envoyer ? » a été lu, le rail compte SUR CETTE liste (même compte que la colonne) :
  // une étape qui y a un point à régler n'est jamais dite « fait ». Sans lecture : le parcours servi, comme avant.
  const pret = useAReglerPret(calepinageId)
  // ACAL1650 — un refus de simulation en cours : l'étape Résultats dit SON compte (les points qui empêchent le calcul).
  const refus = useRefusPublie(calepinageId)
  return (
    <nav aria-label="Étapes" data-testid="cal-rail-etapes" className="cal-rail" hidden={cache || undefined}>
      {ETAPES.map((etape) => {
        const nPret = pret?.[etape.cle]
        const etat = nPret > 0 && etats[etape.cle] === 'fait' ? 'en_cours' : etats[etape.cle]
        const actif = etape.cle === etapeActive
        const aRegler = etape.cle === 'resultats' && refus.length > 0 ? refus.length
          : typeof nPret === 'number' ? nPret : aReglerDeLEtape(manque, etape.cle)
        return (
          <button key={etape.cle} type="button" data-testid={`cal-etape-${etape.cle}`}
            data-etat={etat ?? ''} aria-current={actif ? 'step' : undefined}
            aria-label={etat ? `${etape.libelle} (${LIBELLE_ETAT[etat]})` : undefined}
            onClick={() => onChoisir(etape.cle)} className="cal-rail-etape">
            <Icone nom={etape.cle} />
            <span className="cal-rail-libelle">{etape.libelle}</span>
            {etat && (
              <span data-testid={`cal-etape-${etape.cle}-etat`} className="sr-only">{LIBELLE_ETAT[etat]}</span>
            )}
            {aRegler > 0 && <span className="cal-rail-a-regler">{`${aRegler} à régler`}</span>}
          </button>
        )
      })}
      <span className="cal-rail-espace" aria-hidden="true" />
      <button type="button" data-testid="cal-rail-avance" aria-expanded={avance}
        onClick={() => onAvance(!avance)} className="cal-rail-etape cal-rail-avance">
        <Icone nom="avance" taille={22} />
        <span className="cal-rail-libelle">Avancé</span>
      </button>
    </nav>
  )
}

export default function RailGuide({
  etapeActive, etats, onChoisir, expert = false, onBasculerExpert = null,
  vertical = false, manque = [], avance = false, onAvance = () => {}, cache = false, calepinageId = null,
}) {
  if (vertical) {
    return <RailVertical calepinageId={calepinageId} etapeActive={etapeActive} etats={etats} manque={manque}
      onChoisir={onChoisir} avance={avance} onAvance={onAvance} cache={cache} />
  }
  return (
    <nav aria-label="Étapes du calepinage" data-testid="cal-rail-etapes"
      className="mb-2 flex flex-wrap items-center gap-1.5">
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
            <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">{rang + 1}</span>
            {etape.libelle}
            {etat && (
              <span data-testid={`cal-etape-${etape.cle}-etat`}
                className="text-xs text-muted-foreground">
                {LIBELLE_ETAT[etat]}
              </span>
            )}
          </button>
        )
      })}
      {onBasculerExpert && (
        <label className="ml-auto inline-flex items-center gap-1.5 text-xs text-muted-foreground"
          title="Mémorisé dans ce navigateur, pour votre compte — pas sur le serveur.">
          <input type="checkbox" data-testid="cal-mode-expert" checked={expert}
            onChange={(e) => onBasculerExpert(e.target.checked)} />
          Mode expert
        </label>
      )}
    </nav>
  )
}
