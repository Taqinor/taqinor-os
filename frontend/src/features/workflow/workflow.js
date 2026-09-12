/* ============================================================================
   XPLT8 — logique pure du module Workflow & Jobs (testable sans React/DOM).
   ----------------------------------------------------------------------------
   Toutes les fonctions sont défensives sur des données absentes/malformées
   (jamais de throw sur `undefined`/`null` — l'écran ne doit jamais planter
   sur une réponse API incomplète).
   ========================================================================== */

/** Étape par défaut d'un éditeur de définition. */
export function nouvelleEtape(ordre) {
  return {
    ordre,
    nom: '',
    type_approbation: 'manuelle',
    sla_heures: '',
    role_requis: '',
    escalade_vers: '',
    // NTWFL4/7/10 — champs additifs du designer visuel (backend WIR51 +
    // NTWFL1-10). Valeurs neutres = comportement séquentiel/heures-brutes
    // inchangé tant qu'ils ne sont pas configurés.
    calendrier_ouvre: false,
    condition_transition: null,
    etape_alternative_si_echec: null,
    groupe_parallele: null,
  }
}

/** Renvoie une copie de `steps` avec les `ordre` renumérotés 1..n dans l'ordre
 * du tableau (l'ordre du tableau EST la source de vérité d'affichage). */
export function renumeroterEtapes(steps) {
  if (!Array.isArray(steps)) return []
  return steps.map((s, i) => ({ ...s, ordre: i + 1 }))
}

/** Déplace l'étape à `index` de `delta` positions (−1 = monter, +1 =
 * descendre), borné aux limites du tableau, puis renumérote. Ne mute pas
 * l'entrée. */
export function deplacerEtape(steps, index, delta) {
  if (!Array.isArray(steps)) return []
  const next = [...steps]
  const target = index + delta
  if (index < 0 || index >= next.length) return renumeroterEtapes(next)
  if (target < 0 || target >= next.length) return renumeroterEtapes(next)
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved)
  return renumeroterEtapes(next)
}

/** Ajoute une étape vide à la fin, renumérotée. */
export function ajouterEtape(steps) {
  const base = Array.isArray(steps) ? steps : []
  return renumeroterEtapes([...base, nouvelleEtape(base.length + 1)])
}

/** Retire l'étape à `index`, renumérotée. */
export function retirerEtape(steps, index) {
  if (!Array.isArray(steps)) return []
  return renumeroterEtapes(steps.filter((_, i) => i !== index))
}

/* NTWFL9 — palette de noeuds réutilisables : les 3 types déjà connus du
 * backend (`WorkflowStepDefinition.APPROBATION_CHOICES`), jamais un 4e type
 * inventé côté frontend. */
export const TYPES_ETAPE_PALETTE = [
  { type: 'manuelle', label: 'Manuelle' },
  { type: 'auto', label: 'Automatique' },
  { type: 'role', label: 'Par rôle' },
]

/** Ajoute une étape du `type` demandé (palette NTWFL9) à la fin, renumérotée.
 * Type inconnu => repli sur 'manuelle' (jamais un type qui n'existe pas côté
 * backend). */
export function ajouterEtapeDeType(steps, type) {
  const base = Array.isArray(steps) ? steps : []
  const typeValide = TYPES_ETAPE_PALETTE.some((t) => t.type === type) ? type : 'manuelle'
  const etape = { ...nouvelleEtape(base.length + 1), type_approbation: typeValide }
  return renumeroterEtapes([...base, etape])
}

/** Validation minimale d'une définition avant "création" côté brouillon
 * local : nom non vide + au moins 1 étape + chaque étape a un nom. */
export function validerDefinition(def) {
  const erreurs = []
  if (!def || !String(def.nom || '').trim()) {
    erreurs.push('Le nom de la définition est requis.')
  }
  const steps = (def && Array.isArray(def.steps)) ? def.steps : []
  if (steps.length === 0) {
    erreurs.push('Au moins une étape est requise.')
  }
  steps.forEach((s, i) => {
    if (!String((s && s.nom) || '').trim()) {
      erreurs.push(`L'étape ${i + 1} doit avoir un nom.`)
    }
  })
  return erreurs
}

/** Normalise la liste de jobs renvoyée par `GET core/jobs/` en tableau sûr,
 * triée par nom (le backend trie déjà, mais on ne fait jamais confiance à la
 * forme exacte d'une réponse réseau). */
export function normaliserJobs(data) {
  const list = Array.isArray(data) ? data : []
  return [...list]
    .filter((j) => j && typeof j === 'object')
    .sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')))
}

