import { useEffect, useMemo, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts'
import { Users } from 'lucide-react'
import crmApi from '../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Spinner, Segmented,
} from '../../ui'
import {
  ChartFrame, ChartTooltip, CHART_TOKENS, animationDuration, CHART_ANIM_EASING,
} from '../../ui/charts'
import { formatPercent } from '../../lib/format'
import { cn } from '../../lib/cn'

/* ============================================================================
   SUIVI-ÉQUIPE (fondateur, 29/10/2026) — bloc « Vue d'équipe » de l'écran
   « Suivi des relances », réservé aux rôles responsable/admin : quatre
   chiffres de tête, UNE barre empilée par commercial (toujours en retard →
   traitées en retard → à temps → sautées, du plus en retard au moins), et les
   touches dues jour par jour sur la période.

   Lit `GET relance-etapes/controle/?jours=7|14|30&owner=` — le MÊME contrat
   que le bloc « Contrôle du suivi » du cockpit (`apps/crm/contract_samples/
   controle_suivi.json`, PACT10) : retard compté en jours OUVRÉS, absences
   déclarées excusées, annulations du moteur hors dénominateur.
   `par_commercial` est servi pour TOUS les commerciaux de la portée quel que
   soit `owner` ; le verdict, les exceptions et la frise suivent `owner`.
   AUCUN chiffre n'est recompté ici : les barres rendent `du` / `a_temps` /
   `en_retard` / `ouvert` / `sautees` tels quels ; la seule transformation est
   la répartition d'un `ouvert` servi entre « en retard » et « pas encore en
   retard » selon l'`etat` servi de la case (`en_cours`).

   Recherche du 29/10/2026 (HubSpot, Pipedrive, Outreach, IBM, Geckoboard,
   Few / NN-g / Datawrapper) : une barre empilée par personne avec le retard
   à la BASE (c'est le segment que l'on compare d'une barre à l'autre), triée
   du pire au meilleur, les chiffres écrits dans les segments ; une
   chronologie par date d'échéance à côté ; jamais de double axe, jamais de
   camembert ; la couleur ne porte jamais seule le sens (mot + chiffre, et
   un tableau équivalent sous le graphique).
   ========================================================================== */

const PERIODES = [
  { value: 7, label: '7 jours' },
  { value: 14, label: '14 jours' },
  { value: 30, label: '30 jours' },
]
const PERIODE_DEFAUT = 14

// Les séries de la barre par commercial, dans l'ORDRE depuis la base. Les
// teintes sont les tons de STATUT du kit (jamais une série « 4 » recyclée) ;
// `encre` = la couleur du chiffre écrit dans le segment (lisible clair/sombre).
const SERIES_COMMERCIAL = [
  { key: 'ouvert', label: 'Toujours en retard', fill: CHART_TOKENS.danger, encre: 'var(--card)' },
  { key: 'en_retard', label: 'Traitées en retard', fill: CHART_TOKENS.warning, encre: 'var(--warning-foreground)' },
  { key: 'a_temps', label: 'À temps', fill: CHART_TOKENS.success, encre: 'var(--card)' },
  { key: 'sautees', label: 'Sautées', fill: CHART_TOKENS.muted, encre: 'var(--card)' },
]
// Jour par jour : `ouvert` servi, réparti selon l'`etat` servi de la case.
const SERIES_JOUR = [
  { key: 'ouvert_retard', label: 'Ouvertes, en retard', fill: CHART_TOKENS.danger },
  { key: 'en_retard', label: 'Traitées en retard', fill: CHART_TOKENS.warning },
  { key: 'a_temps', label: 'À temps', fill: CHART_TOKENS.success },
  { key: 'sautees', label: 'Sautées', fill: CHART_TOKENS.muted },
  { key: 'ouvert_cours', label: 'Ouvertes, pas encore en retard', fill: CHART_TOKENS.info },
]
// Un chiffre n'est écrit DANS un segment que s'il a la place (≥ 12 % de la
// barre) ; en dessous, le titre au survol et le libellé accessible le portent.
const PART_MIN_CHIFFRE = 0.12

