import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import messagesApi from '../../../api/messagesApi'
import {
  sortConversations,
  upsertConversation as upsertConv,
  mergeOlderMessages,
  mergeNewerMessages,
  upsertMessage as upsertMsg,
  removeMessage as removeMsg,
  toAsc,
  totalUnread,
  toggleReactionLocal,
} from './messagingUtils'

// S12 — État Redux du module Discuter. La liste des conversations, le fil de la
// conversation ouverte, le total de non-lus (badge) et les épingles. Le polling
// (useChatPolling) dispatche ces thunks ; les helpers PURS (messagingUtils)
// portent toute la logique de fusion/tri et sont testés à part.

export const fetchConversations = createAsyncThunk(
  'messaging/fetchConversations',
  async (params, { rejectWithValue }) => {
    try {
      const res = await messagesApi.listConversations(params)
      return res.data?.results ?? res.data ?? []
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

export const fetchUnreadCount = createAsyncThunk(
  'messaging/fetchUnreadCount',
  async (_, { rejectWithValue }) => {
    try {
      const res = await messagesApi.unreadCount()
      // Le backend répond { per_conversation: {id: n}, total }.
      return res.data?.total ?? res.data?.unread ?? res.data?.count ?? 0
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

// Page initiale (la plus récente) d'une conversation.
export const fetchMessages = createAsyncThunk(
  'messaging/fetchMessages',
  async ({ conversationId, params }, { rejectWithValue }) => {
    try {
      const res = await messagesApi.listMessages(conversationId, params)
      return { conversationId, page: res.data, next: res.data?.next ?? null }
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

// Scroll-up : messages plus anciens fusionnés en tête.
export const fetchOlderMessages = createAsyncThunk(
  'messaging/fetchOlderMessages',
  async ({ conversationId, before }, { rejectWithValue }) => {
    try {
      const res = await messagesApi.listMessages(conversationId, { before })
      return { conversationId, page: res.data, next: res.data?.next ?? null }
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

export const sendMessage = createAsyncThunk(
  'messaging/sendMessage',
  async (payload, { rejectWithValue }) => {
    try {
      const res = await messagesApi.sendMessage(payload)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

export const editMessage = createAsyncThunk(
  'messaging/editMessage',
  async ({ id, data }, { rejectWithValue }) => {
    try {
      const res = await messagesApi.editMessage(id, data)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

export const deleteMessage = createAsyncThunk(
  'messaging/deleteMessage',
  async (id, { rejectWithValue }) => {
    try {
      await messagesApi.deleteMessage(id)
      return id
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

export const markConversationRead = createAsyncThunk(
  'messaging/markRead',
  async ({ conversationId, messageId }, { rejectWithValue }) => {
    try {
      await messagesApi.markRead(conversationId, messageId)
      return conversationId
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

export const fetchPinned = createAsyncThunk(
  'messaging/fetchPinned',
  async (conversationId, { rejectWithValue }) => {
    try {
      const res = await messagesApi.listPinned(conversationId)
      return { conversationId, items: res.data?.results ?? res.data ?? [] }
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

const initialState = {
  conversations: [],
  loadingConversations: false,
  activeId: null,
  // Messages de la conversation ouverte (ordre chronologique croissant).
  messages: [],
  loadingMessages: false,
  loadingOlder: false,
  // Curseur de pagination « plus anciens » (null = plus rien à charger).
  nextOlder: null,
  pinned: [],
  unreadTotal: 0,
  error: null,
}

const slice = createSlice({
  name: 'messaging',
  initialState,
  reducers: {
    setActiveConversation(state, action) {
      if (state.activeId !== action.payload) {
        state.activeId = action.payload
        state.messages = []
        state.nextOlder = null
        state.pinned = []
      }
    },
    // Marque localement une conversation lue (badge instantané) — le serveur
    // est confirmé par markConversationRead.
    clearConversationUnread(state, action) {
      const c = state.conversations.find((x) => x.id === action.payload)
      if (c) c.unread_count = 0
      state.unreadTotal = totalUnread(state.conversations)
    },
    upsertConversation(state, action) {
      state.conversations = upsertConv(state.conversations, action.payload)
    },
    // Réaction optimiste locale (toggle) en attendant la confirmation serveur.
    toggleReaction(state, action) {
      const { messageId, emoji, userId } = action.payload
      const i = state.messages.findIndex((m) => m.id === messageId)
      if (i !== -1) {
        state.messages[i] = toggleReactionLocal(state.messages[i], emoji, userId)
      }
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchConversations.pending, (state) => {
        state.loadingConversations = true
        state.error = null
      })
      .addCase(fetchConversations.fulfilled, (state, action) => {
        state.loadingConversations = false
        state.conversations = sortConversations(action.payload)
        state.unreadTotal = totalUnread(state.conversations)
      })
      .addCase(fetchConversations.rejected, (state, action) => {
        state.loadingConversations = false
        state.error = action.payload
      })

      .addCase(fetchUnreadCount.fulfilled, (state, action) => {
        state.unreadTotal = action.payload
      })

      .addCase(fetchMessages.pending, (state) => {
        state.loadingMessages = true
      })
      .addCase(fetchMessages.fulfilled, (state, action) => {
        state.loadingMessages = false
        if (action.payload.conversationId !== state.activeId) return
        state.messages = toAsc(action.payload.page)
        state.nextOlder = action.payload.next
      })
      .addCase(fetchMessages.rejected, (state, action) => {
        state.loadingMessages = false
        state.error = action.payload
      })

      .addCase(fetchOlderMessages.pending, (state) => {
        state.loadingOlder = true
      })
      .addCase(fetchOlderMessages.fulfilled, (state, action) => {
        state.loadingOlder = false
        if (action.payload.conversationId !== state.activeId) return
        state.messages = mergeOlderMessages(state.messages, action.payload.page)
        state.nextOlder = action.payload.next
      })
      .addCase(fetchOlderMessages.rejected, (state) => {
        state.loadingOlder = false
      })

      .addCase(sendMessage.fulfilled, (state, action) => {
        const msg = action.payload
        if (msg?.conversation === state.activeId || !msg?.conversation) {
          state.messages = mergeNewerMessages(state.messages, [msg])
        }
        state.conversations = upsertConv(state.conversations, {
          id: msg?.conversation,
          last_message: msg,
          unread_count: 0,
        })
      })

      .addCase(editMessage.fulfilled, (state, action) => {
        state.messages = upsertMsg(state.messages, action.payload)
      })

      .addCase(deleteMessage.fulfilled, (state, action) => {
        state.messages = removeMsg(state.messages, action.payload)
      })

      .addCase(markConversationRead.fulfilled, (state, action) => {
        const c = state.conversations.find((x) => x.id === action.payload)
        if (c) c.unread_count = 0
        state.unreadTotal = totalUnread(state.conversations)
      })

      .addCase(fetchPinned.fulfilled, (state, action) => {
        if (action.payload.conversationId === state.activeId) {
          state.pinned = action.payload.items
        }
      })
  },
})

export const {
  setActiveConversation,
  clearConversationUnread,
  upsertConversation,
  toggleReaction,
} = slice.actions

// ── Sélecteurs ──
export const selectConversations = (s) => s.messaging.conversations
export const selectActiveId = (s) => s.messaging.activeId
export const selectMessages = (s) => s.messaging.messages
export const selectUnreadTotal = (s) => s.messaging.unreadTotal
export const selectPinned = (s) => s.messaging.pinned
export const selectActiveConversation = (s) =>
  s.messaging.conversations.find((c) => c.id === s.messaging.activeId) || null

export default slice.reducer
