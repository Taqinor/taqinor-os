import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Sunrise, ExternalLink, ShieldAlert } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { normalizeTodayQueue, categoryTone } from './todayQueue'
import { formatSyncDateTime } from './syncStatus'
import SyncStatusBanner from './SyncStatusBanner'

/* ============================================================================
   PUB42 — File « Aujourd'hui » unifiée — l'écran d'accueil ``/publicite``.
   ----------------------------------------------------------------------------
   Doctrine (Done) : « que dois-je faire ce matin ? » se répond en UN SEUL
   écran, en 30 secondes — garde-fous, alertes, approbations en attente,
   commentaires non traités et le dernier digest hebdomadaire, DÉJÀ classés
   par priorité par le backend (``metrics.today_queue`` — jamais retrié ici).
   Chaque item est cliquable vers SON écran (``item.lien``) : cet écran
   n'introduit AUCUN nouveau sous-écran par item, seulement le point d'entrée
   unifié qui manquait. État-ERREUR distinct de l'état-vide (PUB41) : une
   file vide (rien à faire ce matin, tout va bien) n'est PAS une panne.
   ========================================================================== */

export default function TodayScreen() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.today.get()
      .then(r => {
        setItems(normalizeTodayQueue(r.data).items)
        setLoadError(false)
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  return (
    <div className="page ae-today">
      <div className="page-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Sunrise size={20} aria-hidden="true" /> Aujourd&apos;hui
        </h2>
      </div>

      {/* PUB41 — bandeau global « Meta ne répond plus… » (fraîcheur/panne). */}
      <SyncStatusBanner />

      {loadError && (
        <p data-testid="ae-today-load-error" role="alert" style={{ color: '#dc2626', margin: '0 0 0.75rem' }}>
          Chargement de la file impossible — panne de synchronisation possible.
        </p>
      )}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : items.length === 0
          ? (!loadError && (
              <p data-testid="ae-today-empty" style={{ color: '#64748b' }}>
                Rien à traiter ce matin — tout est à jour.</p>
            ))
          : (
            <ul data-testid="ae-today-list" style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.6rem' }}>
              {items.map(item => {
                const tone = categoryTone(item.categorie)
                const when = formatSyncDateTime(item.quand)
                return (
                  <li key={item.id}>
                    <Link to={item.lien || '/publicite/tableau-de-bord'}
                      className="card ae-today-item" data-testid="ae-today-item"
                      data-categorie={item.categorie}
                      style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem',
                        padding: '0.75rem', border: '1px solid #e2e8f0', textDecoration: 'none',
                        color: 'inherit' }}>
                      {item.categorie === 'garde_fou' && (
                        <ShieldAlert size={16} aria-hidden="true" style={{ color: tone.color, marginTop: 2, flexShrink: 0 }} />
                      )}
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                          <span className="badge" data-testid="ae-today-item-badge"
                            style={{ background: tone.bg, color: tone.color }}>
                            {item.categorie_label}
                          </span>
                          <strong>{item.titre}</strong>
                          {when && (
                            <span style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: '0.8rem' }}>
                              {when}
                            </span>
                          )}
                        </div>
                        {item.detail && (
                          <p style={{ margin: '0.3rem 0 0', color: '#334155' }}>{item.detail}</p>
                        )}
                      </div>
                      <ExternalLink size={14} aria-hidden="true" style={{ color: '#2563eb', marginTop: 3, flexShrink: 0 }} />
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
    </div>
  )
}
