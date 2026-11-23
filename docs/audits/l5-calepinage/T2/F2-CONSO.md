# F2-CONSO — tour 2 — le commercial qui chiffre une usine ou une ferme (consommation, batterie, pompage, réseau)

Relecteur : F2-CONSO · compte `rev_conso` · bureau 1440 × 900, thème clair (plus deux captures à 375 px) · instrument
http://127.0.0.1:5241 (`origin/main@bfb859c90`) · 23/11/2026, ~04 h 30 → ~06 h 45 UTC.
Scripts et captures : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/F2-CONSO/` (captures dans `cap/`).
Mes calepinages (tous préfixés « F2-CONSO ») : 1988 (lead 900 MAD, devis DEV-202611-0012 généré), 1990 (ferme, pompage),
1997 (usine, batterie), 2010, 2011 (pan existant + extension), 2012 (villa, référence sans conso), 2028 (toit plat à châssis).

## 1. Verdict

Les corrections de batterie (secours, coupures, seuils hors réseau, groupe, fenêtres, mode expert) et la carte qui lit la facture
du lead tiennent côté fonction : corps postés exacts, relecture après rechargement, refus sous le champ. Mais la consommation
reste le maillon faible : la facture du lead n'atteint pas la simulation, une charge à venir enregistre une maison à zéro, les
factures mensuelles saisies disparaissent au rechargement, et le mode météo pluriannuel fait afficher des « par an » dix fois trop
grands. Côté pompage, aucun verdict ne peut être obtenu sur le catalogue livré (aucune pompe à courbe n'a de prix).

## 2. Comptes de contre-vérification (23 tâches)

| ok | partiel | non-fait | faux | régression | déjà-présent | non essayé |
|---|---|---|---|---|---|---|
| 10 | 6 | 0 | 0 | 0 | 0 | 7 |

- **ok** : ACAL776, ACAL777, ACAL778, ACAL789, ACAL791, ACAL795, ACAL799, ACAL803, ACAL847 (moitié « avec le droit »), ACAL848.
- **partiel** : ACAL788 et ACAL792 (fonction tenue, cibles < 44 px et champs illisibles dans la colonne étroite) ; ACAL837 (barres
  sept.–déc. coupées aux deux tailles) ; ACAL779 (avertissement servi par l'API, affiché nulle part) ; ACAL780 (pas de
  « Climatisation ») ; ACAL781 (la ligne existe mais donne 17 530 kWh/an pour une voiture à 1 752).
- **non essayé** (raisons au §5) : ACAL807, ACAL811, ACAL815, ACAL820, ACAL821, ACAL813, ACAL840.

Cases de matrice cassées sur mon périmètre :
- `K-SAISIE-PERDUE` : facture du lead × simulation (casse, T2-F2-CONSO-013) ; factures mensuelles × rechargement (casse, -006) ;
  appareils/fenêtres cachés × changement de stratégie (la saisie cachée agit encore, -009). Tient : déclaration batterie et charges
  à venir × rechargement ; facture du lead × carte Recommandation (ACAL777).
- `K-GRANDEUR-UNIQUE` : production carte 11 611 contre onglet Économie 14 620 kWh (-003) ; cible 4 panneaux contre « 400 cible »
  (-001) ; « Couvrir la facture » 4 panneaux contre 174 % pour 13 (-002) ; heures et charges « par an » sommées sur 10 ans en mode
  pluriannuel (-007, -012) ; Wc unitaire 720 contre 710 (étape Panneaux « 10,80 kWc » pour 15 modules, en-tête « 10,65 kWc »,
  `cap/o05.png`, cas F1-004 déjà connu, toujours cassé). Tient : économie carte = onglet Économie (5 739 MAD, ACAL778).

## 3. Constats neufs (registre `registre/constats/T2-F2-CONSO.jsonl`)

- **T2-F2-CONSO-003 (S2)** — carte Recommandation 11 611 kWh/an contre onglet Économie « Production année 1 : 14 620 kWh » (+26 %), sans un mot.
- **T2-F2-CONSO-006 (S2)** — les mois saisis dans « Mes factures » disparaissent après enregistrement + rechargement (seuls un total et une courbe plate restent).
- **T2-F2-CONSO-007 (S2)** — onglet Batterie : « Heures sans import réseau : 74 649 h » (une année a 8 760 h) — somme des 10 ans du mode pluriannuel.
- **T2-F2-CONSO-012 (S2)** — onglet Production : « Charges ajoutées : 17 530 kWh/an » pour une voiture à 30 km/j × 16 kWh/100 km (1 752 attendus).
- **T2-F2-CONSO-013 (S2)** — la facture du lead ne nourrit pas la simulation ; ajouter une voiture enregistre une courbe de base de 24 zéros présentée comme « saisie » : conso = la voiture seule, 0 % de couverture.
- T2-F2-CONSO-001 (S3) — Expert : « Panneaux nécessaires 400 », « 13 posés / 400 cible » quand la bande dit 4 panneaux (le 400 semble être la valeur stockée du choix « Le plus de panneaux »).
- T2-F2-CONSO-002 (S3) — « Couvrir la facture : 4 panneaux · 2,84 kWc » à côté de « 13 panneaux ≈ 174 % » : 4 panneaux ≈ 54 %.
- T2-F2-CONSO-004 (S3) — onglet Économie en Expert : tuiles VAN/TRI/LCOE/RETOUR qui se chevauchent dans la colonne de 300 px.
- T2-F2-CONSO-005 (S3) — « Affiner ma consommation » : 12 barres coupées, chiffres clés superposés.
- T2-F2-CONSO-008 (S3) — onglet Batterie : ligne d'appareil écrasée, champs de 50 px qui montrent « 1 » pour 10, cases de 13-18 px, toasts qui commencent par la clé technique.
- T2-F2-CONSO-009 (S3) — appareils et fenêtres masqués par le changement de stratégie restent postés et agissent (« Réserve déduite de 2 appareils » en Effacement de pointe).
- T2-F2-CONSO-010 (S3) — hors réseau : groupe qui démarre à 20 % sous une veille à 30 % → 75 h défaillantes, groupe 0 h, aucune alerte.
- T2-F2-CONSO-011 (S3) — lead industriel avec facture : « Aucune taille ne se tire des factures de ce lead. Renseigner la facture du lead ».
- T2-F2-CONSO-014 (S3) — onglet Pompage : aucune pompe ni variateur retenus sur le catalogue livré (pompes à courbe sans prix) ; « Modules posés : — » ; clé brute « mois_niveau_bas ».
- T2-F2-CONSO-015 (S3) — onglet Optimiser : « SoftTimeLimitExceeded() » puis « parametres.simulation.mode_meteo : … gh_w_m2 … » en mode pluriannuel.
- T2-F2-CONSO-016 (S3) — aucune liste pour choisir une batterie du stock dans l'atelier (seulement depuis la ligne d'un devis).

## 4. Ce qui est bien (à ne pas casser)

- La carte Recommandation lit la facture du lead (174 %, « Facture du lead : 900 MAD/mois »), nomme son chiffre (« estimation
  de l'atelier, plafonnée à la facture ») et ne renvoie à l'onglet Économie qu'avec un devis lié ; les économies concordent
  (5 739 MAD/an des deux côtés).
- La génération du devis demande confirmation quand la pose dépasse la cible, et nomme la source de la cible.
- Onglet Batterie : corps postés exactement selon le contrat (appareils, coupures, fenêtres à état de charge visé, part/plafond
  effaçables, seuils, groupe), tout est relu après rechargement, « rien n'est prérempli », refus sous le champ fautif, 3 fenêtres
  maximum, résultats de secours lisibles (« Frigo : tient 10 h », énergie non fournie et pire coupure), garde-fou et trois faits
  de la série, banque du mois le plus chargé, mention des seuils saisis.
- « Consommation mesurée » : refus sous mars, mois vide = « — », mention « Comparaison indicative, aucun engagement de garantie ».
- Tableau « Existant / Ajouté / Total » avec P50 neuf en petit et la mention du serveur.
- Pompage : la carte « Pompage direct » dit quel champ remplir quand les heures de demande manquent ; « kW de plaque non saisi : P4 ».

## 5. Non essayé, et pourquoi

- **ACAL807, ACAL811, ACAL815, ACAL820, ACAL821** (pompage) : aucune pompe n'est jamais retenue sur ce catalogue (les seules
  pompes à courbe, OSP 30, n'ont pas de prix ; essais à HMT 60 et 30 m, débits 6 et 2 m³/h) : pas de variateur, donc ni ligne
  rouge à 21 modules, ni appoint à 11 modules, ni 4 pompes sur 5,5 kW, ni réservoir jour par jour, ni 6,0 contre 2,4 m³/h.
  Vu quand même : deux cartes direct / réservoir côte à côte, « Débit de conception : 6,0 m³/h » pour 12 m³ en 2 h, champ manquant
  nommé ; l'erreur « débit souhaité obligatoire » sous son champ ; « mois_niveau_bas » non signalé sous les pastilles des mois.
  Je n'ai pas créé de produit de test (même pollution que « CALX109 »). Constat produit : T2-F2-CONSO-014.
- **ACAL813** : l'onglet Optimiser refuse en mode météo « pluriannuel » (réglage posé par un autre relecteur) ; le remettre en
  TMY le temps d'un balayage aurait changé les simulations des relecteurs en parallèle : je ne l'ai pas touché. Constat : -015.
- **ACAL840** : la moitié « avec OCR simulé » demande une clé absente de la pile ; la moitié « sans clé, aucun bouton » tient
  (message « La lecture de photo de facture est désactivée sur ce serveur… », aucun bouton, à 1440 et à 375 px : `cap/k03-barres.png`, `cap/k04-barres.png`).
- **ACAL847, moitié « sans le droit »** : je n'ai qu'un compte (administrateur, porteur de `calepinage_approuver`).
- Thème sombre, WebKit, tablette : non joués (temps consacré aux 23 tâches). Matrice `K-SAISIE-PERDUE` colonnes « mode devis »
  et « Partir d'un modèle » : non jouées.
- Réglages société : je n'en ai modifié aucun. Produit batterie posé par l'API sur MON calepinage 1997 (`batterie.produit`
  22821) faute de liste à l'écran (-016) ; matériel module/onduleur posé par l'API sur 1997, 2011, 2012, 2028.

À vérifier (vu une fois ou seulement dans le DOM, pas au registre) :
- « Heures de recharge (ex. 22-24) » est un champ `inputmode="decimal"` : le pavé numérique de l'iPhone n'a pas de tiret.
- En mode Expert, cliquer « Générer le devis » de l'en-tête met l'étape Documents en surbrillance mais laisse le panneau du Toit (`cap/c06-apres-clic.png`).
- Toit Guidé : « 2 pans » ne marque aucune carte comme choisie et « Créer le toit » donne « Toit plat, 1 pan » (`cap/p03-cree.png`, sur un calepinage qui avait déjà un toit en brouillon).
- Un calepinage neuf prend comme « module de départ » le produit d'essai « CALX109 » (pollution de données de la pile, `cap/p01-panneaux.png`).
- Après le premier clic « Générer le devis », la section « Électrique » de « Prêt à envoyer ? » se vide (`cap/c08-apres.png`).
- Une simulation de 2011 terminée sans aucun geste de ma part s'est lue « périmée : le document a changé » juste après ; hypothèse non prouvée : un autre relecteur a changé un réglage société entre-temps (société partagée). Relancée, elle s'est lue à jour.

## 6. Trois propositions pour rejoindre les meilleures références

1. **Une seule consommation, visible en Guidé, qui nourrit tout (PV*SOL, profils de charge).** La facture du lead devient une
   courbe horaire choisie par activité (maison, commerce, atelier 8 h-18 h, ferme avec pompage) et sert à la fois la carte, la
   simulation et la batterie ; les factures mensuelles restent affichées et éditables ; une charge à venir s'ajoute à cette base,
   jamais à une base nulle. Aujourd'hui trois factures d'usine donnent une courbe plate 24 h (0,66 kWh chaque heure).
2. **La batterie dans une vraie fenêtre, catalogue compris (PV*SOL, boîte « Batterie »).** Choix du produit du stock, puis un
   champ par ligne à 44 px, stratégie en tête avec seulement ses champs (et ce qui est masqué n'agit plus), résultats en
   moyennes annuelles même en mode pluriannuel, motifs sans clé technique.
3. **Le pompage « besoin d'abord » (Lorentz COMPASS).** Besoin en m³/jour + HMT (ou puits) → pompe, variateur et champ proposés
   même sans prix (prix exigé seulement au devis) ; le débit se déduit du besoin et des heures au lieu d'être un second champ
   obligatoire ; verdicts chaînes/appoint/plusieurs pompes lisibles sur une carte, comme la maquette `Resultats.dc.html`.
