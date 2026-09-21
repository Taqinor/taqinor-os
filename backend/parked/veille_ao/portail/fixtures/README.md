# Fixtures HTML du portail — provenance, sans détour

Ces fichiers rendent **tout le collecteur testable sans réseau et sans base**
(VAO15) : les tests du groupe VAO15–VAO20 ne parlent qu'à eux.

## ⚠ Ce que ces fichiers SONT — et ce qu'ils NE SONT PAS

**Ce ne sont pas des captures octet-pour-octet du portail.** Ce sont des
**reconstructions** des ancres HTML relevées en main, écrites le **2026-08-26**.

| | |
|---|---|
| **Structure d'origine** | relevée en main le **2026-08-01** sur `https://www.marchespublics.gov.ma/index.php?page=entreprise.EntrepriseAdvancedSearch&AllCons&EnCours&searchAnnCons&keyWord=solaire` |
| **Relevé consigné dans** | `tos_risk/marchespublics_gov_ma.md` et `docs/PLAN2.md` (VAO16, VAO17, VAO18) |
| **Ce qui est fidèle** | les ancres : `span#ctl0_CONTENU_PAGE_resultSearch_nombreElement`, le champ caché `PRADO_PAGESTATE` échappé en HTML, `select[name="ctl0$CONTENU_PAGE$resultSearch$listePageSizeTop"]`, `input[name="…$numPageTop"]`, `span.ref`, `<strong> Objet : </strong>`, `Acheteur public :`, la date de publication en `<div>jj/mm/aaaa</div>` sous l'en-tête « Publié le », la date limite `jj/mm/aaaa hh:mm`, l'URL de détail `…EntrepriseDetailConsultation&refConsultation=<n>&orgAcronyme=<code>` |
| **Ce qui est synthétique** | **toutes les valeurs métier** : acheteurs (« Commune de Test-Sud », « Province d'Essai-Nord »…), objets (suffixés « dossier d'essai »), références, montants, tailles de DCE. Aucune donnée réelle d'un acheteur public n'est reproduite ici. |
| **Le `PRADO_PAGESTATE`** | **tronqué**. Le vrai pèse ~87 Ko de base64 ; on en garde une tranche courte, avec les mêmes entités HTML (`&#43;`, `&amp;`) — c'est ce qui rend le déséchappement testable. La taille réelle est une propriété du portail, pas du parseur. |

## Pourquoi une reconstruction et pas une capture

Parce que **capturer, c'est exécuter**. La règle #5 du dépôt exige l'accord
manuel et daté du fondateur avant la première exécution du collecteur, et la
ligne « Founder approval » de `tos_risk/marchespublics_gov_ma.md` est **VIDE**.
Écrire le code est autorisé ; aller chercher les pages ne l'est pas encore
(c'est la tâche VAO4, un acte du fondateur).

**Le jour où la collecte est armée**, remplacer ces fichiers par de vraies
captures est un geste d'une minute : garder les **mêmes noms**, relancer les
tests, ajuster les valeurs figées. Les tests figent volontairement des
**ancres** (le nombre de lignes, la présence du compteur, la forme de l'URL de
détail) et un petit nombre de valeurs de la première ligne — pas 34 lignes de
données métier, qui seraient à réécrire à chaque capture.

## Les fichiers

| Fichier | Ce qu'il représente | Sert à |
|---|---|---|
| `resultats_solaire_10.html` | réponse **GET** `keyWord=solaire` : le portail annonce **34** consultations et n'en affiche que **10** (plafond d'affichage) | étape 1 du client (VAO16), parseur de ligne (VAO17) |
| `resultats_solaire_500.html` | réponse **POST** `listePageSizeTop=500` : les **34** lignes en une seule réponse | étape 2 du client (VAO16), volumétrie du parseur (VAO17) |
| `resultats_vide.html` | recherche sans résultat : compteur à **0**, aucune ligne | « collecte réussie, 0 nouveauté » (VAO20) — le cas NORMAL, jamais une erreur |
| `resultats_incoherent.html` | annonce **34**, ne sert que **3** lignes | contrôle croisé lignes/total → **anomalie** (VAO20) |
| `resultats_derive.html` | 200 OK, mais plus de compteur ni de table de résultats | dérive du HTML tiers → **erreur nommée**, jamais un tableau vide (VAO20) |
| `erreur_403.html` | refus du pare-feu, avec identifiant de refus | **arrêt définitif** du client, sans repli sur un UA de navigateur (VAO16/VAO19) |
| `detail_consultation.html` | page de détail d'un avis : estimation MAD TTC, caution, 2 lots, marqueur PME, lien DCE + taille | enrichissement à la demande (VAO18) |

Chaque fichier porte en tête un bandeau HTML rappelant sa nature reconstruite —
pour qu'un lecteur qui ouvre le fichier seul, sans ce README, ne s'y trompe pas.
