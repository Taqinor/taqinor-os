// CKP5 (fondateur 2026-09-10) — Vue ADHÉRENCE (stratégique) : est-ce que le
// protocole de relance est suivi, à l'heure, et où décroche-t-il. Visible par
// TOUS les rôles (décision transparence — mise en avant admin/responsable
// gérée par l'ORDRE des blocs dans `CrmCockpit.jsx`, jamais en cachant ce
// panneau). AUCUN seuil rouge/vert inventé : des valeurs et des tendances, le
// jugement reste humain (même règle que `KpiRelancesPanel.jsx`, dont ce
// panneau réutilise le socle — sélecteur de période, `Metric`, `dash`/`pct`).
import { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, Minus, Route } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import crmApi from '../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Spinner,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { STAGE_LABELS } from '../../features/crm/stages'

const PERIODES = [
  { value: '7', label: '7 jours' },
  { value: '30', label: '30 jours' },
  { value: '90', label: '90 jours' },
]

const CANAL_LABELS = {
  appel: 'Appel',
  whatsapp: 'WhatsApp',
  email: 'E-mail',
  visite: 'Visite',
}

// `null` (dénominateur 0, règle « aucun chiffre inventé ») → tiret, jamais 0.
const dash = (v) => (v === null || v === undefined ? '—' : v)
const pct = (v) => (v === null || v === undefined ? '—' : `${v} %`)

function Metric({ label, value, hint }) {
  return (
    <div className="rounded-lg border border-border bg-card p-2.5">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-display text-lg font-semibold tabular-nums">{value}</div>
      {hint && <div className="text-[11px] text-muted-foreground">{hint}</div>}
    </div>
  )
}

// Flèche de TENDANCE (premier point de la série vs dernier) — jamais un
// seuil rouge/vert : juste le sens du mouvement sur SA PROPRE base.
function FlecheTendance({ serie, cle }) {
  if (!Array.isArray(serie) || serie.length < 2) return null
  const premier = serie[0]?.[cle]
  const dernier = serie[serie.length - 1]?.[cle]
  if (premier == null || dernier == null || premier === dernier) {
    return <Minus className="inline size-3.5 text-muted-foreground" aria-label="stable" />
  }
  return dernier > premier
    ? <TrendingUp className="inline size-3.5 text-success" aria-label="en hausse" />
    : <TrendingDown className="inline size-3.5 text-danger" aria-label="en baisse" />
}

// Petites barres simples (valeurs affichées à côté) — aucune librairie de
// graphique ajoutée : des `<div>` dont la largeur porte la valeur, bornée au
// maximum de la série.
function BarresSimple({ serie, cle, libelleCle, suffixe = '' }) {
  if (!Array.isArray(serie) || serie.length === 0) {
    return <p className="text-xs text-muted-foreground">—</p>
  }
  const max = Math.max(...serie.map((p) => Number(p[cle]) || 0), 1)
  return (
    <ul className="flex flex-col gap-1">
      {serie.map((point) => (
        <li key={point[libelleCle]} className="flex items-center gap-2 text-xs">
          <span className="w-20 shrink-0 text-muted-foreground">{point[libelleCle]}</span>
          <span className="h-2 flex-1 overflow-hidden rounded bg-muted">
            <span
              className="block h-full rounded bg-primary"
              style={{ width: `${Math.min(100, ((Number(point[cle]) || 0) / max) * 100)}%` }}
            />
          </span>
          <span className="w-14 shrink-0 text-right tabular-nums">
            {point[cle] == null ? '—' : `${point[cle]}${suffixe}`}
          </span>
        </li>
      ))}
    </ul>
  )
}