/** Normalise le catalogue de modèles de workflow (`GET
 * core/workflow-templates/`). */
export function normaliserModeles(data) {
  const list = Array.isArray(data) ? data : []
  return list.filter((m) => m && typeof m === 'object')
}

const SLA_MS_PAR_HEURE = 3600 * 1000

/** Calcule si une instance/étape est en retard SLA : `sla_echeance` (ISO) est
 * dans le passé et le statut est encore en attente. Ne lève jamais — une date
 * invalide renvoie `false`. `maintenant` injectable pour les tests. */
export function estEnRetardSla(item, maintenant = new Date()) {
  if (!item) return false
  const statut = item.statut || item.status
  if (statut && statut !== 'en_attente') return false
  const echeance = item.sla_echeance || item.echeance
  if (!echeance) return false
  const d = new Date(echeance)
  if (Number.isNaN(d.getTime())) return false
  return d.getTime() < maintenant.getTime()
}

/** Nombre d'heures de dépassement SLA (0 si non en retard ou données
 * manquantes). Utile pour trier/afficher "en retard de Xh". */
export function heuresDeRetard(item, maintenant = new Date()) {
  if (!estEnRetardSla(item, maintenant)) return 0
  const echeance = new Date(item.sla_echeance || item.echeance)
  return Math.max(0, Math.round(
    (maintenant.getTime() - echeance.getTime()) / SLA_MS_PAR_HEURE))
}

/* ============================================================================
   NTWFL6 — Designer visuel (canvas) : réordonnancement par glisser-déposer.
   ----------------------------------------------------------------------------
   `deplacerEtapeVersIndex` traduit un DROP (index source -> index cible) en
   delta pour `deplacerEtape` (déjà testé ci-dessus) : les DEUX vues (canvas
   NTWFL6 et éditeur liste XPLT8) partagent EXACTEMENT la même logique de
   réordonnancement -> elles restent forcément synchronisées (même `ordre`).
   ========================================================================== */

/** Déplace l'étape `indexSource` pour qu'elle atterrisse à `indexCible`
 * (sémantique "glisser-déposer" — l'étape prend la place visée, les autres
 * se décalent), puis renumérote. Délègue à `deplacerEtape` (delta = cible -
 * source) : garantit que le canvas NTWFL6 et l'éditeur liste XPLT8
 * produisent TOUJOURS le même résultat pour le même geste. */
export function deplacerEtapeVersIndex(steps, indexSource, indexCible) {
  if (!Array.isArray(steps)) return []
  if (indexSource === indexCible) return renumeroterEtapes(steps)
  return deplacerEtape(steps, indexSource, indexCible - indexSource)
}

/* ============================================================================
   NTWFL8 — Swimlanes par rôle : regroupement PUREMENT visuel (aucun champ
   backend nouveau, dérivé de `role_requis` existant).
   ========================================================================== */

const SANS_ROLE = ''

/** Regroupe `steps` en bandes ("swimlanes") par `role_requis`, dans l'ordre
 * d'apparition des rôles (première étape rencontrée pour ce rôle) ; les
 * étapes sans rôle (`role_requis` vide) forment UNE bande unique en tête.
 * Renvoie `[{ role, steps }, ...]`. Ne mute jamais l'entrée. */
export function swimlanesDe(steps) {
  const list = Array.isArray(steps) ? steps : []
  const ordreRoles = []
  const parRole = new Map()
  list.forEach((s) => {
    const role = String((s && s.role_requis) || SANS_ROLE).trim()
    if (!parRole.has(role)) {
      parRole.set(role, [])
      ordreRoles.push(role)
    }
    parRole.get(role).push(s)
  })
  // Bande "Sans rôle" toujours en tête si présente, puis les rôles dans
  // l'ordre de première apparition.
  const roles = ordreRoles.includes(SANS_ROLE)
    ? [SANS_ROLE, ...ordreRoles.filter((r) => r !== SANS_ROLE)]
    : ordreRoles
  return roles.map((role) => ({ role, steps: parRole.get(role) }))
}

/* ============================================================================
   NTWFL9 — Validation d'une définition AVANT sauvegarde (miroir client de
   core.workflow.valider_definition_steps — le SERVEUR reste la source de
   vérité/dernier mot ; ce miroir n'est qu'un retour immédiat à l'écran).
   ========================================================================== */

/** Valide `steps` (au moins une étape, chaque étape manuelle a un
 * `role_requis`, aucune boucle infinie via `etape_alternative_si_echec`).
 * Renvoie une liste d'erreurs FR (vide = valide). Miroir de
 * `core.workflow.valider_definition_steps` (Python) — garder les DEUX en
 * cohérence si l'un évolue. */
