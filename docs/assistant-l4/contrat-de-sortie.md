# Contrat de sortie — l'assistant IA connaît tout l'ERP (go-deep L4, écrit au tour 0, AVANT tout relecteur)

Règle : une cible absente de ce fichier ne bloque jamais le merge ; une cible présente se mesure à chaque tour. Un seuil
se resserre (ligne au journal), jamais ne se relâche pour sortir. Seuils = valeurs de départ, non calibrées.

En-tête
- Demande, mot pour mot : « i think you can do much more for the AI agent making fully understand the ERP and even if
  the ERP changes in the future, some file like codemap should make the ai agent always aware. i want you to go l4 in
  letting the ai agent fully understand erp and help me use it. dont forget every one get what he already have access
  to so meriem cant see for example buying prices or margin using ai agent »
- Régime : EXISTANT (l'assistant existe : registre d'actions, manuel, copilote, D-COP-5), lu sur `origin/main@d145aa887`
  + PR #1513 (en file) ; niveau : L4.
- Parcours dans le périmètre (liste fermée) : questions sur l'ERP (où, comment, pourquoi) ; questions sur ses données
  (combien, qui, quel devis) ; gestes demandés à l'assistant (D-COP-5) ; confidentialité par rôle ; mise à jour de la
  connaissance quand l'ERP change. Écrans CENTRAUX : le tiroir Copilote et la page `/ia/agent`.
- Hors périmètre : refonte visuelle des écrans métier ; le site public ; tout déploiement.
- Références nommées : le manuel actuel (`backend/fastapi_ia/assistant/manuel.md`), CODEMAP §4/§5 (modèle de « carte
  toujours à jour »), le comportement observé dans les essais réels du 21/11 (PR #1513).
- Rôles joués : Commercial (sans `prix_achat_voir`), Commercial responsable (sans), Directeur (avec) ; en prod le
  21/11 : Meryem = Commercial responsable, Asmaa / Imane = Commercial, Reda / Moumna = Directeur.

## 1. Critères
| id | Axe | Critère | Seuil de sortie | Mesure |
|---|---|---|---|---|
| K1 | tous | constats S1-S2 ouverts | 0 | registre |
| K2 | tous | constats S3 ouverts | ≤ 5 | registre |
| K3 | tous | corrections contre-vérifiées par un relecteur NEUF | ≥ 85 % `ok`, 0 `regression` | registre |
| K11 | serveur | critique adverse du diff (isolation société / rôle, fuite de coût) | 0 bloquant | critique par vague + finale |
| KA | connaissance | couverture de la carte de l'ERP générée : chaque route d'écran du routeur, chaque action du registre, chaque permission de la grille y figure | 100 % | script `--check` en CI (rouge sur l'écart) |
| KB | fraîcheur | ajouter une route, une action ou une permission sans régénérer la carte rend la CI ROUGE | prouvé rouge sur un cas fabriqué, puis vert après régénération | test du script de garde |
| KC | réponses | banque de questions réelles par module et par rôle (≥ 60), rejouée avec le vrai modèle | ≥ 90 % justes (juge neuf), 0 chiffre inventé, 0 « je ne sais pas » quand la carte a la réponse | rejeu sur runner, transcript + verdicts au registre |
| KD | confidentialité | attaques par rôle sans `prix_achat_voir` (≥ 20 : demande directe, détour SQL, calcul de marge depuis deux prix, outil catalogue, devis, PDF, manuel, mémoire de conversation, texte collé) | 0 fuite de prix d'achat, marge, coût interne | rejeu sur runner, comptes Commercial et Commercial responsable |
| KE | droits | le rôle qui a le droit obtient la donnée (pas de sur-blocage) | Directeur : prix d'achat et marge obtenus en interne, jamais dans un texte client | même rejeu, compte Directeur |
| KF | gestes | D-COP-5 tenu : actions directes sans carte, cartes gardées là où la décision le dit | 0 écart | rejeu (bilan des propositions) |

## 2. Plafonds
- k = min(3, floor((90 − u − 10) / c)), c = 21 au départ. Au tour 0 : u = 91 % (« Weekly · all models », lu le
  21/11 vers 04:36 UTC) → k ≤ 0 : **tour 0 seulement**, reprise après la remise à zéro (21/11 11:00 UTC).
- Vérification finale (relecteur ciblé + critique du diff serveur) : réserve à part, jouée avant le dernier merge.
- Disjoncteur par constat : 3 tentatives.

## 3. Décisions de produit
Régime EXISTANT : aucune question posée. Choix pris seuls (réversibles, jamais enregistrés comme décision de Reda) :
- La « carte de l'ERP » est GÉNÉRÉE par un script déterministe (sans modèle) depuis le code, comme CODEMAP ; le manuel
  écrit par le skill reste pour les procédures. Coût si faux : un fichier de plus à régénérer.
- Un rôle avec `prix_achat_voir` obtient prix d'achat et marge EN INTERNE (décision de Reda du 19/11) ; la consigne
  actuelle « Jamais de prix d'achat ni de marge » pour tous est à aligner sur cette décision.

## 4. Journal du contrat
- 21/11 — écrit au tour 0.