export default function AdherenceRelancesPanel() {
  const navigate = useNavigate()
  const [jours, setJours] = useState('30')
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [donnees, setDonnees] = useState(null)

  useEffect(() => {
    let active = true
    queueMicrotask(() => { if (active) { setLoading(true); setErreur(false) } })
    crmApi.getKpiAdherence({ jours })
      .then((r) => { if (active) setDonnees(r.data) })
      .catch(() => { if (active) setErreur(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [jours])

  return (
    <Card data-testid="adherence-relances-panel">
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Route className="h-4 w-4" /> Adhérence au protocole de relance
          </CardTitle>
          <CardDescription>
            Suivi, à l&apos;heure, drop-off — mêmes chiffres pour tous les rôles.
          </CardDescription>
        </div>
        <Select value={jours} onValueChange={setJours}>
          <SelectTrigger className="w-28" aria-label="Période"><SelectValue /></SelectTrigger>
          <SelectContent>
            {PERIODES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {loading ? (
          <Spinner />
        ) : erreur ? (
          <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Metric label="À l'heure" value={pct(donnees?.a_lheure_pct)} />
              <Metric label="Touches faites" value={dash(donnees?.touches_faites)} />
              <Metric label="Retards ouverts" value={dash(donnees?.touches_en_retard_ouvertes)} />
              <Metric
                label="Vitesse 1er contact (médiane)"
                value={dash(donnees?.vitesse_premier_contact?.mediane_heures)}
                hint={donnees?.vitesse_premier_contact?.mediane_heures != null ? 'heures' : undefined}
              />
              {/* Colonnes SÉPARÉES (jamais fondues) : un arrêt du moteur
                  n'est jamais un manquement humain. */}
              <Metric label="Sautées humaines" value={dash(donnees?.sautees_humaines)} />
              <Metric label="Annulées (moteur)" value={dash(donnees?.annulees_moteur)} />
            </div>

            <section>
              <h3 className="mb-1.5 text-sm font-semibold">Drop-off par touche</h3>
              {Array.isArray(donnees?.par_etape) && donnees.par_etape.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="py-1 pr-2">Ordre</th>
                        <th className="py-1 pr-2">Canal</th>
                        <th className="py-1 pr-2">Libellé</th>
                        <th className="py-1 pr-2 text-right">Faites</th>
                        <th className="py-1 pr-2 text-right">À l&apos;heure</th>
                        <th className="py-1 pr-2 text-right">Sautées (humaines)</th>
                        <th className="py-1 text-right">Annulées (moteur)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {donnees.par_etape.map((etape) => (
                        <tr key={`${etape.ordre}-${etape.canal}`} className="border-b border-border/50">
                          <td className="py-1 pr-2">{etape.ordre}</td>
                          <td className="py-1 pr-2">{CANAL_LABELS[etape.canal] ?? etape.canal}</td>
                          <td className="py-1 pr-2">{etape.libelle}</td>
                          <td className="py-1 pr-2 text-right tabular-nums">{dash(etape.faites)}</td>
                          <td className="py-1 pr-2 text-right tabular-nums">{pct(etape.a_lheure_pct)}</td>
                          <td className="py-1 pr-2 text-right tabular-nums">{dash(etape.sautees_humaines)}</td>
                          <td className="py-1 text-right tabular-nums">{dash(etape.annulees_moteur)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <p className="text-xs text-muted-foreground">—</p>}
            </section>

            <div className="grid gap-4 sm:grid-cols-2">
              <section>
                <h3 className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold">
                  Tendance hebdo à l&apos;heure
                  <FlecheTendance serie={donnees?.tendance_a_lheure} cle="a_lheure_pct" />
                </h3>
                <BarresSimple
                  serie={donnees?.tendance_a_lheure} cle="a_lheure_pct"
                  libelleCle="semaine" suffixe=" %"
                />
              </section>
              <section>
                <h3 className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold">
                  Vitesse premier contact (médiane, heures)
                  <FlecheTendance
                    serie={donnees?.vitesse_premier_contact?.tendance_hebdo} cle="mediane_heures"
                  />
                </h3>
                <BarresSimple
                  serie={donnees?.vitesse_premier_contact?.tendance_hebdo} cle="mediane_heures"
                  libelleCle="semaine" suffixe=" h"
                />
              </section>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <section>
                <h3 className="mb-1.5 text-sm font-semibold">Leads sans touche due</h3>
                {Array.isArray(donnees?.leads_sans_touche) && donnees.leads_sans_touche.length > 0 ? (
                  <ul className="flex flex-col gap-1">
                    {donnees.leads_sans_touche.map((lead) => (
                      <li key={lead.lead_id}>
                        <button
                          type="button"
                          className="w-full rounded-md border border-border p-1.5 text-left text-xs hover:bg-muted"
                          onClick={() => navigate(`/crm/leads?lead=${lead.lead_id}`)}
                        >
                          <span className="font-medium">{lead.nom}</span>
                          {lead.ville ? ` · ${lead.ville}` : ''}
                          <span className="block text-muted-foreground">
                            {lead.prochaine_touche} — en retard depuis {lead.en_retard_depuis_heures} h
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : <p className="text-xs text-muted-foreground">Aucun lead sans touche due.</p>}
              </section>
              <section>
                <h3 className="mb-1.5 text-sm font-semibold">Conversion par étape</h3>
                {Array.isArray(donnees?.conversion_par_stage) && donnees.conversion_par_stage.length > 0 ? (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="py-1 pr-2">Étape</th>
                        <th className="py-1 pr-2 text-right">Entrés</th>
                        <th className="py-1 pr-2 text-right">Passés au suivant</th>
                        <th className="py-1 text-right">Taux</th>
                      </tr>
                    </thead>
                    <tbody>
                      {donnees.conversion_par_stage.map((ligne) => (
                        <tr key={ligne.stage} className="border-b border-border/50">
                          <td className="py-1 pr-2">{STAGE_LABELS[ligne.stage] ?? ligne.stage}</td>
                          <td className="py-1 pr-2 text-right tabular-nums">{dash(ligne.entres)}</td>
                          <td className="py-1 pr-2 text-right tabular-nums">{dash(ligne.passes_au_suivant)}</td>
                          <td className="py-1 text-right tabular-nums">{pct(ligne.taux_pct)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : <p className="text-xs text-muted-foreground">—</p>}
              </section>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