export function validerEtapesDefinition(steps) {
  const list = Array.isArray(steps) ? steps : []
  const erreurs = []
  if (list.length === 0) {
    erreurs.push('Une définition de workflow doit comporter au moins une étape.')
    return erreurs
  }

  const parOrdre = new Map()
  list.forEach((s) => { if (s && s.ordre != null) parOrdre.set(s.ordre, s) })

  list.forEach((s) => {
    const nom = (s && s.nom) || `#${s && s.ordre}`
    if (s && s.type_approbation === 'manuelle' && !String(s.role_requis || '').trim()) {
      erreurs.push(`L'étape « ${nom} » (approbation manuelle) doit préciser un rôle requis.`)
    }
  })

  const boucleSignalee = new Set()
  list.forEach((s) => {
    const depart = s && s.ordre
    const alt = s && s.etape_alternative_si_echec
    if (!alt) return
    const vus = new Set([depart])
    let courant = alt
    while (courant != null) {
      if (vus.has(courant)) {
        if (!boucleSignalee.has(depart)) {
          const nom = (s && s.nom) || `#${depart}`
          erreurs.push(`L'étape « ${nom} » forme une boucle infinie via ses étapes alternatives.`)
          boucleSignalee.add(depart)
        }
        break
      }
      vus.add(courant)
      const suivante = parOrdre.get(courant)
      courant = suivante ? suivante.etape_alternative_si_echec : null
    }
  })

  return erreurs
}

/* ============================================================================
   NTWFL7/11 — Portage JS de core.rules.evaluate_condition_group (édition de
   l'étiquette sur l'arête NTWFL6 + simulation NTWFL11). MÊME format,
   MÊME sémantique (tolérante : ne lève jamais, champ absent => false).
   ========================================================================== */

const MISSING = Symbol('missing')

function comparer(gauche, operateur, droite) {
  const op = String(operateur || '').toLowerCase()
  if (op === 'exists') {
    const present = gauche !== MISSING
    const veutPresent = droite == null ? true : Boolean(droite)
    return veutPresent ? present : !present
  }
  if (gauche === MISSING) return false
  try {
    switch (op) {
      case 'eq': return gauche === droite
      case 'ne': return gauche !== droite
      case 'gt': return gauche > droite
      case 'gte': return gauche >= droite
      case 'lt': return gauche < droite
      case 'lte': return gauche <= droite
      case 'in': return Array.isArray(droite) && droite.includes(gauche)
      case 'not_in': return Array.isArray(droite) && !droite.includes(gauche)
      case 'contains': return String(gauche).includes(droite)
      case 'startswith': return String(gauche).startsWith(String(droite))
      default: return false
    }
  } catch {
    return false
  }
}

function estGroupe(noeud) {
  if (!noeud || typeof noeud !== 'object') return false
  const op = noeud.op
  if (typeof op === 'string' && ['and', 'or', 'not'].includes(op.toLowerCase())) return true
  return Array.isArray(noeud.conditions) && noeud.operator === undefined
}

/** Évalue un arbre de conditions (format `core.rules`) contre `contexte`
 * (objet plat `{champ: valeur}`). Tolérant : structure malformée ou champ
 * absent => `false`, ne lève jamais. */
export function evaluerConditionGroupe(noeud, contexte) {
  if (!noeud || typeof noeud !== 'object') return false
  if (!estGroupe(noeud)) {
    const gauche = contexte && typeof contexte === 'object' && noeud.field in contexte
      ? contexte[noeud.field]
      : MISSING
    return comparer(gauche, noeud.operator, noeud.value)
  }
  const op = String(noeud.op || 'and').toLowerCase()
  const conditions = Array.isArray(noeud.conditions) ? noeud.conditions : []
  if (op === 'not') {
    if (conditions.length === 0) return true
    return !conditions.every((c) => evaluerConditionGroupe(c, contexte))
  }
  if (op === 'or') {
    return conditions.some((c) => evaluerConditionGroupe(c, contexte))
  }
  return conditions.every((c) => evaluerConditionGroupe(c, contexte))
}

/* ============================================================================
   NTWFL11 — Mode simulation/test à blanc : exécute la chaîne EN MÉMOIRE,
   JAMAIS persisté (aucun appel réseau, aucune écriture). Réplique la logique
   de core.workflow.avancer côté PUR JS (gardes NTWFL7, groupes NTWFL10).
   ========================================================================== */

