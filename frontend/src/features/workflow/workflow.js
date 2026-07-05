/* ============================================================================
   XPLT8 — logique pure du module Workflow & Jobs (testable sans React/DOM).
   ----------------------------------------------------------------------------
   Toutes les fonctions sont défensives sur des données absentes/malformées
   (jamais de throw sur `undefined`/`null` — l'écran ne doit jamais planter
   sur une réponse API incomplète).
   ========================================================================== */

/** Étape par défaut d'un éditeur de définition (client-only — aucun endpoint
 * CRUD définitions n'existe côté backend ; voir README du module). */
export function nouvelleEtape(ordre) {
  return {
    ordre,
    nom: '',
    type_approbation: 'manuelle',
    sla_heures: '',
    role_requis: '',
    escalade_vers: '',
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
