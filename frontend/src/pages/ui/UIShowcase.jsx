import { useState } from 'react'
import {
  Trash2, Plus, Settings, Search, Download, Inbox, Pencil, Bell, Save,
} from 'lucide-react'
import { ThemeToggle } from '../../design/ThemeToggle'
import { useDensity } from '../../design/theme-context'
import { formatMAD, formatNumber, formatPercent, formatDate, formatPhoneMA } from '../../lib/format'
import {
  Button, IconButton, Spinner,
  Badge, StatusPill, Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter,
  Stat, Separator, Skeleton, SkeletonText, EmptyState,
  Label, Input, Textarea, CurrencyInput, PercentInput, PhoneInput,
  Checkbox, Switch, RadioGroup, RadioGroupItem, Slider, Segmented,
  Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose,
  Sheet, SheetTrigger, SheetContent, SheetHeader, SheetTitle, SheetDescription,
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  Popover, PopoverTrigger, PopoverContent,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator,
  TooltipProvider, SimpleTooltip,
  Toaster, toast, Tag, Avatar, AvatarFallback, AvatarGroup, initials,
  DefinitionList, Tabs, TabsList, TabsTrigger, TabsContent,
  Accordion, AccordionItem, AccordionTrigger, AccordionContent, Progress,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem, SelectLabel,
  Combobox, MultiSelect, DatePicker, DateRangePicker, TimePicker,
  FileUpload,
  Form, FormSection, FormField, FormActions, FormErrorSummary, useDirtyGuard,
} from '../../ui'
import { DataTableDemo } from './DataTableDemo'
import {
  runValidation, errorSummary, isDirty, required, email,
} from '../../ui/form-utils'

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
        <Toaster />
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
                  <SelectLabel>Type d’installation</SelectLabel>
                  <SelectItem value="residentiel">Résidentiel</SelectItem>
                  <SelectItem value="industriel">Industriel / Commercial</SelectItem>
                  <SelectItem value="agricole">Agricole (pompage)</SelectItem>
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
            <DataTableDemo />
          </section>
        </div>
      </div>
    </TooltipProvider>
  )
}

export default UIShowcase
