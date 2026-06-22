import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import iaApi from '../../../api/iaApi'

// ── AG3 — normalisation des messages agent (cartes proposition / résultat) ────
//
// L'agent (AG2) peut renvoyer, en plus d'une réponse texte :
//   • une PROPOSITION pour une action sensible (outward/irréversible) —
//     `{ type:'proposal', action_key, human_preview, confirm_token, inputs }` —
//     que l'UI rend en carte avec Confirmer (→ POST /sql-agent/confirm avec le
//     `confirm_token`) / Annuler (écarte la carte) ;
//   • un RÉSULTAT d'action interne terminée —
//     `{ type:'result', action_key, ok, data:{ reference, wa_url, devis_id… } }`
//     — rendu en carte avec n° de référence, lien « Télécharger le devis »
//     (vers /proposal) et bouton « Ouvrir WhatsApp » (depuis `data.wa_url`).
//
// Les noms de champs reflètent EXACTEMENT le contrat AG2 (action_tools.run_
// catalogue_action + endpoint /sql-agent/confirm). Le payload structuré est lu
// défensivement : champ dédié sur la réponse s'il existe, sinon objet JSON
// éventuellement présent dans `answer`. Quand aucun payload structuré n'est
// présent, le message reste un simple message texte (comportement N86 inchangé).

// Tente d'extraire un objet JSON `{type:'proposal'|'result', …}` d'une chaîne.
// Renvoie l'objet parsé ou null — ne lève jamais.
export function parseStructuredPayload(text) {
  if (!text || typeof text !== 'string') return null
  const trimmed = text.trim()
  // Cas direct : la chaîne EST l'objet JSON.
  const direct = tryParseObject(trimmed)
  if (direct) return direct
  // Cas mixte : un objet JSON est encadré par du texte naturel.
  const start = trimmed.indexOf('{')
  const end = trimmed.lastIndexOf('}')
  if (start !== -1 && end > start) {
    const obj = tryParseObject(trimmed.slice(start, end + 1))
    if (obj) return obj
  }
  return null
}

function tryParseObject(s) {
  try {
    const obj = JSON.parse(s)
    if (obj && typeof obj === 'object' && !Array.isArray(obj)
        && (obj.type === 'proposal' || obj.type === 'result')) {
      return obj
    }
  } catch {
    /* pas du JSON — ignoré */
  }
  return null
}

// Construit le message agent à partir du payload `/sql-agent/query`.
// Priorité : payload structuré dédié (`proposal`/`result`) > JSON dans `answer`
// > message texte simple. Renvoie un objet message prêt pour le store.
export function buildAgentMessage(payload) {
  const answer = payload?.answer ?? ''
  const structured =
    normalizePayload(payload?.proposal, 'proposal')
    ?? normalizePayload(payload?.result, 'result')
    ?? normalizePayload(parseStructuredPayload(answer))

  if (structured?.type === 'proposal') {
    return {
      role: 'agent',
      kind: 'proposal',
      content: answer,
      action_key: structured.action_key ?? '',
      human_preview: structured.human_preview ?? '',
      // Sans Redis le backend renvoie confirm_token=null : carte non confirmable.
      confirm_token: structured.confirm_token ?? null,
      sql_query: payload?.sql_query,
    }
  }
  if (structured?.type === 'result') {
    const data = structured.data ?? {}
    const devisId = data.devis_id ?? data.devis ?? data.id ?? null
    return {
      role: 'agent',
      kind: 'result',
      content: answer,
      action_key: structured.action_key ?? '',
      reference: data.reference ?? data.numero ?? '',
      wa_url: data.wa_url ?? '',
      // Lien client « Télécharger le devis » : SEUL chemin /proposal autorisé.
      proposal_url: devisId != null
        ? `/api/django/ventes/devis/${devisId}/proposal/`
        : '',
      sql_query: payload?.sql_query,
    }
  }
  // Message texte simple (rétro-compatible N86).
  return {
    role: 'agent',
    content: answer,
    sql_query: payload?.sql_query,
    action_performed: payload?.action_performed ?? false,
  }
}

