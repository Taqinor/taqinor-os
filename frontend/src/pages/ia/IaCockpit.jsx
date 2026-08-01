import { Search, Bot, ListChecks } from 'lucide-react'
import { ModuleHero, ModuleDashboard } from '../../ui/module'
import { useHasRole } from '../../hooks/useHasPermission'
import useResource from '../../hooks/useResource'
import { formatNumber } from '../../lib/format'
import iaApi from '../../api/iaApi'

/* ============================================================================
   ODY23 — Cockpit de l'app « Intelligence » (OCR + Agent IA + Actions IA).
   ----------------------------------------------------------------------------
   Porte d'entrée de l'app (VX15 ModuleHero + actions rapides + KPI), premier
   item de `features/ia/module.config.jsx` (route `/ia`) — jusqu'ici OCR/Agent
   IA/Actions IA n'avaient AUCUN écran d'accueil commun, seulement 3 outils
   isolés atteints depuis la Sidebar. Lecture seule : le KPI « Actions IA
   disponibles » réutilise GET /api/django/agent/actions/ (déjà consommé par
   AgentActions.jsx, WR8) — aucun nouvel appel réseau inventé.

   Les 3 cartes reprennent EXACTEMENT les gardes de rôle historiques du menu
   (Sidebar.jsx NAV_SECTIONS « INTELLIGENCE », avant extraction par ODY4) :
   OCR = responsable/admin, Agent IA = admin, Actions IA = tous les rôles
   authentifiés — une carte masquée pour un rôle qui ne peut pas ouvrir l'écran
   cible évite un lien mort plutôt qu'un clic suivi d'un refus silencieux.
   ========================================================================== */

export default function IaCockpit() {
  const canOcr = useHasRole(['responsable', 'admin'])
  const canAgent = useHasRole(['admin'])

  // ARC45 — fetch/état mutualisé ; le catalogue d'actions est déjà filtré par
  // permission côté serveur, donc `count` reflète ce que CET utilisateur peut
  // réellement déclencher (jamais un chiffre optimiste).
  const { data, loading, error } = useResource(
    () => iaApi.getAgentActions(),
    undefined,
    {
      initialData: { count: 0 },
      select: (res) => ({ count: res?.data?.count ?? (res?.data?.actions ?? []).length }),
      errorMessage: 'Catalogue d’actions IA indisponible.',
    },
  )

  const stats = [
    canOcr && {
      label: 'Traitement OCR',
      value: '→',
      hint: 'Extraire un document (facture, BC, devis…)',
      icon: Search,
      to: '/ia/ocr',
    },
    canAgent && {
      label: 'Agent IA conversationnel',
      value: '→',
      hint: 'Poser une question en langage naturel',
      icon: Bot,
      to: '/ia/agent',
    },
    {
      label: 'Actions IA disponibles',
      value: formatNumber(data.count ?? 0),
      hint: 'Catalogue accessible à votre rôle',
      icon: ListChecks,
      to: '/ia/actions',
    },
  ].filter(Boolean)

  return (
    <div className="page flex flex-col gap-6">
      <ModuleHero
        title="Intelligence"
        subtitle="OCR, agent conversationnel et actions agentiques — vue d’ensemble."
        accent="var(--module-accent-lune)"
        kpiSlot={<ModuleDashboard stats={stats} loading={loading} error={error} accent="var(--module-accent-lune)" />}
      />
    </div>
  )
}
