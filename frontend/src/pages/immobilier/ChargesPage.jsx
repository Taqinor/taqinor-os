import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Bar, BarChart, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  CHART_TOKENS, resolveColor, animationDuration, CHART_ANIM_EASING,
} from '../../ui/charts/chart-theme.js'
import { ChartTooltip } from '../../ui/charts/ChartTooltip.jsx'
import { formatMAD, formatPercent } from '../../lib/format.js'
import immobilierApi from '../../api/immobilierApi'

/* ============================================================================
   NTPRO14 — Budget de charges (`/immobilier/charges`).
   ----------------------------------------------------------------------------
   Sélection bâtiment + exercice → tableau par poste (budgété/réel/écart%) +
   barres empilées budgété/réel, puis « Lancer la régularisation » : NTPRO13
   `generer-regularisation` calcule un APERÇU (baux impactés + sens, RIEN
   n'est encore émis côté ventes) qu'on affiche pour confirmation explicite
   AVANT que « Confirmer l'émission » n'appelle `emettre` — jamais les deux
   étapes fusionnées silencieusement.
   ========================================================================== */

function rowsFrom(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

export default function ChargesPage() {
  const [batiments, setBatiments] = useState([])
  const [batimentId, setBatimentId] = useState('')
  const [exercice, setExercice] = useState(String(new Date().getFullYear()))

  const [lignes, setLignes] = useState([])
  const [loading, setLoading] = useState(false)
  const [erreur, setErreur] = useState(null)

  const [apercu, setApercu] = useState(null) // liste RegularisationCharges
  const [apercuLoading, setApercuLoading] = useState(false)
  const [apercuErreur, setApercuErreur] = useState(null)
  const [emisIds, setEmisIds] = useState(() => new Set())
  const [emissionLoading, setEmissionLoading] = useState(false)

  useEffect(() => {
    immobilierApi.batiments.list().then((res) => setBatiments(rowsFrom(res.data)))
  }, [])

  // Chargement déclenché depuis le handler du bouton (pas d'effet keyé sur
  // batimentId/exercice) : évite tout setState synchrone au montage
  // (react-hooks/set-state-in-effect, même motif que RentabiliteActif.jsx).
  const latestRef = useRef(null)

  const charger = useCallback(async () => {
    if (!batimentId || !exercice) return
    const cle = `${batimentId}:${exercice}`
    latestRef.current = cle
    setLoading(true)
    setErreur(null)
    setApercu(null)
    setEmisIds(new Set())
    try {
      const resBudgets = await immobilierApi.budgetsCharges.list({
        batiment: batimentId, exercice,
      })
      const budgets = rowsFrom(resBudgets.data)
      const consommations = await Promise.all(
        budgets.map((b) => immobilierApi.budgetsCharges.consommation(b.id)),
      )
      if (latestRef.current !== cle) return
      setLignes(budgets.map((b, i) => ({
        id: b.id,
        poste: b.poste,
        poste_display: b.poste_display,
        budgete: Number(b.montant_budgete_annuel),
        reel: Number(consommations[i].data.total_reel),
        ecart_pct: consommations[i].data.ecart_pct,
      })))
    } catch {
      if (latestRef.current === cle) setErreur('Chargement des charges impossible.')
    } finally {
      if (latestRef.current === cle) setLoading(false)
    }
  }, [batimentId, exercice])

  const lancerRegularisation = useCallback(async () => {
    if (!batimentId || !exercice) return
    setApercuLoading(true)
    setApercuErreur(null)
    try {
      const res = await immobilierApi.batiments.genererRegularisation(
        batimentId, { exercice: Number(exercice) },
      )
      setApercu(res.data)
      setEmisIds(new Set())
    } catch {
      setApercuErreur('Calcul de la régularisation impossible.')
    } finally {
      setApercuLoading(false)
    }
  }, [batimentId, exercice])

  const confirmerEmission = useCallback(async () => {
    if (!apercu) return
    setEmissionLoading(true)
    const nouveauxEmis = new Set(emisIds)
    for (const ligne of apercu) {
      if (ligne.sens === 'neutre' || nouveauxEmis.has(ligne.id)) continue
      try {
        // eslint-disable-next-line no-await-in-loop -- émission séquentielle
        // volontaire (jamais N requêtes concurrentes non contrôlées vers ventes).
        await immobilierApi.regularisationsCharges.emettre(ligne.id)
        nouveauxEmis.add(ligne.id)
      } catch {
        // Best-effort : une émission en échec n'empêche pas les suivantes ;
        // `emisIds` reflète exactement ce qui a réellement été émis.
      }
    }
    setEmisIds(nouveauxEmis)
    setEmissionLoading(false)
  }, [apercu, emisIds])

  const dur = animationDuration()
  const colorBudgete = resolveColor('muted')
  const colorReel = resolveColor('primary')
  const axisTick = { fontSize: 11, fill: CHART_TOKENS.axis }

  const documentsAEmettre = apercu
    ? apercu.filter((l) => l.sens !== 'neutre' && !emisIds.has(l.id))
    : []

  return (
    <div data-testid="charges-page" style={{ padding: 16 }}>
      <h1>Budget de charges</h1>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 16 }}>
        <select
          aria-label="Sélectionner un bâtiment"
          value={batimentId}
          onChange={(e) => setBatimentId(e.target.value)}
        >
          <option value="">— Sélectionner un bâtiment —</option>
          {batiments.map((b) => (
            <option key={b.id} value={b.id}>{b.nom}</option>
          ))}
        </select>
        <label>
          Exercice{' '}
          <input
            type="number"
            aria-label="Exercice"
            value={exercice}
            onChange={(e) => setExercice(e.target.value)}
            style={{ width: 90 }}
          />
        </label>
        <button type="button" onClick={charger} disabled={!batimentId || loading}>
          Charger
        </button>
      </div>

      {loading && <p>Chargement…</p>}
      {erreur && <p role="alert">{erreur}</p>}

      {lignes.length > 0 && (
        <>
          <table data-testid="table-charges" style={{ marginBottom: 24 }}>
            <thead>
              <tr>
                <th>Poste</th>
                <th>Budgété</th>
                <th>Réel</th>
                <th>Écart %</th>
              </tr>
            </thead>
            <tbody>
              {lignes.map((l) => (
                <tr key={l.id}>
                  <td>{l.poste_display}</td>
                  <td>{formatMAD(l.budgete)}</td>
                  <td>{formatMAD(l.reel)}</td>
                  <td>{l.ecart_pct === null ? '—' : formatPercent(l.ecart_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div data-testid="graphique-budget-reel" style={{ marginBottom: 24 }}>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                data={lignes.map((l) => ({
                  poste: l.poste_display,
                  Budgété: l.budgete,
                  Réel: l.reel,
                }))}
                margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
              >
                <XAxis dataKey="poste" tick={axisTick} tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} hide />
                <Tooltip
                  cursor={{ fill: 'var(--muted)' }}
                  content={<ChartTooltip format={(v) => formatMAD(v)} />}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar
                  dataKey="Budgété" stackId="charges" fill={colorBudgete}
                  isAnimationActive={dur > 0} animationDuration={dur}
                  animationEasing={CHART_ANIM_EASING}
                />
                <Bar
                  dataKey="Réel" stackId="charges" fill={colorReel}
                  isAnimationActive={dur > 0} animationDuration={dur}
                  animationEasing={CHART_ANIM_EASING}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <button type="button" onClick={lancerRegularisation} disabled={apercuLoading}>
            Lancer la régularisation
          </button>
        </>
      )}

      {apercuErreur && <p role="alert">{apercuErreur}</p>}

      {apercu && (
        <div data-testid="apercu-regularisation" style={{ marginTop: 16 }}>
          <h2>Aperçu de la régularisation {exercice}</h2>
          <p>
            {documentsAEmettre.length === 0
              ? 'Aucun document à émettre (tous les soldes sont neutres ou déjà émis).'
              : `${documentsAEmettre.length} document(s) seront créés à la confirmation.`}
          </p>
          <table>
            <thead>
              <tr>
                <th>Bail</th>
                <th>Locataire</th>
                <th>Solde</th>
                <th>Sens</th>
                <th>Statut</th>
              </tr>
            </thead>
            <tbody>
              {apercu.map((l) => (
                <tr key={l.id}>
                  <td>{l.bail_local_reference}</td>
                  <td>{l.bail_locataire_nom}</td>
                  <td>{formatMAD(l.solde)}</td>
                  <td>{l.sens_display}</td>
                  <td>
                    {l.sens === 'neutre'
                      ? 'Aucun document'
                      : emisIds.has(l.id)
                        ? 'Émis'
                        : 'À émettre'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            type="button"
            onClick={confirmerEmission}
            disabled={emissionLoading || documentsAEmettre.length === 0}
          >
            Confirmer l&apos;émission
          </button>
        </div>
      )}
    </div>
  )
}
