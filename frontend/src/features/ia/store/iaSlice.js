import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import iaApi from '../../../api/iaApi'
import { marquerNote, construireContexte, ditUnePanne } from '../copilotMessages.js'
import { instantaneDiagnostic } from '../../../lib/tamponDiagnostic.js'
import {
  ETATS, MESSAGE_INCERTAIN, messageDeReponse, carteDeConfirmation, messageDeSuite,
  messagesDeLHistorique, foyerTouche,
} from '../cartes/cartes.js'

// COP-F1 — les cartes (proposition / résultat) viennent UNIQUEMENT de `cartes[]`
// de la réponse serveur (contrat assistant_reponse.json), jamais du texte libre
// du modèle : voir `cartes/cartes.js` (logique pure, testée avec les échantillons
// du contrat). Chaque carte « proposition » garde SON état (à confirmer / en
// cours / confirmée / expirée / annulée / échec).

// AIC9/COP-F5 — l'argument est la question (texte) ou `{ question, detail,
// diagnostic }`. Le CONTEXTE est lu ICI, au moment de l'envoi (route courante,
// foyer = dernière carte « touche » affichée) : jamais un état resté d'une
// ouverture précédente. `detail` = contexte posé par l'écran d'où part
// l'événement « Demander à l'assistant » (cette question seulement).
const questionDe = (arg) => (typeof arg === 'string' ? arg : arg?.question ?? '')

