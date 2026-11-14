# Vérifie ACNC — contre-visite de mi-parcours du parcours PF9 « gestes rejoués et courses », 14/11/2026

Commande `loop audit` (14/11). L'audit de parcours PF9 (11/11, PR #1373) avait déposé ACNC1-56. Première contre-visite du
groupe, due à mi-parcours : 12 tâches cochées sur 20 constructibles. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `47f925be1`. Branche de claim : `verifie-pf9-11-12-1411`.
- **Registre.** PF9 `rejeu-concurrence`, groupe ACNC : 12 tâches cochées sur 20 constructibles (60 %). 28 autres tâches sont
  livrées et attendent leur preuve en direct ; 8 sont ouvertes et non construites.
- **Échantillon.** Les 12 tâches cochées sont relues : ACNC14, 16, 30, 31, 32, 34, 36, 43, 48, 50, 51 et 54.
- **Méthode.** Commits, code sur `origin/main` et tests nommés, tout lu ; mutants raisonnés. Une sonde hôte neuve, écrite et
  jouée (§3) ; sondes du dossier rejouées. Aucune pile, aucun test Django lancé, aucune production consultée. Joué sur l'hôte :
  les deux gardes de dépôt touchées par ACNC50 et ACNC51 et leurs tests (53 tests).

## 1. Vérificateur (opus, effort élevé, frais)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **9** | ACNC14, 16, 31, 32 (écart de texte assumé), 34, 43, 48, 51, 54 |
| partiel | **3** | ACNC30 (« Expédier » et « Livrer » sans test de course ; jumeau « Annuler » resté ouvert), ACNC36 (moitié « avoir » sans test), ACNC50 (clés gelées périmées non refusées) |
| non-fait / faux / régression / déjà-présent | **0** | — |

ACNC32 : la seconde résolution croisée rend 200 sans effet, et non 400 comme l'écrit la tâche ; le critère principal (une seule
émission) est tenu.

## 2. Tests nommés

