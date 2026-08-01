# NOTES — lane `backend/core-calepinage` (Groupe AOF)

## Réconciliation FRDISI : les chiffres RÉELS des scripts d'origine

Les scripts témoins de `docs/ao-frdisi/releve-2026-07-27/` ont été rejoués
verbatim (partie comptage seule, sans matplotlib) pour ancrer les goldens.
Le moteur neuf redonne leurs comptes AU MODULE PRÈS, rangée par rangée :

| bâtiment | script témoin | compte publié par le script | moteur neuf |
|---|---|---|---|
| C — école (rectangle) | `vue_bat_C.py` | **314** | **314** ✅ (86/86/60/82) |
| A — aile en L (polygone) | `vue_bat_A_v2.py` | **148** | **148** ✅ (42/46/8/14/12/8/10/8) |
| A — sans GRECT (deviné) | idem | 156 (+8) | 156 ✅ |
| A — sans GRECT+PAN | idem | 160 (+12) | 160 ✅ |

**Divergence assumée avec le texte du plan (AOF44/AOF54/AOF183).** Le plan
annonce « l'aile L redonne **178** » et « kits mixtes : 148 → 178 (+30) ».
Le script témoin publie **148** (jeu de rangées explicites, kit portrait
unique) et le DP exact au centimètre du moteur neuf, kits mixtes autorisés,
allée 0,60, rives 0,35, trouve **172** (+24), avec `optimal=True`.
Aucun réglage testé (rive de l'aile appliquée ou non, emprises 4,70/2,25
exactes, pas de recherche 1 cm) ne produit 178. AOF183 tranche explicitement ce
cas : « si l'extraction introduit une erreur silencieuse, le golden VERROUILLE
l'erreur pour toujours » — le témoin fait donc foi, et les tests verrouillent
148 (origine) et 172 (DP mixte), jamais un 178 non reproductible.

## Correctif porté sur AOF35 pendant AOF44

`obstacles.intervalles_bloques` comparait `o.y1 + c <= y0` SANS tolérance :
`20.35 + 0.30` vaut `20.650000000000002` en binaire, si bien qu'un obstacle
dont le dégagement AFFLEURE la rangée bloquait une bande entière. Coût mesuré
sur l'aile L : 148 → 142 (6 modules perdus, sans qu'aucune cote ne bouge). Le
moteur historique portait déjà ce `1e-9` ; `units.TOL_LONGUEUR_M` le porte
maintenant, des deux côtés (compteur ET poseur).
