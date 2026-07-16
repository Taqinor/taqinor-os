import { useState } from 'react'
import {
  Trash2, Plus, Settings, Search, Download, Inbox, Pencil, Bell, Save,
  Check, CheckCircle2, AlertCircle, Loader2,
} from 'lucide-react'
import { ThemeToggle } from '../../design/ThemeToggle'
import { useDensity } from '../../design/theme-context'
import { formatMAD, formatNumber, formatPercent, formatDate, formatPhoneMA } from '../../lib/format'
import {
  Button, IconButton, Spinner,
  Badge, StatusPill, Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter,
  Stat, Separator, Skeleton, SkeletonText, SkeletonLine, SkeletonAvatar, SkeletonCard, EmptyState,
  ErrorBoundary,
  Label, Input, Textarea, CurrencyInput, PercentInput, PhoneInput,
  Checkbox, Switch, RadioGroup, RadioGroupItem, Slider, Segmented,
  Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose,
  Sheet, SheetTrigger, SheetContent, SheetHeader, SheetTitle, SheetDescription,
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  Popover, PopoverTrigger, PopoverContent,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator,
  TooltipProvider, SimpleTooltip,
  toast, Tag, Avatar, AvatarFallback, AvatarGroup, initials,
  DefinitionList, Tabs, TabsList, TabsTrigger, TabsContent,
  Accordion, AccordionItem, AccordionTrigger, AccordionContent, Progress,
  Select, SelectTrigger, SelectValue, SelectContent, SelectGroup, SelectItem, SelectLabel,
  Combobox, MultiSelect, DatePicker, DateRangePicker, TimePicker,
  FileUpload,
  Form, FormSection, FormField, FormActions, FormErrorSummary, useDirtyGuard,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { useConfirmDialog, toastPromise } from '../../ui/confirm'
import { useDelayedLoading } from '../../hooks/useDelayedLoading'
import { useOptimisticSave } from '../../hooks/useOptimisticSave'
import { DataTableDemo } from './DataTableDemo'
import {
  runValidation, errorSummary, isDirty, required, email,
} from '../../ui/form-utils'
import { ModuleDashboard, ListShell, EcheanceCenter, statusPill } from '../../ui/module'

// Données de démonstration pour les sélecteurs G23.
const VILLES = [
  { value: 'casa', label: 'Casablanca' },
  { value: 'rabat', label: 'Rabat' },
  { value: 'marrakech', label: 'Marrakech' },
  { value: 'tanger', label: 'Tanger' },
  { value: 'agadir', label: 'Agadir' },
  { value: 'fes', label: 'Fès', description: 'Région Fès-Meknès' },
]
const TAGS = [
  { value: 'residentiel', label: 'Résidentiel' },
  { value: 'industriel', label: 'Industriel' },
  { value: 'agricole', label: 'Agricole' },
  { value: 'pompage', label: 'Pompage solaire' },
  { value: 'batterie', label: 'Avec batterie' },
]
// Recherche asynchrone simulée (états chargement/vide/erreur du Combobox).
const searchVilles = (q) =>
  new Promise((resolve) => {
    setTimeout(() => {
      const n = q.trim().toLowerCase()
      resolve(VILLES.filter((v) => v.label.toLowerCase().includes(n)))
    }, 350)
  })

function Section({ id, title, children }) {
  return (
    <section id={id} className="scroll-mt-6">
      <h2 className="font-display text-lg font-semibold tracking-tight">{title}</h2>
      <Separator className="my-3" />
      <div className="flex flex-wrap items-start gap-3">{children}</div>
    </section>
  )
}

/* P170 — Petits utilitaires DOC propres au guide de style (jeton mono, libellé). */
function Code({ children }) {
  return (
    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.8125rem] text-foreground">
      {children}
    </code>
  )
}

/* Nuancier : une pastille de couleur + son rôle/jeton. La couleur vient d'une
   variable de thème (jamais une valeur en dur) pour rester fidèle aux tokens. */
function Swatch({ token, role, varName }) {
  return (
    <div className="flex w-32 flex-col gap-1.5">
      <div
        className="h-12 w-full rounded-lg border border-border"
        style={{ background: `var(${varName})` }}
        aria-hidden="true"
      />
      <div className="flex flex-col">
        <span className="text-xs font-medium text-foreground">{role}</span>
        <Code>{token}</Code>
      </div>
    </div>
  )
}

/* Ligne « definition of done » avec puce verte. */
function DoneItem({ children }) {
  return (
    <li className="flex items-start gap-2 text-sm">
      <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
      <span className="text-muted-foreground">{children}</span>
    </li>
  )
}

/* ── P170 · Démo : confirmation + toasts (ui/confirm) ──────────────────────── */
function ConfirmToastDemo() {
  const { confirm: askConfirm, confirmDelete } = useConfirmDialog()

  async function onConfirm() {
    const ok = await askConfirm({
      title: 'Marquer comme contacté ?',
      description: 'Le lead passera à l’étape suivante du pipeline.',
      confirmLabel: 'Marquer',
    })
    if (ok) toast.success('Lead marqué comme contacté.')
  }

  async function onDelete() {
    const ok = await confirmDelete({
      title: 'Supprimer ce devis ?',
      description: 'Le devis DV-2026-014 sera définitivement supprimé.',
    })
    if (ok) toast.error('Devis supprimé.')
  }

  function onPromise() {
    // Promesse simulée (aucun appel réseau) : chargement → succès automatiques.
    const fake = new Promise((resolve) => setTimeout(resolve, 1200))
    toastPromise(fake, {
      loading: 'Enregistrement du devis…',
      success: 'Devis enregistré.',
      error: 'Échec de l’enregistrement.',
    })
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="outline" onClick={onConfirm}>Confirmation générique</Button>
      <Button variant="destructive" onClick={onDelete}><Trash2 /> Confirmer la suppression</Button>
      <Button variant="outline" onClick={onPromise}>toastPromise (mutation)</Button>
    </div>
  )
}

