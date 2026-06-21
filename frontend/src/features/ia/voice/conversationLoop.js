// AG12 — Machine à états du « Mode conversation » (boucle mains-libres).
//
// Boucle continue : écoute → détection de fin de parole (silence) → transcription
// → réponse à voix haute → ré-ouverture du micro, jusqu'à ce que l'utilisateur
// l'arrête. Avec barge-in (parler interrompt la réponse parlée) et un arrêt
// toujours disponible.
//
// SÉCURITÉ CRITIQUE (rule founder #4 / AG3) : la boucle NE confirme JAMAIS
// automatiquement une action sortante/irréversible. Quand une réponse de l'agent
// est une PROPOSITION (carte de confirmation AG3), la machine passe à
// `awaiting_confirm` : elle lit l'aperçu à voix haute et ATTEND un « confirmer »
// parlé explicite (ou un tap) avant d'exécuter. N'importe quel autre énoncé est
// traité comme une nouvelle question — jamais comme une confirmation implicite.
//
// Ce module est PUR (aucune dépendance DOM / navigateur) pour être testable en
// `node:test`. Le hook `useVoiceChat` câble les effets réels (micro, synthèse
// vocale, dispatch Redux) sur les transitions renvoyées ici.

// États possibles de la boucle.
export const LOOP_STATES = Object.freeze({
  IDLE: 'idle',            // boucle arrêtée
  LISTENING: 'listening',  // micro ouvert, on capture la parole de l'utilisateur
  TRANSCRIBING: 'transcribing', // clip envoyé à /transcribe
  THINKING: 'thinking',    // question envoyée à l'agent, on attend la réponse
  SPEAKING: 'speaking',    // réponse lue à voix haute
  AWAITING_CONFIRM: 'awaiting_confirm', // action sensible : on attend « confirmer »
})

// Mots déclenchant une confirmation explicite parlée (FR + darija courante).
// Normalisés (sans accents, minuscules) avant comparaison.
const CONFIRM_WORDS = ['confirmer', 'confirme', 'confirmé', 'oui confirme', 'valider', 'valide']
// Mots d'annulation explicite parlée.
const CANCEL_WORDS = ['annuler', 'annule', 'non', 'annulé', 'stop']

// Normalise un énoncé pour la comparaison : minuscules, sans accents, espaces
// réduits. Renvoie '' pour une entrée vide / non-chaîne.
export function normalizeUtterance(text) {
  if (!text || typeof text !== 'string') return ''
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '') // retire les diacritiques
    .replace(/\s+/g, ' ')
    .trim()
}

// Vrai si l'énoncé est une CONFIRMATION explicite (« confirmer »…).
export function isConfirmUtterance(text) {
  const n = normalizeUtterance(text)
  if (!n) return false
  return CONFIRM_WORDS.some((w) => n === w || n.startsWith(w + ' ') || n.endsWith(' ' + w) || n.includes(' ' + w + ' '))
}

// Vrai si l'énoncé est une ANNULATION explicite (« annuler »…).
export function isCancelUtterance(text) {
  const n = normalizeUtterance(text)
  if (!n) return false
  return CANCEL_WORDS.some((w) => n === w || n.startsWith(w + ' ') || n.endsWith(' ' + w) || n.includes(' ' + w + ' '))
}

