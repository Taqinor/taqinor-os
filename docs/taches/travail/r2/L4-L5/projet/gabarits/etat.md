# <run> — état du chantier (à lire EN PREMIER pour reprendre, sur ce poste ou un autre)

Dernière écriture : <date heure> par <session / poste> · poussé sur `<branche de notes>@<sha9>`.
**Prochaine action unique** : <une phrase : quoi, où, avec quelle commande>

## Demande et cadre
- Demande de Reda, mot pour mot : « <…> » ; consignes en vigueur (ex. « aucune question ») : <…>
- Niveau <L4 | L5> · régime <NEUF | EXISTANT | MIXTE> lu sur `origin/main@<sha9>` (signaux : <F, plan, P = s/t>) ;
  bascules : <aucune | date — raison>
- Contrat de sortie : `<chemin>` (critères K1-K<n>, plafond <k> tours) ; registre : `<chemin>/registre/`
- Coût annoncé : <k> tours × ≤ 25 points ; quota au départ <u> % (lu par <outil | dernière valeur connue>)

## Quota et contexte aux points de contrôle (ajout seulement)
| Point | Date | Quota hebdo | Contexte orchestrateur | Décision |
|---|---|---|---|---|
| tour 0 | | | | |

## Où sont les choses
- Notes de travail : `<dossier>` (branche `<branche de notes>`) — briefs, contrat, rapports `T<n>/`, consolidations,
  registre, fiches de classes.
- Code : branche d'intégration `<branche>`, PR <#n> (<brouillon | en file>, Auto-fix <allumé>) ; worktrees :
  `<worktree monté par l'instrument>` (ne pas modifier pendant une revue ; mise à jour `git merge --ff-only`),
  `<worktree d'intégration>` (plis, poussée `git push origin HEAD:<branche>`), lanes `<liste>`.
- Instrument : `<fiche de l'instrument>` (adresses, comptes ; mot de passe dans `<scratchpad>/env.local`).
- Claims : `<file:… app:…>` tenues par `<poste/branche>` — relâcher APRÈS le merge, jamais au pli.
- Plan : `<plan du propriétaire>` porte `<ids>` ; les « peut attendre » y sont inscrits en `[ ]`.

## Déroulé (un point par étape, avec ses chiffres)
1. Tour 0 : <régime, contrat, instrument, comptes, galerie du tour 0>
2. Tour 1 : <n> relecteurs → <n> constats (retenus <n>, écartés <n>) → <n> corrections, <n> lanes, classes <ids>
3. …

## Restes et demandes croisées (renvoi aux lignes du registre à l'état `reste`)

## À dire à Reda dans le rapport final
- Ce qui n'a PAS été vu (vrai appareil, notifications, une vraie semaine d'usage — sauf étage « vraie vie » de L5).
- Les choix pris seul (§ 3 des consolidations), réversibles, jamais enregistrés comme ses décisions.
- Hors périmètre signalé, non touché.
- Ses gestes à lui (deploy, clés, essai sur son appareil).

## Nettoyage à la fin (cocher chaque ligne)
- [ ] PR mergée par la file ; claims relâchées ; [ ] instrument démonté (conteneurs, port front, `DROP DATABASE`)
- [ ] worktrees de lanes retirés (jonction `node_modules` retirée d'abord par `cmd /c rmdir`) ; accord de suppression
      demandé à Reda tôt si le disque est concerné
- [ ] rétro bornée : classes de rouges CI → `plan_drain_ci_bug_classes` ; mémoire partagée seulement si un
      comportement futur change
