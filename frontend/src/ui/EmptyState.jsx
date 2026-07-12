import { cn } from '../lib/cn'

/* VX40 — Le délice mesuré : pictogramme solaire SVG inline pour les 4-5 états
   vides les plus vus (leads, devis, catalogue, GED, carte). Tons brass/lune
   déjà thémés (light/dark) via les variables de marque — jamais de hex figé,
   aucune dépendance illustration externe. Panneau solaire stylisé + rayons,
   silhouette basse-opacité cohérente avec le glyphe de marque (soleil). */
function SolarPictogram({ className }) {
  return (
    <svg
      viewBox="0 0 64 64"
      className={cn('size-14', className)}
      aria-hidden="true"
      focusable="false"
    >
      {/* Rayons — brass, opacité douce */}
      <g stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round" opacity="0.55">
        <line x1="32" y1="4" x2="32" y2="11" />
        <line x1="50.5" y1="10.5" x2="46" y2="15" />
        <line x1="60" y1="27" x2="53" y2="27" />
        <line x1="13.5" y1="10.5" x2="18" y2="15" />
        <line x1="4" y1="27" x2="11" y2="27" />
      </g>
      {/* Panneau solaire, incliné, grille — lune (neutre marque) */}
      <g transform="translate(10 26) rotate(-8)">
        <rect x="0" y="0" width="34" height="22" rx="2" fill="var(--color-lune-faint)" opacity="0.28" />
        <rect x="0" y="0" width="34" height="22" rx="2" fill="none" stroke="var(--color-lune-faint)" strokeWidth="1.5" opacity="0.6" />
        <line x1="11.3" y1="0" x2="11.3" y2="22" stroke="var(--color-lune-faint)" strokeWidth="1.2" opacity="0.6" />
        <line x1="22.6" y1="0" x2="22.6" y2="22" stroke="var(--color-lune-faint)" strokeWidth="1.2" opacity="0.6" />
        <line x1="0" y1="11" x2="34" y2="11" stroke="var(--color-lune-faint)" strokeWidth="1.2" opacity="0.6" />
      </g>
      {/* Socle */}
      <line x1="20" y1="52" x2="44" y2="52" stroke="var(--color-lune-faint)" strokeWidth="2" strokeLinecap="round" opacity="0.4" />
    </svg>
  )
}

// VX131(a) — `tone` calqué sur ErrorBoundary : un ÉCHEC de chargement doit se
// DISTINGUER visuellement de « rien à afficher » (jusqu'ici identiques — même
// icône grise neutre quelle que soit la cause). `neutral` = comportement
// historique inchangé.
const TONE_STYLES = {
  neutral: { border: 'border-dashed border-border', iconWrap: 'bg-muted text-muted-foreground' },
  error: { border: 'border-destructive/40', iconWrap: 'bg-destructive/12 text-destructive' },
  warning: { border: 'border-warning/40', iconWrap: 'bg-warning/12 text-warning' },
}

/* G30 — État vide : message + action suivante claire. `icon` = composant lucide
   (ignoré si `illustrated`). `illustrated` = pictogramme solaire SVG à la place
   du cercle d'icône, réservé aux 4-5 écrans les plus vus (règle Asana : le
   délice mesuré, pas partout). `tone` (neutral|error|warning, défaut neutral)
   colore la bordure ET le cercle d'icône — jamais l'icône seule. */
export function EmptyState({ icon, illustrated, tone = 'neutral', title, description, action, className, ...props }) {
  const Icon = icon
  const t = TONE_STYLES[tone] || TONE_STYLES.neutral
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-xl border',
        t.border,
        'px-6 py-12 text-center',
        className,
      )}
      {...props}
    >
      {illustrated ? (
        <SolarPictogram />
      ) : Icon && (
        <span className={cn('flex size-11 items-center justify-center rounded-full', t.iconWrap)}>
          <Icon className="size-5" aria-hidden="true" />
        </span>
      )}
      {title && <p className="font-display text-base font-semibold text-foreground">{title}</p>}
      {description && (
        <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
      )}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}

export default EmptyState
