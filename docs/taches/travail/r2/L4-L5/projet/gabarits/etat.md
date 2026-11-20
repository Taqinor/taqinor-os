# <run> — état du chantier (à lire EN PREMIER pour reprendre, sur ce poste ou un autre)

Dernière écriture : <date heure> par <session / poste> · poussé sur `<branche de notes>@<sha9>`.
**Prochaine action unique** : <une phrase : quoi, où, avec quelle commande>
Ce fichier vit POUSSÉ : un worktree sans activité git depuis 7 jours est supprimé par le ménage de 03:00 UTC
(`TaqinorDevClean`) ; rien ne doit exister seulement dans un worktree.

## Demande et cadre
- Demande de Reda, mot pour mot : « <…> » ; consignes en vigueur (ex. « aucune question ») : <…>
- Niveau <L4 | L5> · régime <NEUF | EXISTANT | MIXTE> lu sur `origin/main@<sha9>` (signaux : <F, ALL, plan, P = s/t>) ;
  bascules : <aucune | date — raison>
- Contrat de sortie : `<chemin>` (critères K1-K<n>) ; registre : `<chemin>/registre/`
- Coût annoncé : k = <k> tours (dernier compris) × c = <c> points + réserve finale 10 ; quota au départ <u> % (lu par
  `mcp__ccd_session_mgmt__get_usage`, « Weekly · all models » | donné par Reda le <date>) ; L5 : « coût non mesuré »
- Poste mesuré au tour 0 : <cœurs, mémoire libre, disque libre, autres piles> → <n> agents à navigateur au plus
- Contrôle de l'instrument : « instrument sur » le <date heure> (sortie collée en annexe)

## Valeurs de départ et valeurs mesurées (à recaler à la rétro)
| Valeur | Départ | Mesuré dans ce run |
|---|---|---|
| c (points par tour) | 25 | <tour 1 : …> |
| seuil de contre-vérification totale (non-fait + partiel) | 10 % | <…> |
| disjoncteur (tentatives) | 3 | <…> |
| seuils de régime | 20 % / 80 % | <régime annoncé tenu ? oui / non> |

## Quota et contexte aux points de contrôle (ajout seulement)
Points : après le tour 0, chaque tour de relecteurs, la consolidation, chaque pli, chaque résultat de CI, avant chaque
merge. Contexte de l'orchestrateur ≥ 70 % → écrire cet état AVANT de continuer. Claims renouvelées à chaque point.
| Point | Date | Quota hebdo | Contexte orchestrateur | Claims renouvelées | Décision |
|---|---|---|---|---|---|
| tour 0 | | | | | |

## Où sont les choses
- Notes de travail : `<dossier>` (branche `<branche de notes>`) — briefs, contrat, rapports `T<n>/`, consolidations,
  registre, fiches de classes.
- Code : branche d'intégration `<branche>`, PR <#n> ouverte en brouillon au tour 0 (<brouillon | en file>, Auto-fix
  allumé) ; lecture des jobs de CI contre le périmètre : <job → lit le module ? oui / non>. Worktrees :
  `<worktree monté par l'instrument>` (ne pas modifier pendant une revue ; mise à jour `git merge --ff-only`),
  `<worktree d'intégration>` (plis, poussée `git push origin HEAD:<branche>`), lanes `<liste>`, tests premiers `<liste>`.
- Instrument : `<fiche de l'instrument>` (adresses, comptes ; mot de passe dans `<scratchpad>/env.local`).
- Claims : `<file:… app:…>` tenues avec `--owner <poste>/<branche>` (bail 6 h) — y compris sur les plans d'autres
  propriétaires touchés ; relâcher APRÈS le merge, jamais au pli.
- Plan : `<plan du propriétaire>` porte `<ids>` (format de ce plan) ; les « peut attendre » y sont inscrits en `[ ]`.
- Décisions de Reda prises pendant le run : recopiées dans `docs/audits/decisions.yml` ou `docs/claude-memory/` (PR
  <#n>) — jamais seulement ici.

## Déroulé (un point par étape, avec ses chiffres)
1. Tour 0 : <régime, poste, contrat, instrument et son contrôle, comptes, galerie, PR brouillon, Lane 0>
2. Tour 1 : <n> relecteurs → <n> constats (retenus <n>, écartés <n>) → <n> corrections, <n> lanes, <n> vagues, classes <ids>
3. …

## Merges (un par vague)
| Vague | PR / SHA | Corrections | Pas encore contre-vérifiées (dit à Reda) | Enregistrement d'acceptation |
|---|---|---|---|---|

## Restes et demandes croisées
Sortie de la dernière ligne du script de `registre.md` § 6 (« demandes croisees ouvertes ») + les contre-vérifications
`partiel` / `non-fait` sans correction suivante — aucun autre état de reste n'existe.

## À dire à Reda dans le rapport final
- Ce qui n'a PAS été vu (vrai appareil, notifications, une vraie semaine d'usage — sauf étage « vraie vie » de L5).
- Les choix pris seul (§ 3 des consolidations), réversibles, jamais enregistrés comme ses décisions.
- Hors périmètre signalé, non touché.
- Ses gestes à lui (deploy, drapeau en prod, clés, essai sur son appareil).

## Nettoyage à la fin (cocher chaque ligne)
- [ ] dernière vague mergée par la file ; [ ] claims relâchées ; [ ] instrument démonté (conteneurs, réseau, port
      front, `DROP DATABASE`, fichier d'environnement du run effacé)
- [ ] worktrees de lanes retirés (jonction `node_modules` retirée d'abord par `cmd /c rmdir`) ; accord de suppression
      demandé à Reda tôt si le disque est concerné
- [ ] rétro bornée : classes de rouges CI → `plan_drain_ci_bug_classes` ; valeurs mesurées ci-dessus → `conception.md`
      par une PR à part ; mémoire partagée seulement si un comportement futur change
