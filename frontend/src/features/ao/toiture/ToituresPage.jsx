import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
// Extensions EXPLICITES : `Calibration.jsx` (le composant) et `calibration.js`
// (les maths pures) ne different que par la CASSE. Linux les distingue, mais
// Windows et macOS non — un specifier nu resolvait vers le mauvais module et
// cassait `vite build` hors CI. Ne jamais reduire ces deux imports.
import Calibration from './Calibration.jsx'
import UnderlayImage from './UnderlayImage'
import OutilTrace from './OutilTrace'
import OutilsObstacles from './OutilsObstacles'
import ObstaclesList from './ObstaclesList'
import OutilsZones from './OutilsZones'
import ChainesCotes from './ChainesCotes'
import FermeturesPanel from './FermeturesPanel'
import PointsALever from './PointsALever'
import EnveloppeArc from './EnveloppeArc'
import EnveloppeL from './EnveloppeL'
import ImportDxf from './ImportDxf'
// PACT76 — plans sources RÉELLEMENT persistés (`PlanSource`, AOF20) : le
// calage ci-dessus reste un état React local, perdu au rechargement ; cet
// onglet est le premier consommateur de la ressource serveur.
import PlanSourcePanel from './PlanSourcePanel'
import { estCalibree, peutTracer, reechelonner } from './calibration.js'
import { estPdf } from './rasteriserPdf'

/* Deux outils sont chargés À LA DEMANDE, et pour une raison PRÉCISE — pas par
   goût du découpage :
     · `UnderlayPdf` instancie un worker pdf.js AU CHARGEMENT DU MODULE
       (`new PdfWorker()` en tête de fichier) : un import statique ferait donc
       fabriquer un worker à tout écran qui monte cette page, y compris sous
       jsdom (qui n'a pas `Worker`) ;
     · `RepriseCarte` tire le builder de toiture du site public via l'alias
       `@roofpro` — résolu par `vite.config.js`, ABSENT de `vitest.config.js`.
   Chargés en `lazy()`, ils n'entrent dans le graphe que si l'utilisateur ouvre
   vraiment l'outil. `check_ecrans_atteignables.py` compte l'import dynamique
   comme un import (`_SPEC_DYNAMIQUE`) : ils restent donc bien ATTEIGNABLES. */
const UnderlayPdf = lazy(() => import('./UnderlayPdf'))
const RepriseCarte = lazy(() => import('./RepriseCarte'))

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

   PERSISTANCE (PV53) :
     · « Enregistrer » écrit `contour_local_m` via `aoApi.toitures.update` —
       le MÊME champ que le wizard de création, une liste de `[x, y]` en
       mètres dans le repère local (`apps/ao/models.py:619`). La surface est
       RECALCULÉE par le serveur à chaque écriture : elle n'est jamais
       envoyée, jamais devinée ici ;
     · les OBSTACLES et les CHAÎNES DE COTES de la boîte à outils (PACT167)
       partent EUX AUSSI, dans la MÊME action « Enregistrer » : diff
       create/update/delete vs le dernier instantané serveur connu
       (`synchroniserRessource`). À l'OUVERTURE de l'atelier (ce composant est
       remonté avec `key={toiture.id}`), les deux listes sont RE-CHARGÉES
       depuis le serveur — fermer/rouvrir conserve donc tout ;
     · les ZONES restent LOCALES à l'atelier (PV56, pas encore construit) —
       l'écran l'ANNONCE avant qu'on en saisisse une, plutôt que de la laisser
       croire enregistrée.
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

/* ── PACT167 — UN SEUL obstacle, DEUX écritures ────────────────────────────
   La boîte à outils a deux voies vers le même obstacle : le TABLEAU (AOF77)
   l'écrit en rectangle (`rectX0M…rectY1M`), la PLANCHE (AOF88) en polygone
   (`sommets`). `gardePublication.surfaceObstacle` (AOF90) lit `sommets` en
   priorité : laisser les deux écritures diverger ferait compter une surface
   d'emprise qui ne correspond plus à ce qu'on voit. On les tient donc
   SYNCHRONES à la frontière, dans le sens de la voie qui vient d'écrire. */
