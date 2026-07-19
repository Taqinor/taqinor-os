import { useEffect, useState, useCallback } from 'react'
import adsengineApi from './adsengineApi'
import { formatRatio } from './adsengine'

/* ============================================================================
   ASG6 — Écran « L'Arbre » : la vue plan-vivant.
   ----------------------------------------------------------------------------
   Doctrine (docs/engine/research/dd-assumption-engine.md §3) : « l'arbre EST
   l'historique du plan ». Chaque AssumptionNode (ASG1) porte un statut
   (assumed/testing/validated/stale/retired) et une fraîcheur dérivée de
   `last_tested_at` + la demi-vie de sa classe (créatif/angle/audience) — un
   « acquis » périmé regonfle son incertitude et re-gagne la file (§3.2/§3.3).
   La file VoI (ASG3, argmax S×U×R×T/C) ordonne le PROCHAIN test.
   Cet écran ne fait QUE lire/afficher — aucun score n'est recalculé côté
   front ; les helpers ci-dessous NORMALISENT la réponse API, ils n'inventent
   rien (même doctrine que `adsengine.js`, tenue locale à cet écran car
   `adsengine.js` est hors périmètre de la lane frontend/adsengine ASG6).

   Drill-down (« Done » ASG6) : nœud → ses tests passés (= son historique,
   « l'arbre à travers le temps ») → les leads réels derrière un test (même
   doctrine de traçabilité que le Dashboard ENG23 — jamais de chiffre
   boîte-noire).
   ========================================================================== */

const STATUT_LABELS = {
  assumed: 'Supposé',
  testing: 'En test',
  validated: 'Validé',
  stale: 'Périmé',
  retired: 'Retiré',
}

// Ordre d'affichage des groupes de statut (du plus « vivant » au plus « éteint »).
const STATUT_ORDER = ['testing', 'validated', 'assumed', 'stale', 'retired']

function statutTone(statut) {
  switch (statut) {
    case 'validated': return { bg: '#dcfce7', color: '#166534' }
    case 'testing': return { bg: '#dbeafe', color: '#1d4ed8' }
    case 'stale': return { bg: '#fef9c3', color: '#854d0e' }
    case 'retired': return { bg: '#f1f5f9', color: '#64748b' }
    default: return { bg: '#f1f5f9', color: '#475569' } // assumed
  }
}

const CLASSE_LABELS = {
  creatif: 'Créatif',
  angle: 'Angle',
  audience: 'Audience/structure',
}

// Normalise la liste des nœuds — lecture seule, aucun statut/score inventé.
function normalizeNodes(raw) {
  const list = Array.isArray(raw) ? raw : (raw?.results || raw?.noeuds || [])
  return (list || []).filter(Boolean).map((n, i) => {
    const statut = n.statut || n.status || 'assumed'
    return {
      id: n.id ?? i,
      enonce_fr: n.enonce_fr || n.enonce || n.statement_fr || `Nœud ${i + 1}`,
      classe: n.classe || n.class || '',
      classe_display: CLASSE_LABELS[n.classe] || n.classe_display || n.classe || '—',
      statut,
      statut_display: n.statut_display || STATUT_LABELS[statut] || statut || '—',
      fraicheur_jours: Number.isFinite(Number(n.fraicheur_jours ?? n.staleness_days))
        ? Number(n.fraicheur_jours ?? n.staleness_days) : null,
    }
  })
}

// File VoI (ASG3) — on affiche le RANG et le score déjà calculés par le
// backend, jamais recalculés côté front.
function normalizeQueue(raw) {
  const list = Array.isArray(raw) ? raw : (raw?.results || raw?.file || [])
  return (list || []).filter(Boolean).map((q, i) => ({
    node_id: q.node_id ?? q.id,
    enonce_fr: q.enonce_fr || q.enonce || `Nœud ${i + 1}`,
    voi: Number.isFinite(Number(q.voi ?? q.VoI)) ? Number(q.voi ?? q.VoI) : null,
    rang: q.rang ?? (i + 1),
  }))
}

