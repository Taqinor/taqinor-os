import { useEffect, useState, useCallback } from 'react'
import marketingApi from '../../api/marketingApi'

/* ============================================================================
   WIR64 / FG206 — Formulaires d'intake (landing publique de capture de lead).
   ----------------------------------------------------------------------------
   Écran admin minimal : liste + création (nom, slug public, tag pré-rempli,
   type d'installation par défaut). La landing publique correspondante crée un
   lead via la vue AllowAny `/marketing/intake/<slug>/soumettre/` (crm.services)
   — cet écran n'y touche pas, il ne gère que la définition côté admin.
   ========================================================================== */

export default function FormulairesIntakeList() {
  const [formulaires, setFormulaires] = useState([])
  const [loading, setLoading] = useState(true)
  const [nom, setNom] = useState('')
  const [slug, setSlug] = useState('')
  const [tagPrefill, setTagPrefill] = useState('')
  const [typeInstallation, setTypeInstallation] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.formulairesIntake.list()
      .then((r) => setFormulaires(marketingApi.unwrapList(r)))
      .catch(() => setFormulaires([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const creer = async (e) => {
    e.preventDefault()
    setErr('')
    try {
      await marketingApi.formulairesIntake.create({
        nom,
        slug,
        tag_prefill: tagPrefill,
        type_installation: typeInstallation,
      })
      setNom(''); setSlug(''); setTagPrefill(''); setTypeInstallation('')
      load()
    } catch {
      setErr('Création impossible (slug déjà utilisé ?).')
    }
  }

  return (
    <div className="page">
      <div className="page-header"><h2>Formulaires d'intake</h2></div>
      <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '1rem' }}>
        Landing pages publiques de capture de lead. Chaque soumission d'un slug
        actif crée un lead pré-taggé.
      </p>

      <form onSubmit={creer} style={{ display: 'flex', gap: '0.5rem',
        flexWrap: 'wrap', marginBottom: '1rem' }}>
        <input className="form-input" data-testid="intake-nom" placeholder="Nom"
          required value={nom} onChange={(e) => setNom(e.target.value)}
          style={{ flex: '1 1 180px' }} />
        <input className="form-input" data-testid="intake-slug" placeholder="Slug public"
          required value={slug} onChange={(e) => setSlug(e.target.value)}
          style={{ flex: '1 1 160px' }} />
        <input className="form-input" data-testid="intake-tag" placeholder="Tag pré-rempli"
          value={tagPrefill} onChange={(e) => setTagPrefill(e.target.value)}
          style={{ flex: '1 1 160px' }} />
        <input className="form-input" data-testid="intake-type"
          placeholder="Type d'installation par défaut"
          value={typeInstallation} onChange={(e) => setTypeInstallation(e.target.value)}
          style={{ flex: '1 1 200px' }} />
        <button type="submit" className="btn btn-primary" data-testid="intake-creer">
          Créer
        </button>
      </form>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="intake-table">
            <thead>
              <tr><th>Nom</th><th>Slug</th><th>Tag</th><th>Type</th><th>Actif</th><th>Lien public</th></tr>
            </thead>
            <tbody>
              {formulaires.map((f) => (
                <tr key={f.id} data-testid="intake-row">
                  <td>{f.nom}</td>
                  <td><code>{f.slug}</code></td>
                  <td>{f.tag_prefill || '—'}</td>
                  <td>{f.type_installation || '—'}</td>
                  <td>{f.actif ? 'Oui' : 'Non'}</td>
                  <td><code style={{ fontSize: '0.78rem' }}>{marketingApi.formulairesIntake.lienPublic(f.slug)}</code></td>
                </tr>
              ))}
              {formulaires.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucun formulaire d'intake
                </td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}
