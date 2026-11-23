# Contre-vérification — F2-GESTES-b — Gestes de l'atelier, devis, moteur partagé (corrections du tour 1)

17 corrections livrées (seconde moitié de la liste) sans preuve en direct, S1-S2 d'abord. Pour chacune : rejoue la « preuve », regarde l'écran, écris UN verdict (ok / partiel / non-fait / faux / regression / deja-present).
Le texte complet d'une tâche (constat d'origine, Given/When/Then) : `grep -n "<id> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md` dans le worktree en lecture.

- **ACAL956** (S2) — Cadrer le toit à la fermeture du contour : la caméra prend le zoom qui montre le contour entier, à 58° comme aujourd'hui ; fini quand `go3DView` pose le zoom de `zoomToFitRing` et plus seulement un tangage
  - Preuve : rejouer T1-F1-003 : contour rectangulaire, « Terminer le tracé » : le toit entier est dans le cadre sans toucher la boussole.
  - Écran : étape Toit, essentiel, `docs/audits/l5-calepinage/maquettes/Main.dc.html`.
- **ACAL987** (S2) — Faire échouer la CI dès qu'un écran produit une erreur sans geste de l'utilisateur ou un retour faux ; fini quand l'ouverture de chaque onglet de l'atelier ne déclenche aucune requête 4xx/5xx ni `console.error`, et qu'un calepinag
  - Preuve : la spec est elle-même la preuve en direct (pile locale) ; l'orchestrateur la joue.
- **ACAL993** (S2) — Servir dans le `design-context` du calepinage un bloc `chiffrage` (kWc, production année 1, économie année 1 et son option, chacun `{valeur, unite, source, etat}`) lu par `apps.ventes.services.chiffrer_conception`, calculé à l'ouv
  - Preuve : pile de revue, lead REV-COUTURE — ouvrir l'atelier, lire le bloc dans la réponse réseau.
