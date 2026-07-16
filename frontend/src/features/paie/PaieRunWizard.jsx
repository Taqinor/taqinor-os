import { useEffect, useMemo, useState } from 'react'
import {
  CalendarPlus, FileStack, ClipboardCheck, CheckCircle2, Lock,
  AlertTriangle, RefreshCw, Plus, ArrowRight, ShieldAlert, ChevronDown, Gift,
} from 'lucide-react'
import {
  Button, Card, Input, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, EmptyState, Badge, HelpTip, Spinner, toast,
} from '../../ui'
import { DataTable } from '../../ui'
import { formatMAD } from '../../lib/format'
import { resilientMutation } from '../../lib/resilientMutation'
import paieApi from '../../api/paieApi'
import { StatutPeriode, StatutBulletin } from './statuses.jsx'
import {
  RUN_STEPS, runStepState, anomaliesBulletin, runAAnomalies,
  PERIODE_STATUTS, BULLETIN_STATUTS,
} from './paieLogic.js'

/* ============================================================================
   UX10 — Assistant de run de paie (revue-avant-validation).
   ----------------------------------------------------------------------------
   Un pas-à-pas garde-fou : 1) ouvrir/créer une période, 2) générer les
   bulletins, 3) REVUE (bruts/nets/écarts, anomalies signalées), 4) valider,
   5) clôturer (verrou). Chaque étape est verrouillée tant que la précédente
   n'est pas satisfaite (gating pur dans paieLogic.runStepState). Les montants
   ne sont JAMAIS écrits ici (snapshot serveur) ; aucun prix d'achat/marge.
   ========================================================================== */

const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

const STEP_META = {
  periode: { label: 'Période', icon: CalendarPlus },
  generer: { label: 'Bulletins', icon: FileStack },
  revue: { label: 'Revue', icon: ClipboardCheck },
  valider: { label: 'Validation', icon: CheckCircle2 },
  cloturer: { label: 'Clôture', icon: Lock },
}

