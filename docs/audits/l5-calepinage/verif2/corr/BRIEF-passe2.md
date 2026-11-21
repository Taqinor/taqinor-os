# Brief — seconde passe de correction d'un lot (vague 2, campagne L5 calepinage, 21/11/2026)

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.

## La situation
Ton lot a déjà eu une première passe (un vérificateur, puis un correcteur). Depuis : (1) les correcteurs des AUTRES lots
ont laissé des demandes pour tes tâches ; (2) une critique finale a relu toute la vague et trouvé des défauts
transverses. Tu appliques les deux à TON lot. Tu édites du TEXTE de tâches — tu ne construis rien, tu ne touches à
aucun fichier d'un dépôt.

## À lire d'abord
1. Le brief de la première passe (format des blocs, outils de contrôle, règles qui ne bougent pas) :
   `C:\Users\kasri\AppData\Local\Temp\claude\3e013d81c7d3451c\34e718a0-d494-4e8f-b5dd-46bfdf94a28e\scratchpad\l5\corr\BRIEF-correcteur.md`.
2. Ta copie d'ÉDITION, le seul fichier que tu modifies : `…\scratchpad\l5\corr\src-<LOT>.md`. Lis-la EN ENTIER.
3. TOUTES les demandes croisées : les fichiers `…\scratchpad\l5\corr\croises-*.md` (petits ; lis-les tous) —
   applique chaque ligne qui vise une tâche de TON lot.
4. La critique finale : `…\scratchpad\l5\verif2\CRITIQUE-fable-vague2.md` — § 1 (B5 à B8), § 4 (tableau tâche par
   tâche), § 5 (doublons et incohérences), § 7 (simplicité). Applique ce qui vise une tâche de ton lot, SOUS RÉSERVE
   des arbitrages ci-dessous, qui priment.
Code de référence (`main` d'aujourd'hui), lecture seule : `C:\dev\taqinor-os\.claude\worktrees\l5-vague2-integ\`.
Les autres lots à jour, en lecture : `…\scratchpad\l5\corr\src-*.md`.

## Arbitrages de l'orchestrateur (ils PRIMENT sur la critique et sur les demandes croisées)
**Tâches SUPPRIMÉES de la vague** (ne plus les citer ; un renvoi vers l'une d'elles se repointe sur celle qui reste) :
532 → 593 / 599 / 1065 · 644 → 733 · 656 → 658 · 681 → 752 · 682, 683 → 736 · 684 → 737 · 741 (sans remplaçante) ·
766 et 943 (déjà construit) · 881 → 549 · 917 → 607 · 919 → 606 · 920 → 609 · 933 → 602 / 603 · 936 → 687 ·
941 → 770 · 944 → 768 · 953 → 493 · 570 → 567 · 660 → 659, 720, 816 · 1030 → 901.
À supprimer dans cette passe par le lot qui la porte : **924** (doublon de 776 + 777 ; 985 se repointe sur 777).
**Paires réglées autrement que ne le propose la critique** : 733 reste (644 supprimée) ; 752 reste (681 supprimée) ;
687 reste (936 supprimée) ; 934 et 935 restent avec le vocabulaire `etat` / `points`, 611-613 s'y alignent et restent ;
647 et 725 restent deux tâches enchaînées (`@after`), à condition qu'elles n'écrivent pas la même chose — vérifie-le.
**À faire par le lot qui porte la tâche** :
- 771 et 774 : réduire aux refus HORS réglages ; le 409 unique qui liste tous les réglages manquants est à 940.
- 572, 938, 939 : UN seul écran « Lestage » (572) ; réaligner le décompte de paramètres entre 572 et 939 ; 572 fournit
  l'ancre `#lestage` et un id stable par ligne (938 y renvoie).
