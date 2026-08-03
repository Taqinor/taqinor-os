import { useCallback, useMemo, useState } from 'react'
import aoApi from '../../../api/aoApi'
import recordsApi from '../../../api/recordsApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import { Button, Card, EmptyState, Skeleton, toast } from '../../../ui'
import PageHeader from '../../../components/layout/PageHeader'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
import ModeMobile from '../studio/ModeMobile'
import NouvelleToitureWizard from './NouvelleToitureWizard'

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

/* ── RÉPARATION 03/08/2026 — « Nouvelle toiture » : le bouton qui manquait ──
   `NouvelleToitureWizard` (AOF78, « LE point de création unique ») dormait sur
   le disque, importé NULLE PART : on pouvait lire des toitures, jamais en
   créer une. Cet écran est le seul endroit d'où l'ouvrir.

   PIÈGE DE MODÈLE, VÉRIFIÉ DANS LE CODE SERVEUR (`apps/ao/models.py`,
   `apps/ao/serializers.py`) : **`ToitureAO` n'a AUCUNE clé étrangère vers
   l'appel d'offres.** Ses seuls parents sont `company` (forcée par le serveur)
   et `batiment` → `BatimentAO`, qui porte, lui, le `appel_offre`. Une toiture
   se rattache donc à un BÂTIMENT, jamais à une affaire — et `batiment` est
   OBLIGATOIRE (FK non nulle).

   Le wizard, lui, émet un objet d'ATELIER dont la plupart des champs
   n'existent pas au modèle (`editeur`, `portes`, `origine_lnglat`, `underlay`,
   `calibration`, `chaines`, `obstacles`, `zones`, `statut`) et dont `batiment`
   est un TEXTE LIBRE facultatif. On TRADUIT donc ici, et on n'envoie que ce
   que `ToitureAOSerializer` accepte réellement — DRF ignore en silence toute
   clé hors `fields`, c'est-à-dire qu'un envoi brut aurait eu l'air d'écrire
   des données qui n'existaient nulle part.

   Deux interdits, tenus par des tests : jamais `company` (le serveur la force,
   ARC — elle n'est même pas dans `fields`), jamais `surface_m2` (déclarée
   `read_only=True` et RECALCULÉE par `ToitureAOViewSet` à chaque écriture ;
   une surface envoyée serait ignorée aujourd'hui et fausse demain). */

// Champs du modèle acceptés à la création, dans l'ordre du sérialiseur.
// `contour_local_m` est vide à la création : la géométrie se saisit dans
// l'atelier, et un contour vide n'active pas le refus `polygone_est_simple`.
function payloadToiture(brouillon, batimentId) {
  return {
    batiment: batimentId,
    designation: (brouillon?.nom || '').trim(),
    contour_local_m: Array.isArray(brouillon?.sommets_m) ? brouillon.sommets_m : [],
    angle_nord_deg: brouillon?.azimut_deg ?? 0,
  }
}

const etiquetteBatiment = (b) => (b.designation ? `${b.code} — ${b.designation}` : b.code)

const normaliser = (v) => String(v ?? '').trim().toLowerCase()

/* Résolution du bâtiment saisi (texte libre) vers un bâtiment RÉEL de CETTE
   affaire. Toute issue autre qu'un bâtiment unique et certain est un REFUS
   MOTIVÉ : retomber sur « le premier » rattacherait la toiture au bâtiment
   d'un autre relevé — le défaut silencieux que toute cette journée répare. */
function resoudreBatiment(saisie, batiments) {
  const liste = batiments.map(etiquetteBatiment).join(', ')
  if (!batiments.length) {
    return {
      ok: false,
      motif: 'Cette affaire n’a aucun bâtiment. Une toiture se rattache à un '
        + 'bâtiment (le modèle n’a aucun lien direct vers l’affaire) : créez '
        + 'le bâtiment d’abord. Rien n’a été créé.',
    }
  }
  const cherche = normaliser(saisie)
  if (!cherche) {
    if (batiments.length === 1) return { ok: true, batiment: batiments[0] }
    return {
      ok: false,
      motif: `Précisez le bâtiment : cette affaire en compte ${batiments.length} `
        + `(${liste}). Une toiture se rattache à un bâtiment, jamais à `
        + 'l’affaire. Rien n’a été créé.',
    }
  }
  const candidats = batiments.filter((b) => [
    b.id, b.code, b.designation, etiquetteBatiment(b),
  ].some((v) => v != null && v !== '' && normaliser(v) === cherche))
  if (candidats.length === 1) return { ok: true, batiment: candidats[0] }
  if (candidats.length === 0) {
    return {
      ok: false,
      motif: `Bâtiment « ${String(saisie).trim()} » inconnu de cette affaire — `
        + `bâtiments de l’affaire : ${liste}. Rien n’a été créé.`,
    }
  }
  return {
    ok: false,
    motif: `Bâtiment « ${String(saisie).trim()} » ambigu : ${candidats.length} `
      + 'bâtiments de cette affaire portent ce nom. Rien n’a été créé.',
  }
}

const errMsg = (e, repli) => {
  const donnees = e?.response?.data
  if (typeof donnees === 'string') return donnees
  if (donnees?.detail) return donnees.detail
  if (donnees && typeof donnees === 'object') {
    const [champ, valeur] = Object.entries(donnees)[0] || []
    if (champ) return `${champ} : ${[].concat(valeur).join(' ')}`
  }
  return repli
}

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