export default function PaieRunWizard() {
  const now = new Date()
  const [periodes, setPeriodes] = useState([])
  const [profils, setProfils] = useState([])
  const [bulletins, setBulletins] = useState([])
  const [periode, setPeriode] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [step, setStep] = useState('periode')
  const [avertissements, setAvertissements] = useState([])
  const [avertissementsOuvert, setAvertissementsOuvert] = useState(true)

  // Formulaire de création de période.
  const [annee, setAnnee] = useState(String(now.getFullYear()))
  const [mois, setMois] = useState(String(now.getMonth() + 1))

  useEffect(() => {
    let alive = true
    Promise.all([paieApi.getPeriodes(), paieApi.getProfils()])
      .then(([p, pr]) => {
        if (!alive) return
        setPeriodes(listOf(p.data))
        setProfils(listOf(pr.data))
      })
      .catch(() => toast.error('Chargement de la paie impossible.'))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [])

  // Recharge les bulletins de la période sélectionnée. Le viewset bulletins
  // n'expose pas de filtre `?periode=` (OrderingFilter seul) : on filtre côté
  // client par période pour ne montrer que le run courant.
  const loadBulletins = (per) => {
    if (!per) { setBulletins([]); return Promise.resolve() }
    return paieApi.getBulletins()
      .then((r) => setBulletins(
        listOf(r.data).filter((b) => b.periode === per.id)))
      .catch(() => toast.error('Chargement des bulletins impossible.'))
  }

  // YHIRE3/XPAI15/ZPAI2 — panneau d'avertissements pré-run (RIB/CNSS
  // manquants, dossiers non actifs, CDD échus, salaire nul…). Lecture seule,
  // jamais bloquant côté client — affiché en tête, avant toute génération.
  const loadAvertissements = (per) => {
    if (!per) { setAvertissements([]); return Promise.resolve() }
    return paieApi.avertissements(per.id)
      .then((r) => setAvertissements(Array.isArray(r.data) ? r.data : []))
      .catch(() => setAvertissements([]))
  }

  const selectPeriode = (per) => {
    setPeriode(per)
    loadBulletins(per)
    loadAvertissements(per)
    setAvertissementsOuvert(true)
    setStep(per ? 'generer' : 'periode')
  }

  const steps = useMemo(
    () => runStepState({ periode, bulletins }),
    [periode, bulletins],
  )
  const anomalies = runAAnomalies(bulletins)

  // ── Actions ──
  const creerPeriode = async () => {
    setBusy('periode')
    try {
      const libelle = `${MOIS[Number(mois) - 1]} ${annee}`
      const { data } = await paieApi.createPeriode({
        annee: Number(annee), mois: Number(mois), libelle,
      })
      setPeriodes((l) => [data, ...l])
      selectPeriode(data)
      toast.success('Période créée.')
    } catch (e) {
      toast.error(errMsg(e, 'Impossible de créer la période.'))
    } finally { setBusy('') }
  }

  const genererTous = async () => {
    if (!periode) return
    setBusy('generer')
    try {
      // Importe d'abord les éléments variables RH du mois (best-effort).
      await paieApi.importerElementsRh(periode.id).catch(() => {})
      const actifs = profils.filter((p) => p.actif !== false)
      // VX117 — allSettled + rapport nominatif : un profil en échec ne bloque
      // pas les autres, mais n'avance JAMAIS la période tout seul.
      const { succeeded, failed } = await resilientMutation(actifs, (pr) =>
        paieApi.genererBulletin({ periode: periode.id, profil: pr.id }))
      await loadBulletins(periode)
      // La période ne passe en « calculée » que si TOUS les profils actifs
      // ont un bulletin généré — un échec reste nommé, jamais avalé.
      if (failed.length === 0) {
        await avancerVers(PERIODE_STATUTS.CALCULEE, { silencieux: true })
      }
      await loadAvertissements(periode)
      if (failed.length > 0) {
        const noms = failed.map((f) => f.item.employe_nom || `profil #${f.item.id}`).join(', ')
        toast.error(
          `${succeeded.length} bulletin(s) généré(s), échec pour : ${noms}. `
          + 'Période non avancée — corrigez puis relancez.')
      } else {
        toast.success(`${succeeded.length} bulletin(s) généré(s).`)
        setStep('revue')
      }
    } catch (e) {
      toast.error(errMsg(e, 'Génération impossible.'))
    } finally { setBusy('') }
  }

  const avancerVers = async (cible, { silencieux } = {}) => {
    if (!periode) return
    try {
      const { data } = await paieApi.changerStatutPeriode(periode.id, cible)
      setPeriode(data)
      setPeriodes((l) => l.map((p) => (p.id === data.id ? data : p)))
    } catch (e) {
      if (!silencieux) toast.error(errMsg(e, 'Transition refusée.'))
    }
  }

  const validerTous = async () => {
    if (!periode) return
    setBusy('valider')
    try {
      const aValider = bulletins.filter((b) => b.statut !== BULLETIN_STATUTS.VALIDE)
      // VX117 — allSettled + rapport nominatif : un bulletin en échec ne
      // bloque pas les autres, mais n'avance JAMAIS la période tout seul.
      const { succeeded, failed } = await resilientMutation(aValider, (b) =>
        paieApi.validerBulletin(b.id))
      await loadBulletins(periode)
      if (failed.length === 0) {
        await avancerVers(PERIODE_STATUTS.VALIDEE, { silencieux: true })
      }
      if (failed.length > 0) {
        const noms = failed.map((f) => {
          const pr = profils.find((p) => p.id === f.item.profil)
          return pr?.employe_nom || `profil #${f.item.profil}`
        }).join(', ')
        toast.error(
          `${succeeded.length} bulletin(s) validé(s), échec pour : ${noms}. `
          + 'Période non avancée — seuls les bulletins en échec restent à valider.')
      } else {
        toast.success(`${succeeded.length} bulletin(s) validé(s).`)
        setStep('cloturer')
      }
    } catch (e) {
      toast.error(errMsg(e, 'Validation impossible.'))
    } finally { setBusy('') }
  }

  const cloturer = async () => {
    if (!periode) return
    setBusy('cloturer')
    try {
      const { data } = await paieApi.cloturerPeriode(periode.id, true)
      setPeriode(data)
      setPeriodes((l) => l.map((p) => (p.id === data.id ? data : p)))
      await loadBulletins(periode)
      toast.success('Période clôturée et verrouillée.')
    } catch (e) {
      toast.error(errMsg(e, 'Clôture impossible.'))
    } finally { setBusy('') }
  }

  // XPAI4 — run hors-cycle « 13e mois » : génère les bulletins de
  // gratification de tous les profils actifs sur la période sélectionnée.
  const runGratification = async () => {
    if (!periode) return
    setBusy('gratification')
    try {
      const { data } = await paieApi.runGratification(periode.id)
      const n = Array.isArray(data) ? data.length : data?.crees ?? 0
      toast.success(`${n} bulletin(s) de 13e mois généré(s).`)
      await loadBulletins(periode)
    } catch (e) {
      toast.error(errMsg(e, 'Run 13e mois impossible.'))
    } finally { setBusy('') }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-muted-foreground">
        <Spinner className="size-4" /> Chargement de la paie…
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">
            Run de paie
          </h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Assistant guidé : revue avant validation, clôture verrouillée.
          </p>
        </div>
        {periode && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {periode.libelle || `${MOIS[periode.mois - 1]} ${periode.annee}`}
            </span>
            <StatutPeriode status={periode.statut} />
            <Button variant="outline" size="sm"
              onClick={runGratification} loading={busy === 'gratification'}>
              <Gift size={15} aria-hidden="true" /> Run 13e mois
            </Button>
          </div>
        )}
      </div>

      {/* YHIRE3/XPAI15/ZPAI2 — avertissements pré-run, jamais bloquants. */}
      {periode && avertissements.length > 0 && (
        <AvertissementsPanel
          items={avertissements}
          ouvert={avertissementsOuvert}
          onToggle={() => setAvertissementsOuvert((o) => !o)}
        />
      )}

      {/* Rail d'étapes */}
      <StepRail steps={steps} current={step} onPick={setStep} />

      {/* Corps de l'étape courante */}
      <Card className="p-4 sm:p-5">
        {step === 'periode' && (
          <StepPeriode
            periodes={periodes}
            annee={annee} setAnnee={setAnnee}
            mois={mois} setMois={setMois}
            onCreer={creerPeriode}
            onSelect={selectPeriode}
            busy={busy === 'periode'}
          />
        )}
        {step === 'generer' && (
          <StepGenerer
            gate={steps.generer}
            profilsActifs={profils.filter((p) => p.actif !== false).length}
            bulletins={bulletins}
            onGenerer={genererTous}
            busy={busy === 'generer'}
          />
        )}
        {step === 'revue' && (
          <StepRevue bulletins={bulletins} anomalies={anomalies} />
        )}
        {step === 'valider' && (
          <StepValider
            gate={steps.valider}
            bulletins={bulletins}
            anomalies={anomalies}
            onValider={validerTous}
            busy={busy === 'valider'}
          />
        )}
        {step === 'cloturer' && (
          <StepCloturer
            gate={steps.cloturer}
            periode={periode}
            onCloturer={cloturer}
            busy={busy === 'cloturer'}
          />
        )}
      </Card>
    </div>
  )
}