const tiret = (v) => (v == null ? '—' : v)
const pct = (v) => (v == null ? '—' : formatPercent(v, { decimals: 1 }))

// « lundi 7 septembre » — minuit LOCAL (même règle que `RelancesSuiviPage`).
function jourLong(yyyyMmDd) {
  const d = new Date(`${yyyyMmDd}T00:00:00`)
  const semaine = new Intl.DateTimeFormat('fr-FR', { weekday: 'long' }).format(d)
  const jour = new Intl.DateTimeFormat('fr-FR', { day: 'numeric' }).format(d)
  const mois = new Intl.DateTimeFormat('fr-FR', { month: 'long' }).format(d)
  return `${semaine} ${jour} ${mois}`
}
const jourCourt = (yyyyMmDd) => `${yyyyMmDd.slice(8, 10)}/${yyyyMmDd.slice(5, 7)}`

function Tuile({ label, valeur, hint, alerte = false, testId }) {
  return (
    <div className="rounded-lg border border-border bg-card p-2.5" data-testid={testId}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn('font-display text-lg font-semibold tabular-nums', alerte && 'text-destructive')}>
        {valeur}
      </div>
      {hint && <div className="text-[11px] text-muted-foreground">{hint}</div>}
    </div>
  )
}

/** Légende : la teinte ET le mot — la couleur ne porte jamais seule le sens. */
function Legende({ series, testId }) {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground" data-testid={testId}>
      {series.map((s) => (
        <li key={s.key} className="inline-flex items-center gap-1">
          <span aria-hidden="true" className="inline-block size-2.5 rounded-[2px]" style={{ background: s.fill }} />
          {s.label}
        </li>
      ))}
    </ul>
  )
}

/** LE graphique principal : une barre empilée par commercial, en HTML (largeur
 *  proportionnelle à `du`, 2 px de surface entre les segments), le nom cliquable
 *  pour ne voir que ce commercial dans la file. Les chiffres servis, tels quels. */
function BarresCommerciaux({ lignes, ownerChoisi, onChoisirOwner }) {
  const maxDu = Math.max(0, ...lignes.map((l) => l.du ?? 0))
  const unChoisi = ownerChoisi != null && String(ownerChoisi) !== ''
  return (
    <ol className="flex flex-col gap-2" data-testid="equipe-barres">
      {lignes.map((l) => {
        const du = l.du ?? 0
        const choisi = unChoisi && String(ownerChoisi) === String(l.id)
        const resume = SERIES_COMMERCIAL
          .map((s) => `${l[s.key] ?? 0} ${s.label.toLowerCase()}`).join(', ')
        return (
          <li
            key={l.id} data-testid={`equipe-ligne-${l.id}`}
            className={cn(
              'grid grid-cols-[7rem_1fr] items-center gap-x-2 gap-y-0.5 sm:grid-cols-[9rem_1fr_auto]',
              unChoisi && !choisi && 'opacity-50',
            )}
          >
            <button
              type="button" aria-pressed={choisi}
              title={choisi ? "Revenir à toute l'équipe" : `Ne voir que ${l.nom} dans la file`}
              onClick={() => onChoisirOwner?.(choisi ? '' : l.id)}
              className="focus-ring truncate rounded text-left text-sm font-medium hover:underline"
            >
              {l.nom}
            </button>
            <div
              role="img" className="flex h-5 items-center"
              aria-label={`${l.nom} : ${du} touche(s) jugée(s) — ${resume}`}
            >
              {du === 0 ? (
                <span className="text-xs text-muted-foreground">aucune touche jugée</span>
              ) : (
                <div
                  className="flex h-full gap-[2px] overflow-hidden rounded"
                  style={{ width: `${Math.max(4, Math.round((du / maxDu) * 100))}%` }}
                >
                  {SERIES_COMMERCIAL.map((s) => {
                    const n = l[s.key] ?? 0
                    if (!n) return null
                    return (
                      <span
                        key={s.key} data-serie={s.key} title={`${s.label} : ${n}`}
                        className="flex h-full items-center justify-center text-[11px] font-semibold"
                        style={{ flex: `${n} ${n} 0%`, background: s.fill, color: s.encre }}
                      >
                        {n / du >= PART_MIN_CHIFFRE ? n : ''}
                      </span>
                    )
                  })}
                </div>
              )}
            </div>
            <p className="col-span-2 text-xs text-muted-foreground tabular-nums sm:col-span-1 sm:text-right">
              {pct(l.a_temps_pct)} à temps
              {' · '}
              <span className={cn((l.en_retard_actuel ?? 0) > 0 && 'font-medium text-destructive')}>
                {tiret(l.en_retard_actuel)} en retard
              </span>
              {' · '}
              {tiret(l.aujourdhui)} aujourd&apos;hui
            </p>
          </li>
        )
      })}
    </ol>
  )
}

