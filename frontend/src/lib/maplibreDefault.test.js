/* global process */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

/* ERR122 — maplibre-gl 6 (ESM pur, sans export par défaut) : le builder toiture
   importé d'apps/web écrit `import maplibregl from 'maplibre-gl'`. Le shim doit
   rendre un défaut qui porte les classes utilisées par le builder, et
   vite.config.js doit y rediriger le spécifieur EXACT (sinon `vite build` casse
   en MISSING_EXPORT, cf. PR Dependabot #649). */
import maplibregl, { Map as NamedMap } from './maplibreDefault'

describe('ERR122 — shim d’export par défaut maplibre-gl 6', () => {
  it('le défaut expose les classes du builder', () => {
    for (const k of ['Map', 'Marker', 'Point', 'GeoJSONSource',
      'NavigationControl', 'GeolocateControl', 'MercatorCoordinate']) {
      expect(maplibregl[k], k).toBeTypeOf('function')
    }
    expect(maplibregl.Map).toBe(NamedMap)
  })

  it('vite.config.js redirige le spécifieur exact vers le shim', () => {
    // Vitest tourne depuis frontend/ (jsdom : import.meta.url n'est pas file:).
    const cfg = readFileSync(join(process.cwd(), 'vite.config.js'), 'utf8')
    expect(cfg).toContain("find: /^maplibre-gl$/")
    expect(cfg).toContain('src/lib/maplibreDefault.js')
  })
})
