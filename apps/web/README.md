# taqinor.ma — site public (apps/web)

Site vitrine + génération de leads de Taqinor. Astro 6 (SSR Cloudflare Workers),
Tailwind CSS 4, déployé sur Cloudflare Workers avec assets statiques.

Auto-deploys: connected via Cloudflare Workers Builds, June 2026.

## Pages

| Route | Contenu |
|---|---|
| `/` | Hero + ruban Article 33, bande de confiance, segments, témoignages, formulaire, FAQ |
| `/résidentiel` | Villas/appartements, dimensionnement par tranche de facture, ROI 25 ans |
| `/professionnel` | Industriels, hôtels, cliniques — surplus, régime moyenne tension |
| `/équipement` | Matériel réellement stocké : Deye, Solis, Dyness, panneaux Tier 1 |
| `/loi-82-21` | Sélecteur interactif des 3 régimes (décret 2-25-100) |
| `/regularization-article-33` | Fenêtre de régularisation 18 mois, procédure 5 étapes, sanctions |
| `/contact` | Formulaire + liens WhatsApp + zone de service |
| `POST /api/simulate` | Proxy serveur du formulaire (seul point d'entrée des leads) |

## Flux du formulaire (POST /api/simulate)

1. Validation + normalisation du téléphone en E.164 (`+212XXXXXXXXX`).
2. Simulation : proxy vers `SIMULATOR_API_URL` si configurée, sinon bande
   locale kWc + ROI calculée depuis la tranche de facture. Le navigateur
   n'appelle jamais l'API de simulation directement.
3. Seuil : factures sous 1 000 MAD → état de remerciement, mais le lead
   n'atteint JAMAIS le CRM ni la CAPI.
4. Lead qualifié → POST JSON vers `LEAD_WEBHOOK_URL` (consentement horodaté,
   fbclid + UTM persistés). Panne ou absence tolérée (log Worker).
5. CAPI : POST fire-and-forget vers `CAPI_URL`, absence tolérée en silence.
6. Réponse : bande kWc/ROI + deeplink WhatsApp pré-rempli (auto-ouvert sur mobile).

## Variables d'environnement (secrets Worker)

Voir `.dev.vars.example`. Toutes optionnelles ; le site dégrade proprement.

## Commandes

```sh
npm install
npm run dev          # dev local (workerd)
npm test             # vitest — logique métier (téléphone, seuil, régimes, lead)
npm run build        # build production
npm run preview      # sert le build via wrangler
npm run generate-og  # régénère les images OG (public/og/)
```

## Déploiement

**Pousser/merger sur `main`** — Cloudflare Workers Builds construit et déploie
automatiquement. Ne jamais lancer `wrangler deploy` à la main et ne jamais
demander de token Cloudflare (l'ancien est mort et supprimé).

`taqinor-web.taqinor.workers.dev` répond en **301 vers https://taqinor.ma**
(chemin préservé) : wrapper committé dans `worker/`, installé dans
`dist/server/` au build par le hook `workersDevRedirect` d'`astro.config.mjs`
(qui active aussi `run_worker_first` sur les routes HTML).

## Conventions

- Chaînes client en français, format monétaire `12 500 MAD`, pas de Darija.
- NAP canonique dans `src/lib/nap.ts` — seule source pour nom/téléphone/email/URL.
- Pas de PDF de devis depuis le site, jamais (règle `/proposal`, CLAUDE.md racine).
- Placeholders en attente de contenu définitif : rechercher `PLACEHOLDER(MERYEM)`
  et `PLACEHOLDER(REDA)` dans `src/`.
