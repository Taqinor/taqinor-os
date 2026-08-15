// CH6 — Timeline de cycle de vie du chantier : remplace le simple sélecteur de
// statut par un parcours d'étapes/gates GUIDÉ (CH1/CH2), avec la recette de
// mise en service IEC 62446-1 (CH3) et le pack de remise client (CH4) mis en
// avant comme des gates de premier plan. Field/mobile-friendly : une seule
// colonne, gros boutons, raisons de blocage explicites en français.
// APX26 — la fiche chantier n'a plus DEUX timelines empilées : les jalons datés
// (ex-`ChantierTimeline`, rendu dans une section « Timeline » à part) sont
// fusionnés DANS ce stepper, sous une progression « 3/7 » en tête, et le
// bandeau « Prochaine action » passe sur `ui/NextActionBanner` (partagé avec
// « Ma journée »).
import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, Lock, ClipboardCheck, PackageCheck } from 'lucide-react'
import installationsApi from '../../api/installationsApi'
import {
  Button, Badge, HelpTip, Spinner, Progress, NextActionBanner,
} from '../../ui'
import ChantierTimeline from './ChantierTimeline'
// WIR202/CH3 — formulaire de saisie de la fiche de recette IEC 62446-1.
import RecetteCommissioningDialog from './RecetteCommissioningDialog'

function StageIcon({ satisfait, courante, bloquant }) {
  if (satisfait && !courante) {
    return <CheckCircle2 className="size-5 text-success" aria-hidden="true" />
  }
  if (!satisfait && bloquant) {
    return <Lock className="size-5 text-destructive" aria-hidden="true" />
  }
  return (
    <Circle
      className={`size-5 ${courante ? 'text-info' : 'text-muted-foreground'}`}
      aria-hidden="true"
    />
  )
}

// Une étape — carte compacte avec son état de gate + raisons de blocage.
function StageRow({ etape, isLast }) {
  const { libelle, courante, satisfait, bloquant, raisons, statut_legacy: statutLegacy } = etape
  return (
    <li
      data-testid="ch6-stage"
      data-cle={etape.cle}
      data-courante={courante ? 'true' : 'false'}
      className={`relative flex gap-3 pb-4 ${isLast ? '' : 'border-l border-border ml-2.5 pl-4'}`}
    >
      <span className="absolute -left-[10.5px] top-0 flex size-5 items-center justify-center rounded-full bg-background">
        <StageIcon satisfait={satisfait} courante={courante} bloquant={bloquant} />
      </span>
      <div className="flex flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`text-sm font-semibold ${courante ? 'text-info' : 'text-foreground'}`}>
            {libelle}
          </span>
          {courante && <Badge tone="info">Étape en cours</Badge>}
          {bloquant && <Badge tone="outline">Gate bloquant</Badge>}
          {!bloquant && <Badge tone="neutral">Consultative</Badge>}
          {statutLegacy && (
            <span className="text-[11px] text-muted-foreground">({statutLegacy})</span>
          )}
        </div>
        {!satisfait && raisons?.length > 0 && (
          <ul className="flex flex-col gap-0.5 text-xs text-destructive">
            {raisons.map((r) => <li key={r}>• {r}</li>)}
          </ul>
        )}
      </div>
    </li>
  )
}

// APX26 — bande des jalons datés : rendue UNIQUEMENT quand l'appelant fournit
// le chantier (la fiche le fait). Les surfaces qui ne passent que
// `installationId` gardent le rendu d'origine, au pixel près.
function JalonsBand({ installation }) {
  if (!installation) return null
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-3" data-testid="ch6-jalons">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Jalons datés
      </span>
      <ChantierTimeline installation={installation} />
    </div>
  )
}

