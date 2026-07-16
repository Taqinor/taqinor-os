import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'

/* ============================================================================
   NTMKT6 — Liste des séquences de relance (FG202) + activation des recettes
   seedées (XMKT20).
   ----------------------------------------------------------------------------
   `marketing/sequences-relance/` (CRUD). Les 5 recettes livrées par
   `seed_sequences_marketing` naissent `actif=False` (le founder les active en
   un clic) — le bouton « Activer » n'apparaît que sur une séquence inactive
   et fait un simple PATCH `{actif: true}`.
   ========================================================================== */

export default function SequencesList() {
  const navigate = useNavigate()
  const [sequences, setSequences] = useState([])
  const [loading, setLoading] = useState(true)
  const [nom, setNom] = useState('')
  const [stageDeclencheur, setStageDeclencheur] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.sequences.list()
      .then(r => setSequences(marketingApi.unwrapList(r)))
      .catch(() => setSequences([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const creer = async (e) => {
    e.preventDefault()
    setErr('')
    try {
      await marketingApi.sequences.create({
        nom, stage_declencheur: stageDeclencheur, actif: true,
      })
      setNom(''); setStageDeclencheur('')
      load()
    } catch {
      setErr('Création impossible.')
    }
  }

  const activer = async (id, e) => {
    e.stopPropagation()
    setErr('')
    try {
      await marketingApi.sequences.update(id, { actif: true })
      load()
    } catch {
      setErr('Activation impossible.')
    }
  }

  return (
    <div className="page">
      <div className="page-header"><h2>Séquences de relance</h2></div>

      <form onSubmit={creer} style={{ display: 'flex', gap: '0.5rem',
        flexWrap: 'wrap', marginBottom: '1rem' }}>
        <input className="form-input" data-testid="sequence-nom" placeholder="Nom"
          required value={nom} onChange={e => setNom(e.target.value)}
          style={{ flex: '1 1 200px' }} />
        <input className="form-input" data-testid="sequence-stage"
          placeholder="Clé d'étape déclencheuse (STAGES.py, optionnel)"
          value={stageDeclencheur} onChange={e => setStageDeclencheur(e.target.value)}
          style={{ flex: '1 1 260px' }} />
        <button type="submit" className="btn btn-primary" data-testid="sequence-creer">
          Créer
        </button>
      </form>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="sequences-table">
            <thead><tr><th>Nom</th><th>Déclencheur</th><th>Étapes</th><th>Statut</th><th /></tr></thead>
            <tbody>
              {sequences.map(s => (
                <tr key={s.id} data-testid="sequence-row" style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/marketing/sequences/${s.id}`)}>
                  <td>{s.nom}</td>
                  <td>{s.stage_declencheur || '—'}</td>
                  <td>{(s.etapes || []).length}</td>
                  <td>{s.actif ? 'Active' : 'Inactive'}</td>
                  <td>
                    {!s.actif && (
                      <button className="btn btn-primary" type="button"
                        data-testid="sequence-activer" onClick={(e) => activer(s.id, e)}>
                        Activer une recette
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {sequences.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucune séquence
                </td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}
