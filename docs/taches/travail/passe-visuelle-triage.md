# Passe visuelle — tri de l'orchestrateur (18/11/2026, 05 h 35 UTC)

Rapport complet du juge : `passe-visuelle.md` (même dossier) — 65 écarts, numérotés. Ce fichier dit ce qu'on en fait.

## Décisions (ne pas les rouvrir)
- **D-V1 — les tâches faites restent repliées dans « Faites »** (écart n° 4). La maquette de 15 h les montre barrées à leur
  place ; la référence (`regles.md` §4.1 ligne 9 et §4.2-1) et le contrat (`contract_samples/aujourdhui.json` : une
  gardée faite est servie dans `faites`, pas dans `journee`) disent « Faites », repliée. On garde la référence. UNE
  exception, écrite dans la référence et non tenue par le code : une tâche ESSENTIELLE faite aujourd'hui reste AUSSI
  dans `essentiel`, barrée (§4.1 ligne 3 « ouvertes ou faites aujourd'hui », §4.2-1 « et reste dans essentiel si sa
  ligne y est »). La ligne « → jeu. 26 » d'une gardée déplacée reste un état d'écran (jusqu'à la sortie), pas servi.
- **Ce qui n'est PAS un écart** : les données des errata de `docs/taches/maquettes/SCENARIO.md` §0 ; l'en-tête et la barre
  d'onglets de l'ERP ; les champs date/heure natifs affichés « mm/dd/yyyy » ou « 08:30 AM » (langue du navigateur de
  capture — n° 28, 48 : à régler dans la spec par `locale: 'fr-FR'`, pas dans l'écran) ; les captures prises en
  chargement (n° 5, 9, 10, 6 au bureau) et le tiroir de l'ERP ouvert (n° 12) : à RECAPTURER avant de conclure.
- **Bureau** (n° 1, 2, 3, 34, 42, 43) : la colonne de droite et les vues de projet sont de la fusion 4 ; à vérifier sur des
  captures prises sur `dev-taches-f4`, pas sur celles de la fusion 2.
- **Référence d'apparence** : la maquette HTML FINALE (`docs/taches/maquettes/<nom>.html` + `taches.css` et les
  `ecrans-*.css`) ; les PNG de `…/worktrees/travail/docs/taches/maquettes/captures/` datent d'avant le dernier tour de
  critique. Les libellés viennent de `docs/taches/reference/textes.md`, au caractère près.

## Groupes (une lane chacun, fichiers disjoints)
- **V-A « lignes, Aujourd'hui, bilan »** : n° 13 (ligne de tâche : titre aligné sur la case et l'heure, méta sur une
  ligne), 14, 15, 16, 19, 20, 25, 26 (anneau de focus de la poignée), l'essentielle faite qui reste dans Essentiel (D-V1),
  le compteur « 0/2 » à droite du titre Essentiel, et les mineurs du rapport qui touchent ces écrans.
- **V-B « fiche, saisie, À trier, recherche »** : n° 21, 22, 23, 24, 27, 29, 30, 31, 32, 33, 46, et leurs mineurs.
- **V-C « agenda, planifier, projets, projet, rythme, revue, réglages »** : n° 6, 7, 8, 34, 35, 36, 37, 38, 39, 40, 41,
  44, 45, 47, et les n° 1, 2, 3, 42, 43 à vérifier sur la fusion 4.
- **V-D « Copilote et iPhone »** : n° 11, 47 (Mon iPhone), 49, 50, et `locale: 'fr-FR'` dans les aides de capture.
