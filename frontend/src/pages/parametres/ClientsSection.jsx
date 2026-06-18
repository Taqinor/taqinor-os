// Onglet « Clients » de la page Paramètres (carte d'information).
// Restylé sur le système de design (@/ui) ; texte identique.
import { Card, CardContent } from '../../ui'
import { SectionTitle } from './peComponents'

export default function ClientsSection() {
  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Clients" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
        <p className="text-[12.5px] leading-relaxed text-muted-foreground">
          Les réglages liés aux clients (ICE par défaut, rappels de mentions
          légales sur les documents B2B) apparaîtront ici. Les champs
          personnalisés des fiches clients se gèrent dans l'onglet
          <strong> Avancé</strong>.
        </p>
      </CardContent>
    </Card>
  )
}
