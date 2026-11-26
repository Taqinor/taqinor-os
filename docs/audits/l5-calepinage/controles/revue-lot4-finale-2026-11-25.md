# Relecture finale du lot 4 (PR Taqinor/taqinor-os#1556) — 25/11/2026, 15 h 50 UTC

Relecteur indépendant (n'a rien construit), lecture seule, périmètre : tout ce qui a été ajouté APRÈS la première
relecture (`b51d59a4a8..ce3f0038ee`, backend en entier, fichiers du front listés par l'orchestrateur). Aucun test
joué par le relecteur.

**Verdict : fusionner. Aucun bloquant.** Fusionné le 25/11 à 15 h 56 UTC (`d619459423`).

## Règles vérifiées (toutes tenues)
- `REGLES_COURANTES` inchangé (niveau 14).
- Aucun prix d'achat dans les clés nouvelles (`investissement_ttc`, `cout_onduleur_ttc` viennent des prix de vente,
  arrondis par `quantize_mad`) ; une conception rangée ne les reçoit jamais.
- Société : `apercu-devis` passe par `get_object()` (404 d'une autre société) ; `devis_lu_par_pk` non borné mais son
  seul appelant vérifie la société.
- `_compte_designe` : ne peut ni refuser ni boucler ; la conversion vers une autre puissance rend le même nombre que
  l'ancienne formule.
- Quantités sœurs : suivent seulement un compte de panneaux qui diffère des lignes en base, sur un devis
  résidentiel ; lignes tapées à la main gardées ; lignes composées par le moteur non réécrites.
- Jeton d'édition relu sous verrou ; variables de contexte (`lecture_de_liste`, `temperatures_sans_reseau`) remises
  en `finally`, clés de mémoire distinctes en liste.
- Aperçu à blanc : aucun `save` / `update` / `create` (voir mineur 1).

## Majeur (lot 5)
- **La file « à traiter » omet en silence un bloquant électrique.** Quand la température du site n'est pas dans le
  cache (mémoire du processus, 6 h, 200 entrées, propre à chaque worker), le signal `bloquant_electrique` n'est pas
  émis ; si la ligne n'a aucun autre signal, elle DISPARAÎT de la liste au lieu d'y figurer « non évaluée ». La
  liste diffère d'un worker à l'autre. Correctif : garder la ligne avec son marqueur, ou ranger les températures
  dans un lieu partagé.

## Mineurs (lot 5)
1. `GET apercu-devis` peut créer une ligne `CompanyProfile` / `TariffSettings` pour une société qui n'en a pas
   (`tva_standard` avant la branche `a_blanc`) : envelopper dans `reglages_lus_sans_creer`.
2. L'aperçu « Le devis portera » compose toujours le toit entier à neuf, alors que la génération peut rendre un
   brouillon déjà lié ou ne chiffrer que les surfaces cochées : les deux peuvent différer.
3. Obstacle hors du toit hors de l'empreinte : la géométrie est sûre ; effets de bord — images du document à clé
   d'empreinte restent « à jour » après le déplacement d'un tel obstacle, aucune version enregistrée pour cette
   retouche ; UNE fois après le déploiement, les documents qui portent un tel obstacle voient leur simulation
   « à refaire » et un client tenant l'ancienne empreinte reçoit un 409.
4. `VERSION_MOTEUR` non relevé pour le correctif de `_compte_designe` : une conception rangée avec un hybride
   désigné garde la mauvaise taille jusqu'au prochain changement d'entrée. Note de l'orchestrateur : aucune
   conception n'est rangée en production (les lots 1 à 4 ne sont pas déployés) ; seule la pile de revue en porte.
5. Écran devis, deux aperçus imposés : `reunirOptions` prend le tableau des tailles de l'aperçu « sans » seul ; la
   ligne de la taille « avec » (T4-X4-018) peut manquer.
6. « Nouveau calepinage », recherche après délai dépassé : sans nom tapé, l'écran ouvre le premier calepinage du
   même lead ou client créé dans les 2 minutes — ce peut être celui d'un collègue.

## Non lu par le relecteur
Front hors de la liste donnée (`ventesSlice`, `DevisList`, `ToitureDesign`, étapes de l'atelier, `CarteConception`,
`BoutonDevis`, `ApercuMaterielDevis`, CSS) ; les autres tests (seul `test_x9_009` rapproché de son commit) ; les
contrats au-delà d'un survol ; docs et goldens.