/* ── P170 · Démo : ResponsiveDialog (modale bureau / tiroir bas mobile) ────── */
function ResponsiveDialogDemo() {
  const [open, setOpen] = useState(false)
  return (
    <div className="flex flex-col gap-2">
      <Button variant="outline" onClick={() => setOpen(true)}>Ouvrir le dialog adaptatif</Button>
      <p className="max-w-md text-xs text-muted-foreground">
        Même surface de props ; modale centrée à partir de 768 px, tiroir bas en dessous.
      </p>
      <ResponsiveDialog
        open={open}
        onOpenChange={setOpen}
        title="Assigner le lead"
        description="Choisissez le commercial responsable de ce dossier."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Annuler</Button>
            <Button onClick={() => { setOpen(false); toast.success('Lead assigné.') }}>Assigner</Button>
          </>
        }
      >
        <p className="py-2 text-sm text-muted-foreground">
          Contenu identique quelle que soit la taille d’écran — un seul composant.
        </p>
      </ResponsiveDialog>
    </div>
  )
}

/* ── P170 · Démo : useDelayedLoading (anti-scintillement) ──────────────────── */
function DelayedLoadingDemo() {
  const [loading, setLoading] = useState(false)
  const { phase, showSpinner, showSkeleton } = useDelayedLoading(loading)

  function run(ms) {
    setLoading(true)
    setTimeout(() => setLoading(false), ms)
  }

  return (
    <div className="flex w-full max-w-md flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => run(150)}>Rapide (150 ms)</Button>
        <Button size="sm" variant="outline" onClick={() => run(400)}>Moyen (400 ms)</Button>
        <Button size="sm" variant="outline" onClick={() => run(900)}>Lent (900 ms)</Button>
      </div>
      <div className="flex min-h-[72px] items-center rounded-lg border border-border bg-card p-3">
        {phase === 'idle' && <span className="text-sm text-muted-foreground">Prêt — lancez un chargement.</span>}
        {phase === 'pending' && <span className="text-sm text-muted-foreground">…</span>}
        {showSpinner && <span className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Chargement…</span>}
        {showSkeleton && <div className="w-full"><SkeletonText lines={2} /></div>}
      </div>
      <p className="text-xs text-muted-foreground">
        Phase actuelle : <Code>{phase}</Code>. Rien sous 300 ms, spinner 300–500 ms, squelette au-delà.
      </p>
    </div>
  )
}

/* ── P170 · Démo : useOptimisticSave (edit optimiste + rollback) ───────────── */
function OptimisticSaveDemo() {
  const [serverValue, setServerValue] = useState('Reda Kasri')
  const { value, statusLabel, status, save } = useOptimisticSave(serverValue)
  const [draft, setDraft] = useState(serverValue)

  // Commit simulé : réussit après 700 ms, ou rejette si on demande l'échec.
  function commitOk(next) {
    return new Promise((resolve) => setTimeout(() => { setServerValue(next); resolve(next) }, 700))
  }
  function commitFail() {
    return new Promise((unused, reject) => setTimeout(() => reject(new Error('réseau')), 700))
  }

  return (
    <div className="flex w-full max-w-md flex-col gap-3">
      <div className="grid gap-1.5">
        <Label htmlFor="opt-name">Nom du client (affiché : optimiste)</Label>
        <Input id="opt-name" value={draft} onChange={(e) => setDraft(e.target.value)} />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => save(draft, commitOk)}>Enregistrer (réussit)</Button>
        <Button size="sm" variant="outline" onClick={() => save(draft, commitFail)}>Enregistrer (échoue → rollback)</Button>
        <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
          {status === 'saving' && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          {status === 'saved' && <CheckCircle2 className="size-4 text-success" aria-hidden="true" />}
          {status === 'error' && <AlertCircle className="size-4 text-destructive" aria-hidden="true" />}
          {statusLabel || (status === 'error' ? 'Échec — valeur restaurée' : '')}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        Valeur affichée : <Code>{String(value)}</Code> — appliquée immédiatement, restaurée si le commit rejette.
      </p>
    </div>
  )
}

