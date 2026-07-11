import { Link } from 'react-router-dom'
import { Avatar, AvatarFallback, initials } from '../ui/Avatar'
import { cn } from '../lib/cn'

// VX216(c) — personne ne voit la CHAÎNE de responsabilité du client quand il
// rappelle : « Lead : A · Devis : B · Chantier : C · SAV : D », chaque maillon
// cliquable vers sa fiche réelle (deep-links EXISTANTS et réels — jamais une
// URL ad-hoc inventée) :
//   - Lead   → /crm/leads?lead=<id>   (patron VX79, LeadsPage.jsx)
//   - Devis  → /ventes/devis?devis=<id>
//   - Chantier → /chantiers?id=<id>   (patron VX79, InstallationsPage.jsx)
//   - SAV    → /sav?id=<ticket_id>    (patron VX79, TicketsPage.jsx)
// Un maillon sans id connu est simplement absent (jamais un lien mort).
//
// steps: [{ key, label, id, name, role, href }]
export default function OwnerChain({ lead, devis, chantier, sav, className }) {
  const steps = [
    lead && { key: 'lead', label: 'Lead', name: lead.nom, href: `/crm/leads?lead=${lead.id}` },
    devis && { key: 'devis', label: 'Devis', name: devis.nom ?? devis.reference, href: `/ventes/devis?devis=${devis.id}` },
    chantier && { key: 'chantier', label: 'Chantier', name: chantier.nom ?? chantier.reference, href: `/chantiers?id=${chantier.id}` },
    sav && { key: 'sav', label: 'SAV', name: sav.nom ?? sav.reference, href: `/sav?id=${sav.id}` },
  ].filter(Boolean)

  if (steps.length === 0) return null

  return (
    <div className={cn('flex flex-wrap items-center gap-1.5', className)} role="list" aria-label="Chaîne de responsabilité">
      {steps.map((s, i) => (
        <span key={s.key} className="flex items-center gap-1.5" role="listitem">
          {i > 0 && <span className="text-muted-foreground" aria-hidden="true">·</span>}
          <Link
            to={s.href}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2 py-0.5 text-xs font-medium hover:bg-muted"
            title={`${s.label} : ${s.name ?? '—'}`}
          >
            <Avatar className="size-4">
              <AvatarFallback className="text-[9px]">{initials(s.name) || s.label[0]}</AvatarFallback>
            </Avatar>
            {s.label}{s.name ? ` : ${s.name}` : ''}
          </Link>
        </span>
      ))}
    </div>
  )
}
