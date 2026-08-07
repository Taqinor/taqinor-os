import { useCallback, useMemo, useRef, useState } from 'react'
import { Hand, MousePointer2 } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import recordsApi from '../../../api/recordsApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import { Button, Card, EmptyState, Skeleton, toast } from '../../../ui'
import PageHeader from '../../../components/layout/PageHeader'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
import ModeMobile from '../studio/ModeMobile'
import StudioShell from '../studio/StudioShell'
import CanvasSvg from '../studio/CanvasSvg'
import Selection from '../studio/Selection'
import BarreEtat from '../studio/BarreEtat'
import TableauGeometrie from '../studio/TableauGeometrie'
import useHistoire from '../studio/useHistoire'
import {
  bboxDePoints,
  ecranVersMonde,
  metresParPixel as metresParPixelDe,
} from '../studio/useViewport'
import { aire, perimetre as perimetreDe, azimutAretePrincipale } from '../studio/snap'
import ProvenanceBadge from '../components/ProvenanceBadge'
import { PROVENANCE_ORDER } from '../provenance'
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

   Au-dessus de 768 px, l'écran rend la même lecture PLUS l'atelier de traçage
   interactif (PACT166, plus bas dans ce fichier) : c'est le seul endroit d'où
   il s'ouvre. AUCUN contrôle mort n'est rendu à AUCUNE largeur — chaque
   commande de l'atelier agit vraiment, et ce que l'atelier n'enregistre pas
   encore est ÉCRIT à l'écran avant qu'on y saisisse quoi que ce soit.

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

/* ============================================================================
   PACT166 — L'ATELIER DE TRAÇAGE, ENFIN ASSEMBLÉ.
   ----------------------------------------------------------------------------
   Six composants d'atelier étaient livrés, testés… et importés par PERSONNE :
   `StudioShell` (AOF73, la coquille à slots), `CanvasSvg` (AOF74, la surface
   SVG en mètres), `Selection` (AOF76, la voie SOURIS), `TableauGeometrie`
   (AOF77, la voie CLAVIER — condition du plancher a11y), `BarreEtat` (AOF74)
   et `ProvenanceBadge` (AOF9). Cet écran les met ENSEMBLE, à la place de
   l'ancien `EmptyState` « Atelier de traçage » qui disait que le canvas
   existait ailleurs.

   UN SEUL historique pour les DEUX voies (`useHistoire`, AOF76) : « annuler »
   défait indifféremment un glissement de souris et une frappe de tableau —
   deux piles séparées produiraient un annuler qui ne défait pas ce que
   l'utilisateur vient de faire.

   PERSISTANCE, et ses LIMITES, dites franchement :
     · « Enregistrer » écrit `contour_local_m` via `aoApi.toitures.update` —
       le MÊME champ que le wizard de création, une liste de `[x, y]` en
       mètres dans le repère local (`apps/ao/models.py:619`). La surface est
       RECALCULÉE par le serveur à chaque écriture : elle n'est jamais
       envoyée, jamais devinée ici ;
     · les OBSTACLES saisis dans le tableau restent LOCAUX à l'atelier. Le
       serveur les modélise (`/ao/obstacles/`) avec son propre vocabulaire de
       provenance (`MESURE`/`PLAN`/`DEVINE`…), distinct des 4 niveaux d'écran
       de `provenance.js` : raccorder les deux est une tâche à part, et
       l'écran le DIT avant qu'on en saisisse un plutôt que de le laisser
       croire enregistré.
   ========================================================================== */

// Le modèle sert le contour en `[x, y]` (mètres, repère local, y↑ nord) ;
// l'atelier manipule des `{ x, y }` (contrat commun de `Selection` et de
// `TableauGeometrie`). La traduction vit ICI, aux deux bouts, jamais à moitié.
function contourVersPoints(contour) {
  if (!Array.isArray(contour)) return []
  return contour
    .map((p) => (Array.isArray(p)
      ? { x: Number(p[0]), y: Number(p[1]) }
      : { x: Number(p?.x), y: Number(p?.y) }))
    .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y))
}

// Millimètre : la précision d'un relevé de toiture. Au-delà, on n'écrirait que
// du bruit de virgule flottante dans un champ JSON.
const arrondiMm = (v) => Math.round(v * 1000) / 1000

function pointsVersContour(points) {
  return points.map((p) => [arrondiMm(p.x), arrondiMm(p.y)])
}

const nb = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0)

const nomToiture = (t) => t?.designation || t?.code_document || `Toiture #${t?.id}`

const OUTILS_ATELIER = [
  { id: 'selection', label: 'Sélectionner', icon: MousePointer2, raccourci: 's' },
  { id: 'panoramique', label: 'Main (panoramique)', icon: Hand, raccourci: 'h' },
]

/* Légende de provenance — le vocabulaire du tableau d'obstacles, rendu par le
   composant qui en est la SEULE source de vérité (`ProvenanceBadge`, AOF9),
   jamais recopié en pastilles locales. */
