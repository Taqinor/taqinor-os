import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { ClipboardCheck, History } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { normalizeBrief, briefItemHasAction } from './adsengine'
import TenantBrand from './TenantBrand'

/* ============================================================================
   ENG26 — Écran « Brief hebdomadaire » du moteur publicitaire.
   ----------------------------------------------------------------------------
   Rend le `WeeklyBrief` déterministe en structure « que s'est-il passé →
   pourquoi → suggestion ». Chaque carte porteuse d'une action pointe vers la
   boîte d'approbation (ENG25, /publicite/approbations) ; un lien vers le journal
   (ENG28, /publicite/journal) donne l'historique. Aucun commentaire LLM ici (la
   couche IA du brief est gated — ENG GATED). Le contenu est celui de l'API.
   ========================================================================== */

export default function BriefScreen() {
  const [brief, setBrief] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.brief.latest()
      .then(r => setBrief(normalizeBrief(r.data)))
      .catch(() => setBrief(normalizeBrief(null)))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  return (
    <div className="page ae-brief">
      {/* ENG31 — marque tenant (logo/nom) en tête du brief, repli propre sinon. */}
      <TenantBrand subtitle="Brief hebdomadaire du moteur publicitaire" />
      <div className="page-header">
        <h2>Brief hebdomadaire</h2>
        <Link to="/publicite/journal" className="btn btn-light" data-testid="ae-brief-history"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
          <History size={15} aria-hidden="true" /> Historique
        </Link>
      </div>

      {loading
        ? <p className="page-loading">Chargement…</p>
        : !brief || brief.items.length === 0
          ? <p data-testid="ae-brief-empty" style={{ color: '#64748b' }}>
              Aucun brief disponible pour l&apos;instant.</p>
          : (
            <>
              {brief.periode && (
                <p data-testid="ae-brief-periode" style={{ color: '#475569', margin: '0 0 0.5rem' }}>
                  {brief.periode}
                </p>
              )}
              {brief.resume && (
                <p data-testid="ae-brief-resume" style={{ margin: '0 0 1rem' }}>{brief.resume}</p>
              )}
              <div style={{ display: 'grid', gap: '1rem' }}>
                {brief.items.map(item => (
                  <article key={item.id} className="card ae-brief-card" data-testid="ae-brief-card"
                    style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
                    <div style={{ marginBottom: '0.5rem' }}>
                      <span style={{ color: '#64748b', fontSize: '0.8rem' }}>Que s&apos;est-il passé</span>
                      <p style={{ margin: '0.15rem 0 0', fontWeight: 600 }}>{item.quoi || '—'}</p>
                    </div>
                    {item.pourquoi && (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <span style={{ color: '#64748b', fontSize: '0.8rem' }}>Pourquoi</span>
                        <p style={{ margin: '0.15rem 0 0' }}>{item.pourquoi}</p>
                      </div>
                    )}
                    {item.suggestion && (
                      <div>
                        <span style={{ color: '#64748b', fontSize: '0.8rem' }}>Suggestion</span>
                        <p style={{ margin: '0.15rem 0 0' }}>{item.suggestion}</p>
                      </div>
                    )}
                    {briefItemHasAction(item) && (
                      <div style={{ marginTop: '0.75rem' }}>
                        <Link to="/publicite/approbations"
                          className="btn btn-primary ae-brief-approve-link"
                          data-testid="ae-brief-approve-link"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                          <ClipboardCheck size={15} aria-hidden="true" />
                          Voir dans la boîte d&apos;approbation
                        </Link>
                      </div>
                    )}
                  </article>
                ))}
              </div>
            </>
          )}
    </div>
  )
}