// Historique d'un nœud = ses tests passés (l'arbre à travers le temps).
function normalizeTests(raw) {
  const list = Array.isArray(raw) ? raw : (raw?.results || raw?.tests || [])
  return (list || []).filter(Boolean).map((t, i) => ({
    id: t.id ?? i,
    nom: t.nom || t.name || `Test ${i + 1}`,
    statut_display: t.statut_display || t.statut || '—',
    verdict_display: t.verdict_display || t.verdict || '',
    quand: t.quand || t.date || t.tested_at || '',
  }))
}

export default function TreeScreen() {
  const [nodes, setNodes] = useState([])
  const [queue, setQueue] = useState([])
  const [loading, setLoading] = useState(true)

  // Drill 1 : nœud → tests (historique).
  const [openNodeId, setOpenNodeId] = useState(null)
  const [tests, setTests] = useState([])
  const [testsLoading, setTestsLoading] = useState(false)

  // Drill 2 : test → leads réels.
  const [openTestId, setOpenTestId] = useState(null)
  const [leads, setLeads] = useState([])
  const [leadsLoading, setLeadsLoading] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      adsengineApi.assumptions.nodes()
        .then(r => setNodes(normalizeNodes(r.data)))
        .catch(() => setNodes([])),
      adsengineApi.assumptions.queue()
        .then(r => setQueue(normalizeQueue(r.data)))
        .catch(() => setQueue([])),
    ]).finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  // Drill 1 — ouvre/ferme les tests d'un nœud (toggle).
  const openNode = (nodeId) => {
    const closing = openNodeId === nodeId
    setOpenNodeId(closing ? null : nodeId)
    setOpenTestId(null)
    setLeads([])
    if (closing) return
    setTestsLoading(true)
    setTests([])
    adsengineApi.assumptions.tests(nodeId)
      .then(r => setTests(normalizeTests(r.data)))
      .catch(() => setTests([]))
      .finally(() => setTestsLoading(false))
  }

  // Drill 2 — ouvre/ferme les leads réels d'un test (toggle).
  const openTest = (testId) => {
    const closing = openTestId === testId
    setOpenTestId(closing ? null : testId)
    if (closing) return
    setLeadsLoading(true)
    setLeads([])
    adsengineApi.assumptions.testLeads(testId)
      .then(r => setLeads(Array.isArray(r.data) ? r.data : (r.data?.results || r.data?.leads || [])))
      .catch(() => setLeads([]))
      .finally(() => setLeadsLoading(false))
  }

  const groups = STATUT_ORDER
    .map(statut => ({ statut, items: nodes.filter(n => n.statut === statut) }))
    .filter(g => g.items.length > 0)

  return (
    <div className="page ae-tree">
      <div className="page-header">
        <h2>L&apos;Arbre</h2>
      </div>

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <>
            {/* File VoI (ASG3) — le PROCHAIN test à argmax */}
            <section className="card ae-tree-queue" data-testid="ae-tree-queue" style={{ padding: '1rem', marginBottom: '1.25rem' }}>
              <h3 style={{ margin: '0 0 0.6rem' }}>File de priorité (VoI)</h3>
              {queue.length === 0
                ? <p data-testid="ae-tree-queue-empty" style={{ color: '#64748b', margin: 0 }}>
                    Aucun nœud en file.</p>
                : (
                  <table className="data-table" data-testid="ae-tree-queue-table">
                    <thead><tr><th>Rang</th><th>Nœud</th><th>VoI</th></tr></thead>
                    <tbody>
                      {queue.map(q => (
                        <tr key={q.node_id} data-testid="ae-tree-queue-row">
                          <td>{q.rang}</td>
                          <td>{q.enonce_fr}</td>
                          <td data-testid={`ae-tree-queue-voi-${q.node_id}`}>{formatRatio(q.voi, 2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
            </section>

            {/* Nœuds par statut/fraîcheur */}
            {groups.length === 0
              ? <p data-testid="ae-tree-empty" style={{ color: '#64748b' }}>Aucun nœud d&apos;hypothèse.</p>
              : groups.map(g => (
                <section key={g.statut} className="ae-tree-group" data-testid={`ae-tree-group-${g.statut}`}
                  style={{ marginBottom: '1.25rem' }}>
                  <h3 style={{ margin: '0 0 0.6rem' }}>{STATUT_LABELS[g.statut] || g.statut}</h3>
                  <div style={{ display: 'grid', gap: '0.6rem' }}>
                    {g.items.map(n => {
                      const tone = statutTone(n.statut)
                      const open = openNodeId === n.id
                      return (
                        <div key={n.id} className="card ae-tree-node" data-testid="ae-tree-node">
                          <button type="button" onClick={() => openNode(n.id)}
                            data-testid={`ae-tree-node-toggle-${n.id}`}
                            aria-expanded={open}
                            style={{ display: 'flex', width: '100%', justifyContent: 'space-between',
                              alignItems: 'center', gap: '0.6rem', textAlign: 'left', cursor: 'pointer',
                              padding: '0.75rem', border: '1px solid #e2e8f0', borderRadius: 6, background: 'none' }}>
                            <div>
                              <div>{n.enonce_fr}</div>
                              <div style={{ color: '#64748b', fontSize: '0.8rem', marginTop: '0.2rem' }}>
                                {n.classe_display}
                                {n.fraicheur_jours != null
                                  ? ` · il y a ${formatRatio(n.fraicheur_jours, 0)} j`
                                  : ''}
                              </div>
                            </div>
                            <span className="badge" style={{ background: tone.bg, color: tone.color }}>
                              {n.statut_display}
                            </span>
                          </button>

                          {/* Drill 1 — historique des tests de ce nœud */}
                          {open && (
                            <div data-testid={`ae-tree-node-tests-${n.id}`} style={{ padding: '0.75rem 0 0 0.75rem' }}>
                              {testsLoading
                                ? <p className="page-loading">Chargement…</p>
                                : tests.length === 0
                                  ? <p data-testid="ae-tree-tests-empty" style={{ color: '#64748b', margin: 0 }}>
                                      Aucun test pour ce nœud.</p>
                                  : (
                                    <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.4rem' }}>
                                      {tests.map(t => (
                                        <li key={t.id}>
                                          <button type="button" onClick={() => openTest(t.id)}
                                            data-testid={`ae-tree-test-${t.id}`}
                                            aria-expanded={openTestId === t.id}
                                            style={{ display: 'flex', width: '100%', justifyContent: 'space-between',
                                              cursor: 'pointer', padding: '0.5rem 0.6rem', border: '1px solid #e2e8f0',
                                              borderRadius: 6, background: 'none', textAlign: 'left' }}>
                                            <span>{t.nom}{t.quand ? ` — ${t.quand}` : ''}</span>
                                            <span style={{ color: '#64748b' }}>
                                              {t.verdict_display || t.statut_display}
                                            </span>
                                          </button>

                                          {/* Drill 2 — leads réels derrière ce test */}
                                          {openTestId === t.id && (
                                            <div data-testid={`ae-tree-test-leads-${t.id}`} style={{ padding: '0.5rem 0 0 0.6rem' }}>
                                              {leadsLoading
                                                ? <p className="page-loading">Chargement…</p>
                                                : leads.length === 0
                                                  ? <p data-testid="ae-tree-leads-empty" style={{ color: '#64748b', margin: 0 }}>
                                                      Aucun lead pour ce test.</p>
                                                  : (
                                                    <table className="data-table" data-testid="ae-tree-leads-table">
                                                      <thead><tr><th>Lead</th><th>Ville</th><th>Étape</th></tr></thead>
                                                      <tbody>
                                                        {leads.map((l, i) => (
                                                          <tr key={l.id ?? i} data-testid="ae-tree-lead-row">
                                                            <td>{l.nom || l.name || '—'}</td>
                                                            <td>{l.ville || l.city || '—'}</td>
                                                            <td>{l.stage_label || l.etape || '—'}</td>
                                                          </tr>
                                                        ))}
                                                      </tbody>
                                                    </table>
                                                  )}
                                            </div>
                                          )}
                                        </li>
                                      ))}
                                    </ul>
                                  )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </section>
              ))}
          </>
        )}
    </div>
  )
}
