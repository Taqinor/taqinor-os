# Le moteur de calepinage — contrat, preuve, extension, non-objectifs

> Paquet `backend/django_core/core/calepinage/`. Groupe AOF (`docs/PLAN.md`).
> Compagnon : `docs/ao-fabrique-documentaire.md` (la FABRIQUE — ce qui rend un
> dossier remettable). Ici : le MOTEUR — ce qui calcule.

Le moteur est une **fondation pure** : stdlib + numpy, zéro Django, zéro I/O,
zéro globale mutable. Ce n'est pas une coquetterie d'architecture — c'est ce
qui lui permet d'avoir **deux consommateurs qui ne peuvent pas s'importer l'un
l'autre** (`apps.ao` pour la réponse à appel d'offres, `apps.ventes` pour la
villa) et d'être testé **sans base de données**, donc hors du gate de
migrations. Un contrat import-linter (`calepinage-est-un-noyau-pur`) et un test
AST verrouillent cette pureté ; le sous-paquet `rendu/` est la seule exemption
(matplotlib), et il ne calcule rien.

---

## 1. Le contrat JSON

`core/calepinage/serialisation.py` est la **frontière** entre le moteur et la
persistance. Deux objets sérialisables :

**`EntreeCalepinage`** — `repere`, `surfaces`, `kits`, `parametres`,
`obstacles`, `zones`, `engagements`, `schema_version`.

**`ResultatCalepinage`** — `hash_entree`, `modules`, `kwc`, `rangees`,
`methode`, `optimal`, `version_moteur`, `schema_version`, `plancher`,
`verdict`.

### `hash_entree` ne voit JAMAIS un flottant brut

Le poste de travail est Windows, la CI et la production sont Linux : deux
additions flottantes menées dans un ordre différent donnent `10.760000000000001`
ici et `10.76` là-bas. Un hash calculé dessus ferait croire à **deux relevés
différents pour la même toiture**. Toutes les longueurs sont donc converties en
**entiers de millimètres** avant hachage, les autres nombres arrondis à `1e-6`.

### Tout artefact porte `(hash_entree, version_moteur)`

Deux planches identiques à l'œil peuvent sortir de deux moteurs différents ;
sans ce couple, personne ne sait laquelle fait foi. `version.py` fixe la
sémantique : **MAJEUR** = le contrat change, ou un compte publiable change à
entrée identique (⇒ les études déjà publiées doivent être REJOUÉES avant
d'être re-remises) ; **MINEUR** = capacité ajoutée sans changer un compte ;
**CORRECTIF** = sans effet sur les comptes. `SCHEMA_VERSION` évolue
indépendamment : un moteur peut gagner une capacité sans changer le format
d'échange.

### Repère unifié — une seule convention pour tout le paquet

- `x` : abscisse **le long de la rangée** (sur l'arc : abscisse curviligne du
  bord extérieur) ;
- `y` : coordonnée **transversale**, l'axe sur lequel le DP progresse (sur
  l'arc : ordonnée depuis le bord intérieur).

Les planches d'origine employaient les deux lettres dans les deux sens — l'aile
en L nommait `x` la position de rangée, l'arc la nommait `y`. C'est exactement
la divergence que cette convention supprime.

---

## 2. Les quatre régimes de preuve, et le vocabulaire publiable

C'est le **risque commercial n°1** du produit : l'argument de vente EST la
preuve. Le vocabulaire est donc VERROUILLÉ dans le code
(`types.MethodePreuve`), et la phrase publiée est **générée**, jamais écrite à
la main.

| Régime (`MethodePreuve`) | Exact ? | Ce qu'il autorise à écrire |
|---|---|---|
| `dp_exact_1cm` | oui | « **optimum prouvé** (N modules) » |
| `exhaustif_par_segment` | oui | « **optimum prouvé** (N modules) » |
| `heuristique_bornee` | non | « meilleur plan trouvé (N) — borne supérieure B » |
| `impose_utilisateur` | non | « meilleur plan trouvé (N) — borne supérieure B » |

**Le mot « prouvé » n'est jamais une opinion.** `Preuve.optimal` n'est vrai
qu'à trois conditions cumulées : méthode exacte **ET** `compte_optimal` connu
**ET** `compte_retenu == compte_optimal`. Un plan imposé à la main ressort donc
toujours avec `optimal=False` et son **écart chiffré** face au DP — si
quelqu'un a fait moins bien que le moteur, le dossier le dit.

`nb_plans_optimaux` est plafonné (`CAP_PLANS_OPTIMAUX`) : sur le seul segment
S3 de l'arc, 766 788 jeux de rangées atteignent l'optimum. Au-delà, le nombre
exact n'a plus de sens métier — un optimum calé au millimètre est sans valeur
sur chantier, et c'est `robustesse.py` qui doit ensuite **choisir** parmi eux.

---

## 3. Les deux modes de pose, et pourquoi l'un n'accède jamais à « prouvé »

`Parametres.mode_pose` décide, et `optimum.calculer` est le point d'entrée
unique.

**`rangees_explicites_dp`** — programmation dynamique exacte sur toutes les
positions candidates au pas de recherche (1 cm par défaut), sur TOUS les kits
déclarés. Domaine d'exactitude de référence. `perf.positions_utiles` sait
rendre un jeu de positions **strictement équivalent** et bien plus petit
(points de rupture fermés par chaînage) : les comptes sont identiques, seul le
coût change, et un test le vérifie. Ce mode produit `dp_exact_1cm` — donc
« optimum prouvé ».

**`rangees_uniformes_phase`** — le mode du moteur v1 : rangées à pas constant,
balayage de la phase. Il reproduit la pose réellement réalisable quand
l'installateur impose un pas régulier. Il est **borné par le DP** (le DP lui
fournit sa borne supérieure) mais il n'explore pas l'espace complet : il ne
peut donc pas démontrer qu'aucun meilleur plan n'existe. Il rend
`heuristique_bornee`, et **le mot « prouvé » lui reste inaccessible par
construction** — pas par prudence rédactionnelle, par le code : `optimal`
teste `methode.exacte`.

