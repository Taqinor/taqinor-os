import { useEffect, useMemo, useState } from 'react'
import fpaApi from '../../api/fpaApi'
import { Button, Card } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   NTFPA13 — Écran Prévision glissante (rolling forecast 12-18 mois).
   ----------------------------------------------------------------------------
   Sélecteur département, génération depuis la moyenne des 3 derniers mois réels
   (compta), bascule "généré" vs "ajusté manuellement" par point (badge visuel),
   édition directe d'un point → total annuel recalculé en temps réel sans
   rechargement. Un point édité passe source=manuel et n'est plus écrasé par une
   régénération.
   ========================================================================== */

export default function PrevisionsPage() {
  const [departements, setDepartements] = useState([])
  const [departementId, setDepartementId] = useState('')
  const [horizon, setHorizon] = useState(12)
  const [prevision, setPrevision] = useState(null)
  const [lignes, setLignes] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fpaApi.getDepartements({ actif: 1 })
      .then((res) => setDepartements(
        Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les départements.'))
  }, [])

  const generer = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fpaApi.genererPrevision({
        departement: departementId || null,
        horizon: Number(horizon),
      })
      setPrevision(res.data)
      setLignes(res.data.lignes || [])
    } catch {
      setError('La génération de la prévision a échoué.')
    } finally {
      setLoading(false)
    }
  }

  const editerPoint = async (ligne, montant) => {
    // Une édition manuelle pose source=manuel côté client ; le backend
    // conserve source=manuel (jamais réécrasée par une régénération).
    setLignes((prev) => prev.map((l) => (
      l.id === ligne.id ? { ...l, montant_prevu: montant, source: 'manuel' } : l)))
    try {
      await fpaApi.updateLignePrevision(ligne.id, {
        montant_prevu: Number(montant || 0), source: 'manuel',
      })
    } catch {
      setError('La mise à jour du point a échoué.')
    }
  }

  const totalAnnuel = useMemo(
    () => lignes.slice(0, 12).reduce((s, l) => s + Number(l.montant_prevu || 0), 0),
    [lignes])

  return (
    <div>
      <PageHeader
        title="Prévision glissante"
        subtitle="Rolling forecast 12-18 mois (réel + prévision ajustable)"
        actions={
          <Button onClick={generer} disabled={loading}>
            {loading ? 'Génération…' : 'Générer / régénérer'}
          </Button>
        }
      />
      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <select
          aria-label="Département"
          value={departementId}
          onChange={(e) => setDepartementId(e.target.value)}
        >
          <option value="">Vue globale</option>
          {departements.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}
        </select>
        <select
          aria-label="Horizon"
          value={horizon}
          onChange={(e) => setHorizon(e.target.value)}
        >
          <option value={12}>12 mois</option>
          <option value={18}>18 mois</option>
        </select>
        <span style={{ marginLeft: 'auto', fontWeight: 700 }}>
          Total 12 mois : {formatMAD(totalAnnuel)}
        </span>
      </div>
      {error && <p role="alert" style={{ color: 'var(--danger, #c00)' }}>{error}</p>}
      {prevision && (
        <Card>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: 8 }}>Mois relatif</th>
                  <th style={{ textAlign: 'left', padding: 8 }}>Catégorie</th>
                  <th style={{ padding: 8 }}>Montant prévu</th>
                  <th style={{ padding: 8 }}>Source</th>
                </tr>
              </thead>
              <tbody>
                {lignes.map((l) => (
                  <tr key={l.id}>
                    <td style={{ padding: 8 }}>M+{l.mois_relatif}</td>
                    <td style={{ padding: 8 }}>{l.categorie}</td>
                    <td style={{ padding: 4 }}>
                      <input
                        type="number"
                        step="any"
                        aria-label={`Montant M+${l.mois_relatif} ${l.categorie}`}
                        value={l.montant_prevu ?? ''}
                        onChange={(e) => editerPoint(l, e.target.value)}
                        style={{ width: 100 }}
                      />
                    </td>
                    <td style={{ padding: 8 }}>
                      <span style={{
                        padding: '2px 8px', borderRadius: 6, fontSize: 12,
                        background: l.source === 'manuel'
                          ? 'var(--warning-bg, #fde68a)' : 'var(--muted-bg, #e5e7eb)',
                      }}>
                        {l.source === 'manuel' ? 'Ajusté' : 'Généré'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