/** Simule le déroulé d'une définition (`steps`, triées par `ordre`) pour un
 * `contexte` de test saisi par l'admin. Renvoie
 * `{ chemin: [ordre, ...], issue: 'termine'|'en_attente', etapesIgnorees: [ordre, ...] }`.
 * PUREMENT EN MÉMOIRE — aucune écriture, aucun appel réseau. Les étapes
 * `auto` sans garde se franchissent seules ; une garde échouée route vers
 * `etape_alternative_si_echec` si configurée, sinon la simulation s'arrête
 * (`en_attente`) ; les étapes manuelles/par rôle arrêtent toujours la
 * simulation (une vraie décision humaine échappe au bac à sable). */
export function simulerWorkflow(steps, contexte = {}) {
  const list = [...(Array.isArray(steps) ? steps : [])].sort((a, b) => a.ordre - b.ordre)
  const parOrdre = new Map(list.map((s) => [s.ordre, s]))
  if (list.length === 0) return { chemin: [], issue: 'termine', etapesIgnorees: [] }

  const chemin = []
  const etapesIgnorees = []
  let courant = list[0].ordre
  const visites = new Set() // garde-fou anti-boucle (déjà refusée à la sauvegarde, NTWFL9)

  for (;;) {
    const etape = parOrdre.get(courant)
    if (!etape || visites.has(courant)) {
      return { chemin, issue: 'termine', etapesIgnorees }
    }
    visites.add(courant)

    if (etape.type_approbation === 'auto') {
      const garde = etape.condition_transition
      const ok = !garde || evaluerConditionGroupe(garde, contexte)
      if (!ok && etape.etape_alternative_si_echec) {
        etapesIgnorees.push(courant)
        courant = etape.etape_alternative_si_echec
        continue
      }
      if (!ok) {
        return { chemin, issue: 'en_attente', etapesIgnorees, blocageOrdre: courant }
      }
      chemin.push(courant)
      const suivante = list.find((s) => s.ordre > courant)
      if (!suivante) return { chemin, issue: 'termine', etapesIgnorees }
      courant = suivante.ordre
      continue
    }

    // Étape manuelle/par rôle : la simulation s'arrête ici (décision humaine).
    chemin.push(courant)
    return { chemin, issue: 'en_attente', etapesIgnorees, blocageOrdre: courant }
  }
}

/* ============================================================================
   NTWFL12 -- Formulaires dynamiques : logique de visibilite/completude
   partagee entre DynamicForm.jsx et son ecran d'approbation (miroir client
   de core.workflow._formulaire_incomplet -- le SERVEUR reste le dernier mot).
   ========================================================================== */

/** Un champ (par `nom`) est-il visible selon `champsConditionnels`
 * (`{nom: {visible_si: <condition core.rules>}}`) et les valeurs DEJA
 * saisies. Sans condition : toujours visible. */
export function champVisible(nom, champsConditionnels, valeurs) {
  const regle = (champsConditionnels && champsConditionnels[nom]) || {}
  if (!regle.visible_si) return true
  return evaluerConditionGroupe(regle.visible_si, valeurs || {})
}

/** Liste les champs (du `schema`, hors sections) requis mais absents/vides
 * de `valeurs`, en ne comptant que les champs VISIBLES. Miroir de
 * `core.workflow._formulaire_incomplet`. */
export function champsFormulaireManquants(schema, champsConditionnels, valeurs) {
  const list = Array.isArray(schema) ? schema : []
  const v = valeurs || {}
  return list
    .filter((c) => c && c.type !== 'section' && c.requis)
    .filter((c) => champVisible(c.nom, champsConditionnels, v))
    .filter((c) => {
      const val = v[c.nom]
      return val === undefined || val === null || val === ''
        || (Array.isArray(val) && val.length === 0)
    })
    .map((c) => c.nom)
}

/** Normalise la liste d'items renvoyée par la boîte d'approbations
 * (`GET reporting/approbations-en-attente/?source=workflow`) : ne garde que
 * les items dont la source est bien `'workflow'` (défense en profondeur — le
 * filtre est déjà appliqué côté serveur), et calcule `en_retard` local si le
 * backend n'a pas déjà renvoyé son propre indicateur d'urgence. */
export function normaliserInstances(payload) {
  const items = (payload && Array.isArray(payload.items)) ? payload.items : []
  return items
    .filter((it) => it && it.source === 'workflow')
    .map((it) => ({
      ...it,
      en_retard: typeof it.en_retard === 'boolean'
        ? it.en_retard
        : estEnRetardSla(it),
    }))
}
