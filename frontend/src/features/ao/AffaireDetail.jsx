import { lazy, Suspense, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
// `ClipboardList`/`MessagesSquare` ne sont plus importés : les panneaux réels
// du Bordereau et des Questions terrain portent leur propre iconographie.
import { Building2, LayoutGrid, FolderKanban } from 'lucide-react'
import aoApi from '../../api/aoApi'
import recordsApi from '../../api/recordsApi'
import useResource from '../../hooks/useResource'
import { unwrapList } from '../../api/resource'
import { Button, Card, Textarea, EmptyState, Skeleton, toast } from '../../ui'
import { RecordShell } from '../../ui/module'
import ChatterTimeline from '../../components/ChatterTimeline'
import { formatDate, formatMAD } from '../../lib/format'
import { StatutAffaire } from './statusAo'

/* ============================================================================
   AOF171 — Fiche affaire (`RecordShell`) + chatter.
   ----------------------------------------------------------------------------
   Chatter via `ChatterTimeline` sur la cible `ao.appeloffre` (`records`,
   AUCUNE timeline maison) : notes = `recordsApi.getComments`/`createComment`,
   pièces jointes récentes = `recordsApi.getAttachments` — injectées dans le
   MÊME fil (ChatterTimeline les fusionne déjà). Rendu à la fois dans le
   panneau latéral (`activity`, grand écran) ET dans l'onglet « Historique »
   (accès en ligne sur tout viewport — DetailShell ne montre le panneau
   qu'à partir de `lg:`).

   **Onglet Rentabilité ABSENT — DÉLIBÉRÉMENT.** La route séparée
   `/ao/:id/rentabilite` (AOF161, lane `frontend/ao-directeur`) porte son
   propre écran ; ce composant ne la référence NULLE PART (aucun lien, aucun
   onglet) — masquer un onglet ne protège rien si les données voyagent dans
   le payload de la fiche (en-tête du groupe), donc la fiche n'a même pas le
   VOCABULAIRE « rentabilité » dans son arbre. Aucun panneau branché ci-dessous
   n'importe `aoRentabiliteApi` (export SÉPARÉ d'`aoApi`, jamais mélangé).

   Bandeau de verdict/échéance/complétude/issue : champs AGRÉGÉS lus tels
   quels depuis `affaire` (aucun calcul de KPI côté front) — noms de champs
   anticipés (`verdict_global*`, `prochaine_echeance_*`, `dossier_completude`,
   `resultat_issue_display`), pas encore posés par le serializer legacy ODX11
   (`apps/ao/serializers.py`) — livrés par la lane `backend/ao`. Rendu
   défensif (« — » si absent).

   ── RÉPARATION 03/08/2026 — les 5 onglets morts sont BRANCHÉS ─────────────
   Cinq des sept onglets rendaient un `TabPlaceholder` muet (« écran dédié en
   construction ») alors que les VRAIS panneaux existaient sur le disque, dans
   ce même dossier, importés NULLE PART : 61 écrans du module étaient
   inatteignables depuis la fiche. Chaque onglet monte désormais son panneau
   réel, en CHARGEMENT DIFFÉRÉ (`lazy` + `Suspense`, même patron que
   `module.config.jsx`) — la fiche ne tire pas l'atelier de calepinage, le
   bordereau et le dossier au premier rendu ; Radix démonte le panneau inactif,
   donc l'`import()` d'un onglet ne part qu'à son ouverture.

   La règle qui gouverne les cas bancals : **un panneau qui ne peut pas être
   monté honnêtement affiche un état vide qui DIT POURQUOI** — jamais un
   placeholder muet, jamais une page blanche, et jamais un panneau qui aurait
   l'air juste en montrant les données d'une AUTRE affaire.
   ========================================================================== */

/* ── Panneaux réels, chargés à l'ouverture de leur onglet ──────────────────
   `SeriesPage` est un export NOMMÉ (`export function SeriesPage`) : on le
   remappe en `default` pour `lazy`, au lieu de compter sur le `export default`
   d'appoint du même fichier. */
const ToituresPage = lazy(() => import('./toiture/ToituresPage'))
const CalepinageStudio = lazy(() => import('./calepinage/CalepinageStudio'))
const BordereauPage = lazy(() => import('./bordereau/BordereauPage'))
const DossierPage = lazy(() => import('./dossier/DossierPage'))
const SeriesPage = lazy(() => import('./questions/SeriesPage')
  .then((m) => ({ default: m.SeriesPage })))

/* ── SECONDE VAGUE, 03/08/2026 — les 3 derniers écrans que RIEN n'atteignait ─
   `AdministratifPage`, `EquipementsPage` et `ExigencesPage` existent, sont
   testés, et n'étaient importés nulle part : aucune route du menu, aucun
   onglet. Ils rejoignent les 7 onglets EXISTANTS sans en changer l'ordre ni le
   contenu. Même patron que ci-dessus : `lazy` + `PanneauDiffere`.

   Ces trois panneaux sont sûrs vis-à-vis de l'en-tête du groupe : aucun
   n'importe l'économie du dossier (`EquipementsPage` dit lui-même « AUCUN
   COÛT » : ni prix d'achat, ni marge, ni coût de revient — ni à l'écran, ni
   dans le corps d'une requête). */
const AdministratifPage = lazy(() => import('./administratif/AdministratifPage'))
const EquipementsPage = lazy(() => import('./equipements/EquipementsPage'))
const ExigencesPage = lazy(() => import('./cps/ExigencesPage'))

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const VERDICT_TONE = { confirme: 'success', tendu: 'warning' }

/* Le bordereau des prix EXISTE côté serveur (`bordereaux-prix`, AOF120), mais
   `api/aoApi.js` ne publie AUCUNE ressource bordereau — et ce client a un seul
   propriétaire (lane `frontend/ao-socle`), retouché nulle part ailleurs. On
   monte donc le VRAI `BordereauPage` avec son motif d'indisponibilité plutôt
   que d'inventer ici un chemin réseau : un `axios` direct dans `features/ao/`
   est interdit (ARC44), et une URL devinée produirait le 404 anonyme que
   `endpointNonConstruit` a précisément été écrit pour supprimer. Le jour où
   `aoApi.bordereaux` existe, ce panneau se branche en trois lignes. */
const MOTIF_BORDEREAU = "Le client API du module (api/aoApi.js) ne publie pas encore de "
  + "ressource bordereau : la route serveur « bordereaux-prix » existe, mais aucun appel "
  + "n'est déclaré côté front. Rien n'est deviné ici — le panneau reste vide tant que la "
  + 'ressource n’est pas publiée.'

function VerdictBandeau({ affaire }) {
  const verdictTone = VERDICT_TONE[affaire.verdict_global] ?? 'neutral'
  return (
    <Card className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-4">
      <Info label="Verdict global du site" value={affaire.verdict_global_label} tone={verdictTone} />
      <Info
        label="Échéance la plus proche"
        value={affaire.prochaine_echeance_libelle}
        meta={affaire.prochaine_echeance_date ? formatDate(affaire.prochaine_echeance_date) : null}
      />
      <Info
        label="Complétude du dossier"
        value={affaire.dossier_completude != null ? `${Math.round(affaire.dossier_completude)} %` : null}
      />
      <Info label="Issue (ouverture des plis)" value={affaire.resultat_issue_display} />
    </Card>
  )
}

function Info({ label, value, meta, tone }) {
  const toneClass = tone === 'success' ? 'text-success' : tone === 'warning' ? 'text-warning' : 'text-foreground'
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={`font-display text-base font-semibold ${toneClass}`}>{value || '—'}</dd>
      {meta && <p className="text-xs text-muted-foreground">{meta}</p>}
    </div>
  )
}