C'est délibérément asymétrique. Un mode de pose plus simple ne mérite pas un
mot plus fort ; et un dossier qui écrirait « prouvé » sur un balayage de phase
s'effondrerait à la première contre-expertise.

---

## 4. Les défauts de paramètres et leur PROVENANCE

Les valeurs par défaut viennent du jeu de relevé **« FRDISI 2026-07 »** —
la session AO du 27/07/2026, figée dans
`core/calepinage/golden/frdisi_2026_07_27/`.

| Paramètre | Défaut | Provenance |
|---|---|---|
| `allee_m` | 0,60 m | allée de maintenance du chantier FRDISI |
| `rives.laterale_m` / `extremite_m` | 0,35 m | retrait de rive relevé sur site |
| `pas_recherche_m` | 0,01 m | pas de recherche du DP (domaine d'exactitude) |
| `degagement_defaut_m` | 0,30 m | dégagement d'un obstacle MESURÉ |
| `degagement_nature_inconnue_m` | 0,50 m | prix de l'incertitude, pas une punition |
| `marge_troncon_min_m` | 0,02 m | seuil de publiabilité (robustesse) |
| `marge_bande_min_m` | 0,04 m | seuil de publiabilité (robustesse) |
| Kit `AO_PORTRAIT` | 2 × 625 Wc, 1,134 × 4,70, 15° | table réellement approvisionnée |
| Kit villa `VILLA_720` | 1 × 720 Wc, 2,384 × 1,303, 13° | kit villa réellement approvisionné |

**Ce jeu n'est PAS une norme, et ne doit jamais être appelé ainsi.** Aucun
texte normatif marocain n'est présent dans ce dépôt. Ce sont les valeurs d'UN
chantier réel, documentées comme telles, remplaçables par un `PresetCalepinage`
sur n'importe quelle affaire. Les présenter comme une norme à un maître
d'ouvrage serait une affirmation que rien ici ne soutient.

**Règle produit gravée :** ne JAMAIS publier l'allée minimale quand une allée
large est gratuite. Sur le bâtiment C, le compte est identique (314) de 0,60 m
à 1,94 m d'allée : ce sont 1,90 m de maintenance offerts, et les taire serait
laisser de la valeur sur la table (`allee_gratuite.py`).

---

## 5. Brancher une NOUVELLE `Surface`

Le protocole `surfaces/base.Surface` est le seul point d'extension. Une surface
est **immuable**, ne fait **aucune I/O**, ne compte rien et ne pose rien : elle
répond à des questions de géométrie.

1. Sous-classer `Surface` (dataclass `frozen=True`). Les champs communs —
   `repere`, `rives`, `axe_rangee`, `niveau`, `pente_deg`, `azimut_deg`,
   `origine`, `coupures_declarees` — sont déjà mutualisés.
2. Implémenter `bande(y0, emprise)` — l'intervalle `x` posable le plus long.
   Si la forme peut rendre PLUSIEURS intervalles (contour en U, trous), écrire
   aussi `bandes(...)` : un `bande()` scalaire ne saurait pas l'exprimer.
3. Redéfinir `pas_de_pose` et `vers_feuille` **seulement** si la métrique n'est
   pas cartésienne (c'est le cas de l'arc, où `x` est curviligne).
4. Ajouter la sérialisation dans `serialisation.surface_vers_dict` /
   `surface_depuis_dict` — le TYPE est explicite dans le JSON, jamais deviné.
5. Faire passer la **suite de conformité** : les 6 méthodes de
   `CONFORMITE_METHODES` (`axe_progression`, `bande`, `longueur_utile`,
   `pas_de_pose`, `vers_feuille`, `coupures`).
6. Ajouter un golden. Une forme sans jeu figé n'est pas une forme supportée :
   c'est une forme qui marche aujourd'hui.

Rien d'autre ne change : ni le DP, ni le poseur, ni les garde-fous, ni le
rendu. C'est le but du protocole — la forme du toit disparaît du moteur.

---

## 6. Les limites ASSUMÉES de la v1

Ce qui suit sont des **non-objectifs**, pas des oublis. Chacun porte sa raison :
un lecteur doit pouvoir décider s'il veut la lever, pas se demander si on y a
pensé.

- **Pas de simulation d'ombrage bancable.** PVsyst reste l'autorité du secteur
  pour un rapport opposable à un financeur ; refaire un moteur d'ombrage
  crédible est un produit à part entière, et un ombrage « presque bon » sur un
  document bancable est pire que pas d'ombrage du tout. (Cf. la décision
  AOF59.)
