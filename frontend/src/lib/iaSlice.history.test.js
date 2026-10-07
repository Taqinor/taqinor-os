import { describe, it, expect } from 'vitest'
import reducer, { loadChatHistory } from '../features/ia/store/iaSlice'

describe('iaSlice - loadChatHistory.fulfilled', () => {
  const etat = () => reducer(undefined, { type: '@@init' })

  it('charge une vraie liste de messages', () => {
    const liste = [{ role: 'user', content: 'salut' }]
    const s = reducer(etat(), loadChatHistory.fulfilled(liste, 'rid'))
    expect(s.messages).toEqual(liste)
  })

  it('ignore une reponse non-liste (HTML du repli SPA) au lieu de planter', () => {
    const s = reducer(etat(), loadChatHistory.fulfilled('<!doctype html><html></html>', 'rid'))
    expect(Array.isArray(s.messages)).toBe(true)
    expect(s.messages).toEqual([])
  })
})