/* Frontière de chargement d'un panneau : repli SQUELETTE (jamais un spinner
   nu, jamais une page blanche) — même contrat que les routes du routeur. */
function PanneauDiffere({ children }) {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" data-ao-panneau-differe />}>
      {children}
    </Suspense>
  )
}

/* Sélecteur d'enfant d'affaire (calepinage, dossier) : un panneau qui prend
   l'id d'un SOUS-DOCUMENT ne peut pas se contenter de l'id de l'affaire. */
function SelecteurEnfant({ id, label, valeur, onChange, options }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor={id} className="text-xs text-muted-foreground">{label}</label>
      <select
        id={id}
        className="h-9 min-w-0 max-w-full rounded-md border border-input bg-card px-2 text-sm text-foreground focus-ring"
        value={String(valeur ?? '')}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}

/* ── Onglet « Toitures & relevés » ────────────────────────────────────────
   HISTORIQUE (03/08/2026) : cet onglet a d'abord affiché un état vide, parce
   que `ToituresPage` ne prenait AUCUNE propriété — il listait toutes les
   affaires de la société et retombait sur la PREMIÈRE. L'encastrer tel quel
   aurait montré, sous le titre de CETTE affaire, les toitures d'une AUTRE :
   un écran faux a l'air juste, ce qui est pire qu'un onglet vide.
   L'empêchement a été LEVÉ À LA SOURCE (`ToituresPage` accepte désormais
   `affaireId` : affaire imposée, aucun appel à la liste des affaires, aucun
   sélecteur rendu). On monte donc le vrai panneau. Ne PAS revenir à un
   `ToituresPage` sans `affaireId` ici — ce serait rouvrir la fuite d'affaire.*/
