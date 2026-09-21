import { useCallback, useEffect, useMemo, useState } from 'react'
import fpaApi from '../../api/fpaApi'
import { Button, Card, toast } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   NTFPA17 — Écran Scénarios côte-à-côte.
   ----------------------------------------------------------------------------
   Sélection multi-scénario, tableau comparatif (base + une colonne par
   scénario, écart total annuel), bouton "Promouvoir en budget de base" (copie
   les deltas dans les lignes réelles du cycle, réservé FP&A/Directeur). La
   promotion crée un audit-log et fige l'ancien budget de base en archivé.

   WIR199 — le module était structurellement inamorçable : aucun scénario
   n'était créable depuis l'UI (`fpaApi.createScenario` sans appelant), les
   deltas d'un scénario (`LigneScenario`) n'avaient ni liste ni formulaire, et
   le panneau de sensibilité (NTFPA18, `fpaApi.sensibilite`) n'existait nulle
   part. Les trois blocs ci-dessous complètent l'écran SANS toucher au
   comparatif existant.
   ========================================================================== */

const CATEGORIES = [
  ['', '— Catégorie ciblée (optionnel) —'],
  ['masse_salariale', 'Masse salariale'],
  ['marketing', 'Marketing'],
  ['it', 'IT'],
  ['frais_generaux', 'Frais généraux'],
  ['investissement', 'Investissement'],
  ['autre', 'Autre'],
]

function listeDe(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}

function messageErreur(err, repli) {
  const data = err?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  return repli
}