// Crée une machine à états de la boucle conversation.
//
// `handlers` (tous optionnels — la machine reste pure et synchrone) :
//   startListening()  — ouvrir le micro pour un tour
//   stopListening()   — fermer le micro
//   transcribe(blob)  — renvoyer (async, géré par le hook) le texte
//   ask(text)         — envoyer la question à l'agent
//   speak(text)       — lire un texte à voix haute
//   stopSpeaking()    — couper la synthèse (barge-in)
//   confirm(token)    — exécuter l'action sensible confirmée
//   onState(state)    — notifié à chaque changement d'état
//
// La machine n'appelle JAMAIS confirm() sans un `event('confirm')` (ou
// `userSays` reconnu comme confirmation) reçu pendant `awaiting_confirm`.
export function createConversationLoop(handlers = {}) {
  let state = LOOP_STATES.IDLE
  let running = false
  // Proposition en attente quand on est dans `awaiting_confirm`.
  let pendingProposal = null

  const h = handlers

  function setState(next) {
    if (state === next) return
    state = next
    h.onState?.(state)
  }

  function getState() {
    return state
  }

  function isRunning() {
    return running
  }

  // Démarre la boucle : passe en écoute.
  function start() {
    if (running) return
    running = true
    beginListening()
  }

  // Arrête tout immédiatement (bouton stop toujours visible).
  function stop() {
    running = false
    pendingProposal = null
    h.stopListening?.()
    h.stopSpeaking?.()
    setState(LOOP_STATES.IDLE)
  }

  function beginListening() {
    if (!running) return
    setState(LOOP_STATES.LISTENING)
    h.startListening?.()
  }

  // Appelé par le hook quand le silence a été détecté et qu'un clip est prêt.
  function onSpeechEnd() {
    if (!running) return
    if (state !== LOOP_STATES.LISTENING) return
    h.stopListening?.()
    setState(LOOP_STATES.TRANSCRIBING)
  }

  // Appelé par le hook avec le texte transcrit du dernier clip.
  function onTranscript(text) {
    if (!running) return
    const utterance = (text || '').trim()

    // En attente de confirmation : SEUL un « confirmer » exécute ; « annuler »
    // écarte ; tout autre énoncé est traité comme une nouvelle question (jamais
    // une confirmation implicite).
    if (state === LOOP_STATES.AWAITING_CONFIRM) {
      if (isConfirmUtterance(utterance)) {
        const token = pendingProposal?.confirm_token ?? null
        pendingProposal = null
        if (token) {
          h.confirm?.(token)
          // L'exécution est asynchrone (gérée par le hook) ; on repassera en
          // SPEAKING via onAnswer/onActionDone, puis en écoute.
          setState(LOOP_STATES.THINKING)
          return
        }
        // Pas de token confirmable : on repart en écoute sans rien exécuter.
        beginListening()
        return
      }
      if (isCancelUtterance(utterance)) {
        pendingProposal = null
        beginListening()
        return
      }
      // Énoncé non reconnu pendant l'attente : on NE confirme PAS. On le traite
      // comme une nouvelle question.
      pendingProposal = null
      if (!utterance) {
        beginListening()
        return
      }
      setState(LOOP_STATES.THINKING)
      h.ask?.(utterance)
      return
    }

    // Tour normal.
    if (!utterance) {
      // Rien d'exploitable : on ré-ouvre le micro.
      beginListening()
      return
    }
    setState(LOOP_STATES.THINKING)
    h.ask?.(utterance)
  }

  // Appelé par le hook quand l'agent a répondu. `message` est le message agent
  // normalisé (peut être `{ kind:'proposal', human_preview, confirm_token }`).
  function onAnswer(message) {
    if (!running) return
    const isProposal = message?.kind === 'proposal'

    if (isProposal) {
      // ACTION SENSIBLE : on NE confirme PAS. On lit l'aperçu et on attend un
      // « confirmer » explicite.
      pendingProposal = message
      const preview = message.human_preview || message.content || ''
      setState(LOOP_STATES.AWAITING_CONFIRM)
      const prompt = preview
        ? `${preview} Dites « confirmer » pour valider, ou « annuler ».`
        : 'Confirmation requise. Dites « confirmer » pour valider, ou « annuler ».'
      h.speak?.(prompt)
      return
    }

    // Réponse normale : on la lit, puis (à la fin) on ré-ouvre le micro.
    const text = message?.content ?? (typeof message === 'string' ? message : '')
    setState(LOOP_STATES.SPEAKING)
    h.speak?.(text)
  }

  // Appelé par le hook quand la synthèse vocale d'un tour normal est terminée.
  function onSpeechSpoken() {
    if (!running) return
    if (state === LOOP_STATES.SPEAKING) {
      beginListening()
    }
    // En AWAITING_CONFIRM la fin de lecture de l'aperçu NE relance PAS l'écoute
    // libre : on attend explicitement la confirmation (le hook ré-ouvre le micro
    // pour capter « confirmer » sans changer d'état — voir useVoiceChat).
  }

  // Appelé par le hook quand l'exécution d'une action confirmée est terminée
  // (carte résultat) — on lit un accusé puis on repart en écoute.
  function onActionDone(message) {
    if (!running) return
    const text = message?.content || 'Action effectuée.'
    setState(LOOP_STATES.SPEAKING)
    h.speak?.(text)
  }

  // Barge-in : l'utilisateur parle pendant que l'agent lit → on coupe la synthèse
  // et on ré-ouvre le micro pour capter sa nouvelle requête.
  function onBargeIn() {
    if (!running) return
    if (state === LOOP_STATES.SPEAKING) {
      h.stopSpeaking?.()
      beginListening()
    }
  }

  // Tap explicite « Confirmer » (équivalent au « confirmer » parlé) pendant
  // l'attente — JAMAIS automatique.
  function confirmByTap() {
    if (!running) return
    if (state !== LOOP_STATES.AWAITING_CONFIRM) return
    const token = pendingProposal?.confirm_token ?? null
    pendingProposal = null
    if (token) {
      h.confirm?.(token)
      setState(LOOP_STATES.THINKING)
    } else {
      beginListening()
    }
  }

  return {
    start,
    stop,
    getState,
    isRunning,
    onSpeechEnd,
    onTranscript,
    onAnswer,
    onSpeechSpoken,
    onActionDone,
    onBargeIn,
    confirmByTap,
    // Exposé pour les tests / le hook.
    get pendingProposal() { return pendingProposal },
  }
}
