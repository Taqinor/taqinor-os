import { lazy, Suspense, useCallback, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { FileText, FolderKanban, Lock } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import useVisibilityAwarePolling from '../../../hooks/useVisibilityAwarePolling'
import { Card, EmptyState, Skeleton, toast } from '../../../ui'
import { formatDateTime } from '../../../lib/format'
import PieceRow from './PieceRow'
import { piecesVisibles } from './DossierPage.utils'

/* ============================================================================
   AOF174 — Écran « Dossier de soumission » : pièces, états, péremption.
   ----------------------------------------------------------------------------
   Trois colonnes : (1) les pièces du gabarit avec leur pastille d'état
   (`../statusAo`, AOF10), (2) la prévisualisation au centre, (3) les échéances
   et les actions à droite.

   **PÉREMPTION SANS RAFRAÎCHIR LA PAGE.** Le serveur seul décide qu'une pièce
   est périmée (AOF146/AOF152 : empreinte du contexte). L'écran la VOIT arriver
   parce qu'il resonde le dossier via `useVisibilityAwarePolling` (VX56, le hook
   partagé — jamais un `setInterval` maison, jamais un sondage d'onglet caché) :
   dès que le calepinage ou un prix a bougé, la pièce bascule en PÉRIMÉ avec son
   MOTIF, sans que l'utilisateur ait touché à quoi que ce soit. Aucun calcul de
   péremption côté front (AOF94) : `statut` et `motif_peremption` sont lus tels
   quels.

   **VERROU DE DOSSIER (AOF155).** `dossier.verrou` (porteur + heure) est affiché
   en bandeau et DÉSACTIVE les actions d'écriture — c'est la moitié visible du
   409 nommé côté serveur ; sans elle, l'utilisateur relance et prend une erreur
   sans comprendre.

   **CONFIDENTIALITÉ (en-tête du Groupe AOF).** Les pièces de visibilité
   `interne` ou `directeur` (économie, coût de revient, marge) ne sont JAMAIS
   listées ici : l'écran ne les filtre pas « à l'affichage », il ne les met pas
   dans son arbre du tout. Aucun vocabulaire de coût dans ce fichier.

   Le centre (aperçu) et la colonne de droite (échéances/actions) sont des
   EMPLACEMENTS injectables (`renderApercu`, `renderEcheances`, `actions`) :
   AOF175 (`PiecePreview`), AOF176/AOF177 (contrôles + ZIP) et AOF178
   (`EcheancesDossier`) s'y branchent sans que cet écran les importe en dur.

   ── LES EMPLACEMENTS ONT UN CONTENU PAR DÉFAUT (correctif) ────────────────
   Le raisonnement ci-dessus était juste ET il a produit trois écrans morts :
   les DEUX seuls monteurs réels de cette page — l'onglet « Dossier » de
   `AffaireDetail.jsx` et la route `/ao/dossiers/:id` de `module.config.jsx` —
   la rendaient SANS aucun de ces props, si bien que `ControlesAvantDepot`
   (AOF176), `ZipButton` (AOF177) et `EcheancesDossier` (AOF178) n'étaient
   importés par AUCUN fichier de l'application. Un emplacement facultatif que
   personne ne remplit est un écran perdu.

   Les trois panneaux sont donc le CONTENU PAR DÉFAUT de leur emplacement, en
   `lazy()` : ils restent hors du module de cet écran (chunks séparés, chargés
   à l'ouverture), les props restent prioritaires — un monteur qui passe son
   propre `renderEcheances`/`actions` garde exactement la main d'avant — et
   TOUT monteur, présent ou futur, les obtient sans avoir à les connaître.

   **`peutProroger={false}` — DÉLIBÉRÉ, ce n'est pas un oubli.** Le repli de
   prorogation d'`EcheancesDossier` patcherait `prorogation_date` /
   `prorogation_reference` sur l'affaire ; `AppelOffre` ne porte NI l'un NI
   l'autre (vérifié dans `apps/ao/models.py` et
   `AppelOffreSerializer.Meta.fields`). DRF ignore un champ inconnu et répond
   200 : le formulaire annoncerait « Prorogation enregistrée » sans que RIEN
   n'ait été écrit — le mensonge silencieux qui a déjà coûté les boutons
   « Dupliquer » et « Épingler » du comparateur de variantes. Il revient le
   jour où le serveur sait l'honorer.

   `dateLimite` est une PROP de cet écran (et non une lecture du dossier) :
   `DossierAOSerializer` ne publie aucune date limite — elle appartient à
   l'affaire. Le compte à rebours n'en invente pas : sans la prop, il affiche
   « — ».

   Les ressources serveur consommées sont celles que `api/aoApi.js` (AOF11,
   lane `frontend/ao-socle`) déclare RÉELLEMENT — ce fichier n'est jamais
   retouché ici et aucun `axios` direct n'est utilisé (ARC44).
   ========================================================================== */

// Contenus PAR DÉFAUT des emplacements — `lazy` : jamais tirés dans le module
// de cet écran, chargés à l'ouverture (mêmes chunks que partout ailleurs).
const ControlesAvantDepot = lazy(() => import('./ControlesAvantDepot'))
const EcheancesDossier = lazy(() => import('./EcheancesDossier'))
const ZipButton = lazy(() => import('./ZipButton'))
// PACT71 — la checklist partenaire (AOF136) : sans elle, un point obligatoire
// encore ouvert bloque le dépôt SANS QUE RIEN ne le montre sur cet écran.
const ChecklistPartenaire = lazy(() => import('./ChecklistPartenaire'))
// PACT72 — les pièces FOURNIES (partenaire/acheteur) : la colonne 1 les liste
// déjà en lecture (`PieceRow`), mais aucun écran ne permettait de les marquer
// présentes ni d'y attacher un fichier.
const PiecesFournies = lazy(() => import('./PiecesFournies'))

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const POLL_MS = 15000

/* Motif ÉCRIT SUR le bouton ZIP quand le dossier porte un verrou (AOF155) —
   jamais un bouton grisé sans explication (règle d'AOF176/AOF177). */
const MOTIF_ZIP_VERROU = 'une opération est déjà en cours sur ce dossier'

function VerrouBandeau({ verrou }) {
  if (!verrou) return null
  const depuis = verrou.depuis ? formatDateTime(verrou.depuis) : null
  return (
    <Card className="flex items-start gap-2 border-warning/50 bg-warning/5 p-3" role="status">
      <Lock className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
      <p className="text-sm">
        <span className="font-medium text-warning">Opération en cours sur ce dossier</span>
        {' — '}
        {verrou.operation_label || verrou.operation || 'traitement'}
        {verrou.porteur ? ` par ${verrou.porteur}` : ''}
        {depuis ? ` depuis ${depuis}` : ''}. Les actions d’écriture sont suspendues.
      </p>
    </Card>
  )
}

export default function DossierPage({
  dossierId,
  dateLimite = null,
  renderApercu,
  renderEcheances,
  actions,
  pollIntervalMs = POLL_MS,
}) {
  const params = useParams()
  const id = dossierId ?? params.id
  const [selectedId, setSelectedId] = useState(null)
  const [regeneratingId, setRegeneratingId] = useState(null)

  const { data: dossier, loading, error, refetch } = useResource(
    () => aoApi.dossiers.get(id), id,
    {
      // `aoApi.dossiers.get` est un appel axios brut : `select` déballe la
      // réponse (convention ARC45 de `useResource`). Sans lui, `dossier`
      // valait `{ data: {...} }` et l'écran restait vide.
      select: (res) => res?.data ?? null,
      errorMessage: 'Impossible de charger le dossier de soumission.',
    },
  )

  // Le serveur périme, l'écran le VOIT : resondage sensible à la visibilité de
  // l'onglet (aucun sondage quand l'onglet est masqué).
  useVisibilityAwarePolling(
    useMemo(() => [{ fn: refetch, intervalMs: pollIntervalMs }], [refetch, pollIntervalMs]),
    { enabled: Boolean(id) },
  )

  const pieces = useMemo(() => piecesVisibles(dossier?.pieces), [dossier])
  const selected = useMemo(
    () => pieces.find((p) => p.id === selectedId) ?? pieces[0] ?? null,
    [pieces, selectedId],
  )
  const verrou = dossier?.verrou ?? null

  const regenerer = useCallback(async (piece) => {
    setRegeneratingId(piece.id)
    try {
      await aoApi.dossiers.genererPiece(id, piece.type || piece.code)
      toast.success(`« ${piece.libelle || piece.code} » régénérée.`)
      refetch()
    } catch (e) {
      // 409 du verrou de dossier (AOF155) : le serveur NOMME le porteur.
      toast.error(errMsg(e, 'Régénération impossible.'))
    } finally {
      setRegeneratingId(null)
    }
  }, [id, refetch])

  if (loading && !dossier) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }
  if (error || !dossier) {
    return (
      <EmptyState
        icon={FolderKanban}
        title="Dossier introuvable"
        description={error || "Ce dossier de soumission n'existe pas ou n'est pas accessible."}
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Dossier de soumission {dossier.reference ? `— ${dossier.reference}` : ''}
        </h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Pièces du gabarit, états et péremption — une pièce dont les données sources ont bougé
          repasse en « Périmé » avec son motif.
        </p>
      </div>

      <VerrouBandeau verrou={verrou} />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)_minmax(0,20rem)]">
        {/* ── Colonne 1 : les pièces du gabarit ─────────────────────────── */}
        <Card className="p-3">
          <h2 className="mb-2 font-display text-base font-semibold">Pièces du dossier</h2>
          {pieces.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="Aucune pièce"
              description="Le gabarit de ce dossier ne déclare encore aucune pièce."
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {pieces.map((piece) => (
                <PieceRow
                  key={piece.id}
                  piece={piece}
                  selected={selected?.id === piece.id}
                  onSelect={(p) => setSelectedId(p.id)}
                  onRegenerer={regenerer}
                  regenerating={regeneratingId === piece.id}
                  verrouille={Boolean(verrou)}
                />
              ))}
            </ul>
          )}
        </Card>

        {/* ── Colonne 2 : prévisualisation (AOF175 s'y branche) ─────────── */}
        <Card className="min-h-[24rem] p-3">
          <h2 className="mb-2 font-display text-base font-semibold">Aperçu</h2>
          {renderApercu ? renderApercu({ piece: selected, dossier }) : (
            <EmptyState
              icon={FileText}
              title={selected ? (selected.libelle || selected.code) : 'Aucune pièce sélectionnée'}
              description="Sélectionnez une pièce pour l’afficher."
            />
          )}
        </Card>

        {/* ── Colonne 3 : échéances et actions ──────────────────────────── */}
        <div className="flex flex-col gap-4">
          {renderEcheances ? renderEcheances({ dossier }) : (
            <Suspense fallback={<Skeleton className="h-64 w-full" />}>
              <EcheancesDossier
                affaireId={dossier.appel_offre}
                dateLimite={dateLimite}
                echeances={dossier.echeances || []}
                jalons={dossier.jalons || []}
                peutProroger={false}
              />
            </Suspense>
          )}
          {actions ? (
            <Card className="p-3">
              <h2 className="mb-2 font-display text-base font-semibold">Actions</h2>
              {typeof actions === 'function' ? actions({ dossier, verrou }) : actions}
            </Card>
          ) : (
            /* `ControlesAvantDepot` porte déjà sa propre `Card` et son titre :
               l'imbriquer dans la carte « Actions » ferait une carte dans une
               carte. Le verrou de dossier (AOF155) bloque le ZIP comme il
               bloque la régénération d'une pièce — avec son MOTIF sur le
               bouton, jamais un bouton grisé muet. */
            <Suspense fallback={<Skeleton className="h-40 w-full" />}>
              <ControlesAvantDepot
                dossierId={dossier.id}
                zipSlot={({ bloque, motif }) => (
                  <ZipButton
                    dossierId={dossier.id}
                    bloque={bloque || Boolean(verrou)}
                    motifBlocage={motif || (verrou ? MOTIF_ZIP_VERROU : null)}
                  />
                )}
              />
            </Suspense>
          )}
        </div>
      </div>

      {/* PACT72 — pièces fournies (partenaire/acheteur), PLEINE LARGEUR : le
          panneau se tait lui-même (aucun rendu) si le dossier n'en a aucune. */}
      <Suspense fallback={null}>
        <PiecesFournies dossierId={dossier.id} />
      </Suspense>

      {/* PACT71 — checklist partenaire, PLEINE LARGEUR sous la grille : ses
          sept blocs (CPS, acte d'engagement, bordereau, lettre de soumission,
          mémoire, dossier administratif, vérifications) ne tiennent pas dans
          une colonne de 20rem sans devenir illisibles. */}
      <Suspense fallback={<Skeleton className="h-40 w-full" />}>
        <ChecklistPartenaire dossierId={dossier.id} />
      </Suspense>
    </div>
  )
}
