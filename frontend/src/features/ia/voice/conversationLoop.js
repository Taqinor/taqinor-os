// AG12 — Machine à états du « Mode conversation » (boucle mains-libres).
//
// Boucle continue : écoute → détection de fin de parole (silence) → transcription
// → réponse à voix haute → ré-ouverture du micro, jusqu'à ce que l'utilisateur
// l'arrête. Avec barge-in (parler interrompt la réponse parlée) et un arrêt
// toujours disponible.
//
// SÉCURITÉ CRITIQUE (rule founder #4 / AG3 ; COP-F6) : AUCUNE confirmation à la
// voix. Une action sensible est une PROPOSITION (carte de confirmation) que la
// commerciale confirme d'un DOIGT : la boucle lit l'aperçu, dit d'appuyer sur
// « Confirmer » à l'écran, puis ré-ouvre le micro. Rien de ce qui se dit ne
// confirme quoi que ce soit — avant COP-F6, « non je ne confirme pas » EXÉCUTAIT
// l'action (la phrase contenait « confirme »). Il n'existe donc plus de chemin
// voix → confirmation (ni mots-clés, ni état d'attente, ni `confirm()`).
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
})

// Phrase lue après l'aperçu d'une proposition : la confirmation est un geste du doigt.
export const PHRASE_CONFIRMER_AU_DOIGT = 'Pour valider, appuyez sur « Confirmer » à l’écran.'

// Crée une machine à états de la boucle conversation.
//
// `handlers` (tous optionnels — la machine reste pure et synchrone) :
//   startListening()  — ouvrir le micro pour un tour
//   stopListening()   — fermer le micro
//   ask(text)         — envoyer la question à l'agent
//   speak(text)       — lire un texte à voix haute
//   stopSpeaking()    — couper la synthèse (barge-in)
//   onState(state)    — notifié à chaque changement d'état
export function createConversationLoop(handlers = {}) {
  let state = LOOP_STATES.IDLE
  let running = false

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

  // Appelé par le hook avec le texte transcrit du dernier clip. Un énoncé est
  // TOUJOURS une question : il ne confirme jamais rien (COP-F6).
  function onTranscript(text) {
    if (!running) return
    const utterance = (text || '').trim()
    if (!utterance) {
      // Rien d'exploitable : on ré-ouvre le micro.
      beginListening()
      return
    }
    setState(LOOP_STATES.THINKING)
    h.ask?.(utterance)
  }

  // Appelé par le hook quand l'agent a répondu. `message` : `{ content,
  // proposition?: true, apercu? }` — `proposition` vrai quand la réponse porte
  // une carte à confirmer.
  function onAnswer(message) {
    if (!running) return
    const texte = message?.content ?? (typeof message === 'string' ? message : '')
    if (message?.proposition) {
      // ACTION SENSIBLE : on lit l'aperçu et on dit d'appuyer ; on ne confirme PAS.
      const apercu = message.apercu || texte
      setState(LOOP_STATES.SPEAKING)
      h.speak?.(apercu ? `${apercu} ${PHRASE_CONFIRMER_AU_DOIGT}` : PHRASE_CONFIRMER_AU_DOIGT)
      return
    }
    // Réponse normale : on la lit, puis (à la fin) on ré-ouvre le micro.
    setState(LOOP_STATES.SPEAKING)
    h.speak?.(texte)
  }

  // Appelé par le hook quand la lecture est terminée (ou impossible) : le micro
  // se ré-ouvre TOUJOURS — il ne reste jamais bloqué après une réponse.
  function onSpeechSpoken() {
    if (!running) return
    if (state === LOOP_STATES.SPEAKING) beginListening()
  }

  // Une action confirmée au doigt est terminée (carte résultat) — on lit un
  // accusé puis on repart en écoute.
  function onActionDone(message) {
    if (!running) return
    setState(LOOP_STATES.SPEAKING)
    h.speak?.(message?.content || 'Action effectuée.')
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
  }
}
