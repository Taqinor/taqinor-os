import { useCallback, useMemo, useState } from 'react'
import { AlertTriangle, ClipboardList } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import { Card, EmptyState, Skeleton } from '../../../ui'
import BordereauPage from './BordereauPage'

/* ============================================================================
   PACT69 — Câblage RÉEL de l'onglet « Bordereau » de la fiche affaire.
   ----------------------------------------------------------------------------
   `BordereauPage` (AOF179) est le panneau de présentation ; il a été construit
   avant qu'`api/aoApi.js` ne publie la moindre ressource bordereau, et
   `AffaireDetail.jsx` le montait donc avec `bordereau={null}` et un motif
   d'indisponibilité permanent. La ressource existe réellement côté serveur
   (`bordereaux-prix`/`sections-bordereau`/`lignes-bordereau`, AOF120) : ce
   fichier fait le pont, SANS toucher `BordereauPage.jsx` ni son test (déjà
   vert sur son propre contrat de props).

   MAPPING DE CHAMPS — le contrat RÉEL du serveur (`BordereauPrixSerializer`,
   `LigneBordereauSerializer`) diffère du contrat que `BordereauPage` attend
   (exactement le défaut que ce groupe corrige, cf. l'en-tête `docs/PLAN.md`
   § Groupe PACT) :
     • `montant_remise_globale` (serveur) → `remise_globale` (prop attendue) ;
     • `total_tva` (serveur)             → `tva_montant` (prop attendue) ;
     • `taux_tva_effectif` (serveur)     → `tva` (prop attendue, ligne) ;
     • `montant_ht` (serveur, ligne)     → `total_ht` (prop attendue, ligne).
   `total_ttc_lettres` / `prix_unitaire_lettres` / `deverrouillee*` : AUCUN
   champ serveur ne les porte — jamais inventés, simplement absents du mapping
   (le composant les affiche déjà en repli « — » / masqué, c'est son contrat).

   ÉCRITURE — seule `onModifierLigne` est branchée sur un PATCH réel de
   `lignes-bordereau/<id>/` (désignation/unité/quantité/PU/remise/TVA/section,
   tous des champs écrivables du sérialiseur) ; `onDeplacerLigne` réutilise le
   MÊME PATCH sur le champ `section`. `onDeverrouiller`/`onAppliquerPrix` ne
   sont PAS branchés : aucune route ne trace un motif de déverrouillage ni ne
   propose un prix de bibliothèque de prix — les brancher sur un PATCH nu
   simulerait une traçabilité qui n'existe pas côté serveur. `BordereauPage`
   gère déjà ces handlers absents (les boutons correspondants ne se rendent
   pas), donc rien n'est cassé, rien n'est deviné.

   ABSENCE DE CLAUSE DE RÉSERVE — signalée en direct via l'action serveur
   `controles` (`raisons_bordereau_non_remettable`), jamais recalculée ici.
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

function mapLigne(l) {
  return { ...l, tva: l.taux_tva_effectif, total_ht: l.montant_ht }
}

function mapBordereau(b) {
  if (!b) return null
  return {
    ...b,
    remise_globale: b.montant_remise_globale,
    tva_montant: b.total_tva,
    lignes: (b.lignes || []).map(mapLigne),
  }
}

function SelecteurBordereau({ bordereaux, valeur, onChange }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor="ao-affaire-bordereau" className="text-xs text-muted-foreground">
        Bordereau
      </label>
      <select
        id="ao-affaire-bordereau"
        className="h-9 min-w-0 max-w-full rounded-md border border-input bg-card px-2 text-sm text-foreground focus-ring"
        value={String(valeur ?? '')}
        onChange={(e) => onChange(Number(e.target.value))}
      >
        {bordereaux.map((b) => (
          <option key={b.id} value={b.id}>
            {b.intitule} — indice {b.indice_revision}
          </option>
        ))}
      </select>
    </div>
  )
}

export default function BordereauAffairePanel({ affaireId }) {
  const [choisi, setChoisi] = useState(null)

  const listeParams = useMemo(() => ({ appel_offre: affaireId }), [affaireId])
  const {
    data: bordereaux, loading: chargementListe, error: erreurListe,
  } = useResource(
    () => aoApi.bordereaux.list(listeParams), listeParams,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les bordereaux de cette affaire.',
    },
  )

  const bordereauId = choisi ?? bordereaux[0]?.id ?? null

  const { data: brut, loading, error, refetch } = useResource(
    () => aoApi.bordereaux.get(bordereauId), bordereauId,
    {
      select: (res) => res?.data ?? null,
      errorMessage: (e) => errMsg(e, 'Impossible de charger le bordereau.'),
      enabled: Boolean(bordereauId),
    },
  )

  const { data: controles } = useResource(
    () => aoApi.bordereaux.controles(bordereauId), bordereauId,
    {
      select: (res) => res?.data ?? null,
      // Panneau annexe : une panne sur ce SEUL appel ne doit pas cacher le
      // bordereau lui-même — on se tait plutôt que d'afficher une erreur pour
      // un contrôle qui n'est qu'un signal complémentaire.
      errorMessage: () => '',
      enabled: Boolean(bordereauId),
    },
  )

  const bordereau = useMemo(() => mapBordereau(brut), [brut])

  const rafraichir = useCallback(async () => {
    const frais = await aoApi.bordereaux.get(bordereauId)
    refetch()
    return { data: mapBordereau(frais?.data) }
  }, [bordereauId, refetch])

  const onModifierLigne = useCallback(async (ligne, patch) => {
    await aoApi.lignesBordereau.update(ligne.id, patch)
    return rafraichir()
  }, [rafraichir])

  const onDeplacerLigne = useCallback(async (ligne, sectionId) => {
    await aoApi.lignesBordereau.update(ligne.id, { section: sectionId })
    return rafraichir()
  }, [rafraichir])

  /* UN SEUL chemin de chiffrage : le bordereau devient un DEVIS ventes
     standard, qui repart dans le pipeline devis normal (PDF `/proposal`).
     L'action est SERVEUR et idempotente (un second clic renvoie le brouillon
     déjà créé) ; aucun montant, aucune ligne n'est assemblée ici. Le bordereau
     n'est pas touché par cette action — donc aucune relecture. */
  const onCreerDevis = useCallback(
    () => aoApi.bordereaux.creerDevis(bordereauId), [bordereauId])

  if (chargementListe) {
    return <div className="flex flex-col gap-3"><Skeleton className="h-8 w-64" /><Skeleton className="h-64 w-full" /></div>
  }
  if (erreurListe) {
    return (
      <EmptyState icon={ClipboardList} tone="error" title="Bordereaux indisponibles" description={erreurListe} />
    )
  }
  if (!bordereaux.length) {
    return (
      <EmptyState
        icon={ClipboardList}
        title="Aucun bordereau des prix"
        description="Cette affaire n'a pas encore de bordereau des prix."
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {bordereaux.length > 1 && (
        <SelecteurBordereau bordereaux={bordereaux} valeur={bordereauId} onChange={setChoisi} />
      )}
      {controles && !controles.remettable && (
        <Card className="flex items-start gap-2 border-destructive/60 bg-destructive/5 p-3" role="alert">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium text-destructive">Bordereau non remettable</p>
            <ul className="mt-1 flex flex-col gap-0.5">
              {(controles.raisons || []).map((raison) => (
                <li key={raison} className="text-xs text-destructive">{raison}</li>
              ))}
            </ul>
          </div>
        </Card>
      )}
      <BordereauPage
        bordereau={bordereau}
        loading={loading}
        error={error}
        onModifierLigne={onModifierLigne}
        onDeplacerLigne={onDeplacerLigne}
        onCreerDevis={onCreerDevis}
      />
    </div>
  )
}
