// ODX5 — Onglet « Applications » de la page Paramètres (catalogue de modules).
// ODY24 — … devenu une BOUTIQUE : le même écran, au langage du Menu d'accueil.
//
// Page ADMIN-GATED (Directeur uniquement — plus strict que la plupart des
// autres sections, admin/responsable) : liste les modules installables de la
// société (icône, libellé FR, description, catégorie, dépendances, état
// installé/disponible), branchée sur le catalogue ODX3 (`GET /core/modules/`),
// avec un interrupteur par module. Activer un module active aussi la
// fermeture de ses dépendances (comme l'auto-install Odoo) ; désactiver un
// module dont d'autres modules actifs dépendent est refusé par le serveur
// (400 + liste des dépendants) — la désactivation en cascade n'a lieu qu'après
// confirmation explicite. Le motif éventuel (`ModuleToggle.raison`, ex. « hors
// offre », « en pilote ») est lu depuis `/core/module-toggles/` et affiché sous
// un module désactivé.
//
// CE QUE ODY24 CHANGE (et ce qu'il ne change PAS).
//   • Fonctionnalité BYTE-IDENTIQUE côté serveur : mêmes endpoints
//     (`/core/modules/`, `…/activer/`, `…/desactiver/?cascade=1`,
//     `/core/module-toggles/`), mêmes gardes admin, même sémantique de cascade.
//   • Ce qui change est le RENDU et le MOMENT de la confirmation : la cascade
//     est désormais annoncée AVANT la bascule, calculée depuis le graphe
//     `depends` que le catalogue renvoie DÉJÀ (aucune 2ᵉ source, aucun appel
//     supplémentaire). Le 400 serveur reste le filet de sécurité — il fait
//     toujours foi et rouvre le même dialogue si l'aperçu et le serveur
//     divergent (catalogue rafraîchi entre-temps).
//
// NE PAS CONFONDRE avec la marketplace d'extensions no-code NTEXT14
// (`extensions.ExtensionInstall`) : écran distinct, modèle distinct.
// Distinct aussi de WR12 (4 autres flags métier, pas les modules).
import { useEffect, useMemo, useState } from 'react'
import { useIsAdmin } from '../../hooks/useHasPermission'
import {
  Lock, Package, Users, Truck, Wrench, Settings, Shield, HardHat,
  AlertTriangle, ShoppingCart, BarChart3, Wallet, ScrollText, MessageSquare, Key,
  Search,
} from 'lucide-react'
import { toast } from '../../ui/confirm'
import coreApi from '../../api/coreApi'
import {
  Card, CardContent, Badge, Spinner, EmptyState, Switch, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '../../ui'
import AppIcon from '../../ui/AppIcon'
import { iconNodeForApp, accentForApp } from '../../lib/apps/appIcon'
import { normalise } from '../../lib/apps/appSearch'
import { SectionTitle } from './peComponents'

// Résolution icône par manifest (`module_manifest.icone`, kebab-case côté
// backend) — mapping VOLONTAIREMENT restreint aux icônes déjà utilisées et
// prouvées dans ce dépôt (Sidebar.jsx) : aucun nom d'icône non vérifié.
// Repli neutre (`Package`, « module/app ») pour toute clé non couverte.
const MODULE_ICONS = {
  package: Package,
  users: Users,
  'user-circle': Users,
  truck: Truck,
  wrench: Wrench,
  tool: Wrench,
  settings: Settings,
  shield: Shield,
  'hard-hat': HardHat,
  'alert-triangle': AlertTriangle,
  'shopping-cart': ShoppingCart,
  'bar-chart': BarChart3,
  banknote: Wallet,
  history: ScrollText,
  'message-circle': MessageSquare,
  lock: Key,
}
const iconFor = (icone) => MODULE_ICONS[icone] ?? Package

// Valeur sentinelle du filtre « toutes catégories » : Radix Select interdit
// une valeur vide (elle est réservée à l'effacement).
const TOUTES = '__toutes__'

/* ODY9 — L'ÉCRAN APPLICATIONS EST LA 4ᵉ SURFACE. Il résolvait son icône depuis
   le manifest backend (`MODULE_ICONS` ci-dessus) tandis que le Menu d'accueil,
   le lanceur VX9 et les épinglés VX10 la lisaient du `module.config` frontend :
   deux glyphes possibles pour la MÊME app. On préfère donc désormais l'icône du
   registre frontend (source unique, `lib/apps/appIcon.js`) et on ne retombe sur
   le manifest que pour un module SANS écran frontend — que le registre ne
   connaît pas et que les trois autres surfaces n'affichent donc jamais. */
function glypheModule(mod) {
  const duRegistre = iconNodeForApp(mod.key)
  if (duRegistre) return duRegistre
  const Repli = iconFor(mod.icone)
  return <Repli aria-hidden="true" />
}

/* ODY24 — Fermetures de dépendances calculées depuis le catalogue DÉJÀ chargé.
   Ce n'est pas un 2ᵉ registre : c'est la même arête `depends` que le serveur
   (`core.modules.dependency_closure` / `dependents`) lit du même manifest — on
   la parcourt ici uniquement pour ANNONCER l'effet avant de le demander. Le
   serveur reste seul juge (400 de dépendance conservé). */
function fermetureDependances(key, parKey) {
  const vus = new Set()
  const pile = [...(parKey[key]?.depends ?? [])]
  while (pile.length) {
    const cur = pile.pop()
    if (vus.has(cur) || cur === key) continue
    vus.add(cur)
    pile.push(...(parKey[cur]?.depends ?? []))
  }
  return vus
}

function fermetureDependants(key, modules) {
  const vus = new Set()
  const pile = [key]
  while (pile.length) {
    const cur = pile.pop()
    modules.forEach((m) => {
      if (m.key === key || vus.has(m.key)) return
      if ((m.depends ?? []).includes(cur)) {
        vus.add(m.key)
        pile.push(m.key)
      }
    })
  }
  return vus
}

// Date courte FR (« le 12/07 ») — jamais l'horloge du navigateur, uniquement
// la valeur renvoyée par le serveur (rendu déterministe, testable).
function dateCourte(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const jj = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  return `${jj}/${mm}`
}

/* ODY25 — La ligne d'état d'une carte, construite à partir du JOURNAL
   D'INSTALLATION (`GET /core/modules/journal/`) quand il existe :
   « Installée le 12/07 par Meryem » / « Désactivée le 03/08 par Reda ».
   Sans entrée de journal (bascule antérieure à ODY25, ou app jamais touchée),
   on retombe sur la date du ModuleToggle, puis sur rien du tout — jamais sur
   un auteur inventé. */
function ligneEtat(mod, entree, ligneToggle) {
  const quand = dateCourte(entree?.le ?? ligneToggle?.updated_at)
  const par = entree?.par ? ` par ${entree.par}` : ''
  if (!quand) return ''
  return mod.actif
    ? `Installée le ${quand}${par}`
    : `Désactivée le ${quand}${par}`
}

export default function ApplicationsSection() {
  // Admin-gated (Directeur) : plus strict que le défaut admin/responsable
  // des autres sections — bascule de module est une action sensible.
  const canManage = useIsAdmin()

  const [modules, setModules] = useState([])
  // clé module -> ligne ModuleToggle ({raison, updated_at}) quand elle existe.
  const [toggles, setToggles] = useState({})
  // ODY25 — clé module -> dernière bascule journalisée ({actif, par, le, raison}).
  const [journal, setJournal] = useState({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busyKey, setBusyKey] = useState(null)
  const [recherche, setRecherche] = useState('')
  const [categorieFiltre, setCategorieFiltre] = useState(TOUTES)
  // Confirmation AVEC APERÇU DE CASCADE (ODY24) :
  // { mode: 'installer'|'desinstaller', key, label, cascade: string[], detail }
  const [cascadeConfirm, setCascadeConfirm] = useState(null)

  const load = () => Promise.all([
    coreApi.modules.catalogue(),
    coreApi.modules.toggles.list(),
    // ODY25 — le journal ENRICHIT la boutique, il ne la conditionne pas : s'il
    // échoue (droits, backend plus ancien), l'écran reste pleinement
    // fonctionnel avec un état sans auteur plutôt qu'une page en erreur.
    coreApi.modules.journal().catch(() => ({ data: [] })),
  ])
    .then(([catalogueRes, togglesRes, journalRes]) => {
      setModules(catalogueRes.data ?? [])
      const rows = togglesRes.data?.results ?? togglesRes.data ?? []
      const map = {}
      rows.forEach((row) => { map[row.module] = row })
      setToggles(map)
      const entrees = journalRes?.data?.results ?? journalRes?.data ?? []
      const parModule = {}
      ;(Array.isArray(entrees) ? entrees : []).forEach((row) => {
        if (!parModule[row.module]) parModule[row.module] = row
      })
      setJournal(parModule)
      setLoadError(false)
    })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- court-circuite le chargement pour un utilisateur non-admin
    if (!canManage) { setLoading(false); return }
    load()
  }, [canManage])

  const labelByKey = useMemo(
    () => Object.fromEntries(modules.map((m) => [m.key, m.label])),
    [modules],
  )
  const parKey = useMemo(
    () => Object.fromEntries(modules.map((m) => [m.key, m])),
    [modules],
  )
  const nomsLisibles = (cles) => cles.map((k) => labelByKey[k] ?? k).join(', ')

  const categories = useMemo(() => {
    const set = new Set(modules.map((m) => m.categorie || 'Technique'))
    return [...set].sort()
  }, [modules])

  // Recherche (libellé + description + clé technique, insensible aux accents)
  // et filtre par catégorie — puis regroupement par catégorie, catégories
  // triées, modules triés par libellé : rendu déterministe, testable.
  const groups = useMemo(() => {
    const q = normalise(recherche)
    const byCategorie = {}
    modules.forEach((m) => {
      const cat = m.categorie || 'Technique'
      if (categorieFiltre !== TOUTES && cat !== categorieFiltre) return
      if (q) {
        const foin = normalise(`${m.label} ${m.description ?? ''} ${m.key}`)
        if (!foin.includes(q)) return
      }
      ;(byCategorie[cat] ||= []).push(m)
    })
    return Object.keys(byCategorie).sort().map((categorie) => ({
      categorie,
      items: byCategorie[categorie].slice().sort((a, b) => a.label.localeCompare(b.label)),
    }))
  }, [modules, recherche, categorieFiltre])

  const activer = async (mod, { depuisApercu = false } = {}) => {
    setBusyKey(mod.key)
    try {
      await coreApi.modules.activer(mod.key)
      setCascadeConfirm(null)
      await load()
    } catch (e) {
      if (depuisApercu) setCascadeConfirm(null)
      toast.error(e?.response?.data?.detail ?? 'Activation impossible.')
    } finally {
      setBusyKey(null)
    }
  }

  const desactiver = async (mod, { cascade = false } = {}) => {
    setBusyKey(mod.key)
    try {
      await coreApi.modules.desactiver(mod.key, { cascade })
      setCascadeConfirm(null)
      await load()
    } catch (e) {
      const data = e?.response?.data
      // ODX3 — 400 de dépendance : {detail, dependants: [...]}. Filet de
      // sécurité conservé : si l'aperçu ODY24 et le serveur divergent (une
      // autre session a activé un dépendant depuis le chargement), on rouvre
      // le MÊME dialogue plutôt qu'un simple toast.
      if (e?.response?.status === 400 && Array.isArray(data?.dependants) && data.dependants.length && !cascade) {
        setCascadeConfirm({
          mode: 'desinstaller', key: mod.key, label: mod.label,
          cascade: data.dependants, detail: data.detail,
        })
      } else {
        toast.error(data?.detail ?? 'Désactivation impossible.')
        setCascadeConfirm(null)
      }
    } finally {
      setBusyKey(null)
    }
  }

  const onToggle = (mod, nextActif) => {
    if (nextActif) {
      // Aperçu : les dépendances encore INACTIVES seront activées avec lui.
      const aussi = [...fermetureDependances(mod.key, parKey)]
        .filter((k) => parKey[k] && !parKey[k].actif)
        .sort()
      if (aussi.length) {
        setCascadeConfirm({ mode: 'installer', key: mod.key, label: mod.label, cascade: aussi })
        return
      }
      activer(mod)
      return
    }
    // Aperçu : les dépendants encore ACTIFS seront désactivés avec lui.
    const aussi = [...fermetureDependants(mod.key, modules)]
      .filter((k) => parKey[k]?.actif)
      .sort()
    if (aussi.length) {
      setCascadeConfirm({ mode: 'desinstaller', key: mod.key, label: mod.label, cascade: aussi })
      return
    }
    desactiver(mod)
  }

  const confirmCascade = () => {
    const mod = modules.find((m) => m.key === cascadeConfirm?.key)
    if (!mod) return
    if (cascadeConfirm.mode === 'installer') activer(mod, { depuisApercu: true })
    else desactiver(mod, { cascade: true })
  }

  if (!canManage) {
    return (
      <EmptyState
        icon={Lock}
        title="Accès restreint"
        description="Le catalogue des Applications (activation/désactivation des modules) est réservé aux comptes Directeur."
        className="my-6"
      />
    )
  }

  if (loading) return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (loadError) {
    return (
      <EmptyState title="Impossible de charger le catalogue des modules"
        description="Une erreur est survenue lors du chargement." className="py-6" />
    )
  }

  const installer = cascadeConfirm?.mode === 'installer'

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[11.5px] text-muted-foreground">
        Modules installés pour votre société. Désactiver un module masque sa
        navigation et ses écrans (aucune donnée n'est supprimée) ; le
        réactiver le restaure aussitôt. Activer un module active aussi les
        modules dont il dépend — l'effet exact vous est annoncé avant.
      </p>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search aria-hidden="true"
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
            placeholder="Rechercher une application…"
            aria-label="Rechercher une application"
            className="pl-8"
          />
        </div>
        <div className="sm:w-56">
          <Select value={categorieFiltre} onValueChange={setCategorieFiltre}>
            <SelectTrigger aria-label="Filtrer par catégorie">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TOUTES}>Toutes les catégories</SelectItem>
              {categories.map((c) => (
                <SelectItem key={c} value={c}>{c}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {groups.length === 0 && (
        <EmptyState title="Aucune application ne correspond"
          description="Essayez un autre mot-clé ou une autre catégorie."
          className="py-6" />
      )}

      {groups.map((group) => (
        <Card key={group.categorie}>
          <CardContent className="pt-4 sm:pt-5">
            <SectionTitle label={group.categorie} />
            <div className="module-store-grid">
              {group.items.map((mod) => {
                const ligne = toggles[mod.key]
                const entree = journal[mod.key]
                const raison = !mod.actif ? (ligne?.raison || entree?.raison) : null
                // UNE seule phrase (un seul nœud de texte) : « Désactivée le
                // 03/08 par Reda — raison : hors offre ».
                const etatComplet = [
                  ligneEtat(mod, entree, ligne),
                  raison ? `raison : ${raison}` : '',
                ].filter(Boolean).join(' — ')
                const requis = mod.depends ?? []
                return (
                  <div key={mod.key} className="module-store-card"
                    data-testid={`module-row-${mod.key}`}>
                    <div className="flex items-start gap-3">
                      <AppIcon
                        icon={glypheModule(mod)}
                        accent={accentForApp(mod.key)}
                        size="sm"
                        className="shrink-0"
                      />
                      <div className="min-w-0 flex-1">
                        <span className={[
                          'block truncate font-medium text-sm',
                          mod.actif ? '' : 'opacity-70',
                        ].join(' ')}>
                          {mod.label}
                        </span>
                        <Badge tone={mod.actif ? 'success' : 'neutral'} className="mt-1">
                          {mod.actif ? 'Installée' : 'Disponible'}
                        </Badge>
                      </div>
                      <Switch
                        checked={mod.actif}
                        disabled={busyKey === mod.key}
                        onCheckedChange={(v) => onToggle(mod, v)}
                        aria-label={`${mod.actif ? 'Désactiver' : 'Activer'} le module ${mod.label}`}
                      />
                    </div>
                    {mod.description && (
                      <p className="mt-2 text-xs text-muted-foreground">{mod.description}</p>
                    )}
                    {requis.length > 0 && (
                      <p className="mt-1.5 text-xs text-muted-foreground">
                        Nécessite : {nomsLisibles(requis)}
                      </p>
                    )}
                    {etatComplet && (
                      <p className="mt-1.5 text-xs text-muted-foreground">{etatComplet}</p>
                    )}
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      ))}

      <AlertDialog open={!!cascadeConfirm} onOpenChange={(open) => { if (!open) setCascadeConfirm(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {installer
                ? `Installer « ${cascadeConfirm?.label} » ?`
                : `Désactiver « ${cascadeConfirm?.label} » ?`}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {installer ? (
                `Cette application a besoin de : ${
                  nomsLisibles(cascadeConfirm?.cascade ?? [])
                }. Ces modules seront activés en même temps.`
              ) : (cascadeConfirm?.detail ?? (
                `Les modules actifs suivants en dépendent : ${
                  nomsLisibles(cascadeConfirm?.cascade ?? [])
                }. Les désactiver aussi ?`
              ))}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={(e) => { e.preventDefault(); confirmCascade() }}>
              {installer ? 'Installer avec ses dépendances' : 'Désactiver en cascade'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