function obstacleDepuisRect(o) {
  const x0 = Math.min(nb(o.rectX0M), nb(o.rectX1M))
  const x1 = Math.max(nb(o.rectX0M), nb(o.rectX1M))
  const y0 = Math.min(nb(o.rectY0M), nb(o.rectY1M))
  const y1 = Math.max(nb(o.rectY0M), nb(o.rectY1M))
  return {
    ...o,
    sommets: [{ x: x0, y: y0 }, { x: x1, y: y0 }, { x: x1, y: y1 }, { x: x0, y: y1 }],
  }
}

function obstacleDepuisSommets(o) {
  const b = bboxDePoints(o?.sommets ?? [])
  if (!b) return o
  return { ...o, rectX0M: b.xMin, rectX1M: b.xMax, rectY0M: b.yMin, rectY1M: b.yMax }
}

const sommetsSvg = (sommets) => (sommets ?? []).map((p) => `${nb(p.x)},${nb(p.y)}`).join(' ')

/* ── PV53 — diff LOCAL vs SERVEUR : create/update/delete en une écriture ────
   L'atelier ne persistait QUE le contour ; obstacles et chaînes de cotes
   restaient locaux (l'écran l'annonçait). Les deux voies d'écriture RÉELLES
   (`apps/ao/serializers.py` `ObstacleAOSerializer`/`ChaineCotesSerializer`)
   parlent un vocabulaire DIFFÉRENT de celui de l'atelier (nature/provenance
   en MAJUSCULES côté serveur, minuscules côté outils locaux — deux tableaux
   qui ne se recouvrent pas terme à terme) : chaque correspondance EXACTE est
   prise, et ce qui n'a pas d'équivalent retombe sur le DÉFAUT DU MODÈLE
   lui-même — jamais une valeur inventée pour l'occasion. */

// Vocabulaire LOCAL (`repereLettre.js` NATURES_OBSTACLE) → `ObstacleAO.Nature`.
const NATURE_OBSTACLE_VERS_SERVEUR = {
  edicule: 'edicule',
  cage_escalier: 'cage_escalier',
  cheminee: 'souche',
  lanterneau: 'lanterneau',
  exutoire: 'exutoire_fumee',
  climatisation: 'groupe_clim',
  acrotere: 'acrotere',
  joint_dilatation: 'joint_dilatation',
  muret: 'muret',
  // Sans équivalent serveur — repli sur le défaut du modèle (`caisson_technique`).
  gaine: 'caisson_technique',
  antenne: 'caisson_technique',
  trappe: 'caisson_technique',
  reservation: 'caisson_technique',
}
const NATURE_OBSTACLE_DEPUIS_SERVEUR = {
  edicule: 'edicule',
  cage_escalier: 'cage_escalier',
  souche: 'cheminee',
  lanterneau: 'lanterneau',
  exutoire_fumee: 'exutoire',
  groupe_clim: 'climatisation',
  acrotere: 'acrotere',
  joint_dilatation: 'joint_dilatation',
  muret: 'muret',
  // Natures serveur sans équivalent local (13 clés côté outil, 13 AUTRES
  // clés côté modèle) — meilleure correspondance visuelle disponible.
  caisson_technique: 'gaine',
  decrochement_niveau: 'edicule',
  pan_coupe: 'edicule',
  chemin_cables: 'gaine',
}

// Vocabulaire LOCAL (`ObstacleInspecteur.jsx` PROVENANCES) → `ObstacleAO.Provenance`.
const PROVENANCE_OBSTACLE_VERS_SERVEUR = {
  mesure: 'MESURE',
  confirmer: 'MESURE_DOUTEUX',
  deduit: 'PLAN',
  devine: 'DEVINE',
}
const PROVENANCE_OBSTACLE_DEPUIS_SERVEUR = {
  MESURE: 'mesure',
  MESURE_DOUTEUX: 'confirmer',
  PLAN: 'deduit',
  DEVINE: 'devine',
  // Sans équivalent local — la donnée n'est de toute façon pas MESURÉE.
  DECLARE_CLIENT: 'deduit',
  ECARTE: 'deduit',
}

// Vocabulaire LOCAL (`ChainesCotes.jsx` PROVENANCES des segments) → `StatutCote`.
const STATUT_COTE_VERS_SERVEUR = {
  mesure: 'MESURE',
  confirmer: 'A_CONFIRMER',
  deduit: 'PLAN_OU_DEDUIT',
  devine: 'A_CONFIRMER', // deviné = incertain, comme « à confirmer »
}
const STATUT_COTE_DEPUIS_SERVEUR = {
  MESURE: 'mesure',
  A_CONFIRMER: 'confirmer',
  PLAN_OU_DEDUIT: 'deduit',
}

