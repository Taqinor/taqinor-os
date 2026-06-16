import { Link } from 'react-router-dom'

// Hub « Rapports » : point d'entrée vers les rapports ventes / stock / service
// et l'export comptable. Tous en lecture seule, exportables en .xlsx.
const CARDS = [
  {
    to: '/reporting/rapports/ventes',
    titre: 'Ventes & pipeline',
    desc: "Entonnoir des leads, devis par statut, CA par responsable / canal / période, gagné-perdu par motif. Export comptable journal des ventes + TVA.",
    color: '#3b82f6',
  },
  {
    to: '/reporting/rapports/stock',
    titre: 'Stock',
    desc: "Valorisation (valeur de vente et d'achat — interne), historique des mouvements, ruptures et sous-seuil, répartition par catégorie / marque.",
    color: '#8b5cf6',
  },
  {
    to: '/reporting/rapports/service',
    titre: 'Service (chantiers + SAV)',
    desc: "Charge de planning chantier, délais de réalisation, activité par technicien, SAV ouverts vs résolus, garanties expirant bientôt.",
    color: '#22c55e',
  },
]

export default function RapportsHub() {
  return (
    <div className="page" style={{ maxWidth: 1000 }}>
      <div className="page-header"><h2>Rapports</h2></div>
      <p style={{ color: '#64748b', fontSize: 14, marginTop: -8, marginBottom: '1.5rem' }}>
        Rapports analytiques en lecture seule, exportables en Excel (.xlsx).
      </p>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem',
      }}>
        {CARDS.map(c => (
          <Link key={c.to} to={c.to} style={{ textDecoration: 'none' }}>
            <div style={{
              background: '#fff', borderRadius: 14, padding: '1.4rem',
              boxShadow: '0 1px 4px rgba(0,0,0,0.07)', borderTop: `3px solid ${c.color}`,
              height: '100%',
            }}>
              <div style={{ fontSize: 17, fontWeight: 700, color: '#0f172a', marginBottom: 6 }}>{c.titre}</div>
              <div style={{ fontSize: 13, color: '#64748b', lineHeight: 1.5 }}>{c.desc}</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
