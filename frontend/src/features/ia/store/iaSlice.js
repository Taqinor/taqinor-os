import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import iaApi from '../../../api/iaApi'

export const queryAgent = createAsyncThunk('ia/queryAgent', async (question, { rejectWithValue }) => {
  try {
    const res = await iaApi.queryAgent(question)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

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
    clearMessages(state) { state.messages = [] },
    historyLoaded(state, action) { state.messages = action.payload },
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
        state.messages.push({
          role: 'agent',
          content: action.payload.answer,
          sql_query: action.payload.sql_query,
        })
      })
      .addCase(queryAgent.rejected, (state, action) => {
        state.agentLoading = false
        state.agentError = action.payload
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

export const { clearMessages, historyLoaded, clearOcrResult, clearStockOcrResult, clearErrors } = iaSlice.actions
export default iaSlice.reducer