export default function ScenariosPage() {
  const [cycles, setCycles] = useState([])
  const [cycleId, setCycleId] = useState('')
  const [scenarios, setScenarios] = useState([])
  const [selection, setSelection] = useState([])
  const [comparaison, setComparaison] = useState(null)
  const [error, setError] = useState(null)

  // WIR199 — création d'un scénario.
  const [nomScenario, setNomScenario] = useState('')
  const [descriptionScenario, setDescriptionScenario] = useState('')
  const [occupe, setOccupe] = useState(false)

  // WIR199 — lignes de delta d'un scénario (panneau dépliable).
  const [scenarioOuvert, setScenarioOuvert] = useState(null)
  const [lignes, setLignes] = useState([])
  const [categorieDelta, setCategorieDelta] = useState('')
  const [deltaPct, setDeltaPct] = useState('')
  const [deltaMontant, setDeltaMontant] = useState('')
  const [raisonDelta, setRaisonDelta] = useState('')

  // WIR199 — panneau de sensibilité (NTFPA18).
  const [variableSensibilite, setVariableSensibilite] = useState('taux_conversion')
  const [plageSensibilite, setPlageSensibilite] = useState(20)
  const [pointsSensibilite, setPointsSensibilite] = useState(null)

  const chargerScenarios = useCallback(() => {
    if (!cycleId) return Promise.resolve()
    return fpaApi.getScenarios({ cycle: cycleId })
      .then((res) => setScenarios(listeDe(res.data)))
      .catch(() => setError('Impossible de charger les scénarios.'))
  }, [cycleId])

  useEffect(() => {
    fpaApi.getCycles()
      .then((res) => setCycles(listeDe(res.data)))
      .catch(() => setError('Impossible de charger les cycles.'))
  }, [])

  useEffect(() => { chargerScenarios() }, [chargerScenarios])

  const toggle = (id) => {
    setSelection((prev) => (
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const comparer = async () => {
    setError(null)
    try {
      const res = await fpaApi.comparerScenarios({
        cycle: cycleId, scenarios: selection.join(','),
      })
      setComparaison(res.data)
    } catch {
      setError('La comparaison a échoué.')
    }
  }

  const promouvoir = async (id) => {
    setError(null)
    try {
      await fpaApi.promouvoirScenario(id)
      await chargerScenarios()
    } catch {
      setError('La promotion a échoué (droit FP&A/Directeur requis ?).')
    }
  }

  const creerScenario = async () => {
    if (!cycleId || !nomScenario.trim() || occupe) return
    setOccupe(true)
    try {
      await fpaApi.createScenario({
        cycle: cycleId, nom: nomScenario.trim(), description: descriptionScenario.trim(),
      })
      setNomScenario(''); setDescriptionScenario('')
      toast.success('Scénario créé.')
      await chargerScenarios()
    } catch (err) {
      toast.error(messageErreur(err, 'La création du scénario a échoué.'))
    } finally {
      setOccupe(false)
    }
  }

  const ouvrirLignes = async (scenario) => {
    if (scenarioOuvert === scenario.id) {
      setScenarioOuvert(null)
      setLignes([])
      return
    }
    setScenarioOuvert(scenario.id)
    try {
      const res = await fpaApi.getLignesScenario({ scenario: scenario.id })
      setLignes(listeDe(res.data))
    } catch {
      setLignes([])
      toast.error('Impossible de charger les lignes de ce scénario.')
    }
  }

  const ajouterLigne = async () => {
    if (!scenarioOuvert || occupe) return
    if (!categorieDelta && !deltaPct && !deltaMontant) {
      toast.error('Renseignez au moins une catégorie ou un delta.')
      return
    }
    setOccupe(true)
    try {
      await fpaApi.createLigneScenario({
        scenario: scenarioOuvert,
        categorie: categorieDelta,
        delta_pct: deltaPct === '' ? null : deltaPct,
        delta_montant: deltaMontant === '' ? null : deltaMontant,
        raison: raisonDelta.trim(),
      })
      setCategorieDelta(''); setDeltaPct(''); setDeltaMontant(''); setRaisonDelta('')
      toast.success('Ligne de delta ajoutée.')
      const res = await fpaApi.getLignesScenario({ scenario: scenarioOuvert })
      setLignes(listeDe(res.data))
    } catch (err) {
      toast.error(messageErreur(err, "L'ajout de la ligne a échoué."))
    } finally {
      setOccupe(false)
    }
  }

  const calculerSensibilite = async () => {
    if (!cycleId) return
    try {
      const res = await fpaApi.sensibilite({
        cycle: cycleId, variable: variableSensibilite, plage: plageSensibilite,
      })
      setPointsSensibilite(res.data?.points ?? [])
    } catch {
      toast.error("Le calcul de sensibilité a échoué.")
      setPointsSensibilite(null)
    }
  }

  const base = useMemo(
    () => (comparaison ? Number(comparaison.base || 0) : 0), [comparaison])

  return (
    <div>
      <PageHeader
        title="Scénarios what-if"
        subtitle="Comparaison côte-à-côte et promotion en budget de base"
        actions={
          <Button onClick={comparer} disabled={!cycleId || selection.length === 0}>
            Comparer ({selection.length})
          </Button>
        }
      />
      <div style={{ marginBottom: 16 }}>
        <select
          aria-label="Cycle budgétaire"
          value={cycleId}
          onChange={(e) => { setCycleId(e.target.value); setSelection([]); setComparaison(null) }}
        >
          <option value="">— Cycle budgétaire —</option>
          {cycles.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
        </select>
      </div>
      {error && <p role="alert" style={{ color: 'var(--danger, #c00)' }}>{error}</p>}
      <Card>
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {scenarios.map((s) => (
            <li key={s.id} style={{ padding: 6, borderBottom: '1px solid var(--border, #e5e7eb)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="checkbox"
                  aria-label={`Sélectionner ${s.nom}`}
                  checked={selection.includes(s.id)}
                  onChange={() => toggle(s.id)}
                />
                <span style={{ flex: 1 }}>
                  {s.nom}
                  {s.est_scenario_base && (
                    <strong style={{ marginLeft: 8, fontSize: 12 }}>(base)</strong>
                  )}
                </span>
                <Button variant="ghost" size="sm" onClick={() => ouvrirLignes(s)}>
                  {scenarioOuvert === s.id ? 'Fermer les lignes' : 'Lignes de delta'}
                </Button>
                {!s.est_scenario_base && (
                  <Button variant="ghost" onClick={() => promouvoir(s.id)}>
                    Promouvoir en base
                  </Button>
                )}
              </div>
              {scenarioOuvert === s.id && (
                <div style={{ marginTop: 8, marginLeft: 24 }}>
                  {lignes.length === 0 ? (
                    <p style={{ fontSize: 13, opacity: 0.7 }}>Aucun delta pour ce scénario.</p>
                  ) : (
                    <ul style={{ listStyle: 'none', padding: 0, marginBottom: 8 }}>
                      {lignes.map((l) => (
                        <li key={l.id} style={{ fontSize: 13, padding: 2 }}>
                          {l.categorie || `ligne #${l.ligne_budget}`}
                          {l.delta_pct != null && ` — ${l.delta_pct}%`}
                          {l.delta_montant != null && ` — ${formatMAD(Number(l.delta_montant))}`}
                          {l.raison && ` (${l.raison})`}
                        </li>
                      ))}
                    </ul>
                  )}
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <select
                      aria-label="Catégorie du delta"
                      value={categorieDelta}
                      onChange={(e) => setCategorieDelta(e.target.value)}
                    >
                      {CATEGORIES.map(([val, label]) => (
                        <option key={val} value={val}>{label}</option>
                      ))}
                    </select>
                    <input
                      type="number" step="any"
                      aria-label="Delta en pourcentage"
                      placeholder="Delta %"
                      value={deltaPct}
                      onChange={(e) => setDeltaPct(e.target.value)}
                      style={{ width: 90 }}
                    />
                    <input
                      type="number" step="any"
                      aria-label="Delta en montant"
                      placeholder="Delta montant"
                      value={deltaMontant}
                      onChange={(e) => setDeltaMontant(e.target.value)}
                      style={{ width: 110 }}
                    />
                    <input
                      aria-label="Raison du delta"
                      placeholder="Raison"
                      value={raisonDelta}
                      onChange={(e) => setRaisonDelta(e.target.value)}
                    />
                    <Button size="sm" onClick={ajouterLigne} disabled={occupe}>
                      Ajouter la ligne
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <input
            aria-label="Nom du scénario"
            placeholder="Nom du nouveau scénario"
            value={nomScenario}
            onChange={(e) => setNomScenario(e.target.value)}
          />
          <input
            aria-label="Description du scénario"
            placeholder="Description (optionnel)"
            value={descriptionScenario}
            onChange={(e) => setDescriptionScenario(e.target.value)}
          />
          <Button onClick={creerScenario} disabled={occupe || !cycleId || !nomScenario.trim()}>
            Créer le scénario
          </Button>
        </div>
      </Card>
      {comparaison && (
        <Card>
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: 8 }}>Scénario</th>
                <th style={{ padding: 8 }}>Total</th>
                <th style={{ padding: 8 }}>Écart vs base</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ padding: 8, fontWeight: 700 }}>Budget de base</td>
                <td style={{ padding: 8 }}>{formatMAD(base)}</td>
                <td style={{ padding: 8 }}>—</td>
              </tr>
              {comparaison.scenarios.map((r) => (
                <tr key={r.id}>
                  <td style={{ padding: 8 }}>{r.nom}</td>
                  <td style={{ padding: 8 }}>{formatMAD(Number(r.total || 0))}</td>
                  <td style={{ padding: 8 }}>{formatMAD(Number(r.ecart || 0))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      <Card>
        <h3 style={{ marginBottom: 8 }}>Analyse de sensibilité</h3>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
          <input
            aria-label="Variable de sensibilité"
            placeholder="Variable (ex. taux_conversion)"
            value={variableSensibilite}
            onChange={(e) => setVariableSensibilite(e.target.value)}
          />
          <input
            type="number"
            aria-label="Plage de variation (%)"
            value={plageSensibilite}
            onChange={(e) => setPlageSensibilite(e.target.value)}
            style={{ width: 80 }}
          />
          <Button onClick={calculerSensibilite} disabled={!cycleId}>
            Calculer
          </Button>
        </div>
        {pointsSensibilite && (
          pointsSensibilite.length === 0 ? (
            <p style={{ fontSize: 13, opacity: 0.7 }}>Aucun point calculé.</p>
          ) : (
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: 8 }}>Variation</th>
                  <th style={{ padding: 8 }}>Revenu total</th>
                </tr>
              </thead>
              <tbody>
                {pointsSensibilite.map((p) => (
                  <tr key={p.variation_pct}>
                    <td style={{ padding: 8 }}>{p.variation_pct > 0 ? `+${p.variation_pct}` : p.variation_pct}%</td>
                    <td style={{ padding: 8 }}>{formatMAD(Number(p.revenu_total || 0))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </Card>
    </div>
  )
}