export const queryAgent = createAsyncThunk('ia/queryAgent', async (arg, { rejectWithValue, getState }) => {
  try {
    const contexte = construireContexte({
      chemin: typeof window !== 'undefined' ? window.location.pathname : '/',
      detail: typeof arg === 'string' ? null : arg?.detail ?? null,
      foyer: foyerTouche(getState()?.ia?.messages),
      // COP-F7 — le tampon technique part avec « Signaler un bug » ET tout seul
      // quand la phrase dit une panne (« ça ne marche pas », « bloqué »…).
      diagnostic: (typeof arg === 'string' ? null : arg?.diagnostic)
        ?? (ditUnePanne(questionDe(arg)) ? instantaneDiagnostic() : null),
    })
    const res = await iaApi.queryAgent(questionDe(arg), contexte)
    return { ...res.data, recu_le: Date.now() }
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

// AIC8 — le commercial note la réponse `index` (événement `evenementId`) :
// PATCH note/commentaire (contrat assistant_evenement.json). Une note par
// événement, modifiable (re-noter remplace).
export const noterEvenement = createAsyncThunk(
  'ia/noterEvenement',
  async ({ evenementId, note, commentaire = null }, { rejectWithValue }) => {
    try {
      const res = await iaApi.noterEvenement(evenementId, note, commentaire)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

// AG3/COP-F1 — confirme UNE proposition par son jeton (POST /confirm). L'argument
// porte aussi `index` (message) et `carte` (rang de la proposition dans ses
// cartes) pour que CETTE carte, et elle seule, change d'état. Un jeton ne
// s'exécute qu'une fois, et il est RÉCLAMÉ avant l'exécution : « échec »
// seulement quand le serveur a répondu avec un refus nommé (`ok:false` + détail,
// ou 4xx + détail) ; sans réponse, en 5xx ou sans détail, l'action a pu être
// faite — la carte passe en « incertain » (vérifier avant de redemander).
// `donneesPatch` FUSIONNE dans `donnees` (le composant n'a pas à relire l'état
// courant : plusieurs callbacks asynchrones peuvent se croiser) ; le reste du
// patch s'applique à la carte.
function appliquerPatchCarte(c, patch) {
  const { donneesPatch, ...reste } = patch
  if (donneesPatch) c.donnees = { ...c.donnees, ...donneesPatch }
  Object.assign(c, reste)
}

const refusNomme = (detail) => (typeof detail === 'string' && detail.trim() ? detail : null)

export const confirmAgentAction = createAsyncThunk(
  'ia/confirmAgentAction',
  async ({ token }, { rejectWithValue }) => {
    try {
      const res = await iaApi.confirmAction(token)
      if (res.data && res.data.ok === false) {
        const message = refusNomme(res.data.detail)
        return rejectWithValue({ message, incertain: message == null })
      }
      return { ...res.data, recu_le: Date.now() }
    } catch (err) {
      const statut = err.response?.status ?? 0
      const message = statut >= 400 && statut < 500 ? refusNomme(err.response?.data?.detail) : null
      return rejectWithValue({ message, incertain: message == null })
    }
  },
)

export const loadChatHistory = createAsyncThunk('ia/loadChatHistory', async (_, { rejectWithValue }) => {
  try {
    const res = await iaApi.getChatHistory()
    return res.data
  } catch {
    return rejectWithValue(null) // echec silencieux — pas bloquant
  }
})

export const clearChatHistory = createAsyncThunk('ia/clearChatHistory', async (_, { rejectWithValue }) => {
  try {
    await iaApi.clearChatHistory()
  } catch {
    return rejectWithValue(null)
  }
})

export const processOcrStockDocument = createAsyncThunk('ia/processOcrStockDocument', async ({ file, docType = '' }, { rejectWithValue }) => {
  try {
    const res = await iaApi.processStockDocument({ file, docType })
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const processOcrDocument = createAsyncThunk('ia/processOcrDocument', async (file, { rejectWithValue }) => {
  try {
    const res = await iaApi.processDocument(file)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const saveOcrDocument = createAsyncThunk('ia/saveOcrDocument', async (data, { rejectWithValue }) => {
  try {
    const res = await iaApi.saveOcrDocument(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data?.detail ?? err.message)
  }
})

export const fetchOcrDocuments = createAsyncThunk('ia/fetchOcrDocuments', async (_, { rejectWithValue }) => {
  try {
    const res = await iaApi.getOcrDocuments()
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data?.detail ?? err.message)
  }
})

export const deleteOcrDocument = createAsyncThunk('ia/deleteOcrDocument', async (id, { rejectWithValue }) => {
  try {
    await iaApi.deleteOcrDocument(id)
    return id
  } catch (err) {
    return rejectWithValue(err.response?.data?.detail ?? err.message)
  }
})

const iaSlice = createSlice({
  name: 'ia',
  initialState: {
    // FG350 — Copilote in-app : état ouvert/fermé du tiroir conversationnel
    // global (CopilotPanel). Piloté depuis l'app shell (bouton de l'en-tête).
    copilotOpen: false,
    // Chat agent
    messages: [],
    agentLoading: false,
    agentError: null,
    // OCR
    ocrResult: null,
    ocrLoading: false,
    ocrError: null,
    // OCR Stock
    stockOcrResult: null,
    stockOcrDocType: '',
    stockOcrLoading: false,
    stockOcrError: null,
    // Save
    savedDocumentId: null,
    saveLoading: false,
    saveError: null,
    // Documents list
    documents: [],
    docsLoading: false,
    docsError: null,
  },
  reducers: {
    // FG350 — bascule / ouverture / fermeture du tiroir Copilote global.
    openCopilot(state) { state.copilotOpen = true },
    closeCopilot(state) { state.copilotOpen = false },
    toggleCopilot(state) { state.copilotOpen = !state.copilotOpen },
    clearMessages(state) { state.messages = [] },
    historyLoaded(state, action) { state.messages = messagesDeLHistorique(action.payload) },
    // AG3/COP-F1 — « Annuler » sur UNE carte proposition : sans appel API (le
    // jeton expire seul côté Redis, usage unique). La carte reste, « annulée ».
    dismissProposal(state, action) {
      const { index, carte } = action.payload
      const c = state.messages[index]?.cartes?.[carte]
      if (c?.type === 'proposition') c.etat = ETATS.ANNULEE
    },
    // COP-F2/F3 — une carte posée par un bouton de l'écran (« Préparer »…) :
    // message local, jamais renvoyé au modèle.
    ajouterMessageLocal(state, action) { state.messages.push(action.payload) },
    // COP-F2 — l'état d'une carte survit au remontage du tiroir (Layout est
    // remonté à chaque changement de module) : on le range dans le store.
    majCarte(state, action) {
      const { index, carte, patch } = action.payload
      const c = state.messages[index]?.cartes?.[carte]
      if (c) appliquerPatchCarte(c, patch)
    },
    // COP-F2 — une réponse enregistrée sur une touche vaut pour TOUTES les
    // cartes « touche » de la conversation qui portent cette touche (carte
    // « Préparer » puis carte-écho) : aucune carte restée « à faire » ne rouvre
    // WhatsApp sur une touche close.
    majCartesTouche(state, action) {
      const { toucheId, patch } = action.payload
      const id = Number(toucheId)
      if (!Number.isInteger(id) || id <= 0) return
      for (const msg of state.messages) {
        for (const c of msg?.cartes ?? []) {
          if (c?.type === 'resultat' && c.carte === 'touche' && Number(c.donnees?.touche?.id) === id) {
            appliquerPatchCarte(c, patch)
          }
        }
      }
    },
    clearOcrResult(state) {
      state.ocrResult = null
      state.savedDocumentId = null
      state.saveError = null
    },
    clearStockOcrResult(state) {
      state.stockOcrResult = null
      state.stockOcrDocType = ''
      state.stockOcrError = null
    },
    clearErrors(state) {
      state.agentError = null
      state.ocrError = null
      state.saveError = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(queryAgent.pending, (state, action) => {
        state.agentLoading = true
        state.agentError = null
        state.messages.push({ role: 'user', content: questionDe(action.meta.arg) })
      })
      .addCase(queryAgent.fulfilled, (state, action) => {
        state.agentLoading = false
        // AG3 — buildAgentMessage rend une carte proposition / résultat quand le
        // payload structuré AG2 est présent ; sinon un message texte (N86).
        // L'événement journalisé (AIC6, note AIC8) et le moteur sont conservés.
        state.messages.push(messageDeReponse(action.payload, action.payload?.recu_le))
      })
      .addCase(noterEvenement.fulfilled, (state, action) => {
        const { index, note, commentaire } = action.meta.arg
        if (state.messages[index]) {
          state.messages[index] = marquerNote(state.messages[index], note, commentaire)
        }
      })
      .addCase(queryAgent.rejected, (state, action) => {
        state.agentLoading = false
        state.agentError = action.payload
      })

      // AG3/COP-F1 — confirmation d'UNE proposition.
      .addCase(confirmAgentAction.pending, (state, action) => {
        const { index, carte } = action.meta.arg
        const c = state.messages[index]?.cartes?.[carte]
        if (c) { c.etat = ETATS.EN_COURS; c.erreur = null }
      })
      .addCase(confirmAgentAction.fulfilled, (state, action) => {
        const { index, carte } = action.meta.arg
        const c = state.messages[index]?.cartes?.[carte]
        if (c) {
          c.etat = ETATS.CONFIRMEE
          c.resultat = carteDeConfirmation(action.payload)
        }
        // Moteur natif : l'assistant reprend la tâche après la confirmation.
        if (action.payload?.suite && typeof action.payload.suite === 'object') {
          state.messages.push(messageDeSuite(action.payload.suite, action.payload.recu_le))
        }
      })
      .addCase(confirmAgentAction.rejected, (state, action) => {
        const { index, carte } = action.meta.arg
        const c = state.messages[index]?.cartes?.[carte]
        if (!c) return
        const p = action.payload ?? {}
        if (p.message) {
          c.etat = ETATS.ECHEC
          c.erreur = p.message
        } else {
          // Le jeton a pu être consommé et l'action faite : jamais « non exécutée ».
          c.etat = ETATS.INCERTAIN
          c.erreur = MESSAGE_INCERTAIN
        }
      })

      .addCase(processOcrStockDocument.pending, (state, action) => {
        state.stockOcrLoading = true
        state.stockOcrError = null
        state.stockOcrResult = null
        state.stockOcrDocType = action.meta.arg.docType ?? ''
      })
      .addCase(processOcrStockDocument.fulfilled, (state, action) => {
        state.stockOcrLoading = false
        state.stockOcrResult = action.payload
        state.stockOcrDocType = action.meta.arg.docType ?? ''
      })
      .addCase(processOcrStockDocument.rejected, (state, action) => {
        state.stockOcrLoading = false
        state.stockOcrError = action.payload
      })

      .addCase(processOcrDocument.pending, (state) => {
        state.ocrLoading = true
        state.ocrError = null
        state.ocrResult = null
        state.savedDocumentId = null
        state.saveError = null
      })
      .addCase(processOcrDocument.fulfilled, (state, action) => {
        state.ocrLoading = false
        state.ocrResult = action.payload
      })
      .addCase(processOcrDocument.rejected, (state, action) => {
        state.ocrLoading = false
        state.ocrError = action.payload
      })

      .addCase(saveOcrDocument.pending, (state) => {
        state.saveLoading = true
        state.saveError = null
        state.savedDocumentId = null
      })
      .addCase(saveOcrDocument.fulfilled, (state, action) => {
        state.saveLoading = false
        state.savedDocumentId = action.payload.id
      })
      .addCase(saveOcrDocument.rejected, (state, action) => {
        state.saveLoading = false
        state.saveError = action.payload
      })

      .addCase(fetchOcrDocuments.pending, (state) => {
        state.docsLoading = true
        state.docsError = null
      })
      .addCase(fetchOcrDocuments.fulfilled, (state, action) => {
        state.docsLoading = false
        state.documents = action.payload
      })
      .addCase(fetchOcrDocuments.rejected, (state, action) => {
        state.docsLoading = false
        state.docsError = action.payload
      })

      .addCase(deleteOcrDocument.fulfilled, (state, action) => {
        state.documents = state.documents.filter(d => d.id !== action.payload)
      })

      .addCase(loadChatHistory.fulfilled, (state, action) => {
        // CAD177 : seule une liste est un historique valide (un 200 HTML du repli SPA
        // (service IA absent) portait un `.length` et faisait planter l ecran).
        // COP-F1 : une conversation DÉJÀ en cours n'est jamais écrasée (cartes
        // locales, propositions encore valables, question envoyée pendant le
        // chargement) ; l'historique ne sert qu'à remplir un écran vide.
        if (Array.isArray(action.payload) && action.payload.length && state.messages.length === 0) {
          state.messages = messagesDeLHistorique(action.payload)
        }
      })
      .addCase(clearChatHistory.fulfilled, (state) => {
        state.messages = []
      })
  },
})

export const { openCopilot, closeCopilot, toggleCopilot, clearMessages, historyLoaded, dismissProposal, ajouterMessageLocal, majCarte, majCartesTouche, clearOcrResult, clearStockOcrResult, clearErrors } = iaSlice.actions
export default iaSlice.reducer