function OngletToitures({ affaireId }) {
  return (
    <PanneauDiffere>
      <ToituresPage affaireId={affaireId} />
    </PanneauDiffere>
  )
}

/* ── Onglet « Calepinages » ───────────────────────────────────────────────
   CONTRAT CORRIGÉ AU FOLD, 03/08/2026 — à ne pas re-casser. Cet onglet a
   d'abord listé les VARIANTES et passé une variante en `calepinageId`. Le même
   jour, l'atelier a été rebranché sur les VRAIES routes du serveur
   (`/ao/calepinage/calculer|lancer|resultat`) et pilote désormais une
   TOITURE : sa signature est `({ toitureId })`. Les deux moitiés ont été
   écrites en parallèle et ne se sont pas parlé — exactement le défaut que la
   journée entière a servi à corriger. L'atelier aurait reçu `undefined`.

   On liste donc les TOITURES de l'affaire (`aoApi.toitures`, filtre serveur
   `appel_offre`, le même que l'onglet Toitures) et on passe l'id de la toiture
   choisie. `aoApi.calepinages` (au pluriel) reste NON CONSTRUIT et n'est pas
   consulté : aucun modèle `Calepinage` n'existe côté serveur.

   `onConformite` n'est pas passé : il sert à BLOQUER la publication d'un
   dossier, et aucune porte de publication ne vit dans cette fiche — y brancher
   un consommateur décoratif serait la façade qu'on répare. */
function OngletCalepinages({ affaireId }) {
  const params = useMemo(() => ({ appel_offre: affaireId }), [affaireId])
  const [choisie, setChoisie] = useState(null)

  const { data: toitures, loading, error } = useResource(
    () => aoApi.toitures.list(params), params,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les toitures de cette affaire.',
    },
  )

  if (loading) return <Skeleton className="h-64 w-full" />
  if (error) {
    return <EmptyState icon={LayoutGrid} tone="error" title="Calepinages indisponibles" description={error} />
  }
  if (!toitures.length) {
    return (
      <EmptyState
        icon={LayoutGrid}
        title="Aucune toiture à calepiner"
        description={'Le calepinage se calcule SUR une toiture : relevez-en une dans l’onglet '
          + '« Toitures & relevés », et l’atelier s’ouvrira ici.'}
      />
    )
  }

  // Choix explicite prioritaire, sinon la première toiture — dérivé AU RENDU
  // (jamais un état recopié dans un effet).
  const courante = choisie ?? toitures[0].id

  return (
    <div className="flex flex-col gap-3">
      <SelecteurEnfant
        id="ao-affaire-toiture-calepinage"
        label="Toiture"
        valeur={courante}
        onChange={setChoisie}
        options={toitures.map((t) => ({ value: t.id, label: t.nom || t.libelle || `Toiture #${t.id}` }))}
      />
      <PanneauDiffere>
        <CalepinageStudio toitureId={courante} />
      </PanneauDiffere>
    </div>
  )
}

