import { useEffect, useState, useCallback } from 'react'
import { TestTube, Send, FlaskConical } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   PUB128 — Écran « Tests terrain » (préflight d'autonomie, dd-assumption-engine.md).
   ----------------------------------------------------------------------------
   Les 7 tests FT1..FT7 sont les conditions HUMAINES que la porte d'autonomie
   du moteur exige avant de laisser tourner un budget réel. Cet écran ne fait
   QUE : afficher ce que le serveur a déjà tranché ou non (`tranche`), laisser
   consigner une mesure RÉELLE (`recordResult`), et proposer des STRUCTURES DE
   TEST qui naissent PAUSED et attendent l'approbation humaine
   (`proposeStructures`). Aucun chiffre n'est inventé ici : tout vient du
   payload serveur (plafond, constantes, valeurs mesurées).
   ========================================================================== */

function emptyDraft() {
  return { measured_value: '', evidence: '', measured_on: '' }
}

export default function FieldTestsScreen() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [drafts, setDrafts] = useState({})
  const [busyFt, setBusyFt] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    setErr('')
    adsengineApi.fieldTests.list()
      .then(r => setData(r.data))
      .catch(() => setErr('Chargement des tests terrain impossible.'))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const draftFor = (ft) => drafts[ft] || emptyDraft()

  const setDraftField = (ft, key, value) => {
    setDrafts(d => ({ ...d, [ft]: { ...draftFor(ft), [key]: value } }))
  }

  const submitResult = async (ft, e) => {
    e.preventDefault()
    const draft = draftFor(ft)
    if (!draft.measured_value || !draft.measured_value.trim()) {
      setErr('La valeur mesurée est obligatoire.')
      return
    }
    setBusyFt(ft)
    setErr('')
    setMsg('')
    try {
      /* PUB-P8/C4 — date de mesure VIDE : la clé est OMISE, jamais envoyée à ''
         (le serveur retombe alors sur le jour courant). Envoyer '' faisait
         refuser « ce n'est pas une date » et perdait une mesure RÉELLE pour
         une case optionnelle laissée vide. */
      const payload = {
        measured_value: draft.measured_value,
        evidence: draft.evidence,
      }
      if (draft.measured_on && draft.measured_on.trim()) {
        payload.measured_on = draft.measured_on
      }
      await adsengineApi.fieldTests.recordResult(ft, payload)
      setMsg(`Résultat de ${ft} enregistré.`)
      setDrafts(d => ({ ...d, [ft]: emptyDraft() }))
      load()
    } catch {
      setErr(`Enregistrement du résultat de ${ft} impossible.`)
    } finally {
      setBusyFt('')
    }
  }

  const proposeStructures = async (ft) => {
    setBusyFt(ft)
    setErr('')
    setMsg('')
    try {
      const r = await adsengineApi.fieldTests.proposeStructures(ft, { city: '' })
      const n = (r.data?.actions || []).length
      setMsg(
        `${n} proposition(s) de structure de test créée(s) pour ${ft} — `
        + `elles naissent PAUSED et attendent l'approbation humaine.`
      )
    } catch (e) {
      /* PUB-P8/C5 — la RAISON FR du serveur est affichée telle quelle (ex. :
         devise du compte ≠ MAD ⇒ plafond micro-test non convertible). Un refus
         motivé ne doit jamais être remplacé par un « impossible » muet. */
      const detail = e?.response?.data?.detail
      setErr(detail || `Proposition de structures impossible pour ${ft}.`)
    } finally {
      setBusyFt('')
    }
  }

  return (
    <div className="p-4" data-testid="ae-tests-terrain-screen">
      <h1 className="h4 d-flex align-items-center gap-2">
        <TestTube size={20} aria-hidden="true" /> Tests terrain (préflight d&apos;autonomie)
      </h1>
      <p className="text-muted">
        Ces 7 tests sont les conditions humaines requises avant tout budget réel.
        Chaque test se mesure sur le terrain, jamais en simulation.
      </p>

      {loading ? (
        <p data-testid="ae-tests-terrain-loading">Chargement…</p>
      ) : err && !data ? (
        <div className="alert alert-danger" data-testid="ae-tests-terrain-err">{err}</div>
      ) : data && (
        <>
          <div className="alert alert-warning" data-testid="ae-tests-terrain-plafond">
            Plafond micro-test : <strong>{data.plafond_mad} MAD</strong>. Le lancement d&apos;un
            run réel reste une décision du fondateur ; toute structure de test proposée ici
            naît PAUSED et exige une approbation humaine avant diffusion.
          </div>

          {msg && <div className="alert alert-success" data-testid="ae-tests-terrain-msg">{msg}</div>}
          {err && <div className="alert alert-danger" data-testid="ae-tests-terrain-err">{err}</div>}

          <div className="alert alert-info" data-testid="ae-tests-terrain-global">
            {data.toutes_tranchees
              ? 'Les 7 tests sont tranchés — la porte de préflight peut passer verte.'
              : `La porte de préflight d'autonomie reste ROUGE tant que les 7 tests ne sont pas `
                + `tous tranchés (${(data.constantes_en_attente || []).length} constante(s) en attente).`}
          </div>

          <table className="table" data-testid="ae-tests-terrain-table">
            <tbody>
              {(data.tests || []).map(test => {
                const draft = draftFor(test.ft)
                const busy = busyFt === test.ft
                return (
                  <tr key={test.ft} data-testid={`ae-tests-terrain-row-${test.ft}`}>
                    <td>
                      <div className="d-flex align-items-center gap-2 mb-1">
                        <FlaskConical size={16} aria-hidden="true" />
                        <strong>{test.ft}</strong> — {test.label_fr}
                        <span
                          className={`badge bg-${test.tranche ? 'success' : 'secondary'}`}
                          data-testid={`ae-tests-terrain-status-${test.ft}`}>
                          {test.tranche ? 'Tranché' : 'En attente'}
                        </span>
                      </div>

                      <p className="mb-1">{test.question_fr}</p>

                      {Array.isArray(test.protocole_fr) && test.protocole_fr.length > 0 && (
                        <ol className="mb-1" data-testid={`ae-tests-terrain-protocole-${test.ft}`}>
                          {test.protocole_fr.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ol>
                      )}

                      <p className="text-muted mb-2">{test.mesure_fr}</p>

                      {Array.isArray(test.constantes) && test.constantes.length > 0 && (
                        <ul
                          className="list-unstyled mb-2"
                          data-testid={`ae-tests-terrain-constantes-${test.ft}`}>
                          {test.constantes.map(c => (
                            <li key={c.cle}>
                              <code>{c.cle}</code> — {c.label_fr} : <strong>{c.valeur}</strong>
                              {c.unite ? ` ${c.unite}` : ''} (source : {c.source})
                            </li>
                          ))}
                        </ul>
                      )}

                      {test.tranche && (
                        <div
                          className="alert alert-light border mb-2"
                          data-testid={`ae-tests-terrain-recorded-${test.ft}`}>
                          Valeur mesurée : <strong>{test.valeur_mesuree}</strong>
                          {test.preuve ? ` — Preuve : ${test.preuve}` : ''}
                          {test.mesure_le ? ` — Mesuré le ${test.mesure_le}` : ''}
                        </div>
                      )}

                      <form
                        onSubmit={(e) => submitResult(test.ft, e)}
                        noValidate
                        className="row g-2 align-items-end mb-2">
                        <div className="col-md-4">
                          <label
                            className="form-label"
                            htmlFor={`ae-tests-terrain-valeur-${test.ft}`}>
                            Valeur mesurée (requis)
                          </label>
                          <input
                            id={`ae-tests-terrain-valeur-${test.ft}`}
                            className="form-control"
                            data-testid={`ae-tests-terrain-valeur-${test.ft}`}
                            value={draft.measured_value}
                            onChange={e => setDraftField(test.ft, 'measured_value', e.target.value)}
                            required />
                        </div>
                        <div className="col-md-4">
                          <label
                            className="form-label"
                            htmlFor={`ae-tests-terrain-preuve-${test.ft}`}>
                            Preuve (optionnel)
                          </label>
                          <textarea
                            id={`ae-tests-terrain-preuve-${test.ft}`}
                            className="form-control"
                            data-testid={`ae-tests-terrain-preuve-${test.ft}`}
                            value={draft.evidence}
                            onChange={e => setDraftField(test.ft, 'evidence', e.target.value)} />
                        </div>
                        <div className="col-md-2">
                          <label
                            className="form-label"
                            htmlFor={`ae-tests-terrain-date-${test.ft}`}>
                            Mesuré le
                          </label>
                          <input
                            id={`ae-tests-terrain-date-${test.ft}`}
                            type="date"
                            className="form-control"
                            data-testid={`ae-tests-terrain-date-${test.ft}`}
                            value={draft.measured_on}
                            onChange={e => setDraftField(test.ft, 'measured_on', e.target.value)} />
                        </div>
                        <div className="col-md-2">
                          <button
                            type="submit"
                            className="btn btn-primary w-100"
                            data-testid={`ae-tests-terrain-submit-${test.ft}`}
                            disabled={busy}>
                            <Send size={14} aria-hidden="true" /> Enregistrer
                          </button>
                        </div>
                      </form>

                      <button
                        type="button"
                        className="btn btn-outline-secondary btn-sm"
                        data-testid={`ae-tests-terrain-structures-${test.ft}`}
                        onClick={() => proposeStructures(test.ft)}
                        disabled={busy}>
                        Proposer les structures de test
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