export default function ToituresPage({ affaireId } = {}) {
  const surTelephone = useIsMobile(REQUETE_TELEPHONE)
  const [affaireChoisie, setAffaireChoisie] = useState('')

  // Encastrement dans un onglet de fiche affaire (AffaireDetail — hors
  // périmètre de ce fichier, câblé par une autre lane) : `affaireId` FOURNI
  // impose CETTE affaire, sans jamais lister les autres ni retomber sur une
  // autre — un repli silencieux afficherait les toitures d'une AUTRE affaire
  // sous le titre de celle-ci. `affaireId` ABSENT : comportement de la page
  // pleine largeur `/ao/toitures` strictement inchangé (sélecteur + repli sur
  // la première affaire chargée).
  const encastre = affaireId !== undefined && affaireId !== null && affaireId !== ''

  const { data: affaires } = useResource(
    () => aoApi.affaires.list(),
    undefined,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les affaires.',
      // Encastré : l'affaire est déjà choisie par la fiche — lister TOUTES
      // les affaires de la société ne nourrirait qu'un sélecteur qui ne se
      // rend pas, pour le prix d'une requête réseau inutile.
      enabled: !encastre,
    },
  )

  // Affaire courante DÉRIVÉE au rendu (jamais un état recopié dans un effet,
  // react-hooks/set-state-in-effect) : encastré → `affaireId` imposé SANS
  // repli ; sinon le choix explicite gagne, sinon la première affaire chargée.
  const affaireCourante = encastre
    ? affaireId
    : (affaireChoisie || affaires[0]?.id || '')

  const { data: toitures, loading, error, refetch: rechargerToitures } = useResource(
    (id) => aoApi.toitures.list(id ? { appel_offre: id } : undefined),
    affaireCourante || null,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les toitures.',
    },
  )

  /* Les bâtiments de l'affaire : ce sont EUX qui portent la toiture (cf.
     l'en-tête). On les charge pour pouvoir résoudre la saisie du wizard, et
     pour NOMMER l'empêchement quand il n'y en a aucun. */
  const { data: batiments, loading: batimentsEnCours, error: batimentsErreur } = useResource(
    (id) => aoApi.batiments.list({ appel_offre: id }),
    affaireCourante || null,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les bâtiments de cette affaire.',
      enabled: Boolean(affaireCourante),
    },
  )

  const [wizardOuvert, setWizardOuvert] = useState(false)
  const [refus, setRefus] = useState(null)

  /* Un bouton n'est JAMAIS grisé sans explication : quand la création est
     impossible, la raison est écrite à côté (et portée par `title`). */
  const empechement = useMemo(() => {
    if (!affaireCourante) {
      return 'Choisissez d’abord une affaire : une toiture se rattache à un bâtiment de l’affaire.'
    }
    if (batimentsEnCours) return 'Chargement des bâtiments de l’affaire…'
    if (batimentsErreur) return batimentsErreur
    if (!batiments.length) {
      return 'Cette affaire n’a aucun bâtiment : une toiture se rattache à un bâtiment, '
        + 'jamais directement à l’affaire.'
    }
    return null
  }, [affaireCourante, batimentsEnCours, batimentsErreur, batiments])

  const creerToiture = useCallback(async (brouillon) => {
    const resolution = resoudreBatiment(brouillon?.batiment, batiments)
    if (!resolution.ok) {
      setRefus(resolution.motif)
      toast.error(resolution.motif)
      return
    }
    try {
      await aoApi.toitures.create(payloadToiture(brouillon, resolution.batiment.id))
      setRefus(null)
      toast.success(`Toiture créée sur le bâtiment ${etiquetteBatiment(resolution.batiment)}.`)
      rechargerToitures()
    } catch (e) {
      const motif = errMsg(e, 'Toiture non créée — le serveur a refusé la demande.')
      setRefus(motif)
      toast.error(motif)
    }
  }, [batiments, rechargerToitures])

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

  // Encastré dans une fiche : l'affaire est DÉJÀ choisie par l'onglet — un
  // sélecteur qui proposerait d'en changer serait le piège que l'encastrement
  // doit précisément éviter (affaires MÉLANGÉES sous le titre d'une seule).
  const selecteurAffaire = encastre ? null : (
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

  const actionCreer = (
    <div className="flex flex-col items-start gap-1 sm:items-end">
      <Button
        size="sm"
        disabled={Boolean(empechement)}
        title={empechement || undefined}
        onClick={() => { setRefus(null); setWizardOuvert(true) }}
      >
        Nouvelle toiture
      </Button>
      {empechement && (
        <p className="max-w-xs text-xs text-muted-foreground sm:text-right">{empechement}</p>
      )}
    </div>
  )

  return (
    <div className="flex flex-col gap-3">
      <PageHeader
        title="Toitures & relevés"
        subtitle="Les toitures relevées de l'affaire — géométrie, surface et couverture."
        actions={actionCreer}
        filters={selecteurAffaire}
      />

      {/* Un refus reste LISIBLE après la fermeture du wizard : un toast qui
          s'efface laisserait l'utilisateur devant une liste inchangée sans
          savoir pourquoi rien n'a été créé. */}
      {refus && (
        <Card className="border-destructive/60 bg-destructive/5 p-3" role="alert">
          <p className="text-sm font-medium text-destructive">Toiture non créée — {refus}</p>
        </Card>
      )}

      {/* Monté à l'ouverture SEULEMENT : le wizard ne remet pas ses champs à
          zéro lui-même, un montage frais évite de rouvrir sur la saisie
          précédente. */}
      {wizardOuvert && (
        <NouvelleToitureWizard
          open
          onOpenChange={setWizardOuvert}
          onCreer={creerToiture}
        />
      )}

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
