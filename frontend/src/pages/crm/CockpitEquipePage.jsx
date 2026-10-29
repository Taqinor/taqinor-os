import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import crmApi from '../../api/crmApi'
import {
  Badge, Card, CardContent, Button, Spinner, Input, Label,
  Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription,
} from '../../ui'
import { apiErrorMessage } from '../../lib/apiError'
import { formatMAD, formatNumber } from '../../lib/format'

/* ============================================================================
   Cockpit d'équipe (fondateur, 28/10/2026) — `/crm/cockpit-equipe`.
   Pour le responsable d'équipe commerciale, le directeur commercial et
   Direction/Admin : chaque membre sur tous ses points (objectifs contre
   réalisé, discipline de suivi, pipeline) + la ligne d'équipe, et la pose des
   objectifs par membre. Lit `GET /crm/cockpit-equipe/` (contrat
   `apps/crm/contract_samples/cockpit_equipe.json`) ; écrit par `crm/objectifs/`.
   ========================================================================== */

const PERIODES = [['month', 'Mois'], ['quarter', 'Trimestre'], ['year', 'Année']]

// Période voisine (précédent/suivant) à partir de la période affichée.
function periodeVoisine(p, sens) {
  if (!p) return {}
  if (p.type === 'year') return { periode: 'year', annee: p.annee + sens }
  if (p.type === 'quarter') {
    let q = (p.trimestre ?? 1) + sens
    let a = p.annee
    if (q < 1) { q = 4; a -= 1 } else if (q > 4) { q = 1; a += 1 }
    return { periode: 'quarter', annee: a, trimestre: q }
  }
  let m = (p.mois ?? 1) + sens
  let a = p.annee
  if (m < 1) { m = 12; a -= 1 } else if (m > 12) { m = 1; a += 1 }
  return { periode: 'month', annee: a, mois: m }
}

const nombre = (v) => formatNumber(v, { decimals: Number.isInteger(v) ? 0 : 1 })

function classesPct(pct) {
  if (pct >= 100) return { barre: 'bg-success', texte: 'text-success' }
  if (pct >= 70) return { barre: 'bg-warning', texte: 'text-warning' }
  return { barre: 'bg-destructive', texte: 'text-destructive' }
}

function valeurMetrique(cle, v) {
  if (v === null || v === undefined) return '—'
  return cle === 'ca_signe' ? formatMAD(v, { decimals: 0 }) : nombre(v)
}

function CelluleObjectif({ cle, cell, onClick, ligneEquipe }) {
  const aCible = cell && cell.cible !== null && cell.cible !== undefined
  const pct = aCible && cell.pct !== null && cell.pct !== undefined ? cell.pct : 0
  const c = classesPct(pct)
  const contenu = (
    <>
      <div className="text-sm tabular-nums">
        <span className="font-medium text-foreground">{valeurMetrique(cle, cell?.realise)}</span>
        <span className="text-muted-foreground"> / {aCible ? valeurMetrique(cle, cell.cible) : '—'}</span>
      </div>
      {aCible ? (
        <div className="mt-1 flex items-center gap-2">
          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted" role="progressbar"
               aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
            <div className={`h-full ${c.barre}`} style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
          </div>
          <span className={`text-xs font-medium tabular-nums ${c.texte}`}>
            {formatNumber(pct, { decimals: 0 })} %
          </span>
        </div>
      ) : (
        !ligneEquipe && <div className="mt-1 text-xs text-muted-foreground">Fixer un objectif</div>
      )}
    </>
  )
  if (ligneEquipe) return <div>{contenu}</div>
  return (
    <button type="button" onClick={onClick}
            className="rounded px-1 py-0.5 text-left hover:bg-muted focus-visible:outline focus-visible:outline-2">
      {contenu}
    </button>
  )
}

