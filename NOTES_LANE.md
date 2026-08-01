# NOTES — lane `backend/core-calepinage` (Groupe AOF)

Tâches livrées : AOF34 → AOF57, AOF162, AOF183, AOF184, AOF185 (28 tâches).
Le paquet `core/calepinage/` reste PUR (stdlib seule ; le test AST de pureté
d'AOF33 est vert) et s'importe SANS Django : `python -m unittest discover -s
core/tests -p "test_calepinage*.py"` → **483 tests verts, sans base de données**.

## Réconciliation FRDISI : les chiffres RÉELS des scripts témoins

Les scripts témoins de `docs/ao-frdisi/releve-2026-07-27/` ont été rejoués
verbatim (partie comptage seule, sans matplotlib) par
`scripts/reconcilier_calepinage_frdisi.py`, qui refuse d'écrire un golden tant
que le témoin et le moteur neuf ne disent pas le MÊME nombre. Résultat :

| bâtiment | script témoin | compte du témoin | moteur neuf |
|---|---|---|---|
| A — aile en L (polygone) | `vue_bat_A_v2.py` | **148** | **148** ✅ (42/46/8/14/12/8/10/8) |
| B — arc 3 segments | `vue_bat_B_v2.py` | **120** | **120** ✅ (S1 48 · S2 34 · S3 38) |
| C — école (rectangle) | `vue_bat_C.py` | **314** | **314** ✅ (86/86/60/82) |

Corroborations obtenues sans les chercher : l'échelle de l'arc redonne
A = 112, B = 108, C = 100, D = 104, E = 114, F = 120, G = 126, H = 126 ; les
marges de l'arc redonnent 4,15 cm (tronçon) et 4,90 cm (bande) ; la
contre-épreuve de kit redonne S2 paysage 34 contre portrait 24 et S3 paysage 44
contre portrait 42 ; l'arbitrage de GRECT vaut +8 modules et celui de PAN +4,
exactement ce que le docstring du script témoin annonce.

## Divergences assumées avec le TEXTE du plan (et pourquoi)

1. **« L'aile L redonne 178 » (AOF44) / « kits mixtes : 148 → 178, +30 »
   (AOF54).** Le script témoin publie **148** (rangées explicites, kit portrait
   unique) et le DP exact au centimètre, kits mixtes autorisés, allée 0,60,
   rives 0,35, trouve **172** (+24), `optimal=True`. Aucun réglage testé (rive
   de l'aile appliquée ou non, emprises 4,70/2,25 exactes, pas de recherche
   1 cm, contour avec ou sans rive re-entrante) ne produit 178. AOF183 tranche
   explicitement ce cas — « si l'extraction introduit une erreur silencieuse,
   le golden VERROUILLE l'erreur pour toujours » : le témoin fait foi, les
   tests verrouillent 148 (témoin) et 172 (DP mixte), jamais un 178 non
   reproductible.
2. **« 178 / 126 / 314 » (AOF183).** 314 est exact ; 148 remplace 178 (ci-
   dessus) ; **126 est le compte de l'arc SANS les 3 éléments non cotés**
   (marches G et H de l'échelle), le compte RETENU et publié étant 120 — les
   deux sont testés, chacun sous son nom.
3. **« Bâtiment C : allée gratuite de 0,60 à 1,94 »(AOF50).** Le DP tient le
   compte de 314 jusqu'à **2,04 m** (au-delà, la 4ᵉ rangée ne tient plus :
   0,35 + 4×4,70 + 3×2,04 = 25,27 pour 25,62 relevés). La valeur PUBLIABLE
   proposée reste **1,90 m**, obtenue par la règle « borne haute − 10 cm de
   marge de sécurité, arrondie au multiple de 10 cm inférieur » — le chiffre
   du dossier, atteint par une règle explicable au maître d'ouvrage plutôt que
   par un littéral.
4. **Souches écartées du bâtiment C (AOF183).** Les 4 souches provisoires
   figurent au golden en provenance `ECARTE` avec leur motif, mais **avec une
   emprise nulle** : leur géométrie n'a jamais été relevée et le script témoin
   ne la conserve pas. Elles ne sont donc pas absentes (la traçabilité est
   tenue) et aucune géométrie n'a été inventée.

## Correctif porté sur AOF35 pendant AOF44

`obstacles.intervalles_bloques` comparait `o.y1 + c <= y0` SANS tolérance :
`20.35 + 0.30` vaut `20.650000000000002` en binaire, si bien qu'un obstacle
dont le dégagement AFFLEURE une rangée bloquait une bande entière. Coût mesuré
sur l'aile L : 148 → 142 (6 modules perdus, sans qu'aucune cote ne bouge). Le
moteur historique portait déjà ce `1e-9` ; `units.TOL_LONGUEUR_M` le porte
maintenant, des DEUX côtés (compteur et poseur).

## Écarts de contrat mineurs, documentés

* **Repère unifié.** Le plan écrit `bande(x0, largeur) -> (ymin, ymax)`
  (convention de la planche de l'aile L) et `pas_de_pose(kit, y0)` (convention
  de la planche de l'arc) : les deux planches nomment la position de rangée
  avec des lettres OPPOSÉES. Le moteur fixe UNE convention — `x` = abscisse le
  long de la rangée, `y` = coordonnée transversale (celle de `calepinage.py`,
  le moteur historique) — et garde les noms de méthodes du contrat. C'est
  documenté en tête de `surfaces/base.py`.
* **`optimum.optimiser` a gagné un paramètre `positions`** (AOF48) alors que
  `optimum.py` n'est pas dans les `Files:` d'AOF48 : sans lui, le balayage sur
  points de rupture n'a aucun consommateur. Ajout strictement additif, défaut
  inchangé (grille au centimètre), et un test vérifie que les comptes sont
  IDENTIQUES sur les 3 jeux entre les deux chemins.
* **Points de rupture.** Le raccourci n'est adopté que s'il est plus petit que
  la grille : avec deux kits, la fermeture par chaînage coûte plus qu'elle ne
  rapporte, et `perf.positions_utiles` rend alors la grille. Gain mesuré à un
  kit sur l'aile L : 4 639 positions → 591, DP 0,69 s → 0,07 s, compte
  identique.
* **`garde_fous.valider` fait un SAT de TOUTES les paires de tables** (O(n²)).
  Sur un plan réel (~150 tables) c'est quelques dizaines de millisecondes ;
  c'est seulement le fuzz d'AOF185 qui en souffre, d'où ses 120 cas validés sur
  les 500 engendrés (les 500 passent l'invariant compteur == poseur).
