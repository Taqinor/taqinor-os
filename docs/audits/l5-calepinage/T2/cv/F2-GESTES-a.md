# Contre-vérification — F2-GESTES-a — Gestes de l'atelier, devis, moteur partagé (corrections du tour 1)

18 corrections livrées (première moitié de la liste, S1-S2 d'abord) sans preuve en direct, S1-S2 d'abord. Pour chacune : rejoue la « preuve », regarde l'écran, écris UN verdict (ok / partiel / non-fait / faux / regression / deja-present).
Le texte complet d'une tâche (constat d'origine, Given/When/Then) : `grep -n "<id> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md` dans le worktree en lecture.

- **ACAL915** (S1) — Dire, avant « Générer le devis », ce que le devis va chiffrer : « Le devis chiffre : Zone 1 (42) + Champ au sol 1 (176) = 218 modules » ; fini quand un calepinage à deux surfaces posées l'affiche, lue du serveur, sans case à coche
  - Preuve : REV-COUTURE, rejeu T1-F1-030 — la ligne « = 218 modules » s'affiche avant « Générer ».
- **ACAL916** (S1) — Composer chaque surface de pose à SA puissance (`moduleWc`) même sans `modules[]` ; fini quand une zone 42 × 710 W et un champ 176 × 550 Wc donnent deux modèles 42 × 710 et 176 × 550
  - Preuve : REV-COUTURE, rejeu T1-F1-030 — champ à 550 Wc, générer : lignes 42 et 176.
- **ACAL968** (S1) — Ajouter, à la liste des surfaces d'ACAL915, une case par surface chiffrée, TOUTES cochées à l'ouverture, et ne composer que les cochées (D-ACAL-37) ; fini quand le champ seul coché donne 176 modules, resynchro comprise
  - Preuve : REV-COUTURE, rejeu T1-F1-030 — décocher « Zone 1 », générer, resynchroniser : 176.
- **ACAL1194** (S1) — Lister en lecture seule les calepinages dont l'orientation lue des surfaces de pose changera avec ACAL921 ; fini quand `manage.py acal_dryrun_azimut_surfaces --dry-run` imprime, surface par surface, la valeur saisie, la face lue a
  - Preuve : sur une copie anonymisée de la base de prod (`qa_import_anonymise`), lancer la commande et coller sa sortie dans la PR d'ACAL921, à lire par Reda.
- **ACAL377** (S2) — Faire booter l'atelier sur un fond de repli local quand le STYLE d'imagerie du fournisseur est refusé, pour que la scène s'hydrate et que « Enregistrer le calepinage » s'active ; fini quand, style MapTiler en 403, `/calepinage/:id
  - Preuve : pile locale, clé MapTiler volontairement fausse (style en 403) : `/calepinage/<id>` d'un calepinage de démo ⇒ statut « imagerie indisponible », « Enregistrer le calepinage » actif, enregistrement 200 ; vraie clé remise, rechargement ⇒ conception identique ; aucune `console.error` hors le 403 attendu.
- **ACAL913** (S2) — Poser comme module de départ de chaque pan le premier module CHOISISSABLE du catalogue (« module de départ — à confirmer ») au lieu du 720 Wc de l'atelier ; fini quand le document d'une séance sans choix porte `zones[].geometry.mo
  - Preuve : REV-COUTURE, rejeu T1-S1-018 — pan neuf, simuler (plus de 409), générer : même module.
- **ACAL914** (S2) — Refuser « Générer le devis » quand la composition chiffre un autre module que le dessin (kWc composé ≠ kWc dessiné), en nommant les deux ; fini quand 100 × 720 W dessinés sans 720 W au catalogue rendent 409 « 72,00 kWc dessinés, 7
  - Preuve : REV-COUTURE, rejeu T1-S1-018 avant ACAL913 — générer : le refus nomme 72,00 et 71,00 kWc, la liste des devis ne bouge pas.
- **ACAL918** (S2) — Faire calculer par le moteur la surface créée par « Enregistrer le contour tracé » (bloc `engine` stocké, module du pan actif) pour qu'atelier et onglet Terrain parlent du même champ ; fini quand la liste ne dit plus « — (plan du 
  - Preuve : REV-COUTURE, rejeu T1-F1-028 — tracer la parcelle, Champ au sol, Enregistrer : « N modules » ; recharger ; onglet Terrain : la même surface.
- **ACAL922** (S2) — Demander une CONFIRMATION avant de générer un devis que rien ne dimensionne (ni facture ni taille souhaitée) : 409 avec kWc et TTC, puis 201 avec `confirmer_taille: true` ; fini quand le rejeu rend 409 avec 34,08 kWc et 168 800,00
  - Preuve : REV-COUTURE, rejeu T1-S1-007 — générer : la question ; confirmer : devis créé.
