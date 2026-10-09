---
name: enforce-all-checks
description: Founder rule 09/10/2026 — every CI check is a real gate (API fuzz all checks, no advisory/continue-on-error, debt ratchets driven to zero)
metadata:
  type: project
---

Règle fondateur du 09/10/2026 (réponse à la question sur le triage api-fuzz) : « enforce ALL checks of the API fuzz,
and ALL the checks of my ERP in general ».

- api-fuzz (schemathesis, `release-verify.yml`) : TOUS les checks, job BLOQUANT (plus de `continue-on-error`) ;
  les ~14 500 constats du 07/10 sont à ramener à zéro par causes racines (pas de filtre qui les masque).
- Aucun contrôle CI « advisory » / `continue-on-error` / `|| true` : chaque garde échoue vraiment.
- Les bases de dette (allowlists, cliquets : duplicats, avertissements OpenAPI, arrondis monétaires, on_delete,
  datetime naïfs, seuils électriques, écrans atteignables…) se résorbent jusqu'à zéro ; une exception permanente
  n'existe que si le fondateur l'a approuvée nommément.

Précisions du 09/10 (questions) : duplicats (1 181) ramenés à ZÉRO (pas de cliquet figé) ; hygiène à zéro — flake8 E501, `# noqa`, `eslint-disable`, tests sautés (hors conditions d'environnement signées), seuil de couverture ; api-fuzz bloquant au nocturne ET sur un sous-ensemble PR (~5 min, apps modifiées). Programme : groupe ENF de docs/PLAN.md.

Décisions api-fuzz du 09/10 (triage docs/audits/api-fuzz-triage-2026-10-09.md) : D1 — un paramètre de requête inconnu est REFUSÉ côté serveur (400 nommant le paramètre), jamais filtré dans schemathesis.toml ; D2 — les vues sans fichier n'acceptent que du JSON (le multipart reste sur les vues d'upload).

**Why:** le fondateur veut que « vert » veuille dire « vérifié », sans zone grise.
**How to apply:** ne jamais proposer de rendre un contrôle advisory ni d'élargir une allowlist pour passer ; une
tâche qui échoue sur une garde corrige la cause. Le chantier de mise en conformité est planifié dans docs/PLAN.md.
