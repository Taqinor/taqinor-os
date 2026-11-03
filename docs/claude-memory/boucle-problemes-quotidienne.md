---
name: boucle-problemes-quotidienne
description: 03/11/2026 — revue L3 du journal des problèmes (YJPB) : l'entrée de la boucle d'erreurs est morte (nightly QA, auditeur de cohérence, autopilot), 14 défauts ERR-JPB, groupe BPQ, décisions D-JPB-1..7 ouvertes
metadata:
  type: project
---

# Boucle quotidienne des problèmes (revue L3, 03/11/2026)

Conception et faits mesurés : `docs/boucle-problemes-quotidienne.md` ; défauts : `ERR-JPB-*`
(`docs/ERROR_PLAN.md`) ; à construire : groupe BPQ (`docs/PLAN.md`).

**Ce qui est vrai.** Le journal navigateur (PR #1231) marche en prod (38 lignes/36 h, une seule
personne) ; le drain `work on error plan` marche (184/185). Ce qui est mort, c'est l'ENTRÉE :
nightly QA (script effacé du disque du portable, checkout figé au 14/10, tâche « Interactive only »),
`ventes.audit_coherence_nuit` (tuée à 180 s chaque nuit), error-autopilot (jamais planifié), issues
d'alerte nocturnes GitHub ouvertes sans lecteur (#726, #1002, #461). Les purges de rétention sont des
essais à blanc (`RETENTION_AUTO_APPLY` absent) ; `GUNICORN_MAX_REQUESTS` désarmé.

**Lecture d'un résumé prod (règles apprises le 03/11).** Une rafale de 5xx dans la même seconde
= fenêtre de déploiement (vérifier `docker inspect … StartedAt`) ; des `ECONNABORTED` sur N routes de
polling la même seconde depuis un téléphone = connectivité (vérifier qu'elles n'ont PAS atteint nginx) ;
un `us="-"` à 20 s ne prouve pas que Django a échoué (replace-lines a fini après que le navigateur a
abandonné : vérifier `updated_at`) ; 575 chunks 404 = un scanner (1 IP) et non des bundles périmés.

**Décisions (Reda, 03/11) :** D-JPB-2 TRANCHÉ = Sentry backend seul (jamais de DSN front sans nouvelle
décision) ; D-JPB-3/4 ACCEPTÉS = Reda pose `RETENTION_AUTO_APPLY=1` + `GUNICORN_MAX_REQUESTS=300`/jitter 60
(à vérifier en lecture seule ensuite) ; D-JPB-1 TRANCHÉ = routine cloud (« si le coût est identique on le fait sur cloud » ;
coût identique = usage de l'abonnement dans les deux cas) ; D-JPB-6 balise publique (défaut
non) ; D-JPB-7 sonde externe gratuite (défaut oui).

**Why:** Reda a demandé (02/11) que tout problème vécu soit consigné ET que ce journal serve à
trouver et corriger tous les problèmes ; sans cette mémoire, une session reconstruira la boucle ou
ré-armera les détecteurs morts tels quels (autopilot avec docker local, contraire à « CI d'abord »).

**How to apply:** avant toute automatisation d'un détecteur, le jouer à la main une fois et vérifier
qu'un canal que Reda VOIT (l'ERP, pas GitHub) signale son silence (dead-man's switch BPQ6). Voir
[[ci-avant-docker]], [[prod-read-access]], [[prod-sans-sauvegarde]].