export default function ChantierGateTimeline({ installationId, installation, onAdvanced }) {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null) // { etape_courante, etapes: [] }
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [blockedReasons, setBlockedReasons] = useState(null)

  // CH3 — recette de mise en service (IEC 62446-1).
  const [recette, setRecette] = useState(null)
  const [recetteBusy, setRecetteBusy] = useState(false)
  // WIR202 — dialog de SAISIE de la fiche (la fiche se créait vide, sans
  // aucun formulaire pour la remplir).
  const [recetteFormOpen, setRecetteFormOpen] = useState(false)

  // CH4 — pack de remise client.
  const [pack, setPack] = useState(null)
  const [packBusy, setPackBusy] = useState(false)

  const load = () => {
    setLoading(true)
    installationsApi.getEtapesChantier(installationId)
      .then((r) => { setData(r.data); setError(null) })
      .catch(() => setError('Étapes indisponibles.'))
      .finally(() => setLoading(false))
    installationsApi.getRecette(installationId)
      .then((r) => setRecette(r.data)).catch(() => {})
    installationsApi.getPackRemise(installationId)
      .then((r) => setPack(r.data)).catch(() => {})
  }

  // Charge trois ressources indépendantes (étapes/recette/pack) au montage +
  // après chaque avancement, comme le fait déjà `checkDevisDivergence` plus
  // haut sur cette même page (même repli d'effet).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [installationId])

  const stages = data?.etapes ?? []
  const courante = stages.find((s) => s.courante)
  const idx = stages.findIndex((s) => s.courante)
  const suivante = idx >= 0 ? stages[idx + 1] : undefined

  const avancer = async (cle) => {
    setBusy(true)
    setBlockedReasons(null)
    try {
      await installationsApi.avancerEtape(installationId, cle)
      load()
      onAdvanced?.()
    } catch (err) {
      const raisons = err?.response?.data?.raisons
      if (Array.isArray(raisons) && raisons.length) {
        setBlockedReasons(raisons)
      } else {
        setBlockedReasons([
          err?.response?.data?.detail || 'Avancement impossible.',
        ])
      }
    } finally {
      setBusy(false)
    }
  }

  // WIR202 — le bouton créait une fiche VIDE et s'arrêtait là : elle restait
  // `en_cours` pour toujours et le gate « Mise en service » ne se franchissait
  // jamais. Il ouvre désormais le FORMULAIRE de saisie (en créant la fiche
  // d'abord si elle n'existe pas encore).
  const ouvrirRecette = async () => {
    if (recette?.record?.id) { setRecetteFormOpen(true); return }
    setRecetteBusy(true)
    try {
      const r = await installationsApi.ouvrirRecette(installationId)
      setRecette(r.data)
      if (r.data?.record?.id) setRecetteFormOpen(true)
    } catch { /* 403 si non Responsable/Admin — bouton reste visible, l'action échoue proprement */ }
    finally { setRecetteBusy(false) }
  }

  const genererPack = async () => {
    setPackBusy(true)
    try {
      const r = await installationsApi.genererPackRemise(installationId)
      setPack(r.data)
    } catch { /* 403 si non Responsable/Admin */ }
    finally { setPackBusy(false) }
  }

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement du parcours…
      </p>
    )
  }

  if (error) {
    return <p className="text-sm text-muted-foreground">{error}</p>
  }

  // Dégradation propre : société sans étapes configurées (comportement
  // historique) — aucun parcours à afficher, le statut reste le seul pilote.
  if (stages.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground">
          Aucune étape de cycle de vie configurée pour cette société
          (Paramètres → Chantiers). Le statut classique reste utilisé.
        </p>
        {/* APX26 — même sans parcours configuré, les jalons datés restent
            visibles : la fusion ne supprime aucun contenu. */}
        <JalonsBand installation={installation} />
      </div>
    )
  }

  // APX26 — progression du parcours en tête : « Étape 2/3 » + barre. Le rang de
  // l'étape courante (1-indexé) ; sans étape courante, on compte les satisfaites.
  const rang = idx >= 0 ? idx + 1 : stages.filter((s) => s.satisfait).length
  const pct = Math.round((rang / stages.length) * 100)

  return (
    <div className="flex flex-col gap-4" data-testid="ch6-gate-timeline">
      {/* APX26 — la progression manquait ici alors que la checklist en avait
          une : le parcours ne disait pas « où on en est » d'un coup d'œil. */}
      <div className="flex items-center gap-3" data-testid="ch6-progress">
        <Progress
          value={pct}
          tone={rang === stages.length ? 'success' : 'primary'}
          className="flex-1"
          aria-label="Progression du parcours de chantier"
        />
        <span className="text-sm font-semibold tabular-nums text-muted-foreground">
          {rang}/{stages.length}
        </span>
      </div>
      {/* VX47 — aide contextuelle : la distinction bloquant/consultatif n'est
          pas évidente pour un nouvel employé (un cadenas rouge n'est pas
          auto-explicatif). Une seule pose pour toute la liste, pas de
          re-layout. */}
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span>Gates de chantier</span>
        <HelpTip label="Aide — gates de chantier">
          Un <strong>gate bloquant</strong> (cadenas) empêche de passer à
          l'étape suivante tant qu'il n'est pas satisfait — les raisons du
          blocage s'affichent en rouge sous l'étape. Un gate
          <strong> consultatif</strong> est informatif : il n'empêche pas
          d'avancer, il signale seulement un point à vérifier.
        </HelpTip>
      </div>
      <ol className="flex flex-col" data-testid="ch6-stage-list">
        {stages.map((s, i) => (
          <StageRow key={s.cle} etape={s} isLast={i === stages.length - 1} />
        ))}
      </ol>

      {/* ── Prochaine action explicite (APX26 — `ui/NextActionBanner` partagé
          avec « Ma journée » ; `data-testid` d'origine conservé) ── */}
      {suivante ? (
        <NextActionBanner
          data-testid="ch6-next-action"
          action={(
            <Button
              size="sm"
              className="self-start"
              loading={busy}
              onClick={() => avancer(suivante.cle)}
              data-testid="ch6-avancer-btn"
            >
              Avancer vers « {suivante.libelle} »
            </Button>
          )}
        >
          faire avancer le chantier vers « {suivante.libelle} ».
        </NextActionBanner>
      ) : (
        <div className="flex flex-col gap-2 rounded-lg border border-border p-3" data-testid="ch6-next-action">
          <p className="text-sm text-muted-foreground">
            {courante
              ? `Dernière étape déjà atteinte (${courante.libelle}).`
              : 'Aucune étape courante.'}
          </p>
        </div>
      )}
      {blockedReasons && (
        <div
          role="alert"
          className="flex flex-col gap-1 rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive"
          data-testid="ch6-blocked-reasons"
        >
          <strong>Étape bloquée par un gate&nbsp;:</strong>
          <ul className="flex flex-col gap-0.5">
            {blockedReasons.map((r) => <li key={r}>• {r}</li>)}
          </ul>
        </div>
      )}

      {/* APX26 — les jalons datés (ex-section « Timeline ») vivent maintenant
          dans CE stepper : une seule timeline dans la fiche. */}
      <JalonsBand installation={installation} />

      {/* ── CH3 — recette de mise en service (IEC 62446-1), gate mis en avant ── */}
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-3" data-testid="ch6-recette">
        <ClipboardCheck className="size-4 text-muted-foreground" aria-hidden="true" />
        <span className="text-sm font-semibold">Recette de mise en service (IEC 62446-1)</span>
        {recette?.record ? (
          <Badge tone={recette.record.passe ? 'success' : 'outline'}>
            {recette.record.resultat_display ?? recette.record.resultat}
          </Badge>
        ) : (
          <Badge tone="neutral">Aucune fiche</Badge>
        )}
        {/* WIR202 — l'affordance existe MAINTENANT aussi quand la fiche est
            déjà ouverte : c'est la seule façon de la remplir (et donc de
            franchir le gate). */}
        <Button size="sm" variant="outline" className="ml-auto" loading={recetteBusy} onClick={ouvrirRecette}>
          {recette?.record ? 'Remplir la fiche de recette' : 'Ouvrir la fiche de recette'}
        </Button>
      </div>

      {recetteFormOpen && recette?.record?.id && (
        <RecetteCommissioningDialog
          recordId={recette.record.id}
          onClose={() => setRecetteFormOpen(false)}
          // La fiche enregistrée peut franchir le gate : on recharge étapes +
          // recette + pack, exactement comme après un avancement.
          onSaved={() => { load(); onAdvanced?.() }}
        />
      )}

      {/* ── CH4 — pack de remise client, gate mis en avant ── */}
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-3" data-testid="ch6-pack-remise">
        <PackageCheck className="size-4 text-muted-foreground" aria-hidden="true" />
        <span className="text-sm font-semibold">Pack de remise client</span>
        {pack?.complet ? (
          <Badge tone="success">Complet</Badge>
        ) : (
          <Badge tone="outline">
            {pack?.pieces
              ? `${pack.pieces.filter((p) => p.present).length}/${pack.pieces.length} pièce(s)`
              : 'À préparer'}
          </Badge>
        )}
        {!pack?.persiste && (
          <Button size="sm" variant="outline" className="ml-auto" loading={packBusy} onClick={genererPack}>
            Générer le pack de remise
          </Button>
        )}
      </div>
    </div>
  )
}
