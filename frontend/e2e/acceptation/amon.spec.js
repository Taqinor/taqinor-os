// Acceptation en direct — groupe AMON (monitoring, run 99392c vague 10) : preuve due d'AMON111 — registre des
// certificats carbone (SAV › Monitoring) : annuler un certificat émis, puis « PDF » ⇒ le fichier téléchargé porte
// « ANNULÉ le JJ/MM/AAAA — motif », référence et tonnes inchangées, et AUCUNE nouvelle version GED n'est déposée.
// Montage dans la société de demo_admin : chantier + client, relevé de production (1 000 kWh), facteur CO₂ du réseau
// réglé le temps de l'étape puis rétabli. Émission par la vraie route (rendu WeasyPrint réel + dépôt GED/MinIO),
// annulation et téléchargement par l'écran.
import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, textePdf, API_DJANGO as API } from '../helpers.js'

const etape = groupe('AMON', ['AMON111'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 420_000 })
test.use({ viewport: { width: 1600, height: 1000 } })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const T = { timeout: 120_000 }
const J = JSON.stringify
const URL_CERT = `${API}/monitoring/certificats-carbone/`
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()
const versionsGed = (id) => py(`from apps.ged.services import find_document_by_source
co = U.objects.get(username='demo_admin').company
doc = find_document_by_source(co, source_type='monitoring.certificat_carbone', source_id=${Number(id)})
sortie(None if doc is None else doc.versions.count())`)

etape('P.pdf_certificat_annule', ['AMON111'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const x = await py(`from decimal import Decimal as D
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import ProductionReading
from apps.parametres.models import CompanyProfile
co = U.objects.get(username='demo_admin').company
p = CompanyProfile.get(company=co)
avant = dict(g=None if p.facteur_co2_reseau_g_kwh is None else str(p.facteur_co2_reseau_g_kwh),
             s=p.facteur_co2_reseau_source, d=None if p.facteur_co2_reseau_date is None else p.facteur_co2_reseau_date.isoformat())
p.facteur_co2_reseau_g_kwh = D('810'); p.facteur_co2_reseau_source = 'ONEE'; p.facteur_co2_reseau_date = datetime.date(2026, 1, 15); p.save()
cl = Client.objects.create(company=co, nom='ACC AMON111', prenom='${m}', email='acc-amon111-${m.toLowerCase()}@example.invalid')
inst = Installation.objects.create(company=co, reference='CH-ACC-AMON111-${m}', client=cl, puissance_installee_kwc=D('10'))
ProductionReading.objects.create(company=co, installation=inst, date=datetime.date(2025, 3, 1), period_days=30, energy_kwh=D('1000'))
sortie(dict(inst=inst.id, avant=avant))`)
  try {
    const cert = await lireJson(await r.post(URL_CERT, {
      ...T, data: { installation_id: x.inst, periode_debut: '2025-01-01', periode_fin: '2025-06-30' },
    }), 'émission du certificat')
    expect(Number(cert.tco2_evitees), `0,810 tCO₂ (${J(cert)})`).toBeCloseTo(0.81, 3)
    expect(await versionsGed(cert.id), 'émission : PDF déposé en GED (1 version)').toBe(1)
    // Écran : SAV › Monitoring → registre des certificats → « Annuler » (motif) → « Confirmer l’annulation ».
    await page.goto('/sav/monitoring')
    const carte = page.getByRole('region', { name: 'Certificats carbone' })
    const ligne = carte.locator('li').filter({ hasText: cert.reference }).first()
    await expect(ligne).toBeVisible({ timeout: 60_000 })
    await ligne.getByRole('button', { name: 'Annuler', exact: true }).click()
    await ligne.getByLabel('Motif de l’annulation').fill('période erronée')
    const rep = page.waitForResponse((q) => q.request().method() === 'POST' && q.url().includes(`/certificats-carbone/${cert.id}/annuler/`), T)
    await ligne.getByRole('button', { name: 'Confirmer l’annulation' }).click()
    expect((await rep).status(), 'annulation 200').toBe(200)
    await expect(ligne).toContainText('annulé le', { timeout: 30_000 })
    const relu = await lireJson(await r.get(`${URL_CERT}${cert.id}/`, T), 'certificat relu')
    expect([relu.statut, relu.motif_annulation], 'relu : annulé, motif').toEqual(['annule', 'période erronée'])
    const le = await py(`from apps.monitoring.models import CertificatCarbone
sortie(timezone.localtime(CertificatCarbone.objects.get(pk=${cert.id}).annule_le).strftime('%d/%m/%Y'))`)
    // « PDF » sur la ligne (rechargée : persistance) ⇒ fichier téléchargé, mention lue DANS le fichier.
    await page.reload()
    const ligne2 = page.getByRole('region', { name: 'Certificats carbone' }).locator('li').filter({ hasText: cert.reference }).first()
    await expect(ligne2).toContainText('annulé le', { timeout: 60_000 })
    const [telechargement] = await Promise.all([
      page.waitForEvent('download', T),
      ligne2.getByRole('button', { name: 'PDF', exact: true }).click(),
    ])
    const octets = readFileSync(await telechargement.path())
    expect(octets.subarray(0, 4).toString(), 'un vrai PDF').toBe('%PDF')
    const texte = (await textePdf(octets)).replace(/\s+/g, ' ')
    expect(texte, `mention « ANNULÉ le ${le} — période erronée »`).toContain(`ANNULÉ le ${le} — période erronée`)
    expect(texte, 'référence inchangée').toContain(cert.reference)
    expect(texte, 'tonnes inchangées (0.810)').toMatch(/0[.,]810/)
    // Aucune nouvelle version GED (le PDF d'émission reste la seule version).
    expect(await versionsGed(cert.id), 'GED : toujours une seule version').toBe(1)
  } finally {
    await py(`from apps.parametres.models import CompanyProfile
co = U.objects.get(username='demo_admin').company
p = CompanyProfile.get(company=co)
avant = json.loads(${J(J(x.avant))})
p.facteur_co2_reseau_g_kwh = avant['g']; p.facteur_co2_reseau_source = avant['s']
p.facteur_co2_reseau_date = None if avant['d'] is None else datetime.date.fromisoformat(avant['d']); p.save()
sortie(1)`).catch(() => null)
  }
})