- **Pas d'export bancable tant qu'AOF59 n'est pas tranché.** Tant que la
  décision n'est pas prise, produire un export qui RESSEMBLE à un livrable
  bancable créerait exactement l'ambiguïté qu'on veut éviter.
- **Pas de terrain-following DEM/LIDAR.** Le périmètre v1 est la TOITURE, dont
  le plan de pose est plan ou réglé par segments. Suivre un terrain naturel
  est un autre métier (centrales au sol), avec ses propres données d'entrée.
- **Pas d'import/export DWG ni shapefile.** Les portes d'entrée v1 sont le
  plan calibré à 2 points, le tracé au clavier/souris et la reprise de contour
  du lecteur de cartes. Le DXF est `[GATED]` sur une dépendance (`ezdxf`) non
  encore autorisée ; DWG et shapefile n'ont même pas de demande réelle
  derrière eux.
- **Pas de parcellaire cadastral.** Aucune source cadastrale marocaine
  exploitable n'est disponible dans ce dépôt ; brancher une source
  approximative donnerait des limites de propriété fausses sur un document
  remis à un maître d'ouvrage.
- **Pas de vision par ordinateur.** Un obstacle DEVINÉ depuis une photo est
  exactement ce que le modèle de provenance existe pour dévaluer : sur le
  chantier témoin, quatre « souches » avaient été purement inventées faute de
  photo lisible. Automatiser la devinette irait contre la thèse du produit.
- **Pas de routage de câbles.** Le moteur pose des tables et prouve un compte.
  Le cheminement DC/AC dépend d'arbitrages électriques (chutes de tension,
  chemins de câbles, local onduleur) qui ne sont pas de la géométrie de
  toiture.
- **Pas de double courbure ni de rayon variable.** L'arc v1 est à rayon
  CONSTANT, découpé en segments. Une double courbure invaliderait l'hypothèse
  de métrique curviligne 1D sur laquelle repose tout le comptage de l'arc — ce
  n'est pas un paramètre à ajouter, c'est un autre moteur.
- **Pas de génération automatique d'exclusions réglementaires.** *La raison est
  factuelle :* **aucun texte normatif marocain n'est présent dans ce dépôt.**
  Générer des zones d'exclusion « réglementaires » à partir de rien produirait
  des contraintes inventées, présentées avec l'autorité d'une règle. Les zones
  restent DÉCLARÉES par l'utilisateur, avec leur provenance.
- **Pas de montant en lettres en arabe.** Le formalisme bilingue d'un CPS
  marocain est réel et parfaitement possible à implémenter : c'est un
  **non-objectif explicite de la v1**, pas une omission. `core.nombre_lettres`
  couvre le français au style administratif (AOF109) ; l'arabe demande sa
  propre grammaire des nombres et sa propre relecture humaine.

---

## 7. Où regarder ensuite

| Question | Fichier |
|---|---|
| Types, kits, obstacles, paramètres, preuve | `core/calepinage/types.py` |
| Contrat JSON + hash au millimètre | `core/calepinage/serialisation.py` |
| DP exact, plan imposé, borne supérieure | `core/calepinage/optimum.py` |
| Mode uniforme à phase balayée | `core/calepinage/pose_uniforme.py` |
| Politiques de pas (allée fixe / anti-ombrage / affleurant) | `core/calepinage/politique_pas.py` |
| Dégagement dérivé de (type, provenance) | `core/calepinage/obstacles.py` |
| Garde-fous géométriques (chevauchements, marges) | `core/calepinage/garde_fous.py` |
| Étude, variantes, recommandations, sensibilités | `core/calepinage/{etude,recommandations,sensibilites}.py` |
| Adaptateur villa (`AreaRecord` → entrée canonique) | `core/calepinage/adaptateurs/villa.py` |
| Point d'entrée partagé côté ERP (villa, sans projet AO) | `apps/ao/services.calepiner_surface` / `calepiner_villa` |
| Bascule A/B du devis résidentiel (flag `USE_MOTEUR_CALEPINAGE`) | `apps/ventes/services.arbitrer_compte_calepinage` |
| Goldens FRDISI (148 / 120 / 314) | `core/calepinage/golden/frdisi_2026_07_27/` |
| Planches A3, profils interne/dépôt | `core/calepinage/rendu/` |