function LegendeProvenance() {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1" data-ao-legende-provenance="">
      {PROVENANCE_ORDER.map((niveau) => (
        <ProvenanceBadge key={niveau} level={niveau} />
      ))}
    </div>
  )
}

function AtelierToiture({ toiture, selecteur, onEnregistre }) {
  const toitureId = toiture?.id
  const contourServeur = toiture?.contour_local_m
  const contourInitial = useMemo(() => contourVersPoints(contourServeur), [contourServeur])

  // Monté avec `key={toiture.id}` : changer de toiture REMONTE l'atelier, donc
  // remet l'historique à zéro — jamais un `reinitialiser` dans un effet, qui
  // laisserait un rendu intermédiaire montrer le contour de l'autre toiture.
  const histoire = useHistoire({ points: contourInitial, obstacles: [] })
  const { appliquer, terminer, annuler, retablir } = histoire
  const { points, obstacles } = histoire.etat

  const svgRef = useRef(null)
  const [vue, setVue] = useState(null)
  const [curseur, setCurseur] = useState(null)
  const [selection, setSelection] = useState([])
  const [survol, setSurvol] = useState(null)
  const [outil, setOutil] = useState('selection')
  const [refus, setRefus] = useState(null)
  const [enregistrement, setEnregistrement] = useState(false)

  // `CanvasSvg` remonte sa vue par callback (jamais par un état recopié dans un
  // effet de CE composant) : la surface reste propriétaire de son viewport.
  const majVue = useCallback((viewport, taille) => setVue({ viewport, taille }), [])

  const mesure = Boolean(vue) && vue.taille.largeur > 0 && vue.taille.hauteur > 0
  const mpp = mesure ? metresParPixelDe(vue.viewport, vue.taille) : 0.05

  // Conversion écran → monde pour la voie souris : `Selection` reçoit l'event
  // brut et délègue, la matrice de vue restant la seule vérité de position.
  const versMonde = useCallback((e) => {
    const el = svgRef.current
    if (!el || !mesure) return { x: 0, y: 0 }
    const r = el.getBoundingClientRect()
    return ecranVersMonde(
      { x: e.clientX - r.left, y: e.clientY - r.top }, vue.viewport, vue.taille,
    )
  }, [mesure, vue])

  const zone = mesure
    ? {
      xMin: vue.viewport.x,
      yMin: vue.viewport.y,
      xMax: vue.viewport.x + vue.viewport.l,
      yMax: vue.viewport.y + vue.viewport.h,
    }
    : null

  const majPoints = useCallback((suivants, libelle, opts) => {
    setRefus(null)
    appliquer((prec) => ({ ...prec, points: suivants }), libelle, opts)
  }, [appliquer])

  const majObstacles = useCallback((suivants, libelle, opts) => {
    setRefus(null)
    appliquer((prec) => ({ ...prec, obstacles: suivants }), libelle, opts)
  }, [appliquer])

  const bbox = useMemo(() => bboxDePoints(points), [points])

  const modifie = useMemo(
    () => JSON.stringify(pointsVersContour(points))
      !== JSON.stringify(pointsVersContour(contourInitial)),
    [points, contourInitial],
  )

  const enregistrer = useCallback(async () => {
    if (!toitureId) return
    setEnregistrement(true)
    try {
      // JAMAIS `surface_m2` (read_only, recalculée par `ToitureAOViewSet`),
      // jamais `company` (forcée par le serveur) : seul le contour part.
      await aoApi.toitures.update(toitureId, { contour_local_m: pointsVersContour(points) })
      setRefus(null)
      toast.success('Contour enregistré — la surface est recalculée par le serveur.')
      onEnregistre?.()
    } catch (e) {
      const motif = errMsg(e, 'Contour non enregistré — le serveur a refusé l’écriture.')
      setRefus(motif)
      toast.error(motif)
    } finally {
      setEnregistrement(false)
    }
  }, [toitureId, points, onEnregistre])

  const ongletGeometrie = (
    <div className="flex flex-col gap-3">
      <LegendeProvenance />
      <p className="rounded-md border border-border bg-muted p-2 text-xs text-muted-foreground">
        « Enregistrer » écrit le CONTOUR de cette toiture. Les obstacles saisis
        ci-dessous restent locaux à l’atelier — le serveur les modélise avec un
        autre vocabulaire de provenance, et les y raccorder est une tâche à part :
        ils ne sont pas conservés en quittant l’écran.
      </p>
      <TableauGeometrie
        points={points}
        obstacles={obstacles}
        onGeometrie={majPoints}
        onObstacles={majObstacles}
        onRefus={setRefus}
        onRefusObstacle={setRefus}
        onTerminer={terminer}
      />
    </div>
  )

  return (
    <StudioShell
      titre={`Atelier de traçage — ${nomToiture(toiture)}`}
      sousTitre="Contour en mètres, repère local de la toiture (x vers l’est, y vers le nord)."
      outils={OUTILS_ATELIER}
      outilActif={outil}
      onOutilChange={setOutil}
      actions={selecteur}
      onAnnuler={annuler}
      onRetablir={retablir}
      peutAnnuler={histoire.peutAnnuler}
      peutRetablir={histoire.peutRetablir}
      onEnregistrer={enregistrer}
      enregistrementEnCours={enregistrement}
      verdict={refus
        ? <p role="alert" className="text-sm font-medium text-destructive">{refus}</p>
        : null}
      onglets={[{ id: 'geometrie', label: 'Géométrie', contenu: ongletGeometrie }]}
      inspecteurTitre="Géométrie"
      etat={(
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {/* Surface/périmètre/azimut du BROUILLON en cours, calculés par les
              helpers PURS partagés (`snap.js`) — un éditeur sans retour de
              mesure ne se pilote pas. Le chiffre qui ENGAGE reste celui du
              serveur : il le recalcule à l'enregistrement, et l'écran le dit. */}
          <BarreEtat
            viewport={vue?.viewport}
            taille={vue?.taille}
            curseur={curseur}
            surface={points.length >= 3 ? aire(points) : undefined}
            perimetre={points.length >= 2 ? perimetreDe(points) : undefined}
            azimut={azimutAretePrincipale(points) ?? undefined}
            calibration="sans_objet"
          />
          {modifie && (
            <span className="font-medium text-muted-foreground">
              Contour modifié — la surface définitive est recalculée par le
              serveur à l’enregistrement.
            </span>
          )}
        </div>
      )}
    >
      <CanvasSvg
        ref={svgRef}
        bbox={bbox}
        onCurseur={setCurseur}
        onViewportChange={majVue}
        ariaLabel="Atelier de traçage — contour de la toiture, en mètres"
      >
        {points.length >= 3 && (
          <polygon
            points={points.map((p) => `${p.x},${p.y}`).join(' ')}
            className="fill-primary/10 stroke-primary"
            strokeWidth={1.5}
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />
        )}
        {points.length === 2 && (
          <line
            x1={points[0].x}
            y1={points[0].y}
            x2={points[1].x}
            y2={points[1].y}
            className="stroke-primary"
            strokeWidth={1.5}
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />
        )}
        {obstacles.map((o) => (
          <rect
            key={o.id}
            x={Math.min(nb(o.rectX0M), nb(o.rectX1M))}
            y={Math.min(nb(o.rectY0M), nb(o.rectY1M))}
            width={Math.abs(nb(o.rectX1M) - nb(o.rectX0M))}
            height={Math.abs(nb(o.rectY1M) - nb(o.rectY0M))}
            className="fill-destructive/20 stroke-destructive"
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />
        ))}
        <Selection
          points={points}
          selection={selection}
          onSelectionChange={setSelection}
          survol={survol}
          onSurvol={setSurvol}
          versMonde={versMonde}
          metresParPixel={mpp}
          zone={zone}
          actif={outil === 'selection'}
          onGeometrie={majPoints}
          onTerminer={terminer}
          onRefus={setRefus}
        />
      </CanvasSvg>
    </StudioShell>
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

  /* Toiture ouverte dans l'atelier (PACT166) — DÉRIVÉE au rendu comme
     l'affaire : le choix explicite gagne, sinon la première toiture chargée.
     Une toiture disparue de la liste (rechargement) ne laisse jamais l'atelier
     sur un objet fantôme : `find` échoue, on retombe sur la première. */
  const [toitureChoisie, setToitureChoisie] = useState('')
  const toitureActive = useMemo(
    () => toitures.find((t) => String(t.id) === String(toitureChoisie)) || toitures[0] || null,
    [toitures, toitureChoisie],
  )

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

  /* Choix de la toiture ouverte dans l'atelier — rendu SEULEMENT quand il y a
     vraiment un choix : un sélecteur à une seule option est un contrôle mort. */
  const selecteurToiture = toitures.length > 1 ? (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor="ao-atelier-toiture" className="text-xs text-muted-foreground">
        Toiture
      </label>
      <select
        id="ao-atelier-toiture"
        className="h-9 min-w-0 max-w-full rounded-md border border-input bg-card px-2 text-sm text-foreground focus-ring"
        value={String(toitureActive?.id ?? '')}
        onChange={(e) => setToitureChoisie(e.target.value)}
      >
        {toitures.map((t) => (
          <option key={t.id} value={t.id}>{nomToiture(t)}</option>
        ))}
      </select>
    </div>
  ) : null

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
          {toitureActive ? (
            /* Hauteur EXPLICITE : `StudioShell` est une coquille `h-full` (canvas
               élastique) — dans un flux ordinaire elle s'écraserait à zéro. */
            <div className="h-[70vh] min-h-[30rem]">
              <AtelierToiture
                key={toitureActive.id}
                toiture={toitureActive}
                selecteur={selecteurToiture}
                onEnregistre={rechargerToitures}
              />
            </div>
          ) : (
            <EmptyState
              title="Atelier de traçage"
              description="Relevez une première toiture : l’atelier de traçage (contour, sélection, tableau de géométrie) s’ouvre sur la toiture choisie."
            />
          )}
        </>
      )}
    </div>
  )
}