/* ── Panneau d'avertissements pré-run (YHIRE3/XPAI15/ZPAI2) ──
   Liste plate, jamais bloquante — bloquant/avertissement distingués par
   couleur uniquement (RIB/CNSS manquants, dossier non actif, CDD échu,
   salaire nul). Aucune donnée de salaire n'y figure. */
function AvertissementsPanel({ items, ouvert, onToggle }) {
  const bloquants = items.filter((a) => a.gravite === 'bloquant')
  const autres = items.filter((a) => a.gravite !== 'bloquant')
  return (
    <Card className={cx(
      'border p-4',
      bloquants.length ? 'border-destructive/40 bg-destructive/5'
        : 'border-warning/40 bg-warning/5',
    )}>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-semibold">
          <ShieldAlert size={16} aria-hidden="true"
            className={bloquants.length ? 'text-destructive' : 'text-warning'} />
          {items.length} avertissement(s) avant de lancer la paie
          {bloquants.length > 0 && (
            <Badge tone="danger">{bloquants.length} bloquant(s)</Badge>
          )}
        </span>
        <ChevronDown
          size={16} aria-hidden="true"
          className={cx('transition-transform', ouvert && 'rotate-180')}
        />
      </button>
      {ouvert && (
        <ul className="mt-3 flex flex-col gap-1.5 text-sm">
          {[...bloquants, ...autres].map((a, i) => (
            <li key={`${a.type}-${a.employe_id}-${i}`}
              className="flex items-start gap-2">
              <span className={cx(
                'mt-1.5 size-1.5 shrink-0 rounded-full',
                a.gravite === 'bloquant' ? 'bg-destructive' : 'bg-warning',
              )} />
              <span className={a.gravite === 'bloquant' ? 'text-destructive' : ''}>
                {a.message}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

/* ── Rail d'étapes ── */
function StepRail({ steps, current, onPick }) {
  return (
    <ol className="flex flex-wrap gap-2">
      {RUN_STEPS.map((key, i) => {
        const meta = STEP_META[key]
        const st = steps[key]
        const Icon = meta.icon
        const active = current === key
        return (
          <li key={key}>
            <button
              type="button"
              disabled={!st.unlocked}
              onClick={() => onPick(key)}
              className={cx(
                'flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors',
                active
                  ? 'border-primary bg-primary/10 text-foreground'
                  : 'border-border text-muted-foreground hover:bg-muted',
                !st.unlocked && 'cursor-not-allowed opacity-50',
              )}
            >
              <span className="tabular-nums text-xs text-muted-foreground">
                {i + 1}
              </span>
              <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
              {meta.label}
              {st.done && (
                <CheckCircle2
                  size={15} className="text-success" aria-label="fait"
                />
              )}
            </button>
          </li>
        )
      })}
    </ol>
  )
}

/* ── Étape 1 : période ── */
function StepPeriode({
  periodes, annee, setAnnee, mois, setMois, onCreer, onSelect, busy,
}) {
  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="font-display text-base font-semibold">
          1. Créer ou ouvrir une période
        </h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Un run de paie = un mois. Créez la période puis générez les bulletins.
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Année</span>
          <Input
            type="number" step="any" value={annee}
            onChange={(e) => setAnnee(e.target.value)}
            className="w-28"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Mois</span>
          <Select value={mois} onValueChange={setMois}>
            <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              {MOIS.map((m, i) => (
                <SelectItem key={i} value={String(i + 1)}>{m}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
        <Button onClick={onCreer} loading={busy}>
          <Plus size={16} aria-hidden="true" /> Créer la période
        </Button>
      </div>

      {periodes.length > 0 && (
        <div>
          <p className="mb-2 text-sm font-medium">Périodes existantes</p>
          <div className="flex flex-col divide-y divide-border rounded-lg border border-border">
            {periodes.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => onSelect(p)}
                className="flex items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-muted"
              >
                <span>{p.libelle || `${MOIS[p.mois - 1]} ${p.annee}`}</span>
                <span className="flex items-center gap-2">
                  <StatutPeriode status={p.statut} />
                  <ArrowRight size={15} className="text-muted-foreground" />
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Étape 2 : générer ── */
function StepGenerer({ gate, profilsActifs, bulletins, onGenerer, busy }) {
  if (!gate.unlocked) return <Locked reason={gate.reason} />
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="font-display text-base font-semibold">
          2. Générer les bulletins
        </h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          {profilsActifs} profil(s) de paie actif(s). Les éléments variables RH
          du mois sont importés automatiquement, puis chaque bulletin est
          calculé (brut → CNSS/AMO/IR → net).
        </p>
      </div>
      {bulletins.length > 0 && (
        <Badge tone="info">{bulletins.length} bulletin(s) déjà généré(s)</Badge>
      )}
      <div>
        <Button onClick={onGenerer} loading={busy} disabled={profilsActifs === 0}>
          <FileStack size={16} aria-hidden="true" />
          {bulletins.length ? 'Recalculer les bulletins' : 'Générer les bulletins'}
        </Button>
      </div>
      {profilsActifs === 0 && (
        <p className="text-sm text-warning">
          Aucun profil de paie actif — configurez-les dans Paramètres.
        </p>
      )}
    </div>
  )
}

/* ── Étape 3 : revue ── */
function StepRevue({ bulletins, anomalies }) {
  const columns = revueColumns
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-display text-base font-semibold">
            3. Revue des bulletins
            {/* VX47 — aide contextuelle : la logique revue-avant-validation
                (pourquoi ce garde-fou existe) n'est pas évidente pour un
                nouvel employé. */}
            <HelpTip label="Aide — revue avant validation" className="ml-1.5 align-middle">
              Cette étape est un <strong>garde-fou</strong> : une fois les
              bulletins <strong>validés</strong>, ils ne sont plus modifiables
              directement. Vérifiez chaque brut/net et les écarts signalés
              avant de continuer — un écart marqué ici (ex. net anormal) mérite
              d'être corrigé sur le profil concerné avant validation.
            </HelpTip>
          </h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Vérifiez bruts, nets et écarts avant de valider.
          </p>
        </div>
        {anomalies ? (
          <Badge tone="danger">
            <AlertTriangle size={14} aria-hidden="true" /> Anomalies détectées
          </Badge>
        ) : (
          <Badge tone="success">Aucune anomalie</Badge>
        )}
      </div>
      {bulletins.length === 0 ? (
        <EmptyState
          icon={FileStack}
          title="Aucun bulletin"
          description="Revenez à l’étape « Bulletins » pour les générer."
        />
      ) : (
        <DataTable data={bulletins} columns={columns} searchable
          exportName="revue-paie" />
      )}
    </div>
  )
}

const revueColumns = [
  { id: 'profil', header: 'Profil', accessor: (r) => r.profil,
    cell: (_v, r) => `#${r.profil}` },
  { id: 'brut', header: 'Brut', align: 'right',
    accessor: (r) => Number(r.brut) || 0, cell: (_v, r) => formatMAD(r.brut) },
  { id: 'ir', header: 'IR', align: 'right',
    accessor: (r) => Number(r.ir) || 0, cell: (_v, r) => formatMAD(r.ir) },
  { id: 'net', header: 'Net à payer', align: 'right',
    accessor: (r) => Number(r.net_a_payer) || 0,
    cell: (_v, r) => formatMAD(r.net_a_payer) },
  { id: 'statut', header: 'Statut', accessor: (r) => r.statut,
    cell: (_v, r) => <StatutBulletin status={r.statut} /> },
  { id: 'anomalie', header: 'Écarts', accessor: (r) =>
      anomaliesBulletin(r).join(', '),
    cell: (_v, r) => {
      const a = anomaliesBulletin(r)
      return a.length
        ? <span className="text-destructive text-xs">{a.join(', ')}</span>
        : <span className="text-success text-xs">RAS</span>
    } },
]

/* ── Étape 4 : valider ── */
function StepValider({ gate, bulletins, anomalies, onValider, busy }) {
  if (!gate.unlocked) return <Locked reason={gate.reason} />
  const restants = bulletins.filter(
    (b) => b.statut !== BULLETIN_STATUTS.VALIDE).length
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="font-display text-base font-semibold">
          4. Valider les bulletins
        </h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          La validation fige chaque bulletin (snapshot immuable). {restants}{' '}
          bulletin(s) en brouillon à valider.
        </p>
      </div>
      {anomalies && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm">
          <AlertTriangle size={16} className="mt-0.5 text-destructive" aria-hidden="true" />
          <span>
            Des anomalies subsistent en revue. Vous pouvez valider malgré tout,
            mais vérifiez d’abord les écarts signalés.
          </span>
        </div>
      )}
      <div>
        <Button onClick={onValider} loading={busy} disabled={restants === 0}>
          <CheckCircle2 size={16} aria-hidden="true" />
          Valider {restants || ''} bulletin(s)
        </Button>
      </div>
    </div>
  )
}

/* ── Étape 5 : clôturer ── */
function StepCloturer({ gate, periode, onCloturer, busy }) {
  if (!gate.unlocked) return <Locked reason={gate.reason} />
  const cloturee = periode?.statut === PERIODE_STATUTS.CLOTUREE
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="font-display text-base font-semibold">
          5. Clôturer la période
        </h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          La clôture valide les bulletins en brouillon puis VERROUILLE la
          période : plus aucun bulletin ne peut y être généré. Action définitive.
        </p>
      </div>
      {cloturee ? (
        <Badge tone="success">
          <Lock size={14} aria-hidden="true" /> Période clôturée
        </Badge>
      ) : (
        <div>
          <Button variant="destructive" onClick={onCloturer} loading={busy}>
            <Lock size={16} aria-hidden="true" /> Clôturer et verrouiller
          </Button>
        </div>
      )}
    </div>
  )
}

function Locked({ reason }) {
  return (
    <EmptyState
      icon={Lock}
      title="Étape verrouillée"
      description={reason || 'Terminez d’abord l’étape précédente.'}
    />
  )
}

// ── Helpers ──
function listOf(data) {
  return Array.isArray(data) ? data : (data?.results ?? [])
}
function errMsg(e, fallback) {
  return e?.response?.data?.detail || fallback
}
function cx(...cls) {
  return cls.filter(Boolean).join(' ')
}