function nombreOuNull(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(String(v).replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

// Un id local NUMÉRIQUE (posé par une hydratation ou un enregistrement
// précédent) désigne un enregistrement DÉJÀ connu du serveur ; un id
// non-numérique (`obs-A-169…`, `chaine-3`) vient d'être saisi dans CETTE
// session et n'existe encore nulle part côté serveur.
function estIdServeur(id) {
  return typeof id === 'number' || (typeof id === 'string' && /^\d+$/.test(id))
}

function sommetsDepuisRectServeur(x0, x1, y0, y1) {
  if ([x0, x1, y0, y1].some((v) => v === null || v === undefined)) return []
  return [
    { x: nb(x0), y: nb(y0) }, { x: nb(x1), y: nb(y0) },
    { x: nb(x1), y: nb(y1) }, { x: nb(x0), y: nb(y1) },
  ]
}

function obstacleDepuisServeur(record) {
  const sommets = Array.isArray(record.polygone_local_m) && record.polygone_local_m.length >= 3
    ? record.polygone_local_m.map(([x, y]) => ({ x: nb(x), y: nb(y) }))
    : sommetsDepuisRectServeur(
      record.rect_x0_m, record.rect_x1_m, record.rect_y0_m, record.rect_y1_m,
    )
  return {
    id: record.id,
    repere: record.repere || '',
    nature: NATURE_OBSTACLE_DEPUIS_SERVEUR[record.nature] ?? 'edicule',
    provenance: PROVENANCE_OBSTACLE_DEPUIS_SERVEUR[record.provenance] ?? 'mesure',
    sommets,
    rectX0M: record.rect_x0_m, rectX1M: record.rect_x1_m,
    rectY0M: record.rect_y0_m, rectY1M: record.rect_y1_m,
    epaisseurM: null,
    verrouille: false,
    // Champs que l'outil local ne modélise PAS (hauteur, décision, hors-zone
    // PV…) : gardés tels quels pour être ÉCHOÉS intacts au prochain
    // enregistrement — jamais silencieusement effacés par cet écran.
    _serveur: record,
  }
}

// DRF ignore silencieusement les clés en lecture seule ou inconnues d'un
// ModelSerializer (`id`, `*_display`, `engageable`…) : échoer le dernier
// enregistrement serveur PUIS écraser le sous-ensemble ÉDITABLE localement ne
// peut donc jamais réécrire un champ que l'atelier ne montre pas.
function obstacleVersPayload(o, toitureId) {
  const sommets = o.sommets ?? []
  const bbox = bboxDePoints(sommets)
  return {
    ...(o._serveur ?? {}),
    toiture: toitureId,
    repere: o.repere ?? '',
    nature: NATURE_OBSTACLE_VERS_SERVEUR[o.nature] ?? 'caisson_technique',
    provenance: PROVENANCE_OBSTACLE_VERS_SERVEUR[o.provenance] ?? 'MESURE',
    polygone_local_m: sommets.map((s) => [nb(s.x), nb(s.y)]),
    rect_x0_m: bbox ? bbox.xMin : null,
    rect_x1_m: bbox ? bbox.xMax : null,
    rect_y0_m: bbox ? bbox.yMin : null,
    rect_y1_m: bbox ? bbox.yMax : null,
  }
}

function chaineDepuisServeur(record) {
  return {
    id: record.id,
    axe: record.axe ?? 'x',
    nom: record.libelle || `Chaîne ${record.id}`,
    origine: { x: 0, y: 0 }, // repère d'affichage LOCAL — pas une donnée serveur
    tolerance: record.tolerance_m !== null && record.tolerance_m !== undefined
      ? Number(record.tolerance_m) : 0.05,
    coteMesuree: record.mesure_globale_m !== null && record.mesure_globale_m !== undefined
      ? Number(record.mesure_globale_m) : 0,
    segments: (record.segments ?? []).map((s, i) => ({
      id: `seg-srv-${record.id}-${i}`,
      libelle: s.libelle ?? `S${i + 1}`,
      valeur: Number(s.valeur_m ?? 0),
      provenance: STATUT_COTE_DEPUIS_SERVEUR[s.statut] ?? 'mesure',
    })),
    _serveur: record,
  }
}

function chaineVersPayload(c, toitureId) {
  return {
    ...(c._serveur ?? {}),
    toiture: toitureId,
    libelle: c.nom ?? '',
    axe: c.axe ?? 'x',
    mesure_globale_m: nombreOuNull(c.coteMesuree),
    tolerance_m: nombreOuNull(c.tolerance) ?? 0.05,
    segments: (c.segments ?? []).map((s) => ({
      libelle: s.libelle ?? '',
      valeur_m: nombreOuNull(s.valeur) ?? 0,
      statut: STATUT_COTE_VERS_SERVEUR[s.provenance] ?? 'MESURE',
    })),
  }
}

function erreurNommee(nom, etiquette, e, verbe) {
  const err = new Error(
    `${nom} ${etiquette || ''} non ${verbe} — ${errMsg(e, 'le serveur a refusé l’écriture.')}`
      .replace(/\s+—/, ' —').trim(),
  )
  err.aoMotifPret = true
  return err
}

/* Diff 3 voies (create/update/delete) d'UNE ressource fille de la toiture, vs
   le dernier instantané serveur connu. Un ÉCHEC N'IMPORTE OÙ arrête TOUT (pas
   de suite silencieuse) : le motif nomme la ressource ET l'élément — un
   « Enregistrer » qui échoue à moitié doit se VOIR, jamais se deviner. */
async function synchroniserRessource({ ressource, nomRessource, locaux, distants, versPayload }) {
  const idsLocaux = new Set(
    locaux.filter((l) => estIdServeur(l.id)).map((l) => Number(l.id)),
  )
  for (const distant of distants) {
    if (idsLocaux.has(distant.id)) continue
    try {
      // eslint-disable-next-line no-await-in-loop
      await ressource.remove(distant.id)
    } catch (e) {
      throw erreurNommee(
        nomRessource, distant.repere || distant.libelle || distant.id, e, 'supprimé')
    }
  }
  const resultats = []
  for (const local of locaux) {
    const payload = versPayload(local)
    if (estIdServeur(local.id)) {
      try {
        // eslint-disable-next-line no-await-in-loop
        const { data } = await ressource.update(Number(local.id), payload)
        resultats.push({ ...local, _serveur: data })
      } catch (e) {
        throw erreurNommee(nomRessource, local.repere || local.nom || local.id, e, 'enregistré')
      }
    } else {
      try {
        // eslint-disable-next-line no-await-in-loop
        const { data } = await ressource.create(payload)
        resultats.push({ ...local, id: data.id, _serveur: data })
      } catch (e) {
        throw erreurNommee(nomRessource, local.repere || local.nom || local.id, e, 'créé')
      }
    }
  }
  return resultats
}

/* Export d'un CSV produit par un helper PUR (`exporterPointsALever`) : le
   fichier part du navigateur, aucun aller-retour serveur — donc aucune
   promesse d'enregistrement qui n'aurait pas lieu. */
function telechargerCsv(nomFichier, contenu) {
  if (typeof document === 'undefined' || typeof URL.createObjectURL !== 'function') return
  const url = URL.createObjectURL(new Blob([contenu], { type: 'text/csv;charset=utf-8' }))
  const lien = document.createElement('a')
  lien.href = url
  lien.download = nomFichier
  lien.click()
  URL.revokeObjectURL(url)
}

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
  // remet l'historique à zéro — jamais un `reinitialiser` dans un effet QUI
  // REMPLACE LE CONTOUR, ce qui laisserait un rendu intermédiaire montrer le
  // contour de l'autre toiture. `reinitialiser` sert seulement plus bas à
  // (a) hydrater les obstacles depuis le serveur SANS toucher aux points, et
  // (b) faire des ids locaux les ids serveur après un enregistrement réussi.
  const histoire = useHistoire({ points: contourInitial, obstacles: [] })
  const { appliquer, terminer, annuler, retablir, reinitialiser } = histoire
  const { points, obstacles } = histoire.etat

  // PV53 — dernier instantané SERVEUR connu de chaque ressource fille, pour le
  // diff create/update/delete de « Enregistrer » (une `useRef` : ces valeurs
  // ne pilotent aucun rendu, elles ne servent qu'à la PROCHAINE écriture).
  const distantsObstaclesRef = useRef([])
  const distantsChainesRef = useRef([])
  // Un utilisateur qui a DÉJÀ commencé à éditer (points, obstacles, chaînes…)
  // avant que l'hydratation réseau ne réponde ne doit JAMAIS se faire écraser
  // par elle : l'hydratation s'efface silencieusement dans ce cas, plutôt que
  // de faire disparaître ce que l'utilisateur vient de saisir.
  const interactionRef = useRef(false)

  const svgRef = useRef(null)
  const [vue, setVue] = useState(null)
  const [curseur, setCurseur] = useState(null)
  const [selection, setSelection] = useState([])
  const [survol, setSurvol] = useState(null)
  const [outil, setOutil] = useState('selection')
  const [refus, setRefus] = useState(null)
  const [enregistrement, setEnregistrement] = useState(false)

  /* ── PACT167 — état de la BOÎTE À OUTILS ────────────────────────────────
     Onglet contrôlé : les deux écrans d'import (DXF, carte) proposent « tracer
     à la main » — sans onglet contrôlé, ce bouton n'aurait nulle part où
     emmener l'utilisateur, c.-à-d. un bouton mort de plus. */
  const [onglet, setOnglet] = useState('geometrie')
  const [plan, setPlan] = useState(null) // fichier du fond de calque
  const [calibration, setCalibration] = useState(null)
  const [chaines, setChaines] = useState([])
  const [zones, setZones] = useState([])
  const [enveloppeArc, setEnveloppeArc] = useState(null)
  const [survolObstacle, setSurvolObstacle] = useState(null)
  const [questionProposee, setQuestionProposee] = useState(null)
  // Ce que l'atelier REFUSE de faire, avec son motif — jamais un bouton qui ne
  // fait rien sans le dire.
  const [note, setNote] = useState(null)

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

  // PV53 — hydrate l'atelier depuis le serveur À L'OUVERTURE. L'atelier est
  // remonté avec `key={toiture.id}` : CE mount EST « ouvrir cette toiture »,
  // donc changer de toiture ou y revenir relance cette hydratation — c'est ce
  // qui fait tenir « fermer/rouvrir conserve tout ».
  useEffect(() => {
    let annule = false
    if (!toitureId) return undefined
    ;(async () => {
      try {
        const [obsRes, chaRes] = await Promise.all([
          aoApi.obstacles.list({ toiture: toitureId }),
          aoApi.chaines.list({ toiture: toitureId }),
        ])
        if (annule || interactionRef.current) return
        const obstaclesDistants = unwrapList(obsRes)
        const chainesDistantes = unwrapList(chaRes)
        distantsObstaclesRef.current = obstaclesDistants
        distantsChainesRef.current = chainesDistantes
        reinitialiser(
          {
            points: histoire.etat.points,
            obstacles: obstaclesDistants.map(obstacleDepuisServeur),
          },
          'Chargé depuis le serveur',
        )
        setChaines(chainesDistantes.map(chaineDepuisServeur))
      } catch (e) {
        if (annule) return
        setNote(errMsg(
          e,
          'Obstacles et chaînes de cotes non chargés depuis le serveur — l’atelier '
          + 'reste utilisable, mais « Enregistrer » partirait d’une liste locale '
          + 'incomplète tant que la page n’est pas rechargée.',
        ))
      }
    })()
    return () => { annule = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- une seule hydratation par mount (= par toiture ouverte)
  }, [toitureId])

  const majPoints = useCallback((suivants, libelle, opts) => {
    interactionRef.current = true
    setRefus(null)
    appliquer((prec) => ({ ...prec, points: suivants }), libelle, opts)
  }, [appliquer])

  // Voie TABLEAU (clavier) : le rectangle vient d'être écrit → il fait foi.
  const majObstacles = useCallback((suivants, libelle, opts) => {
    interactionRef.current = true
    setRefus(null)
    appliquer(
      (prec) => ({ ...prec, obstacles: suivants.map(obstacleDepuisRect) }), libelle, opts,
    )
  }, [appliquer])

  // Voie PLANCHE (souris) : les sommets viennent d'être posés → ils font foi.
  const majObstaclesPlanche = useCallback((suivants) => {
    interactionRef.current = true
    setRefus(null)
    appliquer(
      (prec) => ({ ...prec, obstacles: suivants.map(obstacleDepuisSommets) }),
      'Modifier les obstacles',
    )
  }, [appliquer])

  const majChaines = useCallback((suivantes) => {
    interactionRef.current = true
    setChaines(suivantes)
  }, [])

  const bbox = useMemo(() => bboxDePoints(points), [points])

  // Les cotes de TOUTES les chaînes : c'est sur elles que `deduction.js`
  // calcule les points à lever (cote déduite ou écart au-delà du seuil).
  const cotes = useMemo(
    () => chaines.flatMap((c) => (c.segments ?? []).map((s) => ({ ...s }))),
    [chaines],
  )

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

      // PV53 — UNE SEULE écriture cohérente : le contour ET la différence
      // d'obstacles/chaînes de cotes. Un échec ICI (après un contour déjà
      // écrit) est nommé PRÉCISÉMENT par `synchroniserRessource` — jamais un
      // succès affiché alors qu'une partie n'est pas passée.
      const resultatsObstacles = await synchroniserRessource({
        ressource: aoApi.obstacles, nomRessource: 'Obstacle',
        locaux: obstacles, distants: distantsObstaclesRef.current,
        versPayload: (o) => obstacleVersPayload(o, toitureId),
      })
      const resultatsChaines = await synchroniserRessource({
        ressource: aoApi.chaines, nomRessource: 'Chaîne de cotes',
        locaux: chaines, distants: distantsChainesRef.current,
        versPayload: (c) => chaineVersPayload(c, toitureId),
      })

      // Les ids locaux DEVIENNENT les ids serveur : un second « Enregistrer »
      // dans la même session diffère juste, il ne recrée rien en double.
      distantsObstaclesRef.current = resultatsObstacles.map((r) => r._serveur)
      distantsChainesRef.current = resultatsChaines.map((r) => r._serveur)
      reinitialiser({ points, obstacles: resultatsObstacles }, 'Enregistré')
      setChaines(resultatsChaines)

      setRefus(null)
      toast.success('Enregistré — contour, obstacles et chaînes de cotes.')
      onEnregistre?.()
    } catch (e) {
      // `synchroniserRessource` fabrique un motif déjà prêt en français
      // (`aoMotifPret`) ; une réponse axios brute passe par `errMsg` comme
      // avant, pour le refus du CONTOUR lui-même.
      const motif = e?.aoMotifPret
        ? e.message
        : errMsg(e, 'Contour non enregistré — le serveur a refusé l’écriture.')
      setRefus(motif)
      toast.error(motif)
    } finally {
      setEnregistrement(false)
    }
  }, [toitureId, points, obstacles, chaines, onEnregistre, reinitialiser])

  const ongletGeometrie = (
    <div className="flex flex-col gap-3">
      <LegendeProvenance />
      <p className="rounded-md border border-border bg-muted p-2 text-xs text-muted-foreground">
        « Enregistrer » écrit le CONTOUR de cette toiture, les obstacles et les
        chaînes de cotes de la boîte à outils, en une seule écriture (PV53).
        Les zones restent LOCALES à l’atelier — les y raccorder au serveur est
        une tâche à part.
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

  /* ── PACT167 — LA BOÎTE À OUTILS ─────────────────────────────────────────
     Seize outils de relevé étaient livrés et importés par personne. Ils sont
     ici, chacun branché sur l'état RÉEL de l'atelier — jamais rendus « pour la
     forme ». Radix démonte l'onglet inactif : chaque outil non contrôlé
     (planche d'obstacles, chaînes) est donc RE-SEMÉ depuis l'état de l'atelier
     à chaque ouverture de son onglet, ce qui interdit la dérive silencieuse
     entre sa copie interne et la vérité de l'atelier. */

  const appliquerReechelonnage = (ancienne, nouvelle) => {
    majPoints(reechelonner(points, ancienne, nouvelle), 'Ré-échelonner le tracé')
    terminer()
  }

  const ongletCalage = (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        Un fond de calque (photo, scan ou PDF du plan) se cale à l’échelle par
        deux points de distance connue. Sans fond de calque, le relevé se saisit
        directement en mètres et l’échelle reste « Tracé direct ».
      </p>
      <div className="flex flex-col gap-1">
        <label htmlFor="ao-atelier-plan" className="text-xs text-muted-foreground">
          Plan à caler (image ou PDF)
        </label>
        <input
          id="ao-atelier-plan"
          type="file"
          accept="image/*,application/pdf"
          className="text-sm"
          onChange={(e) => setPlan(e.target.files?.[0] ?? null)}
        />
      </div>
      {plan && estPdf(plan) ? (
        <Suspense fallback={<Skeleton className="h-24 w-full" />}>
          <UnderlayPdf fichier={plan} onErreur={setRefus} />
        </Suspense>
      ) : (
        <UnderlayImage fichier={plan} onFichier={setPlan} />
      )}
      <Calibration
        calibration={calibration}
        onCalibration={setCalibration}
        onReechelonner={appliquerReechelonnage}
        aUnTrace={points.length > 0}
      />
    </div>
  )

  const ongletTrace = (
    <div className="flex flex-col gap-4">
      {/* Porte n°2 : le relevé se SAISIT (longueur + direction), il ne se
          dessine pas au pixel. Ce que l'outil publie devient le contour de
          l'atelier — donc ce qui partira à l'enregistrement. */}
      <OutilTrace
        actif={!plan || peutTracer(calibration)}
        onChange={({ sommets_m: sommets }) => {
          majPoints(sommets, 'Tracer le contour')
          terminer()
        }}
      />
      <EnveloppeL
        onValider={({ sommets }) => {
          majPoints(sommets, 'Enveloppe en L')
          terminer()
        }}
      />
      <EnveloppeArc
        onValider={(enveloppe) => {
          setEnveloppeArc(enveloppe)
          setNote(
            'Enveloppe en arc retenue pour le calepinage. Elle décrit un DÉVELOPPÉ '
            + '(segments et murets), pas un contour fermé : « Enregistrer » n’écrit '
            + 'que le contour, cette enveloppe reste donc locale à l’atelier.',
          )
        }}
      />
      {enveloppeArc && (
        <p className="text-xs text-muted-foreground" data-ao-enveloppe-arc-retenue="">
          Enveloppe en arc retenue : {(enveloppeArc.segments ?? []).length} segment(s),
          {' '}
          {(enveloppeArc.murets ?? []).length} muret(s).
        </p>
      )}
    </div>
  )

  const ongletObstacles = (
    <div className="flex flex-col gap-4">
      <OutilsObstacles
        obstaclesInitiaux={obstacles}
        metresParPixel={mpp}
        onChange={majObstaclesPlanche}
      />
      <ObstaclesList
        obstacles={obstacles}
        survolId={survolObstacle}
        onSurvol={setSurvolObstacle}
        onSelection={setSurvolObstacle}
        onPoserQuestion={(question) => setQuestionProposee(question)}
        onPretAPublier={() => setNote(
          'Refus : le modèle de toiture ne porte AUCUN état « prête à publier » '
          + '(aucun champ de ce nom au serveur). Rien n’a été enregistré — la garde '
          + 'ci-dessus reste le verdict à lire avant de s’engager.',
        )}
      />
      {questionProposee && (
        <div
          className="rounded-md border border-border bg-muted p-2 text-xs"
          data-ao-question-proposee=""
        >
          <p className="font-medium text-foreground">{questionProposee.objet}</p>
          <p className="mt-1 whitespace-pre-line text-muted-foreground">
            {questionProposee.corps}
          </p>
          <p className="mt-1 text-muted-foreground">
            Question PRÉ-REMPLIE, pas encore envoyée : elle se crée dans l’onglet
            « Questions terrain » de la fiche affaire.
          </p>
        </div>
      )}
    </div>
  )

  const ongletZones = (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        Zones interdites, réservées ou préférées du relevé. Le serveur ne
        modélise PAS encore de ressource « zones » (le moteur de calepinage en
        reçoit une liste vide) : elles restent locales à l’atelier.
      </p>
      <OutilsZones
        zonesInitiales={zones}
        metresParPixel={mpp}
        onChange={setZones}
      />
    </div>
  )

  const ongletCotes = (
    <div className="flex flex-col gap-4">
      <ChainesCotes
        chainesInitiales={chaines}
        pixelsParMetre={mpp > 0 ? 1 / mpp : 1}
        onChange={majChaines}
      />
      <FermeturesPanel
        chaines={chaines}
        onChaines={majChaines}
        onCalepiner={() => setNote(
          'Chaînes arbitrées. Le calepinage se lance depuis l’onglet « Calepinages » '
          + 'de la fiche affaire (le calcul est sans état, piloté par la toiture) : '
          + 'rien n’a été lancé depuis ici.',
        )}
      />
      <PointsALever
        cotes={cotes}
        onExport={(csv) => telechargerCsv(
          `points-a-lever-${toitureId ?? 'toiture'}.csv`, csv,
        )}
      />
    </div>
  )

  const ongletImport = (
    <div className="flex flex-col gap-4">
      {/* Aucun `analyserDxf` n'est passé : il n'existe AUCUN endpoint serveur
          d'analyse de plan (vérifié). L'écran rend alors son propre état
          dégradé, qui NOMME l'empêchement et propose le tracé à la main —
          c'est exactement ce pour quoi il a été écrit. */}
      <ImportDxf
        onImporter={({ sommets }) => {
          majPoints(
            (sommets ?? []).map(([x, y]) => ({ x: Number(x), y: Number(y) })),
            'Importer le contour DXF',
          )
          terminer()
          setOnglet('geometrie')
        }}
        onTracerAlaMain={() => setOnglet('trace')}
      />
      <Suspense fallback={<Skeleton className="h-24 w-full" />}>
        <RepriseCarte
          onContour={() => setNote(
            'Contour repris de la carte, mais NON appliqué : il est en latitude / '
            + 'longitude, et le modèle de toiture ne stocke qu’un contour en mètres '
            + 'dans un repère local, sans point d’origine géographique. Convertir '
            + 'l’un en l’autre demande ce point d’origine — il n’existe pas encore.',
          )}
          onTracerAlaMain={() => setOnglet('trace')}
        />
      </Suspense>
    </div>
  )

  // PACT76 — onglet « Plans sources », APRÈS les 7 existants (ordre inchangé
  // pour les autres, un onglet nouveau s'ajoute en queue).
  const ongletPlans = <PlanSourcePanel toitureId={toitureId} />

  const onglets = [
    { id: 'geometrie', label: 'Géométrie', contenu: ongletGeometrie },
    { id: 'calage', label: 'Calage', contenu: ongletCalage },
    { id: 'trace', label: 'Tracé', contenu: ongletTrace },
    { id: 'obstacles', label: 'Obstacles', contenu: ongletObstacles },
    { id: 'zones', label: 'Zones', contenu: ongletZones },
    { id: 'cotes', label: 'Cotes', contenu: ongletCotes },
    { id: 'import', label: 'Import', contenu: ongletImport },
    { id: 'plans', label: 'Plans sources', contenu: ongletPlans },
  ]

  const etatCalibration = plan
    ? (estCalibree(calibration) ? 'calibre' : 'non_calibre')
    : 'sans_objet'

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
      verdict={(refus || note) ? (
        <div className="flex flex-col gap-1">
          {refus && (
            <p role="alert" className="text-sm font-medium text-destructive">{refus}</p>
          )}
          {/* Un refus MOTIVÉ n'est pas une erreur : c'est ce que l'atelier ne
              fait pas, et pourquoi. Il reste lisible, jamais un toast fugace. */}
          {note && (
            <p role="status" className="text-sm text-muted-foreground" data-ao-atelier-note="">
              {note}
            </p>
          )}
        </div>
      ) : null}
      onglets={onglets}
      ongletActif={onglet}
      onOngletChange={setOnglet}
      inspecteurTitre="Boîte à outils"
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
            calibration={etatCalibration}
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
        {/* Zones (AOF89) puis obstacles (AOF88) : les DEUX voies d'écriture
            tiennent `sommets` à jour, le canvas n'a donc qu'une forme à lire. */}
        {zones.map((z) => (
          <polygon
            key={z.id}
            points={sommetsSvg(z.sommets)}
            className="fill-muted-foreground/10 stroke-muted-foreground"
            strokeWidth={1}
            strokeDasharray="4 3"
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />
        ))}
        {obstacles.map((o) => (
          <polygon
            key={o.id}
            points={sommetsSvg(o.sommets ?? obstacleDepuisRect(o).sommets)}
            className={`stroke-destructive ${
              survolObstacle === (o.id ?? o.repere) ? 'fill-destructive/40' : 'fill-destructive/20'
            }`}
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