export function UIShowcase() {
  const { density, setDensity } = useDensity()
  const [radio, setRadio] = useState('a')
  const [seg, setSeg] = useState('liste')

  // G23 — sélecteurs
  const [marche, setMarche] = useState('')
  const [ville, setVille] = useState(null)
  const [villeAsync, setVilleAsync] = useState(null)
  const [tags, setTags] = useState(['residentiel'])
  // G24 — dates / heure
  const [date, setDate] = useState(null)
  const [periode, setPeriode] = useState({ start: null, end: null })
  const [heure, setHeure] = useState('09:00')
  // G27 — formulaire piloté
  const [formValues, setFormValues] = useState({ nom: '', email: '' })
  const [formErrors, setFormErrors] = useState({})
  const initialForm = { nom: '', email: '' }
  const dirty = isDirty(initialForm, formValues)
  useDirtyGuard(dirty)
  const formRules = { nom: [required('Le nom est obligatoire.')], email: [required('L’e-mail est obligatoire.'), email()] }
  const submitDemo = (e) => {
    e.preventDefault()
    const errs = runValidation(formValues, formRules)
    setFormErrors(errs)
    if (Object.keys(errs).length === 0) {
      toast.success('Formulaire valide')
      setFormValues(initialForm)
    }
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root min-h-screen px-5 py-8">
        {/* Toaster global monté dans main.jsx (L53) — un seul <Toaster> pour
            toute l'app, /ui compris, sinon chaque toast s'affiche en double. */}
        <div className="mx-auto flex max-w-5xl flex-col gap-10">
          <header className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="font-display text-2xl font-bold tracking-tight">Taqinor — Système UI</h1>
              <p className="text-sm text-muted-foreground">
                Vitrine des primitifs (Groupe G) sur la fondation de tokens (Groupe F).
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Segmented
                size="sm"
                value={density}
                onChange={setDensity}
                options={[
                  { value: 'comfortable', label: 'Confort' },
                  { value: 'compact', label: 'Compact' },
                ]}
              />
              <ThemeToggle />
            </div>
          </header>

          {/* ── P170 — Fondation du design system (Groupe F) documentée ─────── */}
          <section id="tokens" className="scroll-mt-6">
            <h2 className="font-display text-lg font-semibold tracking-tight">Jetons de design (fondation F)</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Système à 3 couches : primitives de marque (OKLCH) → rôles sémantiques (clair/sombre)
              → composants. Aucun écran existant ne change ; les nouveaux primitifs consomment ces jetons.
            </p>
            <Separator className="my-3" />

            <h3 className="mb-2 text-sm font-semibold text-foreground">Couleurs sémantiques</h3>
            <div className="flex flex-wrap gap-3">
              <Swatch role="Fond" token="--background" varName="--background" />
              <Swatch role="Surface / carte" token="--card" varName="--card" />
              <Swatch role="Primaire (laiton)" token="--primary" varName="--primary" />
              <Swatch role="Accent" token="--accent" varName="--accent" />
              <Swatch role="Succès" token="--success" varName="--success" />
              <Swatch role="Attention" token="--warning" varName="--warning" />
              <Swatch role="Danger" token="--destructive" varName="--destructive" />
              <Swatch role="Info" token="--info" varName="--info" />
              <Swatch role="Bordure" token="--border" varName="--border" />
              <Swatch role="Anneau de focus" token="--ring" varName="--ring" />
            </div>

            <h3 className="mb-2 mt-5 text-sm font-semibold text-foreground">
              Palette de marque (OKLCH) — laiton « énergie »
            </h3>
            <div className="flex flex-wrap gap-3">
              <Swatch role="brass 100" token="--color-brass-100" varName="--color-brass-100" />
              <Swatch role="brass 300" token="--color-brass-300" varName="--color-brass-300" />
              <Swatch role="brass 400" token="--color-brass-400" varName="--color-brass-400" />
              <Swatch role="brass 500" token="--color-brass-500" varName="--color-brass-500" />
              <Swatch role="azur 600" token="--color-azur-600" varName="--color-azur-600" />
              <Swatch role="nuit" token="--color-nuit" varName="--color-nuit" />
              <Swatch role="lune" token="--color-lune" varName="--color-lune" />
            </div>

            <h3 className="mb-2 mt-5 text-sm font-semibold text-foreground">
              Échelle typographique (F121) — 7 paliers
            </h3>
            <div className="flex flex-col gap-1.5">
              <p className="text-display font-display font-bold">Display — 3rem</p>
              <p className="text-h1 font-display font-bold">Titre H1 — 2,25rem</p>
              <p className="text-h2 font-display font-semibold">Titre H2 — 1,75rem</p>
              <p className="text-h3 font-display font-semibold">Titre H3 — 1,375rem</p>
              <p className="text-body">Corps — 1rem · interligne confortable pour la lecture.</p>
              <p className="text-small text-muted-foreground">Small — 0,875rem · libellés, aides.</p>
              <p className="text-caption text-muted-foreground">Caption — 0,75rem · légendes, notes de bas.</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Le tracking se resserre vers les grandes tailles ; <Code>.tabular-nums</Code> aligne les
                chiffres (montants, références) avec zéro barré.
              </p>
            </div>

            <h3 className="mb-2 mt-5 text-sm font-semibold text-foreground">
              Élévation (F122) — par rôle, jamais « flottant » au hasard
            </h3>
            <div className="flex flex-wrap items-end gap-4">
              <div className="rounded-lg bg-card p-3 text-xs text-muted-foreground shadow-card">Carte · shadow-card (liseré 1px)</div>
              <div className="rounded-lg bg-card p-3 text-xs text-muted-foreground shadow-card-hover">Survol · shadow-card-hover</div>
              <div className="rounded-lg bg-card p-3 text-xs text-muted-foreground shadow-menu">Menu · shadow-menu</div>
              <div className="rounded-lg bg-card p-3 text-xs text-muted-foreground shadow-modal">Modal · shadow-modal</div>
              <div className="rounded-lg bg-card p-3 text-xs text-muted-foreground shadow-toast">Toast · shadow-toast</div>
            </div>

            <h3 className="mb-2 mt-5 text-sm font-semibold text-foreground">
              Anneau de focus (F122) & mouvement
            </h3>
            <div className="flex flex-wrap items-center gap-4">
              <span
                className="inline-flex items-center rounded-lg border border-border bg-card px-3 py-2 text-sm"
                style={{ boxShadow: 'var(--focus-ring)' }}
              >
                Aperçu de l’anneau de focus
              </span>
              <ul className="text-sm text-muted-foreground">
                <li>Vitesses : <Code>--motion-fast</Code> 120ms · <Code>--motion-base</Code> 180ms · <Code>--motion-slow</Code> 260ms</li>
                <li>Courbe : <Code>--ease-standard</Code> · respecte <Code>prefers-reduced-motion</Code></li>
              </ul>
            </div>
          </section>

          {/* ── P170 — Kit graphique (formatage de marque) ────────────────────── */}
          <section id="kit" className="scroll-mt-6">
            <h2 className="font-display text-lg font-semibold tracking-tight">Kit graphique</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Conventions transverses : police de marque, formats MAD/téléphone marocains,
              chiffres tabulaires, et iconographie (lucide-react, taille via classes).
            </p>
            <Separator className="my-3" />
            <div className="flex flex-wrap items-start gap-6">
              <div className="flex flex-col gap-1 text-sm">
                <span className="font-display text-base font-semibold">Archivo / Hanken Grotesk</span>
                <span className="text-muted-foreground">font-display (titres) · font-brand (corps)</span>
              </div>
              <DefinitionList
                className="w-full max-w-sm"
                items={[
                  { term: 'Montant (MAD)', description: <span className="tabular-nums">{formatMAD(1284500.5)}</span> },
                  { term: 'Téléphone', description: formatPhoneMA('+212612345678') },
                  { term: 'Chiffres tabulaires', description: <span className="tabular-nums">1 234 567 · 0OO0</span> },
                ]}
              />
              <div className="flex items-center gap-3 text-muted-foreground">
                <Bell className="size-4" aria-hidden="true" />
                <Settings className="size-5" aria-hidden="true" />
                <Download className="size-6" aria-hidden="true" />
                <span className="text-xs">Icônes lucide — dimensionnées par <Code>size-*</Code></span>
              </div>
            </div>
          </section>

          {/* ── P170 — Modes de densité ───────────────────────────────────────── */}
          <section id="density" className="scroll-mt-6">
            <h2 className="font-display text-lg font-semibold tracking-tight">Modes de densité</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Deux densités pilotées par <Code>data-density</Code> (jetons <Code>--control-h</Code>,
              <Code> --row-py</Code>, <Code>--field-gap</Code>…). Le sélecteur en tête de page bascule
              toute la vitrine — y compris le DataTable. Densité active : <Code>{density}</Code>.
            </p>
            <Separator className="my-3" />
            <div className="flex flex-wrap items-start gap-4">
              <Segmented
                value={density}
                onChange={setDensity}
                options={[
                  { value: 'comfortable', label: 'Confort (défaut)' },
                  { value: 'compact', label: 'Compact' },
                ]}
              />
              <div className="flex flex-wrap items-center gap-2">
                <Button>Bouton</Button>
                <Input className="w-40" placeholder="Champ" />
                <Badge tone="primary">Étiquette</Badge>
              </div>
            </div>
          </section>

          {/* ── P170 — Definition of done (checklist par composant) ───────────── */}
          <section id="dod" className="scroll-mt-6">
            <h2 className="font-display text-lg font-semibold tracking-tight">
              Definition of done (par composant)
            </h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Critères à cocher avant d’ajouter un composant au système. Chaque primitif livré ici
              les respecte.
            </p>
            <Separator className="my-3" />
            <div className="grid gap-4 sm:grid-cols-2">
              <Card className="p-4">
                <CardTitle className="text-sm">Apparence & thème</CardTitle>
                <ul className="mt-3 space-y-2">
                  <DoneItem>Couleurs via jetons sémantiques — aucune valeur en dur.</DoneItem>
                  <DoneItem>Rendu correct en clair ET en sombre.</DoneItem>
                  <DoneItem>Élévation choisie par rôle (carte / menu / modal / toast).</DoneItem>
                  <DoneItem>Réagit aux deux modes de densité.</DoneItem>
                </ul>
              </Card>
              <Card className="p-4">
                <CardTitle className="text-sm">Accessibilité & comportement</CardTitle>
                <ul className="mt-3 space-y-2">
                  <DoneItem>Navigable au clavier, anneau de focus visible.</DoneItem>
                  <DoneItem>Rôles/aria corrects ; libellés en français.</DoneItem>
                  <DoneItem>Respecte <Code>prefers-reduced-motion</Code>.</DoneItem>
                  <DoneItem>Mobile : cible tactile ≥ 44px, repli adapté.</DoneItem>
                </ul>
              </Card>
              <Card className="p-4">
                <CardTitle className="text-sm">États</CardTitle>
                <ul className="mt-3 space-y-2">
                  <DoneItem>États repos / survol / focus / actif / désactivé.</DoneItem>
                  <DoneItem>Chargement (squelette/spinner) et vide gérés.</DoneItem>
                  <DoneItem>Erreur de saisie signalée inline (texte + couleur).</DoneItem>
                </ul>
              </Card>
              <Card className="p-4">
                <CardTitle className="text-sm">Qualité</CardTitle>
                <ul className="mt-3 space-y-2">
                  <DoneItem>Exporté depuis <Code>src/ui</Code>, props documentées.</DoneItem>
                  <DoneItem>Test de rendu + (axe) accessibilité.</DoneItem>
                  <DoneItem>Aucune nouvelle dépendance non justifiée.</DoneItem>
                  <DoneItem>Documenté ici, dans <Code>/ui</Code>.</DoneItem>
                </ul>
              </Card>
            </div>
          </section>

          {/* ── P170 — Nouveaux primitifs de fondation (confirm / dialog / etc.) ─ */}
          <section id="foundation" className="scroll-mt-6">
            <h2 className="font-display text-lg font-semibold tracking-tight">
              Primitifs de fondation (comportements)
            </h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Helpers transverses montés une seule fois à la racine de l’app — un seul import par page.
              Chaque démo est isolée dans un <Code>ErrorBoundary</Code> pour ne jamais faire planter la page.
            </p>
            <Separator className="my-3" />
            <div className="flex flex-col gap-6">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-foreground">
                  Confirmation &amp; toasts (<Code>ui/confirm</Code>)
                </h3>
                <ErrorBoundary><ConfirmToastDemo /></ErrorBoundary>
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-foreground">
                  ResponsiveDialog (modale ↔ tiroir bas)
                </h3>
                <ErrorBoundary><ResponsiveDialogDemo /></ErrorBoundary>
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-foreground">
                  Squelettes de chargement (variantes)
                </h3>
                <ErrorBoundary>
                  <div className="grid w-full gap-4 sm:grid-cols-3">
                    <div className="space-y-2">
                      <p className="text-xs text-muted-foreground">Ligne / texte</p>
                      <SkeletonLine />
                      <SkeletonText lines={3} />
                    </div>
                    <div className="space-y-2">
                      <p className="text-xs text-muted-foreground">Avatar + bloc</p>
                      <div className="flex items-center gap-3">
                        <SkeletonAvatar />
                        <div className="flex-1 space-y-2">
                          <Skeleton className="h-3.5 w-1/2" />
                          <Skeleton className="h-3 w-1/3" />
                        </div>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <p className="text-xs text-muted-foreground">Carte</p>
                      <SkeletonCard />
                    </div>
                  </div>
                </ErrorBoundary>
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-foreground">
                  Chargement différé anti-scintillement (<Code>useDelayedLoading</Code>)
                </h3>
                <ErrorBoundary><DelayedLoadingDemo /></ErrorBoundary>
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-foreground">
                  Enregistrement optimiste + rollback (<Code>useOptimisticSave</Code>)
                </h3>
                <ErrorBoundary><OptimisticSaveDemo /></ErrorBoundary>
              </div>
            </div>
          </section>

          <Section id="buttons" title="Boutons">
            <Button>Principal</Button>
            <Button variant="secondary">Secondaire</Button>
            <Button variant="outline">Contour</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Supprimer</Button>
            <Button variant="success">Valider</Button>
            <Button variant="link">Lien</Button>
            <Button loading>Chargement</Button>
            <Button disabled>Désactivé</Button>
            <Button><Plus /> Nouveau</Button>
            <IconButton label="Réglages"><Settings /></IconButton>
            <Spinner />
          </Section>

          <Section id="status" title="Badges & statuts">
            <Badge>Neutre</Badge>
            <Badge tone="primary">Primaire</Badge>
            <Badge tone="info">Info</Badge>
            <Badge tone="success">Succès</Badge>
            <Badge tone="warning">Attention</Badge>
            <Badge tone="danger">Danger</Badge>
            <StatusPill status="accepte" label="Accepté" />
            <StatusPill status="envoye" label="Envoyé" />
            <StatusPill status="impayee" label="Impayée" />
            <StatusPill status="en_cours" label="En cours" />
            <StatusPill status="perdu" label="Perdu" />
            <Tag onRemove={() => {}}>résidentiel</Tag>
          </Section>

          <Section id="stats" title="Cartes & KPI">
            <Stat label="Pipeline" value={formatMAD(1284500)} delta={{ value: '+12 %', direction: 'up' }} hint="ce mois" icon={Bell} />
            <Stat label="Devis signés" value={formatNumber(37)} delta={{ value: '-3', direction: 'down' }} hint="vs. N-1" />
            <Card className="w-64">
              <CardHeader>
                <CardTitle>Carte</CardTitle>
                <CardDescription>Surface tokenisée, ombre légère.</CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">Contenu de la carte.</CardContent>
              <CardFooter><Button size="sm">Action</Button></CardFooter>
            </Card>
          </Section>

          <Section id="inputs" title="Champs de saisie">
            <div className="grid w-72 gap-1.5">
              <Label htmlFor="ix" required>Nom</Label>
              <Input id="ix" placeholder="Ex. Reda Kasri" />
            </div>
            <div className="grid w-72 gap-1.5">
              <Label htmlFor="iy">Recherche</Label>
              <Input id="iy" leading={<Search />} placeholder="Rechercher…" />
            </div>
            <div className="grid w-48 gap-1.5">
              <Label htmlFor="ic">Montant</Label>
              <CurrencyInput id="ic" defaultValue="1500" />
            </div>
            <div className="grid w-40 gap-1.5">
              <Label htmlFor="ip">Remise</Label>
              <PercentInput id="ip" defaultValue="5" />
            </div>
            <div className="grid w-56 gap-1.5">
              <Label htmlFor="it">Téléphone</Label>
              <PhoneInput id="it" defaultValue="0612345678" />
            </div>
            <div className="grid w-72 gap-1.5">
              <Label htmlFor="ie">Invalide</Label>
              <Input id="ie" invalid defaultValue="abc@" aria-describedby="ie-err" />
              <p id="ie-err" className="text-xs text-destructive">Email invalide</p>
            </div>
            <div className="grid w-72 gap-1.5">
              <Label htmlFor="ta">Note</Label>
              <Textarea id="ta" placeholder="Quelques mots…" />
            </div>
          </Section>

          <Section id="controls" title="Contrôles">
            <label className="flex items-center gap-2 text-sm"><Checkbox defaultChecked /> Inclure la batterie</label>
            <label className="flex items-center gap-2 text-sm"><Switch defaultChecked /> Notifications</label>
            <RadioGroup value={radio} onValueChange={setRadio} className="flex gap-4">
              <label className="flex items-center gap-2 text-sm"><RadioGroupItem value="a" /> Sans batterie</label>
              <label className="flex items-center gap-2 text-sm"><RadioGroupItem value="b" /> Avec batterie</label>
            </RadioGroup>
            <div className="w-56"><Slider defaultValue={[40]} max={100} step={1} /></div>
            <Segmented
              value={seg}
              onChange={setSeg}
              options={[
                { value: 'liste', label: 'Liste' },
                { value: 'kanban', label: 'Kanban' },
                { value: 'calendrier', label: 'Calendrier' },
              ]}
            />
          </Section>

          <Section id="selects" title="Sélecteurs (G23)">
            <div className="grid w-64 gap-1.5">
              <Label htmlFor="g23-select">Marché (Select)</Label>
              <Select value={marche} onValueChange={setMarche}>
                <SelectTrigger id="g23-select"><SelectValue placeholder="Choisir un marché…" /></SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>Type d’installation</SelectLabel>
                    <SelectItem value="residentiel">Résidentiel</SelectItem>
                    <SelectItem value="industriel">Industriel / Commercial</SelectItem>
                    <SelectItem value="agricole">Agricole (pompage)</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
            <div className="grid w-64 gap-1.5">
              <Label>Ville (Combobox local)</Label>
              <Combobox options={VILLES} value={ville} onChange={setVille} placeholder="Sélectionner une ville…" />
            </div>
            <div className="grid w-64 gap-1.5">
              <Label>Ville (Combobox async)</Label>
              <Combobox onSearch={searchVilles} value={villeAsync} onChange={setVilleAsync} placeholder="Rechercher (async)…" emptyText="Aucune ville" />
            </div>
            <div className="grid w-64 gap-1.5">
              <Label>Étiquettes (MultiSelect)</Label>
              <MultiSelect options={TAGS} value={tags} onChange={setTags} placeholder="Choisir des étiquettes…" />
            </div>
          </Section>

          <Section id="dates" title="Dates & heure (G24)">
            <div className="grid w-56 gap-1.5">
              <Label>Date de relance</Label>
              <DatePicker value={date} onChange={setDate} />
            </div>
            <div className="grid w-72 gap-1.5">
              <Label>Période</Label>
              <DateRangePicker value={periode} onChange={setPeriode} />
            </div>
            <div className="grid w-40 gap-1.5">
              <Label>Heure (HH:mm)</Label>
              <TimePicker value={heure} onChange={setHeure} step={30} />
            </div>
          </Section>

          <Section id="upload" title="Téléversement (G26)">
            <div className="w-full max-w-md">
              <FileUpload
                accept="application/pdf,image/png,image/jpeg"
                maxSize={10 * 1024 * 1024}
                onFiles={(files) => toast.success(`${files[0].name} prêt à l’envoi`)}
                onReject={(r) => toast.error(r[0].error)}
                hint="Démo : aucun envoi réseau"
              />
            </div>
          </Section>

          <Section id="form" title="Système de formulaire (G27)">
            <Form onSubmit={submitDemo} className="w-full max-w-lg">
              <FormErrorSummary errors={errorSummary(formErrors, ['nom', 'email'])} />
              <FormSection title="Coordonnées" description="Disposition label-au-dessus, validation inline.">
                <FormField label="Nom" required htmlFor="nom" error={formErrors.nom}>
                  <Input
                    id="nom"
                    value={formValues.nom}
                    invalid={!!formErrors.nom}
                    onChange={(e) => setFormValues((v) => ({ ...v, nom: e.target.value }))}
                  />
                </FormField>
                <FormField label="E-mail" required htmlFor="email" error={formErrors.email} hint="Format : nom@domaine.ma">
                  <Input
                    id="email"
                    value={formValues.email}
                    invalid={!!formErrors.email}
                    onChange={(e) => setFormValues((v) => ({ ...v, email: e.target.value }))}
                  />
                </FormField>
              </FormSection>
              <FormActions sticky={false}>
                {dirty && <span className="mr-auto text-xs text-amber-600">Modifications non enregistrées</span>}
                <Button type="button" variant="ghost" onClick={() => { setFormValues(initialForm); setFormErrors({}) }}>Annuler</Button>
                <Button type="submit"><Save /> Enregistrer</Button>
              </FormActions>
            </Form>
          </Section>

          <Section id="overlays" title="Overlays">
            <Dialog>
              <DialogTrigger asChild><Button variant="outline">Ouvrir un dialog</Button></DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Confirmer le devis</DialogTitle>
                  <DialogDescription>Cette action enregistre le devis et notifie le client.</DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <DialogClose asChild><Button variant="ghost">Annuler</Button></DialogClose>
                  <DialogClose asChild><Button>Confirmer</Button></DialogClose>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Sheet>
              <SheetTrigger asChild><Button variant="outline">Ouvrir un tiroir</Button></SheetTrigger>
              <SheetContent side="right">
                <SheetHeader>
                  <SheetTitle>Filtres</SheetTitle>
                  <SheetDescription>Panneau coulissant (bottom-sheet sur mobile).</SheetDescription>
                </SheetHeader>
              </SheetContent>
            </Sheet>

            <AlertDialog>
              <AlertDialogTrigger asChild><Button variant="destructive"><Trash2 /> Supprimer</Button></AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Supprimer ce lead ?</AlertDialogTitle>
                  <AlertDialogDescription>Cette action est irréversible.</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Annuler</AlertDialogCancel>
                  <AlertDialogAction>Supprimer</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>

            <Popover>
              <PopoverTrigger asChild><Button variant="outline">Popover</Button></PopoverTrigger>
              <PopoverContent>
                <p className="text-sm font-medium">Aperçu rapide</p>
                <p className="mt-1 text-sm text-muted-foreground">Contenu flottant ancré au déclencheur.</p>
              </PopoverContent>
            </Popover>

            <DropdownMenu>
              <DropdownMenuTrigger asChild><Button variant="outline">Menu</Button></DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuLabel>Actions</DropdownMenuLabel>
                <DropdownMenuItem><Pencil /> Modifier</DropdownMenuItem>
                <DropdownMenuItem><Download /> Exporter</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem destructive><Trash2 /> Supprimer</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <SimpleTooltip label="Astuce contextuelle">
              <Button variant="ghost">Survolez-moi</Button>
            </SimpleTooltip>
          </Section>

          <Section id="feedback" title="Feedback & affichage">
            <Button variant="outline" onClick={() => toast.success('Enregistré')}>Toast succès</Button>
            <Button variant="outline" onClick={() => toast.error('Échec de l’enregistrement')}>Toast erreur</Button>
            <AvatarGroup>
              <Avatar><AvatarFallback>{initials('Reda Kasri')}</AvatarFallback></Avatar>
              <Avatar><AvatarFallback>{initials('Meryem B')}</AvatarFallback></Avatar>
            </AvatarGroup>
            <div className="w-56"><Progress value={64} /></div>
            <div className="w-full max-w-md">
              <Tabs defaultValue="t1">
                <TabsList>
                  <TabsTrigger value="t1">Détails</TabsTrigger>
                  <TabsTrigger value="t2">Historique</TabsTrigger>
                </TabsList>
                <TabsContent value="t1" className="text-sm text-muted-foreground">Contenu — détails.</TabsContent>
                <TabsContent value="t2" className="text-sm text-muted-foreground">Contenu — historique.</TabsContent>
              </Tabs>
            </div>
            <div className="w-full max-w-md">
              <Accordion type="single" collapsible>
                <AccordionItem value="a1">
                  <AccordionTrigger>Profil énergétique</AccordionTrigger>
                  <AccordionContent>Facture moyenne, tranche ONEE, ombrage…</AccordionContent>
                </AccordionItem>
                <AccordionItem value="a2">
                  <AccordionTrigger>Toiture & site</AccordionTrigger>
                  <AccordionContent>Surface, inclinaison, orientation…</AccordionContent>
                </AccordionItem>
              </Accordion>
            </div>
          </Section>

          <Section id="states" title="États (chargement / vide)">
            <div className="w-64 space-y-3">
              <Skeleton className="h-8 w-1/2" />
              <SkeletonText lines={3} />
            </div>
            <EmptyState
              icon={Inbox}
              title="Aucun lead"
              description="Créez votre premier lead pour démarrer le pipeline."
              action={<Button size="sm"><Plus /> Nouveau lead</Button>}
              className="max-w-sm"
            />
          </Section>

          <Section id="format" title="Formatage (lib/format)">
            <DefinitionList
              className="w-full max-w-md"
              items={[
                { term: 'Montant', description: formatMAD(1284500.5) },
                { term: 'Nombre', description: formatNumber(1234567) },
                { term: 'Pourcentage', description: formatPercent(19) },
                { term: 'Date', description: formatDate('2026-06-18') },
                { term: 'Téléphone', description: formatPhoneMA('+212612345678') },
              ]}
            />
          </Section>

          <section id="datatable" className="scroll-mt-6">
            <h2 className="font-display text-lg font-semibold tracking-tight">
              Tableau de données (moteur DataTable — Groupe H)
            </h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Grille réutilisable : tri multi-colonnes, recherche surlignée, filtres,
              colonnes (afficher/masquer/épingler/réordonner/redimensionner), densité,
              sélection + barre d'actions groupées, actions de ligne, édition en place,
              lignes dépliables, sous-totaux TVA, vues sauvegardées, pagination
              « X–Y sur N », persistance URL, virtualisation et repli mobile en cartes.
            </p>
            <Separator className="my-3" />
            {/* P170 — checklist des fonctions premium, avec où les voir dans la démo. */}
            <ul className="mb-4 grid gap-2 text-sm sm:grid-cols-2">
              <DoneItem><strong className="text-foreground">Densité</strong> — suit le sélecteur en tête de page (hauteurs de lignes/contrôles).</DoneItem>
              <DoneItem><strong className="text-foreground">Épinglage</strong> — la colonne « Client » est gelée à gauche (<Code>pinned: &apos;left&apos;</Code>).</DoneItem>
              <DoneItem><strong className="text-foreground">Barre d’actions groupées</strong> — cochez des lignes : slots configurables (assigner, statut, export, supprimer).</DoneItem>
              <DoneItem><strong className="text-foreground">Cartes mobiles</strong> — sous 768 px, chaque ligne devient une carte empilée.</DoneItem>
              <DoneItem><strong className="text-foreground">Édition en place</strong> — le montant est éditable (validation + toast + annuler).</DoneItem>
              <DoneItem><strong className="text-foreground">Virtualisation</strong> — la 2ᵉ table fait défiler 619 lignes sans dépendance.</DoneItem>
            </ul>
            <DataTableDemo />
          </section>

          {/* ── UX1 — Kit « coquille de module ERP » ──────────────────────────── */}
          <section id="module-kit" className="scroll-mt-6">
            <h2 className="font-display text-lg font-semibold tracking-tight">
              Kit module ERP (UX1)
            </h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Coquilles partagées par les modules back-office (contrats, SAV, flotte, QHSE, GED…) :
              tableau de bord de KPI, coquille de liste, centre d’échéances (tri « urgent d’abord »)
              et pastilles de statut par module. Un seul import : <Code>@/ui/module</Code>.
            </p>
            <Separator className="my-3" />
            <ModuleDashboard
              stats={[
                { label: 'Contrats actifs', value: formatNumber(42), delta: { value: '+4', direction: 'up' }, hint: 'ce mois', icon: Bell },
                { label: 'À renouveler (30 j)', value: formatNumber(7), hint: 'échéances proches' },
                { label: 'Interventions SAV', value: formatNumber(13), delta: { value: '-2', direction: 'down' }, hint: 'ouvertes' },
                { label: 'Encaissé', value: formatMAD(284500), hint: 'ce mois' },
              ]}
            />
            <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_320px]">
              <ListShell
                title="Contrats"
                subtitle="Coquille de liste (PageHeader + DataTable) — passe-plat fin."
                actions={<Button size="sm"><Plus /> Nouveau contrat</Button>}
                columns={[
                  { id: 'ref', header: 'Référence', accessor: (r) => r.ref, width: 140 },
                  { id: 'client', header: 'Client', accessor: (r) => r.client },
                  {
                    id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false, width: 130,
                    cell: (v) => <StatutContratDemo status={v} />,
                  },
                  {
                    id: 'montant', header: 'Montant', accessor: (r) => r.montant, align: 'right', numeric: true, width: 150,
                    searchable: false, cell: (v) => formatMAD(v),
                  },
                ]}
                rows={[
                  { id: 1, ref: 'CT-2026-001', client: 'Reda Kasri', statut: 'actif', montant: 120000 },
                  { id: 2, ref: 'CT-2026-002', client: 'Meryem B', statut: 'expire', montant: 84000 },
                  { id: 3, ref: 'CT-2026-003', client: 'Karim T', statut: 'resilie', montant: 46000 },
                ]}
                searchable={false}
                exportName="contrats-demo"
                emptyTitle="Aucun contrat"
              />
              <EcheanceCenter
                title="Échéances à venir"
                items={[
                  { id: 'a', label: 'CT-2026-002 — renouvellement', meta: 'Meryem B', daysLeft: -3 },
                  { id: 'b', label: 'Garantie SAV #418', meta: 'Onduleur Huawei', daysLeft: 5 },
                  { id: 'c', label: 'Contrôle QHSE trimestriel', meta: 'Site Rabat', daysLeft: 21 },
                  { id: 'd', label: 'Entretien flotte — Dacia', meta: 'AB-1234-56', daysLeft: 62 },
                ]}
              />
            </div>
          </section>

          {/* ── VX45 — Voix & microcopie ──────────────────────────────────────── */}
          <section id="voix" className="scroll-mt-6">
            <h2 className="font-display text-lg font-semibold tracking-tight">
              Voix &amp; microcopie
            </h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Deux règles pour tout texte visible (toasts, dialogues, états vides,
              chargements) au registre Doctolib — la chaleur par la CLARTÉ, jamais
              l&apos;emphase.
            </p>
            <Separator className="my-3" />
            <ul className="mb-4 grid gap-2 text-sm sm:grid-cols-2">
              <DoneItem>
                <strong className="text-foreground">Confirmations</strong> — fait +
                objet, jamais un point d&apos;exclamation :{' '}
                <Code>Devis enregistré.</Code> plutôt que{' '}
                <Code>Opération réussie !</Code>
              </DoneItem>
              <DoneItem>
                <strong className="text-foreground">Erreurs</strong> — quoi + la
                prochaine étape, jamais un message technique brut :{' '}
                <Code>Envoi impossible — vérifiez votre connexion et réessayez.</Code>
              </DoneItem>
              <DoneItem>
                <strong className="text-foreground">Chargements</strong> — nommés,
                jamais un spinner muet : <Code>Génération du PDF…</Code> plutôt
                que <Code>Chargement…</Code> seul quand l&apos;action est connue.
              </DoneItem>
              <DoneItem>
                <strong className="text-foreground">Icônes fonctionnelles</strong> —
                toujours un composant lucide (<Code>Zap</Code>, <Code>Home</Code>,
                <Code>FileText</Code>…), jamais un emoji brut : le rendu emoji
                varie par OS et casse le système d&apos;icônes (VX45).
              </DoneItem>
            </ul>
            <div className="flex flex-wrap items-start gap-3">
              <div className="flex w-56 flex-col gap-1 rounded-lg border border-success/30 bg-success/10 p-3">
                <span className="text-xs font-medium text-success">Confirmation</span>
                <span className="text-sm text-foreground">Devis enregistré.</span>
              </div>
              <div className="flex w-56 flex-col gap-1 rounded-lg border border-destructive/30 bg-destructive/10 p-3">
                <span className="text-xs font-medium text-destructive">Erreur</span>
                <span className="text-sm text-foreground">Envoi impossible — vérifiez votre connexion et réessayez.</span>
              </div>
              <div className="flex w-56 flex-col gap-1 rounded-lg border border-info/30 bg-info/10 p-3">
                <span className="text-xs font-medium text-info">Chargement nommé</span>
                <span className="text-sm text-foreground">Génération du PDF…</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </TooltipProvider>
  )
}

/* UX1 — Démo : une taxonomie de statut de module via la fabrique statusPill. */
const StatutContratDemo = statusPill({
  actif: { label: 'Actif', tone: 'success' },
  expire: { label: 'Expiré', tone: 'warning' },
  resilie: { label: 'Résilié', tone: 'danger' },
})

export default UIShowcase