const COLONNES_JOUR = [
  { key: 'date', header: 'Jour', format: (v) => jourLong(v) },
  { key: 'du', header: 'Dues', align: 'right' },
  { key: 'a_temps', header: 'À temps', align: 'right' },
  { key: 'en_retard', header: 'Traitées en retard', align: 'right' },
  { key: 'ouvert', header: 'Encore ouvertes', align: 'right' },
  { key: 'sautees', header: 'Sautées', align: 'right' },
]

/** Compagnon : colonnes empilées par jour d'échéance (frise `jours` servie),
 *  aujourd'hui marqué, jours non ouvrés estompés ; tableau équivalent
 *  (`ChartFrame`) pour l'accessibilité, le mobile et l'impression. */
function ChroniqueJours({ jours, periode }) {
  const dur = animationDuration()
  const lignes = useMemo(() => jours.map((j) => ({
    ...j,
    ouvert_retard: j.etat === 'en_cours' ? 0 : (j.ouvert ?? 0),
    ouvert_cours: j.etat === 'en_cours' ? (j.ouvert ?? 0) : 0,
  })), [jours])
  const aujourdhui = lignes.find((j) => j.aujourdhui)?.date
  const axisTick = { fontSize: 11, fill: CHART_TOKENS.axis }
  return (
    <ChartFrame
      label={`Touches dues jour par jour sur ${periode} jours`}
      columns={COLONNES_JOUR} rows={lignes} getRowKey={(r) => r.date}
    >
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={lignes} margin={{ top: 16, right: 8, bottom: 0, left: 0 }} barCategoryGap="25%">
          <XAxis
            dataKey="date" tickFormatter={jourCourt} tick={axisTick}
            tickLine={false} axisLine={false} minTickGap={12}
          />
          <YAxis allowDecimals={false} hide />
          <Tooltip cursor={{ fill: 'var(--muted)' }} content={<ChartTooltip labelFormatter={jourLong} />} />
          {aujourdhui && (
            <ReferenceLine
              x={aujourdhui} stroke={CHART_TOKENS.axis} strokeDasharray="3 3"
              label={{ value: "Aujourd'hui", position: 'top', fontSize: 10, fill: CHART_TOKENS.axis }}
            />
          )}
          {SERIES_JOUR.map((s) => (
            <Bar
              key={s.key} dataKey={s.key} name={s.label} stackId="jour" fill={s.fill}
              stroke="var(--card)" strokeWidth={1}
              isAnimationActive={dur > 0} animationDuration={dur} animationEasing={CHART_ANIM_EASING}
            >
              {lignes.map((j) => (
                <Cell key={j.date} fillOpacity={j.ouvre === false ? 0.4 : 1} />
              ))}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

export default function RelancesEquipePanel({ owner = '', onChoisirOwner }) {
  const [jours, setJours] = useState(PERIODE_DEFAUT)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [donnees, setDonnees] = useState(null)

  useEffect(() => {
    let active = true
    // setState différé au prochain microtask (jamais synchrone dans l'effet) —
    // même patron que `RelancesSuiviPage.jsx` (react-hooks/set-state-in-effect).
    queueMicrotask(() => { if (active) { setLoading(true); setErreur(false) } })
    const params = { jours }
    if (owner) params.owner = owner
    // Garde défensive (même motif que `MesureCadencePanel`) : une suite qui
    // mocke `crmApi` sans connaître `getControleSuivi` se tait.
    const requete = typeof crmApi.getControleSuivi === 'function'
      ? crmApi.getControleSuivi(params)
      : Promise.reject(new Error('getControleSuivi indisponible'))
    requete
      .then((r) => { if (active) setDonnees(r.data) })
      .catch(() => { if (active) setErreur(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [jours, owner])

  const verdict = donnees?.verdict
  const exceptions = donnees?.exceptions
  const parCommercial = donnees?.par_commercial ?? []
  const vide = !donnees || verdict?.niveau === 'vide'
  const retardTotal = exceptions?.en_retard?.total
  const attenteTotal = exceptions?.taches_en_attente?.total

  return (
    <Card data-testid="relances-equipe-panel" className="mb-3">
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-2 space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-4 w-4" aria-hidden="true" /> Vue d&apos;équipe
          </CardTitle>
          <CardDescription>
            Touches dues sur la période, par commercial — retard compté en jours ouvrés,
            absences déclarées excusées, annulations du moteur exclues.
          </CardDescription>
        </div>
        <Segmented
          size="sm" options={PERIODES} value={jours} onChange={setJours}
          aria-label="Période de la vue d'équipe"
        />
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {loading ? (
          <Spinner />
        ) : erreur ? (
          <p className="text-sm text-muted-foreground">Vue d&apos;équipe indisponible pour le moment.</p>
        ) : vide ? (
          <p className="text-sm text-muted-foreground" data-testid="equipe-vide">
            Pas encore de données sur cette période.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="equipe-tuiles">
              <Tuile
                testId="equipe-tuile-retard" label="En retard maintenant"
                valeur={tiret(retardTotal)} alerte={(retardTotal ?? 0) > 0}
                hint="touches ouvertes, 1 jour ouvré ou plus"
              />
              <Tuile
                testId="equipe-tuile-a-temps" label="À temps"
                valeur={pct(verdict?.a_temps_pct)}
                hint={`période précédente : ${pct(verdict?.precedent_a_temps_pct)}`}
              />
              <Tuile
                testId="equipe-tuile-reportees" label="Reportées"
                valeur={tiret(verdict?.reportees)}
                hint={verdict ? `sur ${verdict.du} jugée(s)` : undefined}
              />
              <Tuile
                testId="equipe-tuile-attente" label="Tâches en attente"
                valeur={tiret(attenteTotal)} alerte={(attenteTotal ?? 0) > 0}
              />
            </div>
            <section aria-label="Par commercial">
              <h3 className="mb-1.5 text-sm font-semibold">Par commercial</h3>
              {parCommercial.length === 0 ? (
                <p className="text-xs text-muted-foreground">—</p>
              ) : (
                <BarresCommerciaux
                  lignes={parCommercial} ownerChoisi={owner} onChoisirOwner={onChoisirOwner}
                />
              )}
              <Legende series={SERIES_COMMERCIAL} testId="equipe-legende-commercial" />
            </section>
            <section aria-label="Jour par jour">
              <h3 className="mb-1.5 text-sm font-semibold">Jour par jour</h3>
              <ChroniqueJours jours={donnees.jours ?? []} periode={donnees.periode_jours ?? jours} />
              <Legende series={SERIES_JOUR} testId="equipe-legende-jours" />
            </section>
          </>
        )}
      </CardContent>
    </Card>
  )
}
