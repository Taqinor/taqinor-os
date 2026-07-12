// ODX5 — Onglet « Applications » de la page Paramètres (catalogue de modules).
//
// Page ADMIN-GATED (Directeur uniquement — plus strict que la plupart des
// autres sections, admin/responsable) : liste les modules installables de la
// société (icône, libellé FR, description, catégorie, dépendances, état
// actif/désactivé), branchée sur le catalogue ODX3 (`GET /core/modules/`),
// avec un interrupteur par module. Activer un module active aussi la
// fermeture de ses dépendances (comme l'auto-install Odoo, transparent pour
// l'utilisateur) ; désactiver un module dont d'autres modules actifs
// dépendent est refusé par le serveur (400 + liste des dépendants) — la
// désactivation en cascade n'a lieu qu'après confirmation explicite. Le motif
// éventuel (`ModuleToggle.raison`, ex. « hors offre », « en pilote ») est lu
// depuis `/core/module-toggles/` et affiché sous un module désactivé.
//
// Distinct de WR12 (qui couvre 4 autres flags métier, pas les modules).
// Fonctionnel uniquement — cartes/Card du kit UX1 (même gabarit que
// ConfidentialiteSection.jsx), aucun travail de design.
import { useEffect, useMemo, useState } from 'react'
import { useIsAdmin } from '../../hooks/useHasPermission'
import {
  Lock, Package, Users, Truck, Wrench, Settings, Shield, HardHat,
  AlertTriangle, ShoppingCart, BarChart3, Wallet, ScrollText, MessageSquare, Key,
} from 'lucide-react'
import { toast } from '../../ui/confirm'
import coreApi from '../../api/coreApi'
import {
  Card, CardContent, Badge, Spinner, EmptyState, Switch,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '../../ui'
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

export default function ApplicationsSection() {
  // Admin-gated (Directeur) : plus strict que le défaut admin/responsable
  // des autres sections — bascule de module est une action sensible.
  const canManage = useIsAdmin()

  const [modules, setModules] = useState([])
  const [raisons, setRaisons] = useState({}) // clé module -> raison (si désactivé)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busyKey, setBusyKey] = useState(null)
  // Confirmation de désactivation en cascade : { key, label, dependants, detail } | null
  const [cascadeConfirm, setCascadeConfirm] = useState(null)

  const load = () => Promise.all([
    coreApi.modules.catalogue(),
    coreApi.modules.toggles.list(),
  ])
    .then(([catalogueRes, togglesRes]) => {
      setModules(catalogueRes.data ?? [])
      const rows = togglesRes.data?.results ?? togglesRes.data ?? []
      const map = {}
      rows.forEach((row) => { if (row.raison) map[row.module] = row.raison })
      setRaisons(map)
      setLoadError(false)
    })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  useEffect(() => {
    if (!canManage) { setLoading(false); return }
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canManage])

  const labelByKey = useMemo(
    () => Object.fromEntries(modules.map((m) => [m.key, m.label])),
    [modules],
  )

  // Regroupement par catégorie du manifest (façon menu Apps d'Odoo) —
  // catégories triées alphabetiquement, modules triés par libellé dans
  // chaque catégorie (rendu déterministe, testable).
  const groups = useMemo(() => {
    const byCategorie = {}
    modules.forEach((m) => {
      const cat = m.categorie || 'Technique'
      ;(byCategorie[cat] ||= []).push(m)
    })
    return Object.keys(byCategorie).sort().map((categorie) => ({
      categorie,
      items: byCategorie[categorie].slice().sort((a, b) => a.label.localeCompare(b.label)),
    }))
  }, [modules])

  const activer = async (mod) => {
    setBusyKey(mod.key)
    try {
      await coreApi.modules.activer(mod.key)
      await load()
    } catch (e) {
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
      // ODX3 — 400 de dépendance : {detail, dependants: [...]}. Sans cascade
      // déjà tentée, proposer la confirmation plutôt qu'un simple toast.
      if (e?.response?.status === 400 && Array.isArray(data?.dependants) && data.dependants.length && !cascade) {
        setCascadeConfirm({
          key: mod.key, label: mod.label,
          dependants: data.dependants, detail: data.detail,
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
    if (nextActif) activer(mod)
    else desactiver(mod)
  }

  const confirmCascade = () => {
    const mod = modules.find((m) => m.key === cascadeConfirm?.key)
    if (mod) desactiver(mod, { cascade: true })
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

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[11.5px] text-muted-foreground">
        Modules installés pour votre société. Désactiver un module masque sa
        navigation et ses écrans (aucune donnée n'est supprimée) ; le
        réactiver le restaure aussitôt. Activer un module active aussi les
        modules dont il dépend.
      </p>

      {groups.map((group) => (
        <Card key={group.categorie}>
          <CardContent className="pt-4 sm:pt-5">
            <SectionTitle label={group.categorie} />
            <div className="flex flex-col gap-2">
              {group.items.map((mod) => {
                const Icon = iconFor(mod.icone)
                const raison = !mod.actif ? raisons[mod.key] : null
                return (
                  <div key={mod.key} className="rounded-lg border border-border p-3"
                    data-testid={`module-row-${mod.key}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      <span className={[
                        'min-w-[140px] flex-[1_1_140px] font-medium text-sm',
                        mod.actif ? '' : 'opacity-60',
                      ].join(' ')}>
                        {mod.label}
                      </span>
                      {mod.depends?.length > 0 && (
                        <span className="text-xs text-muted-foreground">
                          Dépend de : {mod.depends.map((d) => labelByKey[d] ?? d).join(', ')}
                        </span>
                      )}
                      <div className="ml-auto flex items-center gap-2">
                        <Badge tone={mod.actif ? 'success' : 'neutral'}>
                          {mod.actif ? 'Activé' : 'Désactivé'}
                        </Badge>
                        <Switch
                          checked={mod.actif}
                          disabled={busyKey === mod.key}
                          onCheckedChange={(v) => onToggle(mod, v)}
                          aria-label={`${mod.actif ? 'Désactiver' : 'Activer'} le module ${mod.label}`}
                        />
                      </div>
                    </div>
                    {mod.description && (
                      <p className="mt-1 text-xs text-muted-foreground">{mod.description}</p>
                    )}
                    {raison && (
                      <p className="mt-1 text-xs italic text-muted-foreground">Motif : {raison}</p>
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
            <AlertDialogTitle>Désactiver « {cascadeConfirm?.label} » ?</AlertDialogTitle>
            <AlertDialogDescription>
              {cascadeConfirm?.detail ?? (
                `Les modules actifs suivants en dépendent : ${
                  (cascadeConfirm?.dependants ?? []).map((d) => labelByKey[d] ?? d).join(', ')
                }. Les désactiver aussi ?`
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={(e) => { e.preventDefault(); confirmCascade() }}>
              Désactiver en cascade
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
