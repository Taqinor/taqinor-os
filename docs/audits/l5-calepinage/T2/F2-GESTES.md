# Tour 2 — F2-GESTES (le dessinateur pressé, fonction, bureau 1440 × 900 clair)

Compte `rev_gestes`, instrument http://127.0.0.1:5241 (`origin/main@bfb859c90`). Scripts et captures :
`C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/F2-GESTES/`
(`cap/` pour les captures). Leads et calepinages créés, tous préfixés « F2-GESTES » : Villa Marrakech (cal 1928,
DEV-202611-0003), Riad sans facture (1929, DEV-202611-0005), Ferme Agadir (1933), Ferme Taroudant (1934,
DEV-202611-0004), Villa Rabat, Fes, Meknes, Oujda, Safi, Tetouan, Nador (1937-1944, gestes seuls).
L'instrument a été saturé vers 01 h 00-01 h 40 : tout ce qui a été vu pendant la panne a été rejoué ensuite ;
aucun constat ne repose sur une lenteur.

## 1. Verdict

Les gestes de base marchent maintenant (molette, « + », double-clic au 4ᵉ coin, glisser un coin, Effacer qui garde
la cible), et la génération du devis dit enfin ce qu'elle chiffre. Le dessinateur bute encore sur la suite :
le champ au sol se compte deux fois par défaut, son devis tombe dans une impasse avec le module de départ, et ses
choix (surfaces décochées, module choisi) sont perdus à la réouverture ou après Effacer.

## 2. Contre-vérification (18 corrections, `registre/evenements/T2-F2-GESTES-cv.jsonl`)

ok 11 · partiel 6 · non-fait 0 · faux 0 · régression 0 · déjà-présent 0 · non essayé 1.

- ok : ACAL915, 914, 925, 926, 928, 923, 949, 950 (la ligne « partiel » est corrigée par une ligne « ok » : la
  clause « fini quand » est tenue et la maquette v2 met la puce dans la pile de zoom), 954, 955, 377 (moitié
  jouable seulement).
