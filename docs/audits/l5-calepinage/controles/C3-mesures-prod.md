# C3 — Mesures en lecture seule sur la production (23/11/2026, 12 h 40 UTC)

Deux scripts `manage.py shell` en transaction annulée, des comptes et des identifiants seulement (aucun nom, aucune
coordonnée). Fonctions du code servi appelées telles quelles : `crm/devis_auto.py::champs_manquants_detail`,
`ventes/domain/entrees.py::entrees_depuis_lead`, `parametres/pvgis_profils.py::productible_mensuel`,
`ventes/services::cible_depuis_lignes`. Rien n'a été écrit.

## 1. « Mes devis se calculent-ils seuls avec la facture et un profil ? »

| Marché | Leads | Avec une facture ou des kWh | Prêts pour le devis automatique | S'arrêtent sur |
|---|---|---|---|---|
| Résidentiel | 1 065 | 478 | 477 selon la garde du CRM ; **448 que le moteur sait situer** | 29 sur la ville (18 hors « Froid ») ; 587 n'ont pas de facture |
| Commercial | 80 | 42 | **4** | contrat d'électricité 38 · jours d'ouverture 37 · phase (raccordement) 35 |
| Industriel | 1 | 1 | 1 | — |
| Agricole | 2 | 2 | 2 | — |

- Résidentiel : 94 % des leads qui ont une facture aboutissent. Les 29 arrêts viennent de la ville telle qu'elle est
  tapée : « casa » (5), « casablaca », « caaza », « kech », des noms en arabe (فاس, طنجة, سيدي بنور…), « maroc »,
  un quartier (« ain sbaa », « harhoura »), une ville hors du Maroc. La garde du CRM les dit « prêts », le moteur
  refuse ensuite. Sur 1 065 leads, 984 n'ont pas de présence en journée déclarée : le calcul suppose « présent ».
- Commercial : 38 des 42 leads qui ont une facture ne passent pas. 76 leads sur 80 n'ont pas de contrat déclaré, 78
  n'ont pas de catégorie commerciale, 75 pas de jours d'ouverture, 71 pas de phase. C'est ici que « la facture et un
  profil suffisent » n'est pas vrai aujourd'hui (questions Q1 à Q3 de C2).

## 2. Calepinages et devis

- 11 calepinages en production, dont 5 liés à un devis (4 à un brouillon, 1 à un devis envoyé).
- 1 est lié à un autre devis que le dernier envoyé du lead : le calepinage 9 (brouillon 554, envoyé 564).
- 3 sur 5 portent un nombre de panneaux différent de l'option recommandée du devis :
  calepinage 9 (48 posés ; 35 sans batterie, 48 avec ; recommandée : sans), calepinage 7 (6 posés ; 8 et 8),
  calepinage 6 (8 posés ; 8 sans, 14 avec ; recommandée : avec).
- 5 sur 5 n'ont aucune simulation de production. 1 a une désignation d'onduleur saisie à la main (le 9).
- 1 porte un écart de longueur de chaîne contre la constante 16 du dossier d'appel d'offres (le 9).

## 3. Non mesuré

Le devis automatique ne laisse pas de trace lisible dans `etude_params` (clé `journal_auto` absente des 539 devis) :
impossible de dire combien de devis sont sortis du bouton et combien ont été composés à la main.