- **ACAL994** (S2) — Faire afficher par l'atelier ERP la production et l'économie SERVIES par le bloc `chiffrage` (à l'ouverture et après « Enregistrer »), et marquer « estimation » toute valeur encore calculée dans le navigateur ; fini quand, chiffra
  - Preuve : pile de revue, maquette `docs/audits/l5-calepinage/maquettes/Resultats.dc.html` (chiffre héros) — atelier ouvert, carte = Total = valeur servie.
- **ACAL1315** (S2) — Faire de la comparaison aux maquettes un contrôle permanent : une spec qui rend chacune des 13 maquettes en `file://` et l'écran réel à la même taille, range les paires d'images et échoue si un libellé fixe d'une maquette manque à
  - Preuve : PA2.3 — spec rejouée sur la pile par l'orchestrateur, paires rangées, verdict d'un relecteur neuf par paire reporté dans l'enregistrement `docs/audits/acceptation/ACAL/<date>-<sha9>.md`.
- **ACAL384** (S3) — Poser la base visuelle du module Calepinage (liste, atelier — rail et étape toit, onglets Production et Documents), clair et sombre, dans une spec `@visual` du module ; fini quand chaque écran a sa capture de référence et que la s
  - Preuve : `npx playwright test calepinage-visuel.spec.js --update-snapshots` sur la pile locale, images relues par l'orchestrateur à ACAL490.
- **ACAL478** (S3) — Verrouiller le « budget de simplicité » du mode guidé : la spec de mesures échoue si le mode guidé dépasse 5 étapes, le nombre de contrôles du premier écran relevé, ou demande une saisie technique avant un premier résultat ; fini 
  - Preuve : relevé sur la pile locale à ACAL490, section committée avec sa date.
- **ACAL958** (S3) — Montrer la fenêtre « Déplacer les panneaux » dès que le toit est fermé dans l'atelier ERP : `syncProductionWindow` rend aussi le panneau de disposition sans fenêtre de production ; fini quand le toit fermé affiche la fenêtre sans 
  - Preuve : rejouer T1-T1-027 : toit fermé (72 panneaux) puis « Toit en pente » : la fenêtre « Déplacer les panneaux » est visible sans enregistrer ni recharger.
  - Écran : étape Panneaux, expert, `docs/audits/l5-calepinage/maquettes/Panneaux.dc.html`.
- **ACAL962** (S3) — Dire sans clé technique pourquoi l'allée de circulation est refusée et transmettre le pays réglé de la société ; fini quand le refus d'un site sans pays dit « le pays du site n'est pas réglé » et qu'un site au pays réglé n'est plu
  - Preuve : PA2.5 — société au pays « ma », allée sans largeur : aucune clé ni « ? » ; société sans pays : la phrase demande de le régler (rejoué par l'orchestrateur).
- **ACAL965** (S3) — Dire une seule fois que la cible de puissance n'est pas calculée, avec un lien vers la fiche du lead ; fini quand l'atelier d'un lead sans facture ne répète plus le refus et offre « Ouvrir la fiche du lead »
  - Preuve : PA2.5 — lead REV-S1 sans facture : une seule phrase de refus, le lien ouvre la fiche du lead (rejoué par l'orchestrateur).
- **ACAL972** (S3) — Masquer l'épingle du lead dessinée par-dessus les panneaux dès que le toit est fermé ; fini quand le marqueur n'est plus visible après la fermeture du contour et revient quand on efface le tracé
  - Preuve : PA2.5 — lead REV-S1 avec épingle seule : tracer et fermer le toit en vue 3D inclinée : plus d'épingle sur les panneaux ; « Effacer » la ramène (rejoué par l'orchestrateur).
- **ACAL975** (S3) — Ne plus proposer de gain bifacial pour une pose affleurante ; fini quand la carte d'un toit en pente n'écrit plus « + gain bifacial » et que celle d'un toit plat le garde
  - Preuve : PA2.5 — toit en pente, pose affleurante : la carte Recommandation n'écrit plus de gain bifacial (rejoué par l'orchestrateur).
- **ACAL981** (S3) — Nommer « Bâtiment 1 » le bâtiment sans identifiant et ne plus écrire « contour du pan non tracé » quand le toit est fermé ; fini quand le tableau des pans d'un toit tout juste fermé n'a ni « Bâtiment sans id » ni ce motif
  - Preuve : PA2.5 — tracer et fermer un toit : le tableau dit « Bâtiment 1 » et aucun message de contour non tracé (rejoué par l'orchestrateur).
- **ACAL1006** (S3) — Marquer `rapide` le calepinage créé ou adopté à l'ouverture d'un devis automatique jamais dessiné, et le passer `complet` au premier enregistrement du document par une personne ; fini quand l'adoption d'un devis marqué « rapide » 
  - Preuve : pile de revue — « Devis automatique » depuis la fiche d'un lead puis « Concevoir la toiture » : la fiche du calepinage dit « rapide ».
- **ACAL1007** (S3) — Afficher dans l'atelier, sur un calepinage `rapide`, le bandeau « Conception rapide — à vérifier sur place » avec le bouton « J'ai vérifié le toit » qui enregistre ; fini quand l'atelier ouvert sur un calepinage rapide montre le b
  - Preuve : pile de revue, maquette `docs/audits/l5-calepinage/maquettes/Main.dc.html` (bandeau au-dessus du plan) — calepinage rapide ouvert, vérifié, rouvert.
- **ACAL1028** (S3) — Montrer, sur l'onglet Schéma unifilaire quand la fiche technique est incomplète, un croquis de principe grisé au-dessus de la liste des champs manquants ; fini quand le croquis apparaît avec la mention « Croquis de principe, sans 
  - Preuve : rejeu de T1-B1-016 : ouvrir le Schéma unifilaire d'un calepinage à fiche incomplète (croquis grisé puis liste) ; compléter les fiches : le vrai schéma remplace le croquis (captures).
- **ACAL967** (S4) — Ne plus écrire « Calepinage Calepinage … chargé » et raccourcir à 8 caractères les empreintes de la comparaison de versions ; fini quand le titre « Calepinage (copie) » donne « Calepinage (copie) chargé » et qu'une empreinte de 64
  - Preuve : PA2.5 — créer un calepinage depuis un modèle puis l'ouvrir : pas de mot doublé ; comparer deux versions : empreintes courtes (rejoué par l'orchestrateur).
