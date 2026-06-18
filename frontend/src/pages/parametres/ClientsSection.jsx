// Onglet « Clients » de la page Paramètres (carte d'information).
// Texte et styles identiques à l'ancien bloc monolithique.
import { SectionTitle } from './peComponents'
import { cardStyle } from './peConstants'

export default function ClientsSection() {
  return (
    <div style={cardStyle}>
      <SectionTitle color="#0891b2" label="Clients" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
      <p style={{ margin: 0, fontSize: 12.5, color: '#64748b', lineHeight: 1.6 }}>
        Les réglages liés aux clients (ICE par défaut, rappels de mentions
        légales sur les documents B2B) apparaîtront ici. Les champs
        personnalisés des fiches clients se gèrent dans l'onglet
        <strong> Avancé</strong>.
      </p>
    </div>
  )
}
