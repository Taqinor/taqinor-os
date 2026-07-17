/* eslint-disable react-refresh/only-export-components */
import { useEffect, useState } from 'react'
import marketingApi from '../../api/marketingApi'
import {
  addQuestion, removeQuestion, updateQuestion, optionsFromText, optionsToText,
} from './enqueteBuilder'

/* ============================================================================
   NTMKT8 — Constructeur d'enquête générique (NPS/choix/échelle/texte) avec
   logique conditionnelle « question B si réponse A » (XMKT27).
   ----------------------------------------------------------------------------
   `marketing/enquetes/` (CRUD, `token` posé côté serveur à la création) +
   action `tester` (aperçu SANS enregistrer de réponse). Le lien public
   copiable pointe vers l'endpoint public tokenisé existant
   (`enquetes-publiques/<token>/`, aucune authentification requise).
   ========================================================================== */

const TYPES = [
  { key: 'choix', label: 'Choix' },
  { key: 'echelle', label: 'Échelle' },
  { key: 'texte', label: 'Texte' },
  { key: 'nps', label: 'NPS' },
]

export function emptyForm() {
  return { titre: '', questions: [] }
}

export function formFromEnquete(e) {
  return { titre: e.titre || '', questions: e.questions || [] }
}

export function lienPublic(token) {
  if (!token) return ''
  return `${window.location.origin}/api/django/marketing/enquetes-publiques/${token}/`
}

export default function EnqueteBuilder({ initial, onSaved, onCancel }) {
  const [form, setForm] = useState(initial || emptyForm())
  const [id, setId] = useState(initial?.id || null)
  const [token, setToken] = useState(initial?.token || '')
  const [err, setErr] = useState('')
  const [testApercu, setTestApercu] = useState(null)
  const [copie, setCopie] = useState(false)

  // eslint-disable-next-line react-hooks/set-state-in-effect -- resync le formulaire quand la prop initial change
  useEffect(() => { setForm(initial || emptyForm()) }, [initial])

  const setTitre = (e) => setForm(f => ({ ...f, titre: e.target.value }))

  const ajouterQuestion = () => setForm(f => ({ ...f, questions: addQuestion(f.questions) }))
  const supprimerQuestion = (i) => setForm(f => ({ ...f, questions: removeQuestion(f.questions, i) }))
  const patchQuestion = (i, patch) => setForm(f => ({
    ...f, questions: updateQuestion(f.questions, i, patch),
  }))

  const enregistrer = async () => {
    setErr('')
    try {
      if (id) {
        const r = await marketingApi.enquetes.update(id, form)
        setToken(r.data?.token || token)
      } else {
        const r = await marketingApi.enquetes.create(form)
        setId(r.data.id)
        setToken(r.data.token)
      }
      onSaved?.()
    } catch {
      setErr('Enregistrement impossible.')
    }
  }

  const tester = async () => {
    if (!id) { setErr("Enregistrez d'abord l'enquête pour la tester."); return }
    setErr('')
    try {
      const r = await marketingApi.enquetes.tester(id)
      setTestApercu(r.data)
    } catch {
      setErr('Aperçu impossible.')
    }
  }

  const copierLien = async () => {
    try {
      await navigator.clipboard.writeText(lienPublic(token))
      setCopie(true)
    } catch {
      setCopie(false)
    }
  }

  return (
    <div data-testid="enquete-builder" style={{ display: 'grid', gap: '0.6rem', maxWidth: 720 }}>
      <input className="form-input" data-testid="enquete-titre" placeholder="Titre de l'enquête"
        value={form.titre} onChange={setTitre} />

      {form.questions.map((q, i) => (
        <fieldset key={q.id || i} data-testid="enquete-question"
          style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.5rem 0.75rem',
            display: 'grid', gap: '0.4rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <input className="form-input" placeholder="Libellé de la question"
              data-testid={`enquete-question-${i}-libelle`} value={q.libelle}
              onChange={e => patchQuestion(i, { libelle: e.target.value })}
              style={{ flex: '2 1 220px' }} />
            <select className="form-input" data-testid={`enquete-question-${i}-type`}
              value={q.type} onChange={e => patchQuestion(i, { type: e.target.value })}
              style={{ flex: '1 1 120px' }}>
              {TYPES.map(t => <option key={t.key} value={t.key}>{t.label}</option>)}
            </select>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.8rem' }}>
              <input type="checkbox" data-testid={`enquete-question-${i}-obligatoire`}
                checked={!!q.obligatoire}
                onChange={e => patchQuestion(i, { obligatoire: e.target.checked })} />
              Obligatoire
            </label>
            <button type="button" className="btn btn-light"
              data-testid={`enquete-question-${i}-supprimer`}
              onClick={() => supprimerQuestion(i)}>✕</button>
          </div>
          {q.type === 'choix' && (
            <textarea className="form-input" rows={2}
              placeholder="Options (une par ligne)"
              data-testid={`enquete-question-${i}-options`}
              value={optionsToText(q.options)}
              onChange={e => patchQuestion(i, { options: optionsFromText(e.target.value) })} />
          )}
          {i > 0 && (
            <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
              <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Affichée si</span>
              <select className="form-input" data-testid={`enquete-question-${i}-condition-q`}
                value={q.condition?.question_id || ''}
                onChange={e => patchQuestion(i, {
                  condition: e.target.value
                    ? { question_id: e.target.value, valeur: q.condition?.valeur || '' }
                    : null,
                })}>
                <option value="">Toujours affichée</option>
                {form.questions.slice(0, i).map((prev, pi) => (
                  <option key={prev.id || pi} value={prev.id || pi}>
                    {prev.libelle || `Question ${pi + 1}`}
                  </option>
                ))}
              </select>
              {q.condition?.question_id && (
                <input className="form-input" placeholder="Valeur attendue"
                  data-testid={`enquete-question-${i}-condition-valeur`}
                  value={q.condition?.valeur || ''}
                  onChange={e => patchQuestion(i, {
                    condition: { ...q.condition, valeur: e.target.value },
                  })} />
              )}
            </div>
          )}
        </fieldset>
      ))}

      <button type="button" className="btn btn-light" data-testid="enquete-ajouter-question"
        onClick={ajouterQuestion}>+ Ajouter une question</button>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <button type="button" className="btn btn-primary" data-testid="enquete-enregistrer"
          onClick={enregistrer}>
          Enregistrer
        </button>
        {id && (
          <button type="button" className="btn btn-light" data-testid="enquete-tester"
            onClick={tester}>
            Tester (sans enregistrer)
          </button>
        )}
        {token && (
          <button type="button" className="btn btn-light" data-testid="enquete-copier-lien"
            onClick={copierLien}>
            {copie ? 'Lien copié !' : 'Copier le lien public'}
          </button>
        )}
        {onCancel && (
          <button type="button" className="btn btn-light" onClick={onCancel}>Fermer</button>
        )}
      </div>

      {testApercu && (
        <p data-testid="enquete-test-apercu" style={{ color: '#0d9488' }}>
          Aperçu OK — {(testApercu.questions || form.questions).length} question(s) affichée(s).
        </p>
      )}
    </div>
  )
}
