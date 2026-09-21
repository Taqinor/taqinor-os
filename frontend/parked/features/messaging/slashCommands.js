// XKB31 — Commandes / dans le composer.
//
// Helpers PURS (testés en .mjs) pour la détection/le parsing des
// slash-commands (`/lead`, `/tache`, `/devis`, `/aide`) tapées dans le
// composer du chat. Le picker liste les commandes AUTORISÉES pour
// l'utilisateur (filtrées côté serveur via `iaApi.getAgentActions()` — le
// registre d'actions de l'agent existant, `/api/django/agent/actions/`).
// L'EXÉCUTION ne se fait jamais ici : ce module ne fait aucun appel réseau,
// il construit seulement la question en langage naturel envoyée au même
// pipeline propose→confirm que le Copilote (S8/S19 : `iaApi.queryAgent` puis
// `iaApi.confirmAction` sur le `confirm_token` renvoyé).

// Une commande slash déclarée ici mappe vers UNE clé du registre agent
// (`crm.lead.create`, `ventes.devis.creer_auto`…) — mais la correspondance
// réelle est vérifiée à l'usage
// contre la liste retournée par `getAgentActions()` (jamais supposée
// disponible : une commande dont l'action n'est pas dans le registre de
// l'utilisateur reste visible dans `/aide` mais est désactivée dans le
// picker).
export const SLASH_COMMANDS = [
  {
    cmd: 'lead',
    label: '/lead',
    description: 'Créer un lead (opportunité CRM)',
    actionKey: 'crm.lead.create',
    hint: 'nom [ville] [téléphone]',
    // Construit la question en langage naturel envoyée à /sql-agent/query —
    // le même agent qui gère déjà "crée un lead nommé …" depuis le Copilote.
    toQuestion: (args) => {
      const nom = args[0]
      const rest = args.slice(1).join(' ')
      return nom
        ? `Crée un lead nommé ${nom}${rest ? ` (${rest})` : ''}.`
        : 'Crée un lead.'
    },
  },
  {
    // AUCUNE action « créer une tâche » n'existe dans le registre agent à ce
    // jour (grep de tous les `apps/*/agent_actions.py` : rien pour
    // tâche/activité). `actionKey` pointe donc DÉLIBÉRÉMENT vers une clé
    // absente du registre — le picker/`/aide` la montrent, `filterSlashCommands`
    // la marque `available:false` (jamais un no-op silencieux qui ferait
    // croire à une écriture), jusqu'à ce qu'une vraie action serveur existe.
    cmd: 'tache',
    label: '/tache',
    description: 'Créer une tâche / activité de suivi',
    actionKey: 'crm.tache.create', // BLOQUÉ : pas encore dans le registre agent
    hint: 'titre [échéance]',
    toQuestion: (args) => {
      const titre = args.join(' ')
      return titre ? `Crée une tâche : ${titre}.` : 'Crée une tâche.'
    },
  },
  {
    cmd: 'devis',
    label: '/devis',
    description: 'Créer un devis dimensionné (auto-devis)',
    actionKey: 'ventes.devis.creer_auto',
    hint: 'client [détails]',
    toQuestion: (args) => {
      const rest = args.join(' ')
      return rest ? `Crée un devis pour ${rest}.` : 'Crée un devis.'
    },
  },
  {
    cmd: 'aide',
    label: '/aide',
    description: 'Lister les commandes disponibles',
    actionKey: null, // purement local, n'appelle jamais l'agent
    hint: '',
    toQuestion: () => null,
  },
]

// Détecte une commande slash en cours de frappe en DÉBUT de message
// (ex. "/lead Ahmed Casablanca"). Renvoie
// { query, args, raw } où `query` est le nom de commande tapé jusqu'ici (sans
// le "/"), ou null si le texte ne commence pas par "/" ou contient déjà un
// espace avant le curseur ET une commande résolue (on ne réouvre pas le
// picker une fois la commande choisie et des arguments en cours de frappe,
// sauf pour ré-filtrer tant qu'aucun espace n'a été tapé).
export function activeSlashCommand(text) {
  if (!text || !text.startsWith('/')) return null
  const firstSpace = text.indexOf(' ')
  if (firstSpace === -1) {
    // Encore en train de taper le nom de la commande.
    return { query: text.slice(1), args: [], raw: text }
  }
  const cmd = text.slice(1, firstSpace)
  const known = SLASH_COMMANDS.find((c) => c.cmd === cmd)
  if (!known) return null
  const args = text.slice(firstSpace + 1).trim().split(/\s+/).filter(Boolean)
  return { query: cmd, args, raw: text, resolved: known }
}

// Filtre la liste des commandes visibles pour le picker, en ne gardant QUE
// celles dont l'`actionKey` (si non-null) figure dans le registre autorisé
// pour l'utilisateur courant (issu de `iaApi.getAgentActions()` — jamais un
// registre statique côté frontend). `/aide` (actionKey null) est toujours
// visible.
export function filterSlashCommands(query, allowedActionKeys) {
  const q = (query || '').toLowerCase()
  const allowed = new Set(allowedActionKeys || [])
  return SLASH_COMMANDS
    .filter((c) => c.cmd.startsWith(q))
    .map((c) => ({ ...c, available: c.actionKey == null || allowed.has(c.actionKey) }))
}

// Construit le texte d'aide listant les commandes disponibles (pour /aide),
// à partir des mêmes commandes filtrées par disponibilité.
export function buildAideText(allowedActionKeys) {
  const commands = filterSlashCommands('', allowedActionKeys)
    .filter((c) => c.cmd !== 'aide')
  const lines = commands.map((c) => {
    const suffix = c.available ? '' : ' (indisponible pour votre rôle)'
    return `${c.label} ${c.hint} — ${c.description}${suffix}`
  })
  return ['Commandes disponibles :', ...lines].join('\n')
}

// Résout la commande + question à envoyer à l'agent pour un texte complet
// tapé par l'utilisateur (ex. "/lead Ahmed Casablanca"). Renvoie
// { command, question } ou null si le texte n'est pas une commande slash
// reconnue.
export function resolveSlashSubmit(text) {
  const trimmed = (text || '').trim()
  if (!trimmed.startsWith('/')) return null
  const spaceIdx = trimmed.indexOf(' ')
  const cmd = spaceIdx === -1 ? trimmed.slice(1) : trimmed.slice(1, spaceIdx)
  const command = SLASH_COMMANDS.find((c) => c.cmd === cmd)
  if (!command) return null
  const args = spaceIdx === -1 ? [] : trimmed.slice(spaceIdx + 1).trim().split(/\s+/).filter(Boolean)
  return { command, question: command.toQuestion(args) }
}
