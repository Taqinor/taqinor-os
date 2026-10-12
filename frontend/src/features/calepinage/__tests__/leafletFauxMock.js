// Faux Leaflet partagé par les tests de la photo de site (calage, téléversement) :
// UN seul exemplaire, utilisé par `vi.mock('leaflet', async () => (await import(
// './leafletFauxMock')).leafletFauxMock())`.
import { vi } from 'vitest'

export function leafletFauxMock() {
  function fakeMarker(pos) {
    let latlng = Array.isArray(pos) ? { lat: pos[0], lng: pos[1] } : pos
    const marker = {
      addTo: () => marker,
      on: () => marker,
      getLatLng: () => latlng,
      setLatLng: (p) => { latlng = Array.isArray(p) ? { lat: p[0], lng: p[1] } : p },
    }
    return marker
  }
  function fakeMap() {
    const map = {
      addTo: () => map,
      on: () => map,
      remove: () => {},
      latLngToContainerPoint: () => ({ x: 0, y: 0 }),
    }
    return map
  }
  return {
    default: {
      map: vi.fn(() => fakeMap()),
      tileLayer: vi.fn(() => ({ addTo: () => {} })),
      polygon: vi.fn(() => ({ addTo: () => {} })),
      marker: vi.fn((pos) => fakeMarker(pos)),
      divIcon: vi.fn(() => ({})),
    },
  }
}