/* ── Onglet « Dossier » ───────────────────────────────────────────────────
   PIÈGE FERMÉ ICI : `DossierPage` retombe sur `useParams().id` quand aucun
   `dossierId` ne lui est passé. Dans cette fiche, ce paramètre de route est
   l'id de l'AFFAIRE — le laisser faire appellerait `dossiers-ao/<id d'affaire>/`,
   c'est-à-dire un dossier au hasard (ou un 404) présenté comme celui de cette
   affaire. On lui passe donc TOUJOURS un `dossierId` explicite, résolu depuis
   la liste des dossiers de l'affaire (`?appel_offre=`), et on ne le monte pas
   du tout tant qu'il n'y en a aucun. */
function OngletDossier({ affaireId }) {
  const params = useMemo(() => ({ appel_offre: affaireId }), [affaireId])
  const [choisi, setChoisi] = useState(null)

  const { data: dossiers, loading, error } = useResource(
    () => aoApi.dossiers.list(params), params,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les dossiers de soumission de cette affaire.',
    },
  )

  if (loading) return <Skeleton className="h-64 w-full" />
  if (error) {
    return <EmptyState icon={FolderKanban} tone="error" title="Dossiers indisponibles" description={error} />
  }
  if (!dossiers.length) {
    return (
      <EmptyState
        icon={FolderKanban}
        title="Aucun dossier de soumission"
        description={'Cette affaire n’a pas encore de dossier de dépôt : rien à afficher tant '
          + 'qu’un dossier n’a pas été créé pour elle.'}
      />
    )
  }

  const courant = choisi ?? dossiers[0].id

  return (
    <div className="flex flex-col gap-3">
      {dossiers.length > 1 && (
        <SelecteurEnfant
          id="ao-affaire-dossier"
          label="Dossier"
          valeur={courant}
          onChange={setChoisi}
          options={dossiers.map((d) => ({ value: d.id, label: d.reference || `Dossier #${d.id}` }))}
        />
      )}
      <PanneauDiffere>
        <DossierPage dossierId={courant} />
      </PanneauDiffere>
    </div>
  )
}

