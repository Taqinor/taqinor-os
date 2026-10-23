import { describe, it, expect, vi } from 'vitest'
import { retirerCarte } from './retirerCarte'

describe('retirerCarte', () => {
  it('arrête le mouvement, clôt le zoom animé puis retire la carte (dans cet ordre)', () => {
    const ordre = []
    const map = {
      _animatingZoom: true,
      stop: vi.fn(() => ordre.push('stop')),
      _onZoomTransitionEnd: vi.fn(() => ordre.push('fin-zoom')),
      remove: vi.fn(() => ordre.push('remove')),
    }
    retirerCarte(map)
    expect(ordre).toEqual(['stop', 'fin-zoom', 'remove'])
  })

  it('un panBy tardif après remove() est inerte (pas de _mapPane)', () => {
    const panBy = vi.fn()
    const map = { _mapPane: {}, panBy, stop() {}, remove() { this._mapPane = undefined } }
    retirerCarte(map)
    map.panBy([1, 1])
    expect(panBy).not.toHaveBeenCalled()
  })

  it('tolère une carte factice sans stop et un null', () => {
    const remove = vi.fn()
    expect(() => retirerCarte({ remove })).not.toThrow()
    expect(remove).toHaveBeenCalledTimes(1)
    expect(() => retirerCarte(null)).not.toThrow()
  })

  it('désarme le setTimeout du zoom molette (ScrollWheelZoom) avant remove', () => {
    vi.useFakeTimers()
    const performZoom = vi.fn()
    const timer = setTimeout(performZoom, 40)
    const map = { stop: vi.fn(), remove: vi.fn(), scrollWheelZoom: { _timer: timer }, _mapPane: {} }
    retirerCarte(map)
    vi.advanceTimersByTime(100)
    expect(performZoom).not.toHaveBeenCalled()
    expect(map.scrollWheelZoom._timer).toBeNull()
    expect(map.remove).toHaveBeenCalled()
    vi.useRealTimers()
  })
})
