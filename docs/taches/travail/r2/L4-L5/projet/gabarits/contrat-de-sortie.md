# Contrat de sortie — <périmètre> (go-deep L4 / L5, écrit au tour 0, AVANT tout relecteur)

Règle : une cible qui n'est pas dans ce fichier ne bloque jamais le merge plus tard ; une cible qui y est se mesure
à chaque tour et se lit dans le registre. On peut RESSERRER un seuil en cours de route (une ligne au journal, avec la
raison) ; jamais le relâcher pour sortir (si un seuil se révèle faux, le dire au rapport et le laisser rouge).

En-tête
- Demande, mot pour mot : « <…> »
- Régime : <NEUF | EXISTANT | MIXTE>, lu sur `origin/main@<sha9>` ; niveau : <L4 | L5>
- Écrans / parcours dans le périmètre (liste fermée) : <écran 1>, <écran 2>, … ; écrans CENTRAUX : <deux au plus>
- Hors périmètre (signalé, jamais touché) : <…>
- Références nommées pour la comparaison : <produit 1>, <produit 2>, <maquette> (une par axe au moins)
- Appareils et vues : <iPhone 390×844 tactile ×2 | bureau 1440×900> × <clair | sombre>

## 1. Critères (identifiants fixes `K<n>` : le registre les cite)
| id | Axe | Critère | Seuil de sortie | Mesure (qui, comment) |
|---|---|---|---|---|
| K1 | tous | constats A ouverts | 0 | registre : A au verdict `retenu` sans contre-vérification `ok` |
| K2 | tous | constats B ouverts par écran | ≤ <n> par écran (fixé ici) | registre |
| K3 | tous | corrections contre-vérifiées par un NEUF | ≥ <85-90> % `ok`, 0 `régression` | registre, étape `contre-verification` |
| K4 | tous | rendement du tour par relecteur | ≤ 1/3 de celui du tour 1 (proposition, sans source externe) | registre : constats retenus / relecteur / tour |
| K5 | fonction | parcours critiques rejoués de bout en bout sur l'instrument | 100 % verts ; en L5 : k = 3 essais tous verts | specs e2e contre le build assemblé |
| K6 | simplicité | budget de gestes par tâche courante | <tâche> ≤ <n> gestes | relecteur, gestes comptés dans le constat |
| K7 | beauté | mesures DOM fixées ici | ex. 1re ligne utile à ≤ <n> pt ; ≤ <n> tailles de texte par écran ; cibles ≥ 44 px | script de mesure sur l'instrument (même script à chaque tour) |
| K8 | beauté | jugement PAR PAIRES contre la référence nommée | ≥ <n> paires sur <m> préférées ou à égalité (seuil choisi ici : aucune source n'en donne) | 2 relecteurs aveugles en L5 (accord rapporté) ; 1 en L4 |
| K9 | accessibilité | violations automatiques | 0, avec la version d'axe de la CI (pas celle du poste) | spec a11y ; liste manuelle clavier / zoom |
| K10 | données | chiffres servis (EXISTANT) | goldens inchangés sauf correction voulue, nommée | goldens enregistrés sur le commit intact |
| K11 | serveur | critique adverse du diff | 0 bloquant (sécurité, isolation société / compte, perte de données) | une critique neuve par tour fusionné |
| K12 | L5 | reste estimé A + B (Chapman, fourchette, « borne basse ») | ≤ <n> ; jamais décidé sur l'estimation seule | 2 relecteurs sur la même strate (écrans centraux) |
| K… | <axe> | <critère propre au périmètre> | <seuil> | <mesure> |

Un critère sans mesure exécutable n'est pas un critère : le réécrire ou le retirer avant le tour 1.

## 2. Plafonds (l'arrêt est mécanique)
- Tours : <k> (≤ 3 en L4) + le dernier tour « avant le merge » ; k = floor((90 − u − 5) / 25), u = quota hebdomadaire
  utilisé au départ (<u> %) ; k = 0 → tour 0 seulement.
- Quota : pas de nouveau tour à partir de 65 % ; à 90 % : committer, pousser, écrire l'état, s'arrêter.
- Disjoncteur par constat : 3 tentatives au plus (2 par sa lane, 1 par un correcteur neuf d'un cran au-dessus).
- Arrêt : le PREMIER de « K1-K<n> tous atteints », « plafond de tours », « plafond de quota ». « Sec » = deux relecteurs
  DIFFÉRENTS sur le même périmètre sans nouveau A.

## 3. Décisions de produit (régime NEUF / MIXTE sans consigne « aucune question » : le lot posé à Reda)
| # | Question | Recommandation | Autres options | Réponse | Coût si faux |
|---|---|---|---|---|---|

## 4. Journal du contrat (ajout seulement)
- <date> — <seuil resserré / critère ajouté> — <raison>
