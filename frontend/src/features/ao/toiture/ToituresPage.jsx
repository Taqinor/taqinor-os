import { useState } from 'react'
import aoApi from '../../../api/aoApi'
import recordsApi from '../../../api/recordsApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import { Card, EmptyState, Skeleton, toast } from '../../../ui'
import PageHeader from '../../../components/layout/PageHeader'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
import ModeMobile from '../studio/ModeMobile'

/* ============================================================================
   AOF190 — Écran « Toitures & relevés », et son MODE MOBILE réel.
   ----------------------------------------------------------------------------
   Cette destination de nav existait déjà (`module.config.jsx`, AOF7) mais
   rendait un squelette générique : sur un téléphone, l'entrée « Toitures &
   relevés » de la barre basse était donc littéralement le BOUTON MORT
   qu'AOF190 interdit — on tape, il ne se passe rien d'utile, et rien
   n'explique pourquoi. `ModeMobile` (livré par AOF190, mais monté nulle part
   jusqu'ici) est exactement la réponse écrite pour ce cas :

     · l'atelier est rendu en LECTURE (mêmes données, aucune interaction
       lourde) ;
     · la CAPTURE reste possible — « Photo → repère » attache réellement le
       cliché au dossier via `records` (cible `ao.appeloffre`, la seule
       déclarée par `apps/ao/platform.py`), jamais un handler décoratif ;
     · chaque édition lourde refusée affiche SA RAISON
       (`data-ao-tiroir="refus-mobile-…"`, contrat AOF8).

   Au-dessus de 768 px, l'écran rend la même lecture SANS enveloppe de mode :
   l'atelier de traçage interactif (canvas, outils, pose d'obstacles) est
   livré par la lane `frontend/ao-toiture` — l'annoncer ici par des contrôles
   inertes serait la façade que le mode mobile existe précisément pour éviter.
   AUCUN contrôle mort n'est donc rendu à AUCUNE largeur.

   Données : `useResource` + `aoApi` (ARC45/ARC44, zéro fetch manuel). Aucun
   chiffre n'est recalculé côté front (AOF94) — `surface_m2` est la valeur
   recalculée par le serveur à chaque écriture, affichée telle quelle.
   ========================================================================== */

// Le repli carte du DataTable bascule à 768 px (`dt-desktop`, VX180) : le mode
// MOBILE d'AOF190 vise la MÊME frontière, pour qu'un écran ne soit jamais
// « cartes mobiles + atelier bureau » à la fois.
const REQUETE_TELEPHONE = '(max-width: 767px)'

function Champ({ label, valeur }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium text-foreground">
        {valeur === null || valeur === undefined || valeur === '' ? '—' : valeur}
      </dd>
    </div>
  )
}

// Surface : LECTURE du champ serveur (`surface_m2` est recalculée à chaque
// écriture côté `ToitureAOViewSet`), simple mise en forme FR — jamais un
// calcul de substitution depuis le contour.
function surfaceLisible(valeur) {
  const nombre = Number(valeur)
  if (valeur === null || valeur === undefined || Number.isNaN(nombre)) return null
  return `${nombre.toFixed(1).replace('.', ',')} m²`
}

function FicheToitures({ toitures, loading, error }) {
  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-5 w-1/2" />
        <Skeleton className="h-20 w-full" />
      </div>
    )
  }
  if (error) {
    return <p className="text-sm text-destructive">{error}</p>
  }
  if (!toitures.length) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucune toiture relevée pour cette affaire.
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-2">
      {toitures.map((t) => (
        <Card key={t.id} className="p-3">
          <p className="truncate text-sm font-semibold text-foreground">
            {t.designation || t.code_document || `Toiture #${t.id}`}
          </p>
          <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2">
            <Champ label="Forme" valeur={t.forme_display} />
            <Champ label="Surface" valeur={surfaceLisible(t.surface_m2)} />
            <Champ label="Niveau" valeur={t.niveau} />
            <Champ label="Couverture" valeur={t.type_couverture_display} />
          </dl>
        </Card>
      ))}
    </div>
  )
}

export default function ToituresPage() {
  const surTelephone = useIsMobile(REQUETE_TELEPHONE)
  const [affaireChoisie, setAffaireChoisie] = useState('')

  const { data: affaires } = useResource(
    () => aoApi.affaires.list(),
    undefined,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les affaires.',
    },
  )

  // Affaire courante DÉRIVÉE au rendu (jamais un état recopié dans un effet,
  // react-hooks/set-state-in-effect) : le choix explicite gagne, sinon la
  // première affaire chargée.
  const affaireCourante = affaireChoisie || affaires[0]?.id || ''

  const { data: toitures, loading, error } = useResource(
    (id) => aoApi.toitures.list(id ? { appel_offre: id } : undefined),
    affaireCourante || null,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les toitures.',
    },
  )

  // Capture RÉELLE : la photo part en pièce jointe du dossier (`records`).
  const rattacherPhoto = async (fichier) => {
    if (!affaireCourante) {
      toast.error("Choisissez d'abord une affaire : une photo se range dans un dossier.")
      return
    }
    try {
      await recordsApi.uploadAttachment('ao.appeloffre', affaireCourante, fichier)
      toast.success('Photo rattachée au dossier.')
    } catch {
      toast.error("Photo non enregistrée — réessayez une fois le réseau revenu.")
    }
  }

  const lecture = <FicheToitures toitures={toitures} loading={loading} error={error} />

  const selecteurAffaire = (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor="ao-toitures-affaire" className="text-xs text-muted-foreground">
        Affaire
      </label>
      <select
        id="ao-toitures-affaire"
        className="h-9 min-w-0 max-w-full rounded-md border border-input bg-card px-2 text-sm text-foreground focus-ring"
        value={String(affaireCourante)}
        onChange={(e) => setAffaireChoisie(e.target.value)}
      >
        {affaires.length === 0 && <option value="">Aucune affaire</option>}
        {affaires.map((a) => (
          <option key={a.id} value={a.id}>
            {a.reference_acheteur || a.reference || `#${a.id}`}
          </option>
        ))}
      </select>
    </div>
  )

  return (
    <div className="flex flex-col gap-3">
      <PageHeader
        title="Toitures & relevés"
        subtitle="Les toitures relevées de l'affaire — géométrie, surface et couverture."
        filters={selecteurAffaire}
      />

      {surTelephone ? (
        <ModeMobile toiture={lecture} onPhoto={rattacherPhoto} />
      ) : (
        <>
          {lecture}
          <EmptyState
            title="Atelier de traçage"
            description="Le traçage interactif (contour, obstacles, cotes) est livré par sa propre lane du Groupe AOF — cet écran en présente aujourd'hui la lecture."
          />
        </>
      )}
    </div>
  )
}