// Force `type` quand on lit un champ dédié déjà typé par sa provenance.
function normalizePayload(obj, forcedType) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return null
  const type = forcedType ?? obj.type
  if (type !== 'proposal' && type !== 'result') return null
  return { ...obj, type }
}

export const queryAgent = createAsyncThunk('ia/queryAgent', async (question, { rejectWithValue }) => {
  try {
    const res = await iaApi.queryAgent(question)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

// AG3 — confirme une action proposée par son `confirm_token` (POST /confirm).
// Le payload de l'action `arg` porte aussi `index` (position du message
// proposition dans la liste) pour pouvoir, au succès, remplacer la carte par
// son résultat. Sur 4xx/erreur on remonte le détail pour l'afficher.
export const confirmAgentAction = createAsyncThunk(
  'ia/confirmAgentAction',
  async ({ token }, { rejectWithValue }) => {
    try {
      const res = await iaApi.confirmAction(token)
      if (res.data && res.data.ok === false) {
        return rejectWithValue(res.data.detail || 'L\'action n\'a pas pu être exécutée.')
      }
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.detail ?? err.response?.data ?? err.message)
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
    // AG3 — confirmation d'une action proposée (carte Confirmer/Annuler)
    confirmingIndex: null, // index du message proposition en cours de confirmation
    confirmError: null,
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
    historyLoaded(state, action) { state.messages = action.payload },
    // AG3 — « Annuler » sur une carte proposition : on l'écarte sans appel API
    // (le jeton expire seul côté Redis ; usage unique). Le message devient un
    // simple texte « Proposition annulée ».
    dismissProposal(state, action) {
      const i = action.payload
      const msg = state.messages[i]
      if (msg && msg.kind === 'proposal') {
        state.messages[i] = {
          role: 'agent',
          content: msg.content,
          dismissed: true,
        }
      }
      state.confirmError = null
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
        state.messages.push({ role: 'user', content: action.meta.arg })
      })
      .addCase(queryAgent.fulfilled, (state, action) => {
        state.agentLoading = false
        // AG3 — buildAgentMessage rend une carte proposition / résultat quand le
        // payload structuré AG2 est présent ; sinon un message texte (N86).
        state.messages.push(buildAgentMessage(action.payload))
      })
      .addCase(queryAgent.rejected, (state, action) => {
        state.agentLoading = false
        state.agentError = action.payload
      })

      // AG3 — confirmation d'une action proposée.
      .addCase(confirmAgentAction.pending, (state, action) => {
        state.confirmingIndex = action.meta.arg?.index ?? null
        state.confirmError = null
      })
      .addCase(confirmAgentAction.fulfilled, (state, action) => {
        const i = action.meta.arg?.index
        state.confirmingIndex = null
        // Remplace la carte proposition par la carte résultat de l'action.
        if (typeof i === 'number' && state.messages[i]) {
          state.messages[i] = buildAgentMessage({
            answer: action.payload?.detail || state.messages[i].content || '',
            result: action.payload?.data
              ? { type: 'result', action_key: action.payload.action_key, data: action.payload.data }
              : { type: 'result', action_key: action.payload?.action_key, data: {} },
          })
        }
      })
      .addCase(confirmAgentAction.rejected, (state, action) => {
        state.confirmingIndex = null
        state.confirmError = action.payload
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
        if (action.payload?.length) state.messages = action.payload
      })
      .addCase(clearChatHistory.fulfilled, (state) => {
        state.messages = []
      })
  },
})

export const { openCopilot, closeCopilot, toggleCopilot, clearMessages, historyLoaded, dismissProposal, clearOcrResult, clearStockOcrResult, clearErrors } = iaSlice.actions
export default iaSlice.reducer
