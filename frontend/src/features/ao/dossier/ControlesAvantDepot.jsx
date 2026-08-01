import { useMemo } from 'react'
import { AlertTriangle, Check, ShieldOff, X } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { Button, Card, EmptyState, Skeleton } from '../../../ui'
import { StatutControle } from '../statusAo'

/* ============================================================================
   AOF176 — Panneau « Contrôles avant dépôt » et blocage VISIBLE du ZIP.
   ----------------------------------------------------------------------------
   AOF146 fait du contrôleur de cohérence croisée une PORTE côté serveur (la
   transition `pret_a_deposer` est refusée tant qu'un bloquant est rouge). Sans
   écran, cette porte est INVISIBLE : l'utilisateur la contourne par l'API en
   croyant bien faire. Ce panneau la rend lisible.

   **Le bouton ZIP n'est JAMAIS un bouton grisé sans explication.** Quand un
   contrôle bloquant est rouge, le motif est écrit SUR le bouton (et non dans
   une infobulle qu'on peut ne pas survoler) : « ZIP bloqué — … ». C'est la
   règle produit de cette tâche.

   **Une pièce « hors contrôle » (AOF149) n'est jamais présumée verte.** Les
   pièces fournies à la main (acte au modèle de l'acheteur, attestations,
   caution bancaire) échappent aux ~14 invariants : elles sont listées à part,
   nommées, avec leur motif — un dossier « tout vert » dont un tiers n'a jamais
   été vérifié est plus dangereux qu'un dossier orange.

   Aucun verdict n'est calculé ici (AOF94) : sévérité, message et code de règle
   viennent du serveur ; l'écran ne fait que TRIER et AFFICHER.
   ========================================================================== */

const BLOQUANT = 'bloquant'

// Sévérité normalisée : le serveur peut la porter sur `severite` (AOF146) ou
// sur `statut` — les deux valent la même chose, on n'en invente pas une 3e.
export function severiteDe(controle) {
  return controle?.severite || controle?.statut || 'ok'
}

/** Motif AFFICHABLE du blocage : le message du premier contrôle bloquant
    (ou son code de règle à défaut). `null` quand rien ne bloque. */
export function motifBlocage(controles) {
  const bloquant = (controles || []).find((c) => severiteDe(c) === BLOQUANT)
  if (!bloquant) return null
  return bloquant.message || bloquant.libelle || bloquant.code || 'contrôle bloquant'
}

// Le serveur peut renvoyer un tableau nu ou une enveloppe {controles, ...}.
function lireControles(res) {
  const data = res?.data
  if (Array.isArray(data)) return { controles: data, horsControle: [] }
  return {
    controles: data?.controles ?? data?.results ?? [],
    horsControle: data?.pieces_hors_controle ?? [],
  }
}

function ControleRow({ controle, onOuvrirPiece }) {
  const severite = severiteDe(controle)
  const ok = severite === 'ok'
  const Icone = ok ? Check : X
  return (
    <li
      data-ao-controle={controle.code || String(controle.id)}
      className={[
        'flex flex-col gap-1 rounded-lg border border-l-4 p-2.5',
        severite === BLOQUANT ? 'border-l-destructive' : '',
        severite === 'avertissement' ? 'border-l-warning' : '',
        ok ? 'border-l-success' : '',
        'border-border',
      ].filter(Boolean).join(' ')}
    >
      <div className="flex items-start gap-2">
        {/* ✓/✗ décoratif : la pastille `StatutControle` porte le texte (la
            couleur n'est jamais le seul signal). */}
        <Icone
          className={`mt-0.5 size-4 shrink-0 ${ok ? 'text-success' : 'text-destructive'}`}
          aria-hidden="true"
        />
        <span className="min-w-0 flex-1 text-sm font-medium">
          {controle.libelle || controle.code}
        </span>
        <StatutControle status={severite} data-ao-etat={severite} />
      </div>
      {controle.message && (
        <p className="pl-6 text-xs text-muted-foreground">{controle.message}</p>
      )}
      {controle.piece_id != null && onOuvrirPiece && (
        <Button
          size="sm"
          variant="link"
          className="self-start pl-6"
          onClick={() => onOuvrirPiece(controle)}
        >
          Ouvrir « {controle.piece_libelle || `pièce #${controle.piece_id}`} »
          {controle.ancre ? ` — ${controle.ancre}` : ''}
        </Button>
      )}
    </li>
  )
}

export default function ControlesAvantDepot({
  dossierId,
  onOuvrirPiece,
  zipSlot,
}) {
  const { data, loading, error, refetch } = useResource(
    () => aoApi.dossiers.controlesAvantDepot(dossierId), dossierId,
    {
      initialData: { controles: [], horsControle: [] },
      select: lireControles,
      errorMessage: 'Impossible de charger les contrôles avant dépôt.',
    },
  )

  const controles = data?.controles ?? []
  const horsControle = data?.horsControle ?? []
  const motif = useMemo(() => motifBlocage(controles), [controles])
  const bloque = Boolean(motif)

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div>
        <h2 className="font-display text-base font-semibold">Contrôles avant dépôt</h2>
        <p className="text-xs text-muted-foreground">
          Cohérence croisée du dossier — un contrôle bloquant rouge interdit le dépôt.
        </p>
      </div>

      {loading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 3 }).map((unused, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      ) : error ? (
        <EmptyState
          icon={AlertTriangle}
          title="Contrôles indisponibles"
          description={error}
          action={<Button size="sm" variant="outline" onClick={refetch}>Réessayer</Button>}
        />
      ) : controles.length === 0 ? (
        <EmptyState
          icon={AlertTriangle}
          title="Aucun contrôle exécuté"
          description="Le contrôleur de cohérence n’a pas encore tourné sur ce dossier."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {controles.map((c) => (
            <ControleRow key={c.id ?? c.code} controle={c} onOuvrirPiece={onOuvrirPiece} />
          ))}
        </ul>
      )}

      {horsControle.length > 0 && (
        <div className="rounded-lg border border-warning/40 bg-warning/5 p-3">
          <p className="flex items-center gap-1.5 text-sm font-medium text-warning">
            <ShieldOff className="size-4" aria-hidden="true" />
            {horsControle.length} pièce(s) hors contrôle — non vérifiées par la fabrique
          </p>
          <ul className="mt-1.5 flex flex-col gap-1">
            {horsControle.map((p) => (
              <li key={p.id} className="text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{p.libelle || p.code}</span>
                {p.motif ? ` — ${p.motif}` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Le ZIP : jamais grisé sans explication. */}
      {zipSlot
        ? zipSlot({ bloque, motif, controles })
        : (
          <Button
            className="self-start"
            disabled={bloque}
            title={motif || undefined}
          >
            {bloque ? `ZIP bloqué — ${motif}` : 'Constituer le ZIP de dépôt'}
          </Button>
        )}
    </Card>
  )
}
