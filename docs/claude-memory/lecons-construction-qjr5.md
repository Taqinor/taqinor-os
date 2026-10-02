---
name: lecons-construction-qjr5
description: 7 causes prouvées pour lesquelles des tâches QJR5 cochées [x] étaient fausses (01-02/10/2026) — critères à appliquer à toute construction et à toute rédaction de tâche
metadata:
  type: feedback
---

La vérification post-construction du groupe QJR5 (171 tâches, 9 vérificateurs + test en direct + critique Fable, 01/10/2026) a trouvé 14 écarts derrière des tâches cochées et une CI verte. Causes, chacune prouvée :

1. **Vert en CI ≠ déployable.** La CI compile le dépôt entier ; l'image Docker ne voit que ce que `frontend/Dockerfile.prod` copie. Un import vers `apps/web/worker` (QJR663) a cassé l'auto-deploy prod en boucle. Garde : `frontend/scripts/check_dockerfile_context.mjs`.
2. **État d'écran non persisté.** Un marqueur gardé seulement en mémoire (QJR570 `compose`) disparaît à la réouverture → recalcul qui écrase une saisie manuelle. Prouver « enregistrer → rouvrir → enregistrer sans toucher » = objet serveur identique.
3. **Source inexistante.** Une décision « branchée » sur une app parquée (QJR668 → `cpq`) donne du code mort ; le test passait parce qu'il patchait la source testée. Interdit de mocker la source sous test.
4. **Paramètre jamais transmis.** QJR605 : `hors_reseau` ajouté, aucun des 4 appelants ne le passait ; QJR612 : un seul des deux endroits câblé. Une tâche liste TOUS les appelants (grep) et chacun doit transmettre.
5. **Test affaibli.** Espion au lieu du résultat stocké (QJR564), regex sur le source comme seule preuve (QJR575), garde promise jamais écrite (QJR593). Test comportemental, rouge d'abord.
6. **Jumeau oublié.** En corrigeant le remplissage CGV du PDF, la page publique de signature gardait sa propre copie divergente. Tout correctif cherche les autres implémentations du même geste (pages publiques, PDF, apps/web) et les supprime dans le même commit.
7. **Aucune preuve en direct pendant la construction.** Le test Playwright sur la pile locale (migrate + rebuild du front d'abord) avait trouvé 5 défauts majeurs à l'audit ; aucun build ne l'a rejoué. Une vague touchant un parcours se clôt par un aller-retour en direct.

Aussi : listes d'exceptions repérées par numéro de ligne (`check_naive_datetime`) et tuples figés (`EntreesMoteur`) cassent dès qu'on insère un champ — les mettre à jour dans le même commit ; refaire `git fetch origin` juste avant de fusionner/pousser (#767 et #768 ont construit deux fois les mêmes 14 items en parallèle).

**Why:** Reda (02/10/2026) a validé ces leçons pour qu'elles s'appliquent à toute construction, y compris les « work on the plan » lancés depuis ses autres sessions.

**How to apply:** les inscrire comme critères d'acceptation dans chaque tâche rédigée (audit) et les vérifier à la relecture de chaque lane (construction) ; un verdict « fait » exige les preuves 2, 3, 4, 5 et 6 quand elles s'appliquent. Voir [[devis-parcours-modifiable-qjr5]], [[qjr5-decisions-fondateur]].
