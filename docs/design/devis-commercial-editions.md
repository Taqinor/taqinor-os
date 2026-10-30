# Devis commercial (C&I) — étude de design « deux éditions » (29/10/2026)

Demande du fondateur (28/10, soir) : « le plus beau devis commercial du monde », deux
publics possibles (dirigeant lettré / commerçant de tous les jours), **sans toucher au
devis actuel** — une version à côté, à juger le lendemain. Investigation niveau L3
(`go-deep`) : 7 lanes de recherche web, synthèse, construction, 3 lentilles de
vérification. Le code vit dans `apps/ventes/quote_engine/commercial_editions/` ; il
n'est **pas branché** sur le dispatch (`builder.registre_renderers`) et se rend par
`commercial_editions/apercu.py` (règle #4 : un seul chemin client, `/proposal` ; les
éditions sont destinées à devenir un *choix de gabarit* de ce même chemin, jamais un
second chemin).

## Ce que la recherche a établi (sources dans `scratchpad/research/01-07`, non versionnées)

| Fait | Source (lane) | Conséquence de design |
|---|---|---|
| Au Maroc, parmi les alphabétisés 10+, 99,2 % lisent l'arabe, 57,7 % le français (HCP 2024 via Le Matin) ; darija écrite rare (39 %) | 02 | L'arabe a sa place dans le document : libellés doublés FR/AR **depuis le catalogue** (jamais une traduction écrite dans le code) ; titres en arabe standard simple |
| Les devis marocains attendent un squelette : ICE/RC/IF du vendeur, numéro, validité, tableau désignation/qté/PU HT/TVA/total, « Bon pour accord », cachet | 06 (Clicpaie, AMDE) | Le squelette reste intégral dans les deux éditions (page devis + accord) |
| Les meilleures propositions solaires mettent UN chiffre personnalisé en couverture, la valeur avant le prix, ≤ 3 chiffres-titres ; ROI à côté du prix | 01 (Aurora/OpenSolar/Qwilr/Proposify) | Couverture = économie année 1 en héros, retour + part couverte + production en 4 faits, investissement sur sa rangée |
| Barres groupées > empilées ; facture « avant / après » en deux barres ; cumul réservé au point de retour (MeasuringU : 82-88 % lisent mal la pente d'un cumul) ; pictogrammes toujours avec le nombre | 04 | `graphiques.py` : barres mensuelles groupées, facture avant/après, frise du cumul avec point de retour, rangée de soleils + « 47 % » |
| Lecteur peu lettré : un chiffre-héros, une idée par page, pas de HT/TVA/kWc en pages 1-2, un vrai visage et un numéro, chiffres latins, isolats bidi | 05 (NN/g, CFPB, Medhi CHI 2009, MicroSave) | Édition Directe : question « ce que vous gagnez » → facture → prix → qui appeler |
| Jurys / systèmes de design : 3 rôles typographiques, filets au lieu de cartes, une couleur d'accent, pas d'or métallisé, marges asymétriques, chiffres tabulaires | 07 (Vercel, Butterick, Strom, Stripe) | Système commun `commun.py` : Fraunces (grands chiffres) + IBM Plex Sans (tabulaire par défaut) + IBM Plex Sans Arabic ; filets 0,5 pt ; un accent par édition |
| Les 3 polices actuelles n'ont pas de chiffres tabulaires et pas de glyphe U+202F (séparateur de milliers du moteur) ; l'or #F5A623 échoue au contraste en texte | 03 (mesuré fontTools) | Plex Sans suit toujours Fraunces/Plex Arabic dans la pile (il porte U+202F) ; l'ocre #B7791F ne sert qu'en filet/point, jamais en texte courant |
| Une couverture claire lit mieux sur téléphone qu'un aplat sombre (NN/g) ; la vignette WhatsApp n'est pas garantie | 03, 05 | Photo réelle en bandeau haut à voile plat, papier clair ; exporter la page 1 en image pour WhatsApp = suite à décider |

Une seule marque, deux éditions : la lane Maroc conclut que les preuves justifient une
scission **langue / densité**, pas deux marques. Les deux éditions partagent polices,
grille, filets et squelette légal ; elles diffèrent par le ton (encre pétrole / papier
chaud terracotta), la densité et la langue.

## Les deux éditions

**Signature** (dirigeant) — p1 couverture-affiche (photo, projet, héros « économies
estimées / an », facture avant/après, 4 faits, investissement ancré en bas) · p2 énergie
mois par mois, installation en bref, activité, position nette sur 25 ans (frise, jalons,
retour, TRI), bases du calcul · p3 le devis (tableau tabulaire, chaîne de totaux, option
batterie, options proposées, surplus), garanties, échéancier, services, étapes,
conditions, bon pour accord style contrat, bande légale.

**Directe** (commerçant) — p1 « ce que vous gagnez » (héros, facture avant/après en
grand, part couverte en soleils + nombre, prix clé en main, retour, échéancier, qui
appeler + QR) · p2 « ce que vous recevez » (devis, garanties, étapes, installation en
bref, activité, énergie mois par mois) · p3 retour sur 25 ans, bases du calcul,
services, conditions, accord avec cachet, bande légale. Libellés FR doublés en arabe
quand le catalogue porte la clé.

## Garanties tenues (vérifié le 29/10)

- **Zéro chiffre inventé** : `donnees.modele` lit `synthese_ci` / `totaux_all` /
  `chiffres_cles` et formate par les helpers existants ; parité des ancres
  `data-figure` avec le renderer actuel = identique sur hotel / boulangerie / café /
  dégradé (script `parite.py`). Les seuls nombres « nouveaux » sont des valeurs servies
  en décimales (facture avant/après, jalons du cumul, TRI) imprimées à l'unité comme la
  page finance industrielle.
- **Pages exactes, rien sous le pied** (`commercial.equip._tient`) sur les 3 fixtures,
  la fixture dégradée, la fixture complexe (deux options, sections, options proposées,
  note, interlocuteur), le devis réel DEV-202610-0119 (21 lignes, 2 taux de TVA,
  arrondi, QR) et en arabe — avec 3 paliers de densité (CIQ317).
- Python 3.11 (`compileall`), CSS tables seulement, polices OFL vendorisées en TTF
  statiques (les woff2 variables de Google ne sont pas lus par l'image prod — mesuré).

## Décisions à prendre (fondateur)

1. **Brancher ou non** : option `gabarit=signature|directe` de `/proposal`
   (`clean_pdf_options`) et choix par devis / par lead ; les tests de pages (AMOT36) et
   de parité suivent. Tant que non branché, rien ne change pour les clients.
2. **Économie mensuelle** : les lecteurs peu lettrés décident sur « par mois » (NREL,
   lane 04/05) ; le moteur ne sert pas ce chiffre (`economie_ci`), les éditions ne le
   calculent donc pas. L'ajouter côté moteur = une clé servie, pas un calcul de gabarit.
3. **14 clés à cataloguer** (3 langues, traductions fondateur) :
   `donnees.CLES_A_CATALOGUER` — hors français elles impriment leur littéral FR.
4. **Photo** : une seule photo C&I réelle (`industriel-45-couchant.jpg`) ; la
   bibliothèque `assets/installations/` gagne à recevoir des photos par activité.
5. **WhatsApp** : exporter la page 1 en image 4:5 (rasterisation du même PDF) ; la
   vignette PDF n'est pas garantie.
6. Le logo PNG actuel est petit et pâle sur photo ; un SVG/PNG haute définition de la
   marque améliorerait les deux couvertures.

## Révision du 29/10 (matin) — direction Khatam, trois éditions

Retour du fondateur sur la première passe : « Directe » devait porter beaucoup moins
d'information, « Signature » n'était pas assez marocaine et trop claire, et il faut trois
versions (Signature, Normale, Basique) qui rendent le devis actuel bien meilleur.

**Panel de conception (Workflow, 8 agents)** : quatre directions marocaines
indépendantes — Khatam (géométrie, marine et or), Majorelle & safran (couleur, arc
outrepassé), Riad (tadelakt, vert zellige, terracotta), Atlas (vert et or
institutionnel) — notées par trois juges (jury design, patron de PME marocaine,
ingénieur WeasyPrint) sur premium / marocain / sans cliché / lisibilité / marque /
faisabilité. **Khatam gagne à l'unanimité** (143 points contre 121-122 et 107) ; la
synthèse greffe : Fraunces 400 au lieu de 300 (réponse au « trop léger »), fenêtre en arc
pour la photo (de Majorelle, sans clipPath), double filet encre + or et laiton #7A5C1E
comme seul or lisible en texte (d'Atlas), accroche en italique (de Riad), QR dans la
Basique.

**Système** : marine #0F2345 en aplats tramés d'un carreau khatam (étoile à huit
branches au trait, SVG base64, jamais d'opacité), or #C9A04E en filets et losanges
seulement, bleu royal #1E4A8C réservé aux données, contrastes WCAG mesurés (script du
panel). Une seule marque ; seul le papier change (#FAF8F3 Signature, blanc ailleurs).

| Édition | Pages | Contenu | Aplat |
|---|---|---|---|
| Signature | 3 | tout le devis actuel + énergie mois par mois + position nette 25 ans ; photo en arc, héros 60 pt, bloc prix marine, cartouche d'accord | ≈ 44 % en page 1 |
| Normale | 3 | exactement le contenu actuel, registre de six faits, prix sur papier ; variante A (garanties + échéancier en page 2) puis B | bandeau 64 mm |
| Basique | 1 (2 si tableau long) | titre, client, réserve, trois chiffres, tableau simple, chaîne de totaux, échéancier et garanties sur une ligne, conditions, QR, accord, bande légale ; FR/AR du catalogue | bandeau 30 mm, pied à filets |

**Vérifié** : 15 rendus fixtures + devis réel DEV-202610-0119 + arabe, pages exactes ;
parité des ancres de chiffres avec le moteur actuel. **À signaler au moteur** : la bande
légale servie porte « Gérant : … » (contraire à D-APDF) ; la société TAQINOR Solutions
n'a pas de logo dans son profil (les éditions impriment la marque en lettres).

**Critique adversariale (Workflow, 3 lentilles × 3 éditions, 62 contre-vérifications) :**
59 constats confirmés. 43 corrigés dans la foulée : trame khatam lisible et rognée à sa
boîte (plus de tirets parasites), Fraunces 600 vendorisé pour les titres et chiffres
(réponse au « trop léger »), vert zellige #0E6B53 comme accent de données et or aligné
sur le logo, frise or sous les bandeaux des trois éditions, arc en fer à cheval, barres
de facture avec la part servie en 20 pt, typographie des graphiques au corps du document,
bandeaux intérieurs fixes de 16 mm, garanties en page 2 de la Signature, Basique sur une
page avec P.U./TVA et sous-lignes résumées, arabe selon une règle unique, téléphones
insécables, « MAD » aligné, point de retour au décimal servi, étiquettes MAD servies sur
la courbe, marque en lettres sans logo. 14 hors périmètre des éditions, à traiter au
moteur ou dans la fixture : « Gérant : … » dans la bande légale (D-APDF), fixture hôtel
incohérente (Σ lignes ≠ sous-total, TVA, retour, remplacement onduleur repris du 461),
raison sociale et précision du kWc servies, deux listes d'étapes héritées, photo unique
pour tous les clients (décision : n'afficher l'arc qu'avec une photo du site).

## Révision du 29/10 (soir) — UNE édition, « Khatam », sur le devis actuel

Décision du fondateur (29/10) : garder une seule version, **celle que nous avions**, et y
ajouter la touche marocaine de la Signature et une part de son écriture — « le style actuel,
en mieux ». Signature et Basique sont retirées (`git rm`), Normale devient **Khatam**
(`commercial_editions/khatam/`), reconstruite sur la grammaire exacte des trois pages du moteur
(`commercial/cover.py`, `equip.py`, `trust.py`) : même contenu, même ordre, mêmes marges
(14 mm), mêmes blocs (héros, tuiles, note autoconsommation, investissement, énergie mois par
mois, prochaines étapes et QR ; tableau, chaîne de totaux, note, clauses, option batterie,
options proposées, surplus, case d'activité, installation en bref ; étapes, garanties,
échéancier, financement, services, bases du calcul, conditions, bon pour accord, bande légale).

**Ce qui change, et seulement cela** : héros marine tramé khatam avec filet et frise or et la
photo dans une fenêtre en arc outrepassé (colonne de titre 116 mm) ; bandeaux intérieurs de
16 mm tramés ; tuiles à filet or (plus de pastilles orange), économie en vert zellige ;
investissement sur bloc marine à double filet ; rangée Total TTC sur marine ; puces en étoile,
numéros d'étapes dans l'octogone, garanties Fraunces 600 séparées par des filets or, bon pour
accord en cartouche à double filet ; Fraunces 600 pour titres et chiffres, IBM Plex Sans
(chiffres tabulaires) pour le texte ; arabe du catalogue à côté de la référence, de l'économie,
de l'investissement, du Total TTC, des titres de page 3 et du bon pour accord (désactivé hors
document français). Le logo suit désormais `quote_engine.logo.css_boite` (R3 de `main`).

**Vérifié le 29/10 au soir** : 5 fixtures + devis réel DEV-202610-0119 + arabe, 3 pages
exactes au palier 0 ; parité des ancres de chiffres avec le moteur actuel (hôtel, boulangerie,
café, sans étude : aucune différence, aucun nombre hors base). Toujours non branchée (règle #4) :
rendue par `apercu.rendre` seulement.

## Révision du 30/10 — cas de référence unique, sans arabe, sans photo de stock

Fondateur (30/10) : pas d'arabe ; aucune information étrangère au dossier ; le devis de la
boulangerie (DEV-202610-0119, lead 1637) est LE cas de référence, toujours rendu à partir de ce
que l'ERP sert ; comparer avec le PDF que l'ERP rend réellement, pas avec un rendu local.

**Fait** : l'édition n'imprime plus d'arabe (libellés du catalogue retirés de la couverture, de
la page 2 et de la page 3) ; la fenêtre en arc n'apparaît qu'avec une photo DU SITE servie par le
devis (`roof_photo`), jamais la photothèque — la boulangerie n'en a pas, le héros est plein. La
charge utile et le PDF de référence sont lus sur le serveur de production (lecture seule, même
chemin que `/proposal` : `build_quote_data` + `echapper_textes_client` + renderer commercial,
sans dépôt MinIO) ; depuis le 29/10 seul le logo de la société a changé dans l'ERP (139 Ko).
L'édition est rendue sur la charge utile ÉCHAPPÉE, comme le moteur.

**Écart constaté dans le moteur actuel (hors édition)** : pour ce devis, le PDF rendu par l'ERP
tient en 3 pages mais SANS énergie mois par mois, prochaines étapes, QR, « Votre installation en
bref » ni « Bases du calcul ». Au palier 0 le document fait 4 pages : la fiche « en bref »,
ancrée au bas de la page 2 (`commercial/equip.py`), déborde d'une ligne depuis que le
regroupement R3 (28/10) a ajouté la ligne « Supervision & comptage » ; `document_adaptatif`
monte alors de palier jusqu'à céder ces cinq blocs. Correction à faire au moteur (la fiche doit
suivre le tableau), pas dans l'édition — qui, elle, garde les cinq blocs en 3 pages.

**Vérification du 30/10 (Workflow, 4 lentilles × opus + 2 contre-vérificateurs par constat, 32
agents)** : 20 constats confirmés, 2 réfutés. Corrigés dans l'édition : légende « Réalisation »
sous une photo du site (texte inventé, retiré), clés de graphique du catalogue (`ci_gr_*`) à la
place de clés nouvelles, en-tête « Total HT » comme le moteur, Total TTC de la page 2 en Fraunces,
trame posée sur la rangée (plus de raccord), bandeau des pages 2-3 réduit au logo (surtitre et
référence imprimés une fois), icône de catégorie en or sur le marine, pied centré, titre sur une
ligne, numéros d'étapes alignés, adresse de la proposition insécable, mentions ≥ 6,8 pt, titre
« Garanties » au style des titres de page, restes de code arabe retirés (police, `ar()`,
paramètres). Diagnostic du moteur affiné par la lentille « moteur » (reproduit deux fois en
conteneur neuf) : au palier 0 le div vide `.c2-tot-sp` (vertical-align baseline) gonfle la rangée
des totaux de ≈ 295 pt ; le document fait 4 pages ; `document_adaptatif` ne monte pas de palier
mais passe directement à `_sans_graphiques` et cède les cédables de la page 1 aussi. Correction
minimale au moteur : `vertical-align:top` sur `.c2-tot-sp` / `.c2-tot-box` dans
`commercial/equip.py` (vérifié : 3 pages au palier 0, les cinq blocs rendus).

## Révision du 30/10 (suite) — photo et courbe de retour rétablies

Fondateur : la photo de l'installation dans la fenêtre marocaine et la courbe des retours sur
25 ans devaient rester. Rétablies : la fenêtre en arc montre la photo du site servie par le
devis (`roof_photo`) ou, sinon, **la plus grande installation réelle de la photothèque**
(`quote_engine/assets/installations/`), légendée « Réalisation {société} » ; la page 2 porte
« Votre retour » — position nette cumulée servie (`flux.cumul_mad`), jalons, TRI — cédée aux
paliers denses (≥ 2).

**Photothèque (à corriger côté moteur, décision fondateur)** : il n'y a aucune photo
« commercial », et le repli universel `default.jpg` est la petite installation résidentielle
(≈ 5 kW) — c'est elle que le moteur sert à tout devis C&I. Deux fichiers portent une puissance
fausse : `industriel-45-couchant.jpg` et `residentiel-18-reflet.jpg` sont deux vues du même
site, El Jadida 17,04 kWc (réf. 468, `apps/web/src/lib/caseStudies.ts`). Renommer en
`residentiel-17-couchant.jpg` / `residentiel-17-reflet.jpg` corrige aussi le choix « puissance
la plus proche » des couvertures résidentielles. L'édition accepte `_photo_realisation`
(fragment de nom) pour l'étude.

## 30/10 — variante « sans limite de toit, avec batterie » (moteur de l'ERP)

Fondateur : « make the version with battery (if you take out the size of the roof it will
increase the number of panels and offer the battery as well) ». Construite avec LE moteur de
l'ERP (`creation_auto.build_devis_auto` → `_build_devis_auto_ci`, composition
`moteur_ci`), jamais à la main, sur une base locale isolée `erp_khatam` (clone de la base
locale) où le contexte de prod a été chargé en lecture seule sous des pk décalés de 100 000 :
société 1 + profil, 224 produits + 93 fiches techniques, lead 1637, client 189, tiers.
Témoin (surface 200 m² gardée) : 49 panneaux, 35,035 kWc, 21 lignes, offre « sans » seule —
identique au devis 461 de prod (reproduction vérifiée). Sans surface déclarée
(`surface_toiture_m2 = None` sur la copie locale du lead, `batterie_souhaitee = les_deux`) :
**77 panneaux, 55,055 kWc** (arrêt « horizon marginal » de la règle des 10 ans), **deux
options** — sans batterie 294 100 MAD TTC (économie 73 842 MAD HT/an, retour 3,4 ans, 41 %
couverts) ; avec batterie 144 panneaux / 102,96 kWc, 6 × Deye 15 kW hybrides, 15 × Dyness
PowerBrick 16 kWh, 1 195 400 MAD TTC (économie 177 180 MAD HT/an, 98 % couverts) — c'est la
règle « panneaux ajoutés jusqu'à batterie pleine » (26/10) appliquée au talon de nuit d'une
boulangerie ; alerte interne du moteur : 4 batteries écartées (fiche sans capacité utile ni
tension nominale). Les deux rendus (moteur actuel et Khatam) tiennent en 3 pages ; le logo et le
QR viennent de la charge utile de prod (pièces jointes hors du contexte local).

**30/10 — règle de la banque contestée par le fondateur** (« the battery should be full, I never
said add 6 batteries… the calculator should calculate the right number of batteries ; if I add
batteries manually, more panels to fill them »). Ce que fait `moteur_ci/batterie.py` : besoin =
toute la consommation hors fenêtre solaire d'un jour moyen (boulangerie, 70 % la nuit : 229 kWh)
→ banque = le moins de modules qui la couvre (15 × 15,27 kWh) → panneaux ajoutés jusqu'au
remplissage tous les mois (144) → hybrides sur la puissance de charge (6 × 15 kW). Balayage de
la banque forcée à n modules, le reste de la chaîne inchangé (base locale `erp_khatam`,
`scratchpad/batterie/balayage_banque.py`) — option « avec », coût de vente HT, économie HT/an,
retour simple :

| modules | kWh utiles | panneaux | coût HT | économie/an | retour |
|---|---|---|---|---|---|
| 1 | 15 | 77 | 338 339 | 80 986 | 4,2 ans |
| 2 | 31 | 77 | 367 505 | 88 130 | 4,2 |
| 4 | 61 | 77 | 425 839 | 102 418 | 4,2 |
| 6 | 92 | 85 | 526 315 | 117 233 | 4,5 |
| 8 | 122 | 105 | 643 193 | 135 600 | 4,8 |
| 10 | 153 | 112 | 737 542 | 150 147 | 5,0 |
| 15 | 229 | 144 | 1 013 572 | 177 180 | 5,8 |

Lecture : jusqu'à 4 modules (61 kWh) le champ de la règle des 10 ans (77 panneaux) remplit déjà
la banque ; au-delà, chaque module tire des panneaux. Retour marginal par module : ≈ 4 ans
jusqu'à 4, 6,4-6,8 ans de 4 à 10, 10,2 ans de 10 à 15. Règles candidates : (A) banque = ce que
le surplus du champ « sans » remplit chaque jour du mois le plus bas (4 modules ici ; une banque
ajoutée à la main tire ses panneaux) ; (B) règle marginale des 10 ans sur les modules
(≈ 10-12) ; (C) l'actuelle, toute la nuit (15). Décision fondateur attendue ; changement à
faire dans le moteur (`moteur_ci/batterie.py::besoin_nocturne_kwh` / `choisir_banque`), pas
dans l'édition.