function DialogueObjectif({ cible: ctx, periode, onFermer, onEnregistre }) {
  const [valeur, setValeur] = useState(
    ctx.cell.cible !== null && ctx.cell.cible !== undefined ? String(ctx.cell.cible) : '')
  const [erreur, setErreur] = useState(null)
  const [envoi, setEnvoi] = useState(false)

  const sauver = async (e) => {
    e.preventDefault()
    const n = Number(String(valeur).replace(',', '.').replace(/\s/g, ''))
    if (valeur.trim() === '' || !Number.isFinite(n) || n < 0) {
      setErreur('Saisissez un nombre positif.')
      return
    }
    setEnvoi(true)
    const cible = n.toFixed(2)
    try {
      if (ctx.cell.objectif_id) {
        await crmApi.saveObjectif(ctx.cell.objectif_id, { cible })
      } else {
        const data = {
          owner: ctx.membre.id, metric: ctx.metrique.cle, period_type: periode.type,
          period_year: periode.annee, cible,
        }
        if (periode.type === 'month') data.period_month = periode.mois
        if (periode.type === 'quarter') data.period_quarter = periode.trimestre
        await crmApi.saveObjectif(null, data)
      }
      onEnregistre()
    } catch (err) {
      setErreur(apiErrorMessage(err, 'L’enregistrement de l’objectif a échoué.'))
      setEnvoi(false)
    }
  }

  const effacer = async () => {
    setEnvoi(true)
    try {
      await crmApi.deleteObjectif(ctx.cell.objectif_id)
      onEnregistre()
    } catch (err) {
      setErreur(apiErrorMessage(err, 'La suppression de l’objectif a échoué.'))
      setEnvoi(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onFermer() }}>
      <DialogContent>
        <form onSubmit={sauver} noValidate className="space-y-4">
          <DialogHeader>
            <DialogTitle>Objectif — {ctx.membre.nom}</DialogTitle>
            <DialogDescription>{ctx.metrique.libelle} · {periode.libelle}</DialogDescription>
          </DialogHeader>
          <div className="space-y-1">
            <Label htmlFor="cockpit-cible">Cible</Label>
            <Input id="cockpit-cible" inputMode="decimal" step="any" value={valeur}
                   onChange={(e) => setValeur(e.target.value)} autoFocus />
          </div>
          {erreur && <p role="alert" className="text-sm text-destructive">{erreur}</p>}
          <DialogFooter>
            {ctx.cell.objectif_id && (
              <Button type="button" variant="outline" disabled={envoi} onClick={effacer}>Effacer l’objectif</Button>
            )}
            <Button type="button" variant="outline" onClick={onFermer}>Annuler</Button>
            <Button type="submit" disabled={envoi}>Enregistrer</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function Tableau({ children }) {
  return <div className="overflow-x-auto"><table className="w-full min-w-max text-sm">{children}</table></div>
}
const TH = 'px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground whitespace-nowrap'
const TD = 'px-3 py-2 align-top whitespace-nowrap'

// La liste des leads comprend `?owner=<id>` : les leads de CE membre. Le
// responsable de l'équipe (il prend aussi des leads) porte un badge.
function NomMembre({ m }) {
  return (
    <>
      <Link to={`/crm/leads?owner=${m.id}`} className="font-medium text-foreground hover:underline">
        {m.nom}
      </Link>
      {m.est_responsable && <Badge tone="neutral" className="ml-2">Responsable</Badge>}
    </>
  )
}

const pctPremier = (s) => (s.premier_contact_5min_pct === null || s.premier_contact_5min_pct === undefined
  ? '—' : `${formatNumber(s.premier_contact_5min_pct, { decimals: 0 })} %`)

export default function CockpitEquipePage() {
  const [params, setParams] = useState({})
  const [data, setData] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [interdit, setInterdit] = useState(false)
  const [cible, setCible] = useState(null)

  // Clés EXPLICITES (garde ENF D1 : chaque ?x= doit être déclaré au schéma).
  const charger = useCallback(() => crmApi.getCockpitEquipe({
    equipe: params.equipe, periode: params.periode, annee: params.annee,
    mois: params.mois, trimestre: params.trimestre,
  })
    .then((res) => { setData(res.data); setErreur(null); setInterdit(false) })
    .catch((e) => {
      if (e?.response?.status === 403) { setInterdit(true); return }
      setErreur(apiErrorMessage(e, 'Le chargement du cockpit d’équipe a échoué.'))
    }), [params])

  useEffect(() => { charger() }, [charger])

  if (interdit) {
    return <p role="alert" className="p-6 text-sm text-muted-foreground">Vous n’avez pas accès au cockpit d’équipe.</p>
  }
  if (erreur && !data) return <p role="alert" className="p-6 text-sm text-destructive">{erreur}</p>
  if (!data) return <div className="p-6"><Spinner /></div>
  if (!data.equipe) {
    return <p className="p-6 text-sm text-muted-foreground">Vous ne dirigez aucune équipe commerciale.</p>
  }

  const { equipe, periode, metriques, membres, equipe_totaux: tot } = data
  const equipeId = equipe.id
  const aller = (sens) => setParams({ equipe: equipeId, ...periodeVoisine(periode, sens) })
  const typePeriode = (t) => setParams({
    equipe: equipeId, periode: t, annee: periode.annee,
    ...(t === 'month' ? { mois: periode.mois ?? 1 } : {}),
    ...(t === 'quarter' ? { trimestre: periode.trimestre ?? Math.ceil((periode.mois ?? 1) / 3) } : {}),
  })

  const lignesSuivi = [...membres.map((m) => ({ m, s: m.suivi })), ...(tot ? [{ s: tot.suivi }] : [])]
  const lignesPipeline = [...membres.map((m) => ({ m, p: m.pipeline })), ...(tot ? [{ p: tot.pipeline }] : [])]

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold text-foreground">Cockpit d’équipe</h1>
        {data.equipes_accessibles.length > 1 ? (
          <select aria-label="Équipe" value={equipeId}
                  onChange={(e) => setParams({ equipe: Number(e.target.value) })}
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm">
            {data.equipes_accessibles.map((eq) => <option key={eq.id} value={eq.id}>{eq.nom}</option>)}
          </select>
        ) : <span className="text-sm text-muted-foreground">{equipe.nom}</span>}
        <select aria-label="Période" value={periode.type} onChange={(e) => typePeriode(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-2 text-sm">
          {PERIODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <div className="flex items-center gap-1">
          <Button type="button" variant="outline" size="sm" aria-label="Période précédente" onClick={() => aller(-1)}>‹</Button>
          <span className="min-w-[8rem] text-center text-sm font-medium" data-testid="cockpit-periode">{periode.libelle}</span>
          <Button type="button" variant="outline" size="sm" aria-label="Période suivante" onClick={() => aller(1)}>›</Button>
        </div>
      </header>
      {erreur && <p role="alert" className="text-sm text-destructive">{erreur}</p>}

      <Card><CardContent className="pt-4">
        <h2 className="mb-2 text-base font-semibold text-foreground">Objectifs</h2>
        <Tableau>
          <thead><tr>
            <th className={TH}>Membre</th>
            {metriques.map((mt) => <th key={mt.cle} className={TH}>{mt.libelle}</th>)}
          </tr></thead>
          <tbody>
            {membres.map((m) => (
              <tr key={m.id} className="border-t border-border">
                <td className={TD}>
                  <NomMembre m={m} equipeId={equipeId} />
                  {m.fonction && <div className="text-xs text-muted-foreground">{m.fonction}</div>}
                </td>
                {metriques.map((mt) => (
                  <td key={mt.cle} className={TD}>
                    <CelluleObjectif cle={mt.cle} cell={m.objectifs[mt.cle]}
                                     onClick={() => setCible({ membre: m, metrique: mt, cell: m.objectifs[mt.cle] })} />
                  </td>
                ))}
              </tr>
            ))}
            {tot && (
              <tr className="border-t-2 border-border font-bold" data-testid="cockpit-total-objectifs">
                <td className={TD}>Équipe</td>
                {metriques.map((mt) => (
                  <td key={mt.cle} className={TD}>
                    <CelluleObjectif ligneEquipe cle={mt.cle} cell={tot.objectifs[mt.cle]} />
                  </td>
                ))}
              </tr>
            )}
          </tbody>
        </Tableau>
      </CardContent></Card>

      <Card><CardContent className="pt-4">
        <h2 className="mb-2 text-base font-semibold text-foreground">Discipline de suivi</h2>
        <Tableau>
          <thead><tr>
            <th className={TH}>Membre</th><th className={TH}>Premier contact &lt; 5 min</th>
            <th className={TH}>Relances en retard</th><th className={TH}>Jamais contactés</th>
            <th className={TH}>En attente d’attribution</th>
          </tr></thead>
          <tbody>
            {lignesSuivi.map((l) => (
              <tr key={l.m ? l.m.id : 'equipe'} className={`border-t border-border ${l.m ? '' : 'border-t-2 font-bold'}`}>
                <td className={TD}>{l.m ? <NomMembre m={l.m} equipeId={equipeId} /> : 'Équipe'}</td>
                <td className={TD}>
                  {pctPremier(l.s)}
                  {l.s.premier_contact_mesures > 0 && (
                    <span className="ml-1 text-xs font-normal text-muted-foreground">({l.s.premier_contact_mesures} mesurés)</span>
                  )}
                </td>
                <td className={TD}>{l.s.relances_en_retard}</td>
                <td className={TD}>{l.s.leads_non_contactes}</td>
                <td className={TD}>{l.s.leads_en_attente}</td>
              </tr>
            ))}
          </tbody>
        </Tableau>
      </CardContent></Card>

      <Card><CardContent className="pt-4">
        <h2 className="mb-2 text-base font-semibold text-foreground">Pipeline</h2>
        <Tableau>
          <thead><tr>
            <th className={TH}>Membre</th><th className={TH}>Leads ouverts</th>
            <th className={TH}>Devis ouverts</th><th className={TH}>Valeur des devis ouverts</th>
          </tr></thead>
          <tbody>
            {lignesPipeline.map((l) => (
              <tr key={l.m ? l.m.id : 'equipe'} className={`border-t border-border ${l.m ? '' : 'border-t-2 font-bold'}`}>
                <td className={TD}>{l.m ? <NomMembre m={l.m} equipeId={equipeId} /> : 'Équipe'}</td>
                <td className={TD}>{l.p.leads_ouverts}</td>
                <td className={TD}>{l.p.devis_ouverts}</td>
                <td className={TD}>{formatMAD(l.p.valeur_devis_ouverts, { decimals: 0 })}</td>
              </tr>
            ))}
          </tbody>
        </Tableau>
      </CardContent></Card>

      {cible && (
        <DialogueObjectif cible={cible} periode={periode} onFermer={() => setCible(null)}
                          onEnregistre={() => { setCible(null); charger() }} />
      )}
    </div>
  )
}
