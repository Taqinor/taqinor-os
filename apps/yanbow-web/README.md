# yanbow-web — site public YanBow

Site Astro + Cloudflare Workers de YanBow (plan `docs/plans/PLAN_YANBOW_WEB.md`).
Paquet autonome : il ne partage AUCUN fichier avec `apps/web` (site TAQINOR) ni
avec `frontend/` (ERP).

## Commandes (Node ≥ 22.12)

| Commande | Rôle |
| --- | --- |
| `npm ci` | installe les dépendances exactes du `package-lock.json` |
| `npm run dev` | serveur de développement local |
| `npm run check` | `astro check` puis `tsc -p tsconfig.check.json` (pages, API, Worker, scripts, tests) |
| `npm run build` | construit `dist/` (pages statiques + Worker) |
| `npm test` | tests vitest |
| `npm run test:e2e` | gardes navigateur Playwright (sur le build) |
| `npm run lighthouse` | porte Lighthouse (sur le build) |

Le `package-lock.json` se régénère avec `npx -y npm@10.9.8 install --package-lock-only`
(npm 11 sous Windows élague des entrées Linux — garder les `@emnapi/*`).

## Règles de test

- `npm test` suppose un build à jour (`npm run build` d'abord) : les gardes
  lisent les pages construites via `tests/builtHtml.ts`.
- **Aucun test ne lit le source par regex quand le rendu existe** : on teste le
  HTML rendu (`tests/builtHtml.ts`, ou l'API Container pour un composant) et
  les réponses du Worker, jamais le texte d'un fichier `.astro`.
- Le réseau est interdit : `tests/setup.ts` remplace `fetch` par une fonction
  qui lève ; un test qui en a besoin le simule explicitement.

## Variables

Toutes listées dans `.dev.vars.example` (copier en `.dev.vars` en local).
Aucun secret dans le dépôt : en production, Reda les pose au tableau de bord
Cloudflare. `wrangler.jsonc` ne contient ni `vars`, ni KV, ni cron.

## Déploiement

Jamais à la main : le projet Workers Builds (créé par Reda, racine
`apps/yanbow-web`) construit et déploie à chaque merge sur `main`. Jamais
`wrangler deploy`, jamais de jeton Cloudflare demandé.