- **Les 12 tests nommés existent** et sont comportementaux. Ceux d'ACNC30, 31, 32, 34 et 36 jouent deux VRAIES connexions
  (`TransactionTestCase`, l'une tient sa transaction) et relisent un effet unique ; ceux d'ACNC14, 16, 43, 48 et 54 rejouent le
  geste et relisent l'état.
- Les mutants sont raisonnés, pas joués : chaque test tue le retrait du verrou ou de la déduplication qu'il couvre.
- **Trous de test (§4).** Rien ne tue un mutant qui retire le verrou d'« Expédier », de « Livrer » (ACNC30) ou de la
  suppression d'un avoir fournisseur (ACNC36). Le code est correct à la lecture.
- Gardes jouées : `check_read_modify_write.py` et `check_get_or_create.py` rendent 0 ; leurs 53 tests passent. Aucun test Django
  lancé : la preuve d'un vert est la CI des merges.

## 3. Le S2 nouveau : deux « Annuler » croisés d'une livraison expédiée

**Ce qui se passe.** `backend/django_core/apps/installations/views/livraison.py::LivraisonViewSet.annuler` juge la transition sur
la copie rendue par `get_object()`, sans transaction ni verrou. Il appelle ensuite
`backend/django_core/apps/installations/services.py::contre_transferer_stock_livraison`, qui lit `stock_mouvemente` sur cette même
copie. Deux « Annuler » qui ont chargé la ligne avant que l'autre ne valide font donc chacun le contre-transfert camionnette →
dépôt. La camionnette est unique par société : dès qu'elle porte le stock d'une autre livraison, le second transfert réussit.
ACNC30 a mis « Expédier » et « Livrer » sous verrou et a laissé « Annuler » « hors périmètre », sans tâche ; la liste gelée de la
garde le cite « tâche ACNC du plan chantiers » sans tâche réelle.

**Sonde rejouée.** `docs/audits/sondes/ACNC/C-ACNC-VER1-100.py`, relue puis rejouée le 14/11 : `repro: true`, deux réponses
« annulée », deux contre-transferts, stock final camionnette 0 et dépôt 10 au lieu de 5 et 5.
- Elle exécute les VRAIES `annuler` et `contre_transferer_stock_livraison`, extraites du dépôt ; seuls `transfer_stock` et l'ORM
  sont factices.
- Elle ne reproduit pas par construction : si `annuler` relisait la ligne sous verrou, le code extrait appellerait
  `Livraison.objects`, absent du bouchon, et la sonde planterait au lieu de rendre `repro: true`. Elle vérifie aussi l'absence de
  `select_for_update` dans le corps réel.
- Sa limite : l'entrelacement est simulé (deux copies chargées avant toute écriture), comme toutes les sondes du dossier PF9.

**Lecture du code, 14/11.** `expedier` et `livrer` relisent la livraison par `select_for_update()` dans `transaction.atomic()` ;
`annuler` non. `contre_transferer_stock_livraison` a un seul appelant, `annuler`. La route est servie
(`/api/django/installations/livraisons/<id>/annuler/`, wrapper `installationsApi.js::annulerLivraison`) mais aucun écran ne
l'appelle.

**Gravité retenue : S2, pas S1.**
- Pas S1 : les seuils S1 sont l'argent faux, la perte, la fuite ou un chiffre client faux. Le stock total de la société est
  inchangé ; aucun montant ni document client n'est touché ; la route n'a aucun écran ; le dossier PF9 ne retient aucun S1 pour
  des doubles mouvements de stock.
- S2 plutôt que S3 : c'est du stock compté deux fois par emplacement, sans trace d'erreur. La camionnette affiche 0 alors que 5
  unités y sont, le dépôt affiche 5 de trop ; l'annulation de l'autre livraison ne trouve plus rien à rendre dans la camionnette
  et saute son contre-transfert en silence. C'est le mal que le groupe a été ouvert pour fermer.
- Le dossier PF9 avait classé S3 le constat d'origine d'ACNC30 parce que la route n'a aucun écran. On garde ici S2 : le défaut a
  été laissé ouvert en connaissance de cause à côté de deux frères corrigés, et la liste gelée le donne pour suivi alors qu'aucune
  tâche ne le porte. Le groupe ne peut pas passer « vérifié » sur ce point.

**Tâche :** ACNC57, dans `docs/plans/PLAN_AUDIT_CHANTIERS.md`.

**Autres sondes du dossier PF9, rejouées le 14/11.**
- 004, 005 et 006 (stock) rendent encore « reproduit », mais **ces trois sondes sont périmées** (rectificatif du 14/11 au
  soir). Elles ne rejouent que la fonction d'avant le correctif : la garde de version du bon fournisseur, la clé de rejeu des
  mouvements et la transaction de l'action de masse vivent dans la vue ou dans un mixin qu'elles ne chargent pas. Une copie
  de chacune, adaptée pour passer par le vrai code corrigé, ne reproduit plus ; son témoin sans le correctif reproduit
  toujours. Le code d'ACNC21 à 24 est sur `main` depuis la PR #1395 ; ces tâches attendent leur preuve en direct (§6).
- 001 montre toujours deux paiements pour le même corps envoyé sans clé, ce qui est attendu tant qu'ACNC4 n'est pas construite ;
  sa partie « avec clé » plante sur un bouchon périmé.
- 002 et 008 ne reproduisent plus : ACNC5 et ACNC10 sont livrées.
- 003, 007 et 011 plantent à l'extraction (bouchons périmés) ; 018 ne reproduit plus. ACNC56 exige « avant reproduit, après non »
  pour les sondes S2 : 001, 003, 007 et 011 sont à rafraîchir avant elle.

**Preuve en direct.** Les 12 tâches cochées portent « Preuve en direct : n/a » (API seule, clé absente, garde de dépôt) : aucun
enregistrement n'est dû. Il n'existe aucun enregistrement d'acceptation du groupe.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ACNC-VER1-100 | ACNC30 | S2 | Deux « Annuler » croisés d'une livraison expédiée font deux contre-transferts camionnette → dépôt (`backend/django_core/apps/installations/views/livraison.py::LivraisonViewSet.annuler`) | `docs/audits/sondes/ACNC/C-ACNC-VER1-100.py` (`repro: true`) | ACNC57 |
| C-ACNC-VER1-101 | ACNC30 | S3 | « Expédier » et « Livrer » verrouillés mais sans test de course : un mutant sans verrou reste vert (`backend/django_core/apps/installations/views/livraison.py::LivraisonViewSet.expedier`) | STATIQUE (lecture : seul `executer` a un test à deux connexions) | ACNC58, ACNC59 |
| C-ACNC-VER1-102 | ACNC36 | S3 | Moitié « avoir » sans test de course (`backend/django_core/apps/stock/views/avoir_fournisseur.py::AvoirFournisseurViewSet.perform_destroy`) | STATIQUE (lecture : seul le cas facture a un test à deux connexions) | ACNC60 |
| C-ACNC-VER1-103 | ACNC50 | S3 | 7 clés gelées que la garde ne signale plus, dont `core/payment.py::marquer_paye` ; la garde ne refuse pas une clé périmée, la liste ne décroît pas d'elle-même (`scripts/check_read_modify_write.py::main`) | STATIQUE (garde jouée : 59 clés gelées, 52 signalées) | ACNC61 |

**Pourquoi S3 pour les trois derniers.** Le code est correct à la lecture : ce sont des trous de preuve ou de garde, sans défaut
produit aujourd'hui. Une régression sur ces chemins passerait pourtant la CI, d'où une tâche pour chacun.

**Routage.** Une tâche par propriétaire :
- ACNC57, ACNC58, ACNC59 → chantiers ;
- ACNC60 → stock ;
- ACNC61 → deploy.

« Expédier » et « Livrer » vivent dans des modules de test différents et prouvent deux effets différents (ventilation, notification) :
deux tâches. ACNC58 et ACNC60 ne sont pas regroupées : fichiers et propriétaires différents.

**Réfuté ou requalifié.** Aucun écart n'est réfuté. Les sondes périmées ne sont pas un défaut du produit : §5.

## 5. Optionnel (non déposé)

- Rafraîchir les sondes 001, 003, 007, 011 du dossier PF9 avant ACNC56 ; la sonde 008 cherche la clé de l'écran avec une
  expression trop courte et la croit absente.
- ACNC50 : 28 clés de la liste gelée portent encore « à trier » sans tâche réelle ; `_sain_sous_verrou` accepte un
  `select_for_update` sur n'importe quelle ligne de la fonction.
- ACNC14 : la déduplication est consommée avant le refus d'une facture non encaissable ; une capture refusée ne sera jamais
  rejouée (choix défendable).
- ACNC16 : la déduplication est validée hors transaction ; si l'écriture du journal lève ensuite, le message est perdu au relevé
  suivant.
- ACNC43 : la branche « autre statut » de `rafraichir` écrit encore depuis l'instance non relue.
- ACNC48 : un rejeu ne recalcule plus le lead lié ; si la création du lead du gagnant a échoué, le referral reste orphelin.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 12 tâches cochées : code, commits, tests nommés, jumeaux, gardes jouées ; une sonde neuve sur le S2.
- **Ce qui reste ouvert, et c'est le risque d'argent et de stock du groupe.**
  - **Argent : ACNC4** (second paiement identique sans clé, décision D-ACNC-1 du 13/11 : accepté seulement après
    confirmation). Aucun code n'existe. La sonde 001 montre toujours deux paiements pour le même corps envoyé deux fois.
  - **Stock et achats : ACNC21 à 24** (rectificatif du 14/11 au soir). Leur code est livré (PR #1395) et relu : ACNC21, 22
    et 24 sont conformes, ainsi qu'ACNC28 et 29 ; leurs tests jouent deux gestes et relisent un seul effet. Il leur manque
    la preuve en direct. **ACNC23 est incomplète** : l'écran du grand livre des paiements fournisseur enregistre un règlement
    sans clé de rejeu, donc un nouveau clic après une réponse coupée crée un second règlement (C-ACNC-VER3-100, S1, latent :
    aucune facture fournisseur en production au 11/11 ; tâche ACNC67). Deux écarts S3 au passage : ACNC68 et ACNC69.
  - **Stock : ACNC57**, le S2 nouveau de §3.
  - ACNC28, ACNC29 (S3) ; ACNC56, l'acceptation en direct du groupe, jamais jouée.
- **Non couvert.**
  - Aucun test Django lancé, aucun rejeu en direct ; les tests à deux connexions sont supposés verts par la CI des merges.
  - Les 28 tâches livrées en attente de preuve en direct (ACNC1-3, 5-13, 15, 25-27, 33, 35, 41, 42, 44-47, 49, 52, 53, 55) n'ont
    pas été relues une à une ; leurs rejeux sur un runner sont en cours le 14/11. Toutes les tâches S2 de facturation (ACNC1, 2,
    3, 5, 8, 9) en font partie.
- **Statut.** Un écart S2 nouveau (C-ACNC-VER1-100) : le groupe ne peut pas devenir « vérifié ». Une contre-visite
  des correctifs sera due quand ACNC57-61 seront cochées.

## 7. Coût

- 1 vérificateur (opus, effort élevé) et 1 rédacteur (opus) ; jetons non mesurés ici.
- Aucun appel Fable.

<!-- verifie | groupe: ACNC | pct: 60 | ecarts_s1_s2: 2 -->
