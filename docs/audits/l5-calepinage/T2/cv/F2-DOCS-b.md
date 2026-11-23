# Contre-vérification — F2-DOCS-b — Documents : planche, rapport d'étude, dossier, exports

16 corrections livrées (seconde moitié de la liste) sans preuve en direct, S1-S2 d'abord. Pour chacune : rejoue la « preuve », regarde l'écran, écris UN verdict (ok / partiel / non-fait / faux / regression / deja-present).
Le texte complet d'une tâche (constat d'origine, Given/When/Then) : `grep -n "<id> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md` dans le worktree en lecture.

- **ACAL592** (S3) — Publier la nomenclature de fixation PAR PAN et l'imprimer en encart sur la feuille A4 du pan ; fini quand, sur un projet à deux pans, la somme des quantités des deux encarts égale la ligne de `bom-fixation/` (unité « m », à 0,01 p
  - Preuve : plan de pose de la démonstration avec un système saisi : l'encart de chaque pan se lit sur sa page A4 ; recompter à la main les pinces d'un pan.
- **ACAL594** (S3) — Créer une variante par module coché du stock sur la même implantation ; fini quand cocher deux modules crée deux variantes nommées par module, l'une valide telle quelle (mêmes cotes) et l'autre marquée « à re-poser » (cotes différ
  - Preuve : `curl` authentifié sur la pile locale : `POST variantes-par-module/` avec deux produits du stock ⇒ `GET variantes/` liste deux variantes nommées par module ; l'écran est celui d'ACAL600.
- **ACAL595** (S3) — Servir le module de chaque variante dans le comparatif (`lignes[].module`) ; fini quand `GET comparer/` donne, pour chaque variante, le module désigné par ses pans (libellé, puissance, cotes) ou « mixte »
  - Preuve : `GET /api/django/calepinage/calepinages/<pk>/comparer/` sur le projet de démonstration après ACAL594 : chaque ligne porte son module ; l'écran est celui d'ACAL600.
- **ACAL596** (S3) — Servir par un sélecteur les points de contrôle de pose d'un calepinage retenu (système de fixation, chaînes dans l'ordre) ; fini quand `points_de_controle_pose(devis_id, company)` d'un projet à 2 chaînes rend 2 lignes de chaîne et
  - Preuve : `python manage.py shell` sur la démonstration : `points_de_controle_pose(<devis>, <société>)` rend les lignes attendues ; leur apparition dans la check-list est la preuve d'ACAL597.
- **ACAL598** (S3) — Ajouter l'échafaudage à la nomenclature de fixation : bases `longueur_egouts_m` et `facade_egouts_m2` lues sur les arêtes d'égout et la hauteur de bâtiment SAISIES, rôle « échafaudage », quantité par la règle de la société ; fini 
  - Preuve : saisir un composant « Échafaudage » dans le système de la démonstration (rôle, unité, règle, source) puis `GET bom-fixation/` : la surface s'affiche ; retirer la hauteur du bâtiment : la ligne dit ce qui manque.
- **ACAL600** (S3) — Ouvrir « Comparer d'autres modules » depuis l'étape Panneaux (niveau expert) : cocher 2 à 3 modules du stock, créer les variantes et ouvrir la comparaison avec une ligne « Module » ; fini quand cocher deux modules mène à la compar
  - Preuve : atelier local en mode expert : étape Panneaux, « Comparer d'autres modules », cocher deux modules, valider : le comparatif s'ouvre avec les deux variantes et la ligne « Module » ; une variante de cotes différentes dit « à re-poser ».
- **ACAL643** (S3) — Dessiner sur le plan de câblage le sens de numérotation des modules de chaque chaîne (flèche et légende) ; fini quand chaque chaîne de plus d'un module du `plan-cablage.pdf` porte sa flèche et la légende « sens de numérotation — l
  - Preuve : pile locale — onglet Documents : télécharger le plan de câblage d'un calepinage à deux chaînes.
- **ACAL672** (S3) — Imprimer sur le plan de câblage, pour chaque chaîne, sa tension à froid avec la température citée et son courant de court-circuit, lus dans la réponse du serveur ; fini quand chaque chaîne du `plan-cablage.pdf` porte « Voc à −5 °C
  - Preuve : pile locale — onglet Documents : télécharger le plan de câblage d'un calepinage à deux chaînes et lire la légende.
- **ACAL673** (S3) — Imprimer sur le plan de câblage la consigne DC de la société (texte saisi une fois dans les réglages, avec sa source), vide ⇒ rien d'imprimé ; fini quand la consigne saisie figure sous la légende du PDF
  - Preuve : pile locale — saisir la consigne dans les réglages société, télécharger le plan de câblage.
- **ACAL674** (S3) — Écrire dans le DXF un bloc `MODULE` défini une fois et inséré par module avec les attributs CHAINE, MPPT, ONDULEUR et N ; fini quand le DXF relu compte autant d'INSERT que de modules posés et que chaque attribut CHAINE égale l'aff
  - Preuve : pile locale — télécharger le DXF d'un calepinage affecté et l'ouvrir dans un lecteur CAO ou ezdxf.
- **ACAL686** (S3) — Faire dire au bandeau du schéma unifilaire sans norme ce qui n'est pas dessiné après l'onduleur (disjoncteur AC, compteur de production, TGBT, compteur du réseau) et quoi renseigner pour l'obtenir ; fini quand le bandeau d'un cale
  - Preuve : pile locale — calepinage sans norme choisie : onglet Schéma unifilaire, lire le bandeau ; avec une norme : bandeau vide.
- **ACAL831** (S3) — Enregistrer le dernier dimensionnement de pompage rendu, pour que le rapport d'étude puisse l'imprimer ; fini quand un POST `pompage/` complet laisse `pompage_dernier` dans le résultat stocké et répond `enregistre: true`, sans rie
  - Preuve : PA2.5 — API : POST du dimensionnement d'essai, puis lecture du résultat stocké.
- **ACAL832** (S3) — Ajouter au rapport d'étude interne la section « Consommation et hypothèses », omise quand aucune consommation n'est servie ; fini quand `rapport-etude.pdf` imprime l'origine de la courbe, le total, les charges ajoutées avec leur m
  - Preuve : PA2.5 — onglet Documents : rapport d'étude PDF d'un calepinage simulé avec consommation, puis d'un autre sans.
- **ACAL833** (S3) — Ajouter au rapport d'étude interne la section « Hors réseau » (défaillance par mois, pire mois, banque), omise pour une installation raccordée ; fini quand le PDF d'un calepinage hors réseau simulé l'imprime et que celui d'un cale
  - Preuve : PA2.5 — rapport PDF d'un calepinage déclaré hors réseau, puis d'un raccordé.
- **ACAL834** (S3) — Ajouter au rapport d'étude interne la section « Pompage » lue sur le dernier dimensionnement enregistré (HMT et composantes, pompe et variateur, volumes par mois, couverture), omise sans dimensionnement ; fini quand le PDF l'impri
  - Preuve : PA2.5 — API : POST `pompage/`, puis rapport PDF.
- **ACAL889** (S3) — Imprimer sur le plan de pose la tension DC maxi à froid de chaque chaîne et, si la société en a saisi une, sa consigne de sécurité ; fini quand le PDF d'exemple porte une ligne par chaîne et cette consigne mot pour mot
  - Preuve : PA2.5 — PDF du plan de pose d'un calepinage chaîné : une ligne de tension par chaîne.
