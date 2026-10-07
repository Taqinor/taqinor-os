import { describe, it, expect, vi, afterEach } from 'vitest'

/* Lot 2 critique #26 — la fiche et la liste préfixent l'URL RELATIVE de
   l'aperçu par l'origine de l'API (ACAL197), par le MÊME helper. */
afterEach(() => { vi.unstubAllEnvs(); vi.resetModules() })

describe('urlImage', () => {
  it('préfixe une URL relative par l’origine de l’API, laisse une absolue', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.taqinor.ma/api/django')
    vi.resetModules()
    const { urlImage } = await import('./urlImage')
    expect(urlImage('/api/django/calepinage/x.png'))
      .toBe('https://api.taqinor.ma/api/django/calepinage/x.png')
    expect(urlImage('https://minio.example/x.png')).toBe('https://minio.example/x.png')
    expect(urlImage(null)).toBeNull()
  })
})
