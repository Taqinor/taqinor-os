import { LayoutGrid, LayoutList, MessageCircle } from 'lucide-react'
import {
  Button, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Spinner, TabsTrigger,
} from '../../ui'

/* Éléments d'écran PARTAGÉS des listes Ventes (Devis, Factures, Bons de
   commande, Relances, Remises) : un seul endroit, jamais recopiés écran par
   écran (garde de duplicat littéral). */

/** Page de liste en cours de chargement : en-tête, spinner et/ou squelette. */
export function PageListeChargement({ pageHeader, showSpinner, showSkeleton, libelle, children }) {
  return (
    <div className="page">
      {pageHeader}
      {showSpinner && (
        <div className="mt-4 flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Spinner /> {libelle}
        </div>
      )}
      {showSkeleton && (
        <>
          {children}
        </>
      )}
    </div>
  )
}

/** Choix FR / Darija de la langue des messages WhatsApp. */
export function LangueWhatsApp({ waLangue, setWaLangue, ariaLabel, title, className }) {
  return (
    <div role="group" aria-label={ariaLabel}
         className={className}
         title={title}>
      <MessageCircle className="size-4 text-muted-foreground" />
      {[['fr', 'FR'], ['darija', 'Darija']].map(([val, label]) => (
        <Button key={val} size="sm"
                variant={waLangue === val ? 'default' : 'outline'}
                aria-pressed={waLangue === val}
                onClick={() => setWaLangue(val)}>
          {label}
        </Button>
      ))}
    </div>
  )
}

/** Bascule d'affichage Liste / (Kanban | Board). */
export function BasculeAffichage({ viewMode, setViewMode, autreMode, autreLabel }) {
  return (
    <div className="ml-auto flex items-center gap-1 rounded-md border border-border p-0.5"
         role="group" aria-label="Mode d’affichage">
      <Button
        type="button" size="sm"
        variant={viewMode === 'liste' ? 'secondary' : 'ghost'}
        aria-pressed={viewMode === 'liste'}
        onClick={() => setViewMode('liste')}
      >
        <LayoutList className="size-4" aria-hidden="true" /> Liste
      </Button>
      <Button
        type="button" size="sm"
        variant={viewMode === autreMode ? 'secondary' : 'ghost'}
        aria-pressed={viewMode === autreMode}
        onClick={() => setViewMode(autreMode)}
      >
        <LayoutGrid className="size-4" aria-hidden="true" /> {autreLabel}
      </Button>
    </div>
  )
}

/** Onglet de liste avec son compteur (masqué à zéro). */
export function OngletCompteur({ value, label, count, className }) {
  return (
    <TabsTrigger value={value} className={className}>
      {label}
      {count > 0 && (
        <span className="ml-1.5 rounded bg-muted px-1.5 text-xs text-muted-foreground">{count}</span>
      )}
    </TabsTrigger>
  )
}

/** Sélecteur de client (liste déroulante nom + prénom) des formulaires Ventes. */
export function SelectClient({ clients, value, onValueChange, disabled, id, invalid, autoFocus }) {
  return (
    <Select value={value} onValueChange={onValueChange} disabled={disabled}>
      <SelectTrigger id={id} invalid={invalid} autoFocus={autoFocus}>
        <SelectValue placeholder="— Sélectionner un client —" />
      </SelectTrigger>
      <SelectContent>
        {clients.map(c => (
          <SelectItem key={c.id} value={String(c.id)}>
            {c.nom}{c.prenom ? ` ${c.prenom}` : ''}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
