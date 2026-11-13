// ADCG — preuves en direct du parcours PF3 « deploy, CI, gardes » (dossier
// docs/audits/2026-11-10-parcours-PF3.md) jouables à l'ÉCRAN, au format de `_format.md`.
// Les autres preuves du groupe (compose, e2e-local, bancs du deploy, load-smoke) sont des
// étapes hors navigateur du workflow de rejeu, fusionnées par `_enregistrement.js`.
// ADCG115 : un VRAI `manage.py dump_database` tourne avec des variables BACKUP_OFFSITE_*
// factices (cible injoignable) ; l'écran Paramètres → Sauvegardes doit en afficher la cause.
import { test, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage } from '../helpers.js'

const etape = groupe('ADCG', ['ADCG115'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

/** `manage.py <args>` dans le même environnement que le shell Django des specs. */
function manage(args, env = {}) {
  const [cmd, ...pre] = (process.env.E2E_DJANGO_EXEC || 'docker compose exec -T django_core').split(' ')
  return execFileSync(cmd, [...pre, 'python', 'manage.py', ...args], {
    encoding: 'utf8', timeout: 600_000, env: { ...process.env, ...env },
  })
}

etape('PF3.sauvegardes.copie_distante_echec', ['ADCG115'], async ({ page }) => {
  // Cible hors serveur FACTICE : port 9 de la boucle locale, refusé — la copie distante échoue,
  // le dump local réussit (run « termine ») et sa cause est consignée dans detail.offsite.
  const sortieDump = manage(['dump_database'], {
    BACKUP_OFFSITE_ENDPOINT: 'http://127.0.0.1:9',
    BACKUP_OFFSITE_BUCKET: 'acceptation-adcg115',
    BACKUP_OFFSITE_ACCESS_KEY: 'cle-factice',
    BACKUP_OFFSITE_SECRET_KEY: 'secret-factice',
  })
  console.log(`[ADCG115] ${sortieDump.trim()}`)
  const run = await py(`from core.models import BackupRun
r = BackupRun.objects.filter(kind=BackupRun.KIND_DB_DUMP, company__isnull=True).order_by('-id').first()
sortie(dict(id=r.pk, statut=r.statut, offsite=(r.detail or {}).get('offsite')))`)
  try {
    expect(run.statut).toBe('termine')
    expect(run.offsite?.status).toBe('echec')
    const cause = String(run.offsite?.message || '')
    expect(cause.length).toBeGreaterThan(0)
    console.log(`[ADCG115] BackupRun #${run.id} — cause servie : ${cause}`)

    // L'API sert la cause (lecture seule, aucun appel ajouté).
    const api = await page.request.get('/api/django/core/mes-sauvegardes/')
    expect(api.status()).toBe(200)
    const copie = (await api.json()).copie_distante
    expect(copie?.etat).toBe('echec')
    expect(copie?.message).toBe(cause)

    // L'écran l'affiche : « Copie hors serveur en échec le <date> : <cause> » (200 caractères max).
    const attendu = ` : ${cause.slice(0, 200)}`
    for (const passage of ['ouverture', 'rechargement']) {
      if (passage === 'ouverture') await page.goto('/parametres/sauvegardes')
      else await page.reload()
      const badge = page.getByText(/^Copie hors serveur en échec le /)
      await expect(badge, `badge danger (${passage})`).toBeVisible({ timeout: 30_000 })
      await expect(badge).toContainText(attendu)
      const texte = (await badge.innerText()).trim()
      console.log(`[ADCG115] écran (${passage}) : ${texte}`)
      expect(texte.startsWith('Copie hors serveur en échec le ')).toBe(true)
    }
  } finally {
    await py(`from core.models import BackupRun
BackupRun.objects.filter(pk=${Number(run.id)}).delete()
sortie(1)`)
  }
})
