// Onglet « Équipe & rôles » de la page Paramètres (carte d'information).
// Texte et styles identiques à l'ancien bloc monolithique.
import { SectionTitle } from './peComponents'
import { cardStyle } from './peConstants'

export default function EquipeSection() {
  return (
    <div style={cardStyle}>
      <SectionTitle color="#4f46e5" label="Équipe & rôles" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
      <p style={{ margin: 0, fontSize: 12.5, color: '#64748b', lineHeight: 1.6 }}>
        La gestion des employés se fait dans
        <strong> Administration → Utilisateurs</strong> (menu latéral), et
        les rôles dans <strong>Administration → Rôles</strong>. Un éditeur
        de rôles et permissions plus fin arrivera prochainement.
      </p>
    </div>
  )
}
