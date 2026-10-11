// @vitest-environment node
// AFAC62 — la garde eslint « catch vide autour d'un await » sur les écrans de facturation.
import { describe, it, expect } from 'vitest'
import { ESLint } from 'eslint'

const eslint = new ESLint({ cwd: process.cwd() })
const FICHIER = 'src/pages/ventes/RelancesPage.jsx'

async function lint(code, filePath = FICHIER) {
  const [r] = await eslint.lintText(code, { filePath })
  return r.messages.filter((m) => m.ruleId === 'no-restricted-syntax')
}

describe('AFAC62 — catch vide autour d un await (facturation)', () => {
  it('signale un catch vide avec await', async () => {
    const m = await lint('async function f(){ try { await api.relancerFacture(1) } catch {} }\n')
    expect(m).toHaveLength(1)
    expect(m[0].message).toContain('Erreur serveur avalée')
  })

  it('signale un catch contenant seulement un commentaire', async () => {
    const m = await lint('async function f(){ try { await api.x() } catch { /* ignoré */ } }\n')
    expect(m).toHaveLength(1)
  })

  it('ne vise pas un catch vide sans await (localStorage)', async () => {
    const m = await lint("function f(){ try { return localStorage.getItem('a') } catch { /* */ } }\n")
    expect(m).toHaveLength(0)
  })

  it('ne vise pas un catch qui traite l erreur', async () => {
    const m = await lint('async function f(){ try { await api.x() } catch (e) { console.error(e) } }\n')
    expect(m).toHaveLength(0)
  })

  it('ne touche pas les autres dossiers', async () => {
    const m = await lint('async function f(){ try { await api.x() } catch {} }\n', 'src/pages/crm/Autre.jsx')
    expect(m).toHaveLength(0)
  })
})