- partiel : ACAL916 (zone 710 W + champ 720 W composés en 56 × 710 W, refus d'ACAL914 ; deux lignes jamais vues),
  913 (mention « à confirmer » perdue après rechargement, absente sur certains pans neufs), 968 (génération et
  resynchronisation justes, mais à la réouverture les cases sont re-cochées et la phrase dit 106 au lieu de 50),
  922 (le 409 n'a pas de kWc : `kwc: null`, phrase en TTC seul), 918 (« N modules » OK, l'onglet Terrain ne relit
  pas la surface et demande de l'« enregistrer d'abord »), 946 (pas de « Approuver » pour l'auteur, mais un refus
  s'affiche deux fois, dont un bandeau rose presque illisible avec la clé brute « motif »).
- non essayé : ACAL1194 (commande `manage.py` sur une copie anonymisée de la prod : aucune commande docker permise).

Cases de matrice cassées :
- K-GESTE (Chromium souris) : fermer par « Terminer » → dézoom + 3D (001) ; bouton Annuler / Rétablir grisés sur
  toit fermé alors que Ctrl+Z marche (013) ; bouton « Générer le devis » de la barre sans effet (003). Tenues :
  molette, clic coin, double-clic 4ᵉ coin, glisser coin (42 → 56 m²), glisser carte (surface inchangée), « + »
  et « − », plein écran.
- K-SAISIE-PERDUE : matériel × Effacer (014) ; surfaces décochées × réouverture (012). Tenues : facture → cible 4,
  cible hydratée × Effacer, 4ᵉ coin × double-clic, module + cible tapée × rechargement.
- K-DEFAUT-CHOIX : pente d'un tracé libre (« Toit plat » sans « à confirmer », 008) ; module de départ (007, 015).
  Tenues : E-O plus jamais 35° ni 0° ; « toit rempli sans facture » demande confirmation (mais sans kWc).

## 3. Constats neufs (`registre/constats/T2-F2-GESTES.jsonl`, 16 : S1 × 1, S2 × 3, S3 × 9, S4 × 3)

- 004 S1 — « Enregistrer le contour tracé » laisse le pan « Zone 2 » à côté du « Champ au sol 1 » : 106 modules
  cochés par défaut pour un seul champ (rejeu de T1-F1-028/030, toujours là).
- 005 S2 — devis du champ au sol refusé (« le catalogue compose 35,50 kWc ») avec le module que l'atelier propose ;
  aucun choix de module sur une surface : impasse.
- 012 S2 — à la réouverture, les surfaces décochées reviennent cochées et la phrase annonce 106 modules au-dessus
  du devis lié à 50.
- 014 S2 — Effacer + retracer remplace le module choisi (Jinko 710 W) par le module de départ (720 W).
- 001 S3 — « Terminer le tracé » dézoome et passe en 3D : toit tracé sur 450 px réduit à ~75 px.
- 002 S3 — toast « Aucun changement » sur la carte « Devis DEV-… créé ».
- 003 S3 — « Générer le devis » de la barre ne génère jamais (défile, ou rien).
- 006 S3 — chaque refus de génération affiché deux fois (encadré + toast).
- 007 S3 — « module de départ, à confirmer » devient « Module posé » après rechargement.
- 008 S3 — tracé libre : « Toit plat » affiché comme un fait.
- 009 S3 — bandeau 2,84 kWc contre bloc 2,88 kWc après Effacer.
- 013 S3 — ↶ ↷ grisés sur toit fermé ; Ctrl+Z / Ctrl+Maj+Z marchent.
- 015 S3 — pan neuf : « Module posé : Canadian Solar » sans « à confirmer » (un calepinage sur deux).
- 010 S4 — la carte de surface recouvre la consigne d'étape pendant le tracé.
- 011 S4 — « Terminer le tracé » grisé reste sur la carte en Expert.
- 016 S4 — légende de « Prêt à envoyer ? » tassée en colonne quand la section Électrique s'affiche.

Les deux constats du relecteur précédent (forme « 2 pans » avant « Créer le toit », repavage au changement de forme)
n'ont pas été croisés : mes tracés n'ont pas changé de forme.

## 4. Ce qui est bien (à ne pas casser)

Molette sans erreur ; le centre du « + » zoome ; « Terminer le tracé » visible sur la carte dès 3 coins, avec
« Annuler le dernier point » ; le double-clic au 4ᵉ coin garde les 4 sommets (61 m² contre 30) ; Effacer demande
confirmation en ligne et garde la cible hydratée (« 4 posés / 4 cible ») ; glisser un coin et glisser la carte sont
justes ; l'ordre de tabulation passe par « Enregistrer » avant « Générer » ; l'enregistrement marche sans imagerie.
À l'étape Documents : la phrase « Le devis chiffre : … = N modules » lue du serveur, des cases de 44 px, un devis
qui ne chiffre que les surfaces cochées (50 modules exacts), la garde 72/71 kWc qui refuse au lieu de substituer,
la question « Confirmer et générer » avec le TTC, et la carte « Devis DEV-… créé · Voir le devis ». Thème sombre
lisible sur ces blocs.

## 5. Non essayé, et pourquoi

- ACAL1194 : commande serveur sur une copie de la prod (docker interdit).
- ACAL377, moitié « vraie clé remise » et Alt + molette sur un fond calé (ACAL949) : pas d'imagerie sur la pile.
- K-GESTE WebKit iPhone / iPad, pincer, glisser au doigt : temps consommé par la panne de l'instrument.
- « Partir d'un modèle », températures (K-SAISIE-PERDUE) ; « simuler » d'ACAL913.
- ACAL916 dans son cas exact (710 + 550 Wc) : aucun second module composable d'une autre puissance au catalogue.
- Note : un module « CALX109 Module mwsikr9s10 » (720 W, prix 1 000) a été ajouté au catalogue partagé à 00:14 par
  une autre lane ; il est devenu le « module de départ » de plusieurs de mes pans. Le réglage « visite exigée » de la
  société a aussi basculé pendant ma séance (refus « feu vert » vu une fois puis disparu) : non retenu comme constat.

## 6. Trois propositions

1. **Un geste de tracé qui ne bouge pas la caméra** (Aurora, OpenSolar ; maquette v2 Main) : après fermeture, rester
   en Plan à la même échelle, coins saisissables, cotes sur chaque bord, et des boutons ↶ ↷ qui suivent exactement
   l'historique du clavier (coins, cotes, Effacer).
2. **Un seul modèle de champ au sol** (OpenSolar « ground mount », PVsyst une surface = un champ) : « Enregistrer le
   contour tracé » transforme le pan en surface (plus de « Zone 2 » fantôme), la surface porte son module choisi dans
   la même liste que les pans, et l'onglet Terrain n'est qu'une autre vue de cette même surface.
3. **Des choix qui tiennent** (Aurora, conception versionnée) : le module choisi, les surfaces chiffrées et la cible
   tapée sont enregistrés avec la conception et survivent à Effacer, au rechargement et à la resynchronisation ; un
   défaut reste marqué « à confirmer » tant que personne ne l'a choisi, partout.
