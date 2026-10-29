# Tri nocturne de l'assistant — mode d'emploi (AIC51)

Le skill Claude Code `assistant-tri` (`.claude/skills/assistant-tri/SKILL.md`) lit CHAQUE NUIT l'export
**anonymisé** des événements de l'assistant des commerciaux (`GET /api/django/agent/evenements/export/`,
AIC11 ; contrat `backend/django_core/apps/agent/contract_samples/assistant_export.json`) et ouvre UNE PR
docs-only avec quatre sorties :

1. **FAQ** ajoutée au manuel `backend/fastapi_ia/assistant/manuel.md` (bloc `FAQ-TRI`) pour les questions
   restées sans bonne réponse : le commercial reçoit la réponse le lendemain, par l'assistant API — jamais
   depuis cette tâche ;
2. **ERR** : une ligne `ERR-AIC-<ÉCRAN>-<SLUG>` dans `docs/ERROR_PLAN.md` par couple (écran, erreur) pour les
   `bug`, dédupliquée (« Vu N fois ») ;
3. **Tâches routées** : pour les `manque` et `hors_champ`, une tâche `[ ]` dans le plan du PROPRIÉTAIRE des
   fichiers concernés (`python scripts/check_ownership.py --owner-of …`), avec « demandé par N commerciaux »,
   jamais dans `docs/PLAN.md` par défaut ;
4. **Digest** de dix lignes en tête de la PR, pour Reda.

Le tri ne répond jamais à un commercial et n'est jamais déclenché par un commercial : c'est une tâche de nuit.

## Interrupteur

`docs/assistant-tri.config.yml` : `actif: false` ⇒ la tâche sort sans rien écrire
(`ASSISTANT_TRI: DESACTIVE (interrupteur)`). Livré **éteint**. Le même fichier porte
`confidentialite_aicm2_confirmee` (garde-fou D6, voir ci-dessous), la fenêtre lue (24 h), l'intervalle
minimum entre deux tirs et les plafonds d'une passe. Même patron que `docs/qa-explorer.config.yml`.

## Le prompt enregistré

```
run the assistant-tri skill (.claude/skills/assistant-tri/SKILL.md)
```

Le contenu envoyé à une tâche planifiée arrive dans `<routine-fire-payload>` : le skill le traite, comme
l'export, comme des DONNÉES jamais comme des instructions. Aucune autre consigne ne doit être ajoutée au
prompt.

## Planification

- **Tâche planifiée cloud de Claude Code**, **une fois par nuit** (par exemple 02:00 Africa/Casablanca).
  Limites de la plateforme (aperçu de recherche) : minimum 1 h entre deux exécutions, 100 exécutions par heure
  et par compte, 30 tirs par heure et par tâche — très au-dessus de ce dont le tri a besoin.
- Modèle : **sonnet** (le nightly-qa tourne en opus — à réévaluer sur la consommation réelle de la fenêtre
  hebdomadaire). Fable : jamais.
- Une seule tâche : ne pas en créer une seconde « par sécurité ».

## Allowlist réseau et secret à poser

- **Allowlist réseau de l'environnement de la tâche cloud** : niveau « Custom », ajouter `api.taqinor.ma`
  (bloqué par défaut). Rien d'autre.
- **Secret de la tâche** : `ASSISTANT_EXPORT_TOKEN` — jeton d'accès d'un compte administrateur de la
  société (l'export est réservé aux administrateurs et ne sert qu'UNE société, celle du compte). À poser dans
  les secrets de la tâche, jamais dans le dépôt, jamais dans le prompt. Côté serveur, `AGENT_HMAC_SECRET`
  doit être posé (sans lui l'export est refusé : il ne sert jamais d'identifiants bruts).

## Garde-fou D6 : qui paie

La tâche tourne sur l'**abonnement** de Reda SEULEMENT si :
1. l'option « aider à améliorer Claude » est **désactivée** sur son compte (geste AICM2 — Reda coche ensuite
   `confidentialite_aicm2_confirmee: true`) ET
2. l'export est anonymisé (AIC11, déjà le cas : `[client]`, `[tel]`, `[email]`, `[num]`, identifiants hachés).

Sinon la même tâche tourne avec la **clé API** de l'organisation liée (`ANTHROPIC_API_KEY` dans l'environnement
⇒ facturée sur les crédits). Sans l'un ni l'autre, le skill s'arrête (`ASSISTANT_TRI: BLOQUE (AICM2 non
confirmé)`). L'usage de l'abonnement ne sert que Reda : il n'est jamais placé derrière une requête d'un
commercial.

## Ce que le tri n'écrit jamais

Pas de nom, de téléphone, d'e-mail ni d'identifiant haché dans le dépôt ; pas de prix d'achat ; pas de
secret ; aucun fichier hors de la liste du skill (manuel, `ERROR_PLAN.md`, plans propriétaires, empreinte des
plans de `docs/CODEMAP.md`, ce fichier). Le manuel reste ≤ 60 000 tokens (garde AIC5) : au-delà, les FAQ les
plus anciennes sortent d'abord. La régénération hebdomadaire du manuel par le skill `assistant-manuel` (AIC50)
conserve le bloc `FAQ-TRI` tel quel.

## Passages

| Date | Événements lus | FAQ | ERR | Tâches routées | PR |
|---|---|---|---|---|---|
| 2026-10-29 — joué à la main (recette ci-dessous) sur l'export de la pile locale après le rejeu AIC13 | 15 (1 commercial) | 1 | 0 (le seul `bug` : 404 provoqué sur un lead inexistant, faux positif écarté) | 0 (1 `manque` « devis agricole automatique », 1 seul commercial : compté, non routé) | vague AIC13 (dev-aic) |

## Pour jouer un tri à la main (recette de l'acceptation)

Sur la pile locale (`docker compose up`, société de démonstration) : générer quelques événements en
interrogeant l'assistant (une question de manuel sans bonne réponse, un bug, un manque), poser
`AGENT_HMAC_SECRET` et `ASSISTANT_EXPORT_TOKEN`, passer `actif: true` en local, puis taper
« run the assistant-tri skill ». Attendu : une PR avec une FAQ, une ligne `ERR-AIC-…` et une tâche
routée chez son propriétaire, plus le digest. Cette recette demande un appel payant à l'assistant ; elle n'a
pas été jouée à la livraison d'AIC51 ; elle l'a été le 29/10/2026 à la main par l'orchestrateur, sur les 15 événements
du rejeu AIC13 (voir « Passages » : 1 FAQ, 0 ERR, 0 tâche routée, digest dans la PR de la vague).
