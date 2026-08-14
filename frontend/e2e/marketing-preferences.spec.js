// NTMKT43 — E2E Playwright : centre de préférences self-service (NTMKT22).
//
// PÉRIMÈTRE RÉEL COUVERT — cas token invalide/expiré, en profondeur, contre
// le VRAI backend (`GET`/`POST /api/django/marketing/preferences/<token>/`,
// `AllowAny`) : jamais une 500, toujours un message propre.
//
// Cas nominal (token VALIDE) — PAS COUVERT ICI, et volontairement : NTMKT22
// (apps/marketing/public_views.py) est un module 100% backend — son propre
// périmètre de tâche ne listait aucun fichier frontend (pas de page publique
// React pour `/marketing/preferences/<token>` dans ce dépôt à ce jour), et
// AUCUNE route/API n'expose un jeton de préférences mintable/prévisualisable
// pour un usage staff/E2E (`generer_token_preferences` est un helper Python
// interne, jamais câblé derrière un endpoint REST). Sans page à ouvrir ET
// sans moyen d'obtenir un jeton valide depuis l'extérieur du process Django
// (le jeton est signé avec `SECRET_KEY`, inaccessible à ce test), un
// parcours navigateur du cas nominal ne peut pas être construit sans élargir
// le périmètre de cette tâche (créer la page publique ET/OU un endpoint de
// prévisualisation staff) — hors périmètre de NTMKT43 (Files: uniquement ce
// spec). Signalé ici plutôt que simulé faussement.
import { test, expect } from '@playwright/test'

const API = '/api/django/marketing'

test.describe('NTMKT43 : centre de préférences self-service — robustesse token', () => {
  test('un jeton complètement invalide est rejeté proprement (jamais une 500)', async ({ request }) => {
    const res = await request.get(`${API}/preferences/nimportequoi/`)
    expect(res.status()).toBe(400)
    const body = await res.json()
    expect(body.detail).toBe('Lien invalide.')
  })

  test('un jeton signé mais altéré (une lettre modifiée) est rejeté proprement', async ({ request }) => {
    // Un jeton `django.core.signing` bien formé mais dont la signature ne
    // correspond plus (falsifié) doit échouer comme un jeton inconnu —
    // jamais une exception non gérée.
    const res = await request.get(`${API}/preferences/a.b.c-falsifie/`)
    expect(res.status()).toBe(400)
    const body = await res.json()
    expect(body.detail).toBe('Lien invalide.')
  })

  test('POST sur un jeton invalide est rejeté proprement (jamais une 500)', async ({ request }) => {
    const res = await request.post(`${API}/preferences/nimportequoi/`, {
      data: { canaux: { email: false } },
    })
    expect(res.status()).toBe(400)
    const body = await res.json()
    expect(body.detail).toBe('Lien invalide.')
  })

  test('un jeton vide (URL malformée) ne provoque jamais une 500', async ({ request }) => {
    const res = await request.get(`${API}/preferences/%20/`)
    expect(res.status()).toBeLessThan(500)
  })
})
