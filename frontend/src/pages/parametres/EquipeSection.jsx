// Onglet « Équipe & rôles » de la page Paramètres (carte d'information).
// Restylé sur le système de design (@/ui) ; texte identique.
import { Card, CardContent } from '../../ui'
import { SectionTitle } from './peComponents'

export default function EquipeSection() {
  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Équipe & rôles" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
        <p className="text-[12.5px] leading-relaxed text-muted-foreground">
          La gestion des employés se fait dans
          <strong> Administration → Utilisateurs</strong> (menu latéral), et
          les rôles dans <strong>Administration → Rôles</strong>. Un éditeur
          de rôles et permissions plus fin arrivera prochainement.
        </p>
      </CardContent>
    </Card>
  )
}