- **ACAL923** (S2) — Poser à l'écran la question de confirmation : « Aucune facture : le devis remplit le toit (34,08 kWc, 168 800,00 MAD TTC). Confirmer ou renseigner la facture » ; fini quand le 409 `confirmation_taille` affiche la question au lieu 
  - Preuve : REV-COUTURE, rejeu T1-S1-007 — générer : la question ; confirmer : le devis s'ouvre.
- **ACAL925** (S2) — Garder la cible hydratée quand on clique « Effacer » : après `reset`, le nombre de panneaux voulu redevient celui du devis ou de la facture du lead, jamais « remplir le toit » ; fini quand le lead à 4 panneaux de cible garde 4 apr
  - Preuve : REV-COUTURE, rejeu T1-S1-024 — Effacer, retracer : 4 panneaux voulus ; générer : 4.
- **ACAL926** (S2) — Poser le dernier coin quand on finit un tracé par un double-clic à un NOUVEL endroit (le coin en attente est posé, puis le contour fermé) ; fini quand trois clics puis un double-clic au 4ᵉ coin donnent 4 sommets (rejeu : ~194 m², 
  - Preuve : REV-COUTURE, rejeu T1-S1-025 — rectangle fini par un double-clic au 4ᵉ coin : aire ≈ 194 m².
- **ACAL928** (S2) — Limiter les inclinaisons essayées en Est-Ouest aux inclinaisons constructibles de V6 (10, 12, 15°) ; fini quand, sur un toit plat de 163 m² à Marrakech, la recommandation n'est ni « Est-Ouest 35° » ni « Est-Ouest 0° » et qu'aucune
  - Preuve : atelier, toit plat d'environ 163 m² à Marrakech (geste de T1-F1-023) : la carte « recommandé » ne dit ni 35° ni 0° en Est-Ouest.
- **ACAL946** (S2) — Remplacer « Approuver » par « La conception doit être approuvée par un autre relecteur » pour l'auteur, et n'afficher un refus qu'une fois ; fini quand l'état dit si le lecteur peut approuver et qu'un refus ne s'affiche plus 3 foi
  - Preuve : rejouer T1-S2-012 : administrateur auteur du calepinage 12 de REV-COUTURE : pas de « Approuver », la phrase, aucune bulle.
  - Écran : Approbation, expert, `docs/audits/l5-calepinage/maquettes/Documents.dc.html`.
- **ACAL949** (S2) — Faire zoomer la molette sans erreur : le gestionnaire `wheel` ne lit plus la position avant de tester Alt ; fini quand un cran de molette sans Alt ne lève ni exception ni toast et qu'Alt + molette tourne toujours le fond calé
  - Preuve : rejouer T1-F1-001 : un cran de molette au centre de la carte du calepinage 1, ni toast ni `pageerror`.
  - Écran : étape Toit, essentiel, `docs/audits/l5-calepinage/maquettes/Main.dc.html`.
- **ACAL950** (S2) — Sortir la puce « Plein écran » de la pile des boutons de zoom : en haut à gauche sous la boussole, fond opaque, 44 px ; fini quand le centre du « + » reçoit le clic de zoom et non celui de la puce
  - Preuve : rejouer T1-F1-002 : `document.elementFromPoint` au centre du « + » rend le bouton de zoom ; la puce se lit sur la carte.
  - Écran : étape Toit, essentiel, `docs/audits/l5-calepinage/maquettes/Main.dc.html` (bascule Plan / 3D hors de la pile de zoom).
- **ACAL954** (S2) — Poser « Terminer le tracé » sur la carte, pas sous la flottaison : bouton `#rp9-finish` remonté dans l'enveloppe de la carte, centré en bas ; fini quand, sur 900 px de haut, il se voit sans défiler pendant le tracé
  - Preuve : rejouer T1-S1-002 : 1440 × 900, trois coins posés : « Terminer le tracé » se voit sur la carte.
  - Écran : étape Toit, essentiel, `docs/audits/l5-calepinage/maquettes/Main.dc.html`.
- **ACAL955** (S2) — Faire passer « Enregistrer » avant « Générer le devis » : la barre d'enregistrement se rend au-dessus du bloc qui porte « Générer le devis » ; fini quand « Enregistrer le calepinage » précède « Générer le devis » dans l'ordre de l
  - Preuve : rejouer T1-S1-014 : atelier d'un calepinage, toit fermé : « Enregistrer » se voit et se tabule avant « Générer le devis ».
  - Écran : barre d'actions, essentiel, ordre « Enregistré à 14:32 … Générer le devis » de `docs/audits/l5-calepinage/maquettes/Main.dc.html`.
