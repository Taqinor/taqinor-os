import { cn } from '../lib/cn'

/* VX149 — carte à accent coloré par statut : la « carte à accent » (barre de
   couleur pilotée par `--kb-accent`, poignée de glissé au survol) était
   réinventée en parallèle par le kanban interventions
   (`InterventionsPage.jsx`, classes `.kb-card`/`.kc-card` + style
   inline `--kb-accent`) et par le calendrier chantiers inline
   (`InstallationsPage.jsx`, `style={{ background: dot }}` posé à la main sur
   une puce). Ce composant factorise le bon craft pour toute surface qui veut
   le même accent, sans dupliquer le style inline à chaque écran.

   `as` : élément racine ('div' par défaut ; les kanbans existants gardent
   leur propre marquage `article.kb-card` — CE composant ne remplace PAS le
   kanban leads, il donne une base commune aux autres écrans à accent).
   `accent` : couleur CSS (hex/var) pilotant `--kb-accent`.
   `variant` :
     - 'card' (défaut) — le plein craft carte (`kb-card kc-card`, barre de
       survol, poignée de glissé) pour les cartes de kanban.
     - 'compact' — même craft, padding resserré, pas de curseur "grab" (liste
       plate type Ma journée).
     - 'bare' — pose UNIQUEMENT la variable `--kb-accent` sur l'élément,
       sans imposer les classes `kb-card`/`kc-card` : pour un élément qui a
       déjà sa propre classe de présentation (ex. `.cal-chip`) et lit
       simplement l'accent via CSS (`var(--kb-accent)`). */
export function StatusAccentCard({
  accent, variant = 'card', as = 'div', className, style, children, ...props
}) {
  const Comp = as
  const shellClass =
    variant === 'bare' ? null
      : variant === 'compact' ? 'kb-card kc-card kb-card-compact'
        : 'kb-card kc-card'
  return (
    <Comp
      className={cn(shellClass, className)}
      style={{ ...style, '--kb-accent': accent }}
      {...props}
    >
      {children}
    </Comp>
  )
}

export default StatusAccentCard