- 889 : la consigne imprimée est le texte société d'ACAL673 (`@after: ACAL673`), jamais une phrase en dur.
- 548 et 714 (deux seuils d'accès solaire) : UNE règle écrite dans les deux tâches — le réglage société (714) est la
  valeur de départ ; la valeur du document (548), si l'utilisateur l'a changée pour ce dossier, prime et l'écran le dit.
- 547 et 835 (« couvre le besoin ») : un seul calcul, celui du serveur (835) ; 547 affiche la valeur servie ou porte
  le mot « estimation » — même règle que la porte de chiffrage (ACAL993-995).
- 846 et 847 (consommation mesurée contre simulée) : même patron et même emplacement que 886-888 (étape Résultats,
  niveau expert).
- 901 : devient une tâche à DEUX propriétaires. En-tête `## ACAL901 @@ docs/plans/PLAN_AUDIT_TRANSVERSE.md`, tag
  `(@atomique: calepinage, devis)` (forme exacte : relis `docs/audits/METHODE.md` § C.5 et un exemple dans
  `docs/plans/PLAN_AUDIT_TRANSVERSE.md` du code de référence), et elle reprend dans ses `Files:` et ses tests le
  réalignement de `apps/ventes/tests/test_selectors_surface.py` que portait 1030.
- 911 et 921 : même cas (un test de `apps/ventes/tests/` appartenant au propriétaire « devis » casse dans le même
  commit) → tâche atomique au plan transverse, mêmes règles ; 922 : la clé `motif_code` de `ventes/selectors.py` est
  une vraie moitié « devis » à livrer AVANT — écris-la comme tâche neuve `@@ docs/plans/PLAN_AUDIT_DEVIS.md` (id pris
  dans ta plage libre) et pose `(@after: <elle>)` sur 922. 921 reçoit aussi la demande de `croises-D8.md` si elle existe.
- 914 : retirer `BoutonDevis.test.jsx` de ses `Files:` (l'assertion d'écran va à 915 / 923).
- 978 : retirer ACAL884 de ses `@after`.
- 1031 (acceptation) : sa liste d'ids couverts suit les suppressions, scissions et créations (l'orchestrateur la
  régénère : n'y passe pas de temps).

## Règles transverses à appliquer à CHAQUE tâche de ton lot
**R1 — Dépendances.** Toute dépendance réelle est un `(@after: ACALnnn)`, même vers une tâche d'un AUTRE plan (le
planificateur le respecte : `scripts/plan_lanes.py::apply_external_after_gate`). Une phrase « s'appuie sur ACALnnn »,
« ordre : après ACALnnn », « à partir dans le même merge » sans le tag ne suffit pas : ajoute le tag, garde la phrase.
Exception : jamais d'`@after` vers une tâche supprimée ni vers une tâche déjà cochée sur main. La critique § 1-B7
liste des arêtes ; vérifie aussi les tiennes.
**R2 — Migration.** La tâche qui ajoute un champ de modèle porte SA migration dans ses `Files:` (les dossiers
`apps/*/migrations/` sont des surfaces « append-only » : toute tâche peut y déclarer un fichier), nom
`0NNN_<sujet>.py` avec la mention « numéro de migration à relire sur origin/main à la construction ». Concerne 567,
659, 720, 816 (colonnes exactes dans `croises-AUTRES-PLANS.md`) : retire toute phrase « la migration est chez
ACAL570 / ACAL660 », et rétablis `makemigrations --check` vert dans leur preuve.
**R3 — `selectors.py` et `urls.py`.** Ne jamais déclarer `apps/calepinage/urls.py` (une route s'attache par
`views/rattachements.py`). Une fonction de lecture NEUVE pour une autre app ne va pas dans
`apps/calepinage/selectors.py` mais dans un module frère : `selectors_chantier.py` (588, 596, 665),
`selectors_devis.py` (997), module frère + route par `rattachements.py` (960), route par `rattachements.py` (558),
gardes chez les appelants (1008). Seules NEUF tâches gardent `apps/calepinage/selectors.py` dans `Files:` parce
qu'elles modifient une fonction qui y existe : 572, 595, 770, 883, 895, 948, 961, 964, 978 — elles forment la
« vague 0 », construite d'abord. Aucune de ces neuf ne doit porter d'`@after` vers une tâche d'écran pur. Pour 557 et
614 (contrats posés seuls qui déclarent `frontend/src/api/calepinageApi.js`) : lis
`scripts/check_contrats_calepinage_deux_moities.py` et dis ce que la garde exige vraiment ; si la citation côté
client n'est pas exigée dans le même commit, retire `calepinageApi.js` de leurs `Files:` (la ligne va à la tâche
d'écran) ; si elle l'est, garde-la et écris-le dans ton compte rendu.
**R4 — Fichiers de 2 000 lignes ou plus** (garde `scripts/forme_code/fichier_mur.py`, jouée à la construction : un tel
fichier ne grossit pas, sauf budget écrit). Liste des fichiers concernés que la vague déclare :
`…\scratchpad\l5\corr\_fichiers_murs.txt` (lignes « taille chemin »). Toute tâche qui déclare l'un d'eux écrit dans sa
clause « Code net » la phrase EXACTE « lignes nettes attendues ≤ N » en citant le chemin COMPLET entre backticks, avec
un N honnête ; si elle doit y ajouter du code, elle dit d'abord quel bloc elle en extrait, vers quel module voisin
(extraction ≥ ajout). Une seule occurrence de la phrase par tâche (seule la première est lue).
**R5 — Compteurs figés.** Un total qu'un test fige et que plusieurs tâches font bouger (`ORDRE_ETAPES`, nombre de
clés du profil de départ, `NOMBRE_CLES_EXTRAITES`, nombre d'onglets de `Rail.test.jsx`, `len(tables)`…) s'écrit
« valeur relue à la construction + n », jamais un total absolu.
**R6 — Simplicité (demande centrale du fondateur : « extremely simple »).** Toute tâche qui déclare un fichier d'écran
(`frontend/src/**`, `apps/web/src/**`) dit dans sa clause « Emplacement » :
« Simplicité : étape <Toit | Panneaux | Électrique | Résultats | Documents | Réglages | Liste | hors atelier>, niveau
<essentiel | expert> ; premier écran : +0 | +N | −N ». Règle de rangement : une capacité NOUVELLE va au niveau expert,
ou derrière un contrôle qui existe déjà (+0) ; seule une tâche qui corrige un défaut constaté par un relecteur (elle
cite un constat `T1-…`) ou qui remplace un contrôle existant peut toucher le niveau essentiel. Une tâche qui garde
« +N » au premier écran de l'atelier déclare `frontend/e2e/calepinage-mesures-ecran.baseline.json` dans ses `Files:`
et dit qu'elle relève la base de N dans le même commit. Relis dans le code où l'élément se monte vraiment
(`parcoursGuide.js`, `Rail.jsx`, `atelier/onglets.js`) avant d'écrire l'étape ; une tâche qui touche
`atelier/onglets.js` dit si elle AJOUTE une entrée et sous quelle étape. Libellé unique du bouton : « Générer le devis ».
**R7 — Rien d'autre ne change.** Une tâche que rien de ce qui précède ne vise reste telle quelle. Sur une tâche
modifiée : mention `STATIQUE (lecture du 21/11 sur 684d77f02)` et tampon `(gen manuel 684d77f)`.

## Contrôle avant de rendre
Les deux commandes du brief de première passe, avec ton `<LOT>` : aucune « ALERTE », puis « 0 en echec » (exception
admise : lignes « proprietaire de … » pour une tâche rangée dans un plan autre que calepinage, après vérification
`python scripts/check_ownership.py --owner-of <chemin>` depuis le code de référence).

## Compte rendu (25 lignes au plus)
Par règle (arbitrages, R1 à R6) : les ids touchés, une proposition chacun. Tâches supprimées ou créées. Demandes
croisées NON appliquées et pourquoi. Pour R6 : combien de tâches d'écran dans ton lot, combien au niveau essentiel,
somme des « +N » du premier écran. Ce que tu n'as pas vérifié. Dernière ligne du validateur.
