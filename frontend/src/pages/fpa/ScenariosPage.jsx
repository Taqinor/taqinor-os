import { useEffect, useMemo, useState } from 'react'
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

   WIR199 — l'écran était structurellement vide : aucun scénario n'était
   CRÉABLE (createScenario jamais appelé), les lignes de delta d'un scénario
   n'étaient jamais visibles ni ajoutables (getLignesScenario/
   createLigneScenario), et le panneau de sensibilité (analyse_sensibilite,
   NTFPA18) n'était consommé nulle part.
   ========================================================================== */

function messageErreurScenario(err, repli) {
  const data = err?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (typeof data === 'string' && data) return data
  return repli
}

const CATEGORIES = [
  ['', '— Catégorie —'],
  ['masse_salariale', 'Masse salariale'],
  ['marketing', 'Marketing'],
  ['it', 'IT'],
  ['frais_generaux', 'Frais généraux'],
  ['investissement', 'Investissement'],
  ['autre', 'Autre'],
]

export default function ScenariosPage() {
  const [cycles, setCycles] = useState([])
  const [cycleId, setCycleId] = useState('')
  const [scenarios, setScenarios] = useState([])
  const [selection, setSelection] = useState([])
  const [comparaison, setComparaison] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fpaApi.getCycles()
      .then((res) => setCycles(
        Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les cycles.'))
  }, [])

  const chargerScenarios = () => {
    if (!cycleId) return
    fpaApi.getScenarios({ cycle: cycleId })
      .then((res) => setScenarios(
        Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les scénarios.'))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { chargerScenarios() }, [cycleId])

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
      toast.success('Scénario promu en budget de base.')
      chargerScenarios()
    } catch (err) {
      toast.error(messageErreurScenario(err, 'La promotion a échoué (droit FP&A/Directeur requis ?).'))
    }
  }

  // ── WIR199 — création d'un scénario (jusqu'ici l'écran ne pouvait QUE
  // lister des scénarios déjà créés en admin Django). ──────────────────────
  const [nouveauNom, setNouveauNom] = useState('')
  const [creantScenario, setCreantScenario] = useState(false)

  const creerScenario = async () => {
    if (!cycleId || !nouveauNom.trim()) return
    setCreantScenario(true)
    try {
      await fpaApi.createScenario({ cycle: cycleId, nom: nouveauNom.trim() })
      toast.success('Scénario créé.')
      setNouveauNom('')
      chargerScenarios()
    } catch (err) {
      toast.error(messageErreurScenario(err, 'Création du scénario impossible.'))
    } finally {
      setCreantScenario(false)
    }
  }

  // ── WIR199 — lignes de delta d'un scénario ouvert (jamais consommées
  // jusqu'ici : `getLignesScenario`/`createLigneScenario` existaient côté
  // API sans aucun appelant). ──────────────────────────────────────────────
  const [scenarioOuvertId, setScenarioOuvertId] = useState(null)
  const [lignesDelta, setLignesDelta] = useState([])
  const [deltaForm, setDeltaForm] = useState({ categorie: '', delta_pct: '', delta_montant: '', raison: '' })
  const [ajoutantDelta, setAjoutantDelta] = useState(false)

  const ouvrirScenario = async (id) => {
    setScenarioOuvertId(id)
    try {
      const res = await fpaApi.getLignesScenario({ scenario: id })
      setLignesDelta(Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
    } catch {
      setLignesDelta([])
      toast.error('Lignes de delta indisponibles.')
    }
  }

  const ajouterLigneDelta = async () => {
    if (!scenarioOuvertId) return
    setAjoutantDelta(true)
    try {
      await fpaApi.createLigneScenario({
        scenario: scenarioOuvertId,
        categorie: deltaForm.categorie || undefined,
        delta_pct: deltaForm.delta_pct || undefined,
        delta_montant: deltaForm.delta_montant || undefined,
        raison: deltaForm.raison,
      })
      toast.success('Ligne de delta ajoutée.')
      setDeltaForm({ categorie: '', delta_pct: '', delta_montant: '', raison: '' })
      const res = await fpaApi.getLignesScenario({ scenario: scenarioOuvertId })
      setLignesDelta(Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
    } catch (err) {
      toast.error(messageErreurScenario(err, "Ajout de la ligne de delta impossible."))
    } finally {
      setAjoutantDelta(false)
    }
  }

  // ── WIR199 — panneau de sensibilité (NTFPA18), jamais rendu jusqu'ici. ──
  const [variableSensi, setVariableSensi] = useState('taux_conversion')
  const [plageSensi, setPlageSensi] = useState('20')
  const [pointsSensi, setPointsSensi] = useState(null)
  const [chargeantSensi, setChargeantSensi] = useState(false)

  const analyserSensibilite = async () => {
    if (!cycleId) return
    setChargeantSensi(true)
    try {
      const res = await fpaApi.sensibilite({ cycle: cycleId, variable: variableSensi, plage: plageSensi })
      setPointsSensi(res.data?.points ?? [])
    } catch (err) {
      toast.error(messageErreurScenario(err, 'Analyse de sensibilité impossible.'))
      setPointsSensi(null)
    } finally {
      setChargeantSensi(false)
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
      <div style={{ marginBottom: 16, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <select
          aria-label="Cycle budgétaire"
          value={cycleId}
          onChange={(e) => {
            setCycleId(e.target.value); setSelection([]); setComparaison(null)
            setScenarioOuvertId(null); setPointsSensi(null)
          }}
        >
          <option value="">— Cycle budgétaire —</option>
          {cycles.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
        </select>
        {/* WIR199 — création d'un scénario sur le cycle sélectionné. */}
        <input
          placeholder="Nom du nouveau scénario"
          aria-label="Nom du nouveau scénario"
          value={nouveauNom}
          onChange={(e) => setNouveauNom(e.target.value)}
          disabled={!cycleId}
        />
        <Button variant="outline" onClick={creerScenario} disabled={!cycleId || !nouveauNom.trim() || creantScenario}>
          {creantScenario ? 'Création…' : 'Créer le scénario'}
        </Button>
      </div>
      {error && <p role="alert" style={{ color: 'var(--danger, #c00)' }}>{error}</p>}
      <Card>
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {scenarios.map((s) => (
            <li key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 6 }}>
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
              <Button variant="ghost" onClick={() => ouvrirScenario(s.id)}>
                Lignes de delta
              </Button>
              {!s.est_scenario_base && (
                <Button variant="ghost" onClick={() => promouvoir(s.id)}>
                  Promouvoir en base
                </Button>
              )}
            </li>
          ))}
          {scenarios.length === 0 && (
            <li style={{ padding: 8, color: 'var(--muted-foreground, #64748b)' }}>
              Aucun scénario pour ce cycle.
            </li>
          )}
        </ul>
      </Card>

      {/* WIR199 — lignes de delta du scénario ouvert : appliquées en
          LECTURE seulement (jamais écrites dans le cycle réel — le seul
          chemin d'écriture reste « Promouvoir en base »). */}
      {scenarioOuvertId && (
        <Card data-testid="fpa-scenario-deltas">
          <h3 style={{ fontSize: 14, fontWeight: 600, padding: '8px 8px 0' }}>Lignes de delta</h3>
          <ul style={{ listStyle: 'none', padding: 8 }}>
            {lignesDelta.map((l) => (
              <li key={l.id} style={{ padding: 4 }}>
                {(CATEGORIES.find(([v]) => v === l.categorie)?.[1]) || l.categorie || '—'}
                {' '}
                {l.delta_pct != null && `${l.delta_pct}%`}
                {l.delta_montant != null && ` ${formatMAD(Number(l.delta_montant))}`}
                {l.raison && ` — ${l.raison}`}
              </li>
            ))}
            {lignesDelta.length === 0 && (
              <li style={{ color: 'var(--muted-foreground, #64748b)' }}>Aucune ligne de delta.</li>
            )}
          </ul>
          <div style={{ display: 'flex', gap: 8, padding: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <select
              aria-label="Catégorie du delta"
              value={deltaForm.categorie}
              onChange={(e) => setDeltaForm((f) => ({ ...f, categorie: e.target.value }))}
            >
              {CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <input
              type="number" step="any"
              placeholder="Delta %"
              aria-label="Delta pourcentage"
              value={deltaForm.delta_pct}
              onChange={(e) => setDeltaForm((f) => ({ ...f, delta_pct: e.target.value }))}
              style={{ width: 90 }}
            />
            <input
              type="number" step="any"
              placeholder="Delta montant"
              aria-label="Delta montant"
              value={deltaForm.delta_montant}
              onChange={(e) => setDeltaForm((f) => ({ ...f, delta_montant: e.target.value }))}
              style={{ width: 110 }}
            />
            <input
              placeholder="Raison"
              aria-label="Raison du delta"
              value={deltaForm.raison}
              onChange={(e) => setDeltaForm((f) => ({ ...f, raison: e.target.value }))}
            />
            <Button variant="outline" onClick={ajouterLigneDelta} disabled={ajoutantDelta}>
              {ajoutantDelta ? 'Ajout…' : 'Ajouter la ligne'}
            </Button>
          </div>
        </Card>
      )}

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

      {/* WIR199 — panneau de sensibilité (NTFPA18, `analyse_sensibilite`),
          jamais rendu par aucun écran jusqu'ici. */}
      <Card data-testid="fpa-sensibilite" style={{ marginTop: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, padding: '8px 8px 0' }}>Analyse de sensibilité</h3>
        <div style={{ display: 'flex', gap: 8, padding: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            aria-label="Variable de sensibilité"
            value={variableSensi}
            onChange={(e) => setVariableSensi(e.target.value)}
          >
            <option value="taux_conversion">Taux de conversion</option>
          </select>
          <input
            type="number" step="1" min="5"
            aria-label="Plage de variation (%)"
            value={plageSensi}
            onChange={(e) => setPlageSensi(e.target.value)}
            style={{ width: 70 }}
          />
          <Button variant="outline" onClick={analyserSensibilite} disabled={!cycleId || chargeantSensi}>
            {chargeantSensi ? 'Calcul…' : 'Analyser'}
          </Button>
        </div>
        {pointsSensi && (
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                <th style={{ padding: 8 }}>Variation</th>
                <th style={{ padding: 8 }}>Revenu total</th>
              </tr>
            </thead>
            <tbody>
              {pointsSensi.map((p) => (
                <tr key={p.variation_pct}>
                  <td style={{ padding: 8, textAlign: 'center' }}>{p.variation_pct > 0 ? `+${p.variation_pct}` : p.variation_pct}%</td>
                  <td style={{ padding: 8, textAlign: 'center' }}>{formatMAD(Number(p.revenu_total))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