export default function AffaireDetail() {
  const { id } = useParams()
  const [note, setNote] = useState('')
  const [sending, setSending] = useState(false)

  // `select` OBLIGATOIRE : `useResource` passe la valeur résolue TELLE QUELLE
  // (cf. son contrat — « pour un axios brut, passez `select: (res) => res.data` »).
  // Sans lui, `affaire` valait la réponse axios entière et TOUS les champs de
  // la fiche étaient lus un cran trop haut : titre « #undefined », objet,
  // statut et bandeau vides. Même convention que `DashboardPage.jsx`.
  const { data: affaire, loading, error } = useResource(
    () => aoApi.affaires.get(id), id,
    { select: (res) => res.data, errorMessage: 'Affaire introuvable.' },
  )
  const { data: comments, refetch: refetchComments } = useResource(
    () => recordsApi.getComments('ao.appeloffre', id), id,
    { initialData: [], select: unwrapList, errorMessage: () => '' },
  )
  const { data: attachments } = useResource(
    () => recordsApi.getAttachments('ao.appeloffre', id), id,
    { initialData: [], select: unwrapList, errorMessage: () => '' },
  )

  const chatterEntries = (comments || []).map((c) => ({
    id: c.id,
    kind: 'note',
    body: c.body,
    user_nom: c.author_display || c.author_username,
    created_at: c.created_at,
  }))

  const ajouterNote = async () => {
    const body = note.trim()
    if (!body) return
    setSending(true)
    try {
      await recordsApi.createComment('ao.appeloffre', id, body)
      setNote('')
      refetchComments()
    } catch (e) {
      toast.error(errMsg(e, 'Note non enregistrée.'))
    } finally {
      setSending(false)
    }
  }

  const chatterPanel = (
    <Card className="p-4">
      <h3 className="mb-3 font-display text-base font-semibold">Chatter</h3>
      <div className="mb-4 flex flex-col gap-2">
        <Textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Ajouter une note…"
          rows={2}
          aria-label="Nouvelle note"
        />
        <Button size="sm" className="self-end" disabled={sending || !note.trim()} onClick={ajouterNote}>
          {sending ? 'Envoi…' : 'Noter'}
        </Button>
      </div>
      <ChatterTimeline entries={chatterEntries} attachments={attachments} />
    </Card>
  )

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (error || !affaire) {
    return (
      <EmptyState
        title="Affaire introuvable"
        description={error || "Cette affaire n'existe pas ou n'est pas accessible."}
      />
    )
  }

  return (
    <RecordShell
      title={affaire.reference || `#${affaire.id}`}
      subtitle={affaire.objet}
      status={affaire.statut}
      statusPill={StatutAffaire}
      backTo="/ao/affaires"
      backLabel="Retour aux affaires"
      activity={chatterPanel}
      tabs={[
        {
          value: 'synthese',
          label: 'Synthèse',
          content: (
            <div className="flex flex-col gap-4">
              <VerdictBandeau affaire={affaire} />
              <Card className="p-4">
                <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
                  <Info label="Acheteur" value={affaire.acheteur} />
                  <Info label="Type de marché" value={affaire.type_marche_display || affaire.type_marche} />
                  <Info label="Lot" value={affaire.lot} />
                  <Info
                    label="Date limite de remise des plis"
                    value={affaire.date_limite ? formatDate(affaire.date_limite) : null}
                  />
                  <Info
                    label="Montant estimé"
                    value={affaire.montant_estime != null ? formatMAD(affaire.montant_estime) : null}
                  />
                  <Info
                    label="Caution provisoire"
                    value={affaire.caution_provisoire != null ? formatMAD(affaire.caution_provisoire) : null}
                  />
                </dl>
              </Card>
            </div>
          ),
        },
        {
          value: 'toitures',
          label: 'Toitures & relevés',
          content: <OngletToitures affaireId={id} />,
        },
        {
          value: 'calepinages',
          label: 'Calepinages',
          content: <OngletCalepinages affaireId={id} />,
        },
        {
          value: 'bordereau',
          label: 'Bordereau',
          content: (
            <PanneauDiffere>
              <BordereauPage bordereau={null} error={MOTIF_BORDEREAU} />
            </PanneauDiffere>
          ),
        },
        {
          value: 'dossier',
          label: 'Dossier',
          content: <OngletDossier affaireId={id} />,
        },
        {
          value: 'questions_terrain',
          label: 'Questions terrain',
          content: (
            <PanneauDiffere>
              <SeriesPage affaireId={id} />
            </PanneauDiffere>
          ),
        },
        {
          value: 'historique',
          label: 'Historique',
          content: <ChatterTimeline entries={chatterEntries} attachments={attachments} />,
        },
        /* ── Les 3 onglets ajoutés le 03/08/2026, APRÈS les 7 ci-dessus ──── */
        {
          value: 'administratif',
          label: 'Administratif',
          /* `affaireId` passé EXPLICITEMENT. `AdministratifPage` retombe sur
             `useParams().id` quand on ne lui passe rien : ici ce paramètre
             SE TROUVE être l'id de l'affaire, donc le repli marcherait — par
             coïncidence de nommage, pas par contrat. Une fiche montée sous une
             autre route (ou un onglet imbriqué) le casserait en silence. */
          content: (
            <PanneauDiffere>
              <AdministratifPage affaireId={id} />
            </PanneauDiffere>
          ),
        },
        {
          value: 'equipements',
          label: 'Équipements',
          /* Signature déclarée : `({ affaireId })` — aucun repli `useParams`.
             Le panneau filtre `?appel_offre=` (le champ réel du modèle
             `EquipementAO`, honoré par `EquipementAOViewSet.get_queryset`). */
          content: (
            <PanneauDiffere>
              <EquipementsPage affaireId={id} />
            </PanneauDiffere>
          ),
        },
        {
          value: 'cps',
          label: 'CPS & exigences',
          /* BUG BLOQUANT CORRIGÉ AVANT DE MONTER CET ONGLET (voir
             `cps/ExigencesPage.jsx`) : l'écran listait ses clauses avec
             `?affaire=`, un paramètre que `ExigenceCPSViewSet` n'honore PAS et
             ignore sans rien dire — il aurait affiché les clauses de TOUTES les
             affaires de la société sous le titre de celle-ci. Le filtre est
             désormais `?appel_offre=`, vérifié dans `apps/ao/views.py`. */
          content: (
            <PanneauDiffere>
              <ExigencesPage affaireId={id} />
            </PanneauDiffere>
          ),
        },
      ]}
    />
  )
}
