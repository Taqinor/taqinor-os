# R1 — Beauté et simplicité d'un outil de calepinage (recherche web, lue le 22/11/2026)

## Comment lire ce rapport (honnêteté sur la preuve)

- Outil utilisé : lecture de pages en TEXTE (WebFetch) et recherche web. Je n'ai VU aucune capture ni aucune vidéo : je ne peux donc jamais écrire « j'ai vu l'écran ». Tout ce qui décrit un écran vient d'un texte (page produit, notes de version, centre d'aide).
- Étiquettes de preuve utilisées plus bas :
  - [P] = page de l'éditeur ou source primaire lue en entier par moi dans cette session.
  - [R] = seulement un résumé de moteur de recherche, page non relue par moi.
  - [T] = tiers (blog, comparateur) : à prendre avec précaution.
  - [E] = affirmation de l'éditeur (marketing), non vérifiée de façon indépendante.
  - [PROP] = proposition de ma part (pas une source) : une consigne de design à tester.
  - [CALC] = valeur calculée par moi ici (contrastes WCAG calculés avec un script Python ; palettes lues dans matplotlib local).
- Toute date de source est donnée ; date de lecture = 22/11/2026 pour toutes.
- Aucun nom de société, de personne ou de projet du fondateur n'a été envoyé aux services : seulement des noms de produits publics.

---

## A. Dix constats : ce qui sépare « correct » de « superbe »

1. **Le décor s'efface, le contenu mène.** Linear, refonte du 12/03/2026 : barre latérale « quelques crans plus sombre » pour que la zone de contenu domine, moins de séparateurs, séparateurs adoucis et arrondis, icônes plus petites et moins nombreuses, fonds colorés d'icônes d'équipe retirés, gris passés du bleuté à un gris légèrement plus chaud [P] https://linear.app/now/behind-the-latest-design-refresh (12/03/2026).
   Consigne [PROP] : la coque (bandeau + rail) est moins lumineuse que la carte et le panneau d'étape ; traits de séparation à 8-10 % d'opacité, jamais de cadre plein autour de chaque bloc ; icônes du rail 18-20 px, sans pastille de couleur sauf l'étape active.

2. **Un thème = 3 réglages, pas 98.** Linear 2024 : thème généré dans l'espace LCH (clarté perçue uniforme), 98 variables réduites à 3 (couleur de base, accent, contraste) ; texte et icônes neutres plus sombres en clair, plus clairs en sombre ; surfaces par étages d'élévation (fond, avant-plan, panneaux, dialogues, modales) [P] https://linear.app/now/how-we-redesigned-the-linear-ui (28/03/2024).
   Consigne [PROP] : définir le bleu nuit, l'or et les gris en OKLCH (même famille que LCH), n'écrire à la main que 3 entrées (base, accent, contraste) ; générer 5 étages d'élévation par écart de clarté fixe (ex. +3 à +4 points de L par étage en sombre).

3. **Une échelle de couleurs à rôles fixes.** Vercel Geist : 10 échelles, 10 pas chacune ; 100-300 = fonds (repos / survol / actif), 400-600 = bordures (repos / survol / actif), 700-800 = fonds à fort contraste, 900 = texte secondaire/icônes, 1000 = texte principal ; deux fonds de page seulement [P] https://vercel.com/geist/colors (lu 22/11/2026, page non datée).
   Consigne [PROP] : même grammaire pour le bleu nuit, l'or et le gris : un designer sait toujours quel pas prendre ; pas plus de 2 fonds de page.

4. **Deux voix typographiques, pas une.** Linear : Inter Display pour les titres (traits plus lourds, espacement plus serré), Inter pour le reste [P, mars 2024, même page que le constat 2 ; version « Inter Display seulement » 2026 = [T] sspai.com]. Notion Calendar (critique tierce) : titre 64 px à crénage serré, grille à 1 px à 9 % d'opacité, chiffres d'heure tabulaires [T] https://blakecrosley.com/guides/design/notion-calendar.
   Consigne [PROP] : Archivo (titres et gros chiffres, axe de largeur 62-125 et graisse 100-900, vérifié sur le dépôt Google Fonts, voir C) à crénage −1 % à −2 % pour tout texte ≥ 28 px ; Hanken Grotesk pour l'interface ; ne jamais descendre sous 12 px (11 px réservés aux légendes de carte).

5. **Les chiffres sont traités comme du dessin.** MDN : `font-variant-numeric: tabular-nums` rend tous les chiffres de même largeur (alignement en colonnes) [P] https://developer.mozilla.org/en-US/docs/Web/CSS/font-variant-numeric. Geist : la classe d'étiquette 13 px est la classe « chiffres » tabulaire [P https://vercel.com/geist/typography]. Stripe (reconstruction tierce, non officielle) : `tnum` sur chiffres financiers [T https://www.shadcn.io/design/stripe].
   Consigne [PROP] : chiffre héros 48-56 px, graisse 600, crénage −2 % ; unité (kWc, kWh/an, MAD, %) à 16-18 px, graisse 500, couleur texte secondaire (≈ 60 % d'opacité) alignée sur la ligne de base ; tabular-nums sur TOUTE cellule numérique ; espace fine insécable entre nombre et unité. À vérifier : que Archivo et Hanken Grotesk contiennent la fonction `tnum` (non vérifié ; si absente, utiliser Geist Mono ou Inter Tight pour les tableaux).

6. **Ne pas tout faire flotter : les panneaux fixes ont gagné chez Figma.** Figma a testé des panneaux flottants (UI3) puis les a refixés au lancement général (01/10/2024, disponible à tous le 10/10/2024) : « ils ralentissaient les gens », cernaient le canevas sur petits écrans, éloignaient les règles du dessin. Gardé : barres d'outils flottantes EN BAS de tous les produits ; « Minimize UI » (replie les panneaux latéraux) remplace « Hide UI » [P] https://www.figma.com/blog/our-approach-to-designing-ui3/ (01/10/2024).
   Consigne [PROP] : conserver le panneau d'étape fixe à droite (déjà dans les maquettes) ; outils de carte dans un dock flottant bas-centre (hauteur 44-48 px, rayon 14 px) ; bouton « Plein plan » qui replie rail + panneau en une touche (raccourci F).

7. **Le verre dépoli, mais avec retenue et plan B.** Linear (21/10/2025) : a choisi flou + masquage + éclairage, a ABANDONNÉ la réfraction du « Liquid Glass » d'Apple parce qu'elle « peut rendre les interfaces denses plus difficiles à lire » ; sous « Augmenter le contraste », contours pleins [P] https://linear.app/blog/linear-liquid-glass (21/10/2025).
   Consigne [PROP] : verre uniquement sur les éléments qui flottent sur la carte (dock, légende, bulles de cote) : flou 16-24 px, opacité de fond ≥ 72 %, contour 1 px blanc à 12 %, ombre douce ; jamais sur le panneau d'étape ; repli plein opaque avec `prefers-contrast: more` et `prefers-reduced-transparency`.

8. **Le mouvement est court, sorti en douceur, et coupé sur demande.** NN/g : retour simple ~100 ms ; la plupart des animations 100-400 ms ; changement d'écran important 200-300 ms ; fenêtre qui apparaît ~300 ms, qui disparaît 200-250 ms ; éviter ≥ 500 ms ; ease-out à l'entrée, ease-in à la sortie ; respecter « réduire les animations » [P] https://www.nngroup.com/articles/animation-duration/ (lu 22/11/2026, non daté). Courbe Material « emphasized decelerate » cubic-bezier(0.05, 0.7, 0.1, 1) [T, guide communautaire, https://camoa.github.io/dev-guides/css/css-craft/motion-design-tokens].
   Consigne [PROP] : tokens 120 ms (survol/bascule), 220 ms (panneaux, popovers), 320 ms (changement d'étape, révélation des chiffres) ; entrée `cubic-bezier(0.05,0.7,0.1,1)`, sortie `cubic-bezier(0.3,0,0.8,0.15)` ; `prefers-reduced-motion` → fondu 80 ms seulement.

9. **La lumière de la carte raconte l'heure.** Mapbox Standard : `lightPreset` = dawn / day / dusk / night, change couleur de température, direction des ombres et intensité des lumières ambiante et directionnelle sur toute la carte ; 3D bâtiments/arbres/repères activables séparément ; thèmes default / faded / monochrome [P] https://docs.mapbox.com/map-styles/standard/guides/ (lu 22/11/2026). Aurora (blog graphismes, non daté) : passage d'une lumière ambiante uniforme à un éclairage par image (carte d'environnement ciel/sol, three.js), couleurs neutres du midi au coucher, plus de teinte rougeâtre à midi [P] https://aurorasolar.com/blog/feeling-the-sun-behind-the-scenes-with-aurora-graphics/. Aucun chiffre donné (ni ombres, ni matériaux).
   Consigne [PROP] : curseur de soleil (heure x jour) qui pilote DIRECTION de l'ombre + température de couleur (≈ 4 500 K à l'aube/crépuscule, 6 000-6 500 K à midi) ; satellite légèrement désaturé (−15 % de saturation, +0 à −8 % de luminosité) pour que le calepinage ressorte ; quatre préréglages nommés (Matin, Midi, Soir, Hiver) plutôt qu'un curseur seul.

10. **Les résultats sont racontés d'une seule source, avec les pertes montrées.** Reonic : une seule simulation (pas de 15 min sur 20 ans) alimente tous les chiffres de l'offre ; score de 0 à 10 par panneau ; PDF jusqu'à cinq vues 3D [E, page lue] https://reonic.com/en-gb/product/360h/planning/. PVsyst, HelioScope, Solargis : diagramme de pertes en cascade / Sankey de l'irradiation jusqu'au réseau [R/T : https://help-center.helioscope.com/hc/en-us/articles/8536898678803 ; https://kb.solargis.com/docs/solargis-evaluate-pv-system-losses-in-detail] ; attention relevée : les % de pertes PVsyst ne partent pas tous de la même base, donc les additionner trompe.
   Consigne [PROP] : un seul chiffre héros (production kWh/an ou économie MAD/an selon le rôle de l'écran), les 3-4 chiffres secondaires à côté, puis UNE cascade de pertes en 6-8 barres où chaque barre dit « par rapport à quoi » ; les mêmes nombres, aux mêmes arrondis, à l'écran et au PDF (règle du moteur de devis de la maison).

---

## B. Idées par écran (3 à 6 chacun)

### Liste (des études)
- Ligne = vignette satellite carrée 56-64 px (rayon 10 px) + nom + kWc en chiffre tabulaire + pastille d'état ; densité ~56 px/ligne ; survol = ombre légère, pas de changement de fond. Source : Linear 12/03/2026 (moins de séparateurs, icônes plus petites) [P].
- État vide illustré par une vraie vignette de carte grisée + une seule action dorée « Nouvelle étude » [PROP].
- Squelettes (gris animés 1,2 s) pour les vignettes pendant le chargement, jamais un spinner plein écran [PROP].
- Palette de commandes (Ctrl/Cmd+K) : ouvrir une étude, créer, changer d'étape ; Rayon met l'accent sur « commandes » précises en plus des actions rapides [P https://www.rayon.design/blog/rayon-foundations, daté 25/10/2023 mais métadonnées 19/11/2026 : dates contradictoires].
- Filtres en pastilles au-dessus de la liste (Tous / En cours / Envoyés), pas de colonne de filtres [PROP].

### Démarrage (adresse → toit)
- Deux entrées seulement : adresse + facture mensuelle moyenne. Aurora Lead Capture : les pages obligatoires avant résultat = accueil, adresse, facture ; adresse et facture « ne peuvent pas être retirées » car elles servent à générer le modèle 3D ; âge/matériau du toit sont optionnels [R, https://aurorasolar.com/blog/get-solar-leads-hooked-with-lead-capture-ai-customizations ; la page directe a renvoyé 404 à ma lecture].
- Aurora AI : « modèle 3D du toit en moins de 10 secondes à partir d'une adresse et d'une facture » [E, page lue https://aurorasolar.com/aurora-ai/, sans date, pied de page 2026].
- Écran de génération avec carte de statut sur la vue satellite (OpenSolar Ada : « Auto Design Generating » sur la propriété, limites surlignées) [P, texte de page https://www.opensolar.com/auto-design/].
- Si l'imagerie est mauvaise : bascule explicite vers « esquisse 2D » (OpenSolar, outil d'esquisse de pans quand la qualité d'image est faible, notes OS 3.0) [P https://www.opensolar.com/?p=14518].

### Toit
- Dessin avec aimantation à 90° / 180° et glisser-déposer des nœuds au lieu de clics multiples ; arêtes du toit plus visibles ; cliquer un pan sélectionne le pan, pas le groupe (OpenSolar OS 3.0) [P].
- Reonic : forme du toit, pente par arête, obstacles avec hauteur, retraits de bord ; détection automatique OpenStreetMap à contrôler et corriger [E/P page lue].
- Cotes en bulles de verre dépoli sur les arêtes (longueur en m, 1 décimale), unité en plus petit [PROP, constat 5/7].
- Source de 3D à choisir : Google Photorealistic 3D Tiles est un maillage texturé d'imagerie haute résolution, mais la page ne dit rien de la qualité des toits, exige l'attribution et une nouvelle requête racine après 3 h ; les facturations dans l'EEE ont des conditions différentes depuis le 08/07/2025 [P https://developers.google.com/maps/documentation/tile/3d-tiles].
- Un seul panneau d'étape court : « Contour → Pente/azimut → Obstacles » en 3 lignes, pas un formulaire long [PROP].

### Panneaux
- Remplissage automatique d'abord, retouche ensuite : Reonic annonce que la grille automatique atteint « typiquement 80 à 90 % » de la disposition finale [E] ; OpenSolar place les panneaux automatiquement avec pitch, azimut et ombrage calculés sans saisie [E].
- Au survol d'un groupe : panneau latéral « Groupe 2 : pose à plat, azimut 213,5°, pente 20,5°, accès solaire annuel » (OpenSolar, texte de la capture décrite) [P].
- Résumé flottant « 41 panneaux » sur le côté droit (OpenSolar) [P] : à reprendre en chiffre héros kWc.
- Score par panneau 0-10 (Reonic) ou % d'accès solaire par panneau (Aurora « Irradiance on modules » : valeurs d'irradiance par module pour repérer l'ombrage inter-rangs et celui des obstacles) [R https://www.aurorasolar.com/smarter-solar-design-with-irradiance-on-modules].
- Carte d'ensoleillement activable en un bouton avec légende en bas (échelle chiffrée, voir C) [PROP].
- Changer le module sans perdre la disposition (Reonic) [E].

### Électrique
- Auto-stringing : Solargraf 2025 a ajouté le stringing automatique ; OpenSolar a accéléré « Auto String » de ~20 s à 3-5 s (notes OS 3.0) [P].
- Reonic signale les strings dont le courant dépasse la limite de l'onduleur [E] : le message doit nommer le chiffre (« 14,2 A > 13,5 A ») avec un seul bouton de correction.
- Un voyant « Conforme / À revoir » en haut du panneau, rien d'autre tant que tout est vert [PROP, principe Dia de la « première expérience sans friction » : https://browsercompany.substack.com/p/the-strategy-behind-dias-design, R].
- OpenSolar : configurations de schéma unifilaire plus grandes dans OS 3.11 (17/09/2026) [P https://www.opensolar.com/product-updates/].

### Schéma (unifilaire)
- Reonic génère le schéma automatiquement des composants planifiés, modifiable à la main ; une fonction IA applique des changements décrits en une phrase (selon réglages) [E].
- Trait 1,5 px, symboles 24 px, texte 12 px, un seul accent (or) pour le chemin sélectionné [PROP].
- Mode lecture « présentation » : plein écran, sans poignées d'édition (Felt a un plein écran avec Cmd+. : https://felt.com/blog/ui-upgrades, 30/11/2023) [P].
- Export PDF identique à l'écran, mêmes polices (Solargraf 2025 : aperçu multi-appareils et PDF identique au web) [P https://www.solargraf.com/blog/solargraf-2025-redefining-speed-precision-and-growth].

### Résultats
- Bento : 1 grande carte héros (production ou économie) + 4 petites (couverture, autoconsommation, retour, CO2) + 1 carte large (courbe du jour type) + 1 carte large (cascade de pertes) [PROP, constat 10].
- Anneau d'autoconsommation (part consommée sur place / part injectée) à 3 chiffres autour : couverture %, autoconsommation %, excédent kWh [PROP].
- Jour type : deux courbes superposées (production, consommation), remplissage à 18 % d'opacité, curseur de saison [PROP].
- PV*SOL premium 2026 (sortie 11/2025) : présentation client exportable en PDF ou DOCX après le calcul [R https://www.solarserver.de/2025/11/27/valentin-stellt-pv-planungssoftware-pvsol-premium-2026-vor/].
- Les hypothèses par défaut au-dessus des chiffres dans une ligne repliable : « Basé sur : orientation ..., pertes 14 %, facture 1 200 MAD ... » (voir section simplicité) [PROP].

### Documents
- Un aperçu à gauche (page par page) et trois cases à droite ; le bouton doré « Générer ». Solargraf : aperçu multi-appareils et modèles ; OpenSolar : aperçu en direct pour modifications de propositions « Scroll » (OS 3.9, 24/07/2026) [P product-updates].
- Pas d'option qui ne change pas le PDF : le nombre de pages affiché doit être exact (règle maison).
- État de génération avec progression en trois temps (Mise en page, Graphiques, Assemblage) [PROP].

### Présentation client (plein écran)
- Mode « Présentation » : coque masquée, carte 3D en fond, un chapitre à la fois (OpenSolar Sales Machine : chapitres Maison / Énergie / Économies / Valider, comparaison côte à côte des options de système et de paiement ; bêta fermée) [P https://www.opensolar.com/?p=14518].
- Aurora Sales Mode : proposition interactive mobile, performance et impact sur la facture mis à jour en direct quand le système se construit (annonce sept. 2026) [R https://pv-magazine-usa.com/2026/09/22/aurora-solar-updates-platform-to-include-home-electrification-and-new-financing-tools/ ; la page lue ne détaille pas les graphiques].
- Rayon (29/09/2026, tiers) : mode présentation pour éditer des plans en direct avec le client [T https://www.credaily.com/?p=223202].
- Jamais de chiffre d'achat ni de marge ; chiffres héros 64-72 px [PROP].

### Tablette
- Cibles tactiles ≥ 44 px ; dock flottant bas ; panneau d'étape en tiroir latéral 360 px repliable ; geste de pincement et deux doigts pour tourner (cohérence avec Figma : barre d'outils en bas partout [P]).
- Pas de survol : chaque info du survol (valeur d'un panneau) devient une pression longue ou un appui [PROP].

### Téléphone
- Rayon a sorti une application « mobile d'abord » (29/09/2026) [T credaily].
- Carte pleine hauteur + feuille du bas à 3 hauteurs (réduite 88 px / mi-hauteur / pleine) ; rail d'étapes devient un sélecteur à 5 puces en haut [PROP].
- Mode « lecture » d'abord : le téléphone sert à montrer et valider, pas à dessiner le toit [PROP].

---

## Simplicité : ce que j'ai trouvé (tâche 4)

- **Parcours le plus court vers un résultat** : adresse + facture → modèle 3D + panneaux placés (Aurora Lead Capture AI et Aurora AI ; « moins de 10 secondes » [E]). Reonic « Quick Planning » : devis chiffré « en minutes » depuis quelques saisies [E], « Planification 3D complète » plus longue mais fige le nombre exact de modules [E].
- **Conception automatique : ce que l'utilisateur doit encore confirmer.** OpenSolar : la page ne cite aucune confirmation requise ; elle précise « bêta » ; des modèles de système standardisent prix, matériel, retraits (notes OS 3.0) [P]. Reonic : roof/obstacles détectés (OSM) à contrôler, module grid à retoucher [P]. Aurora AI : la page ne dit pas ce qu'il reste à confirmer [P]. => Constat : les éditeurs ne documentent pas bien la confirmation ; le point faible du marché est justement l'annonce honnête de ce qui a été deviné.
- **Annonce des hypothèses par défaut** : je n'ai TROUVÉ aucune source publique décrivant un motif d'interface « valeurs supposées ». Aurora Sales Mode parle de « garde-fous de précision » quand on conçoit en direct avec le client [R]. Le motif ci-dessous est donc [PROP] : une ligne « Hypothèses (5) » repliable sous le chiffre héros, chaque hypothèse = valeur + champ modifiable + pastille « supposé » en or ; modifier une valeur recalcule en < 400 ms et retire la pastille.
- **Mode rapide puis affiner** : Reonic le décrit en deux niveaux (Quick Planning / planification 3D) [E] ; Rayon « Styles pour travailler vite ou en profondeur » [P rayon-foundations] ; OpenSolar bascule 3D → esquisse 2D (modèle plus léger) [P].
- **Nouveautés 2025-2026 à connaître** : OpenSolar OS 3.0 (Ada, voix, auto-design en bêta, widget intégrable) et OS 3.5 → 3.13 (03/03/2026 → 16/11/2026) [P product-updates] ; Aurora : sept. 2026 électrification (pompes à chaleur, bornes VE, batterie) dans une seule proposition, import de scans de drone « bientôt » [P pv-magazine]; Solargraf 2025 : stringing auto, nouveau parcours guidé, LiDAR affiché selon le zoom, voies d'accès pompiers générées depuis la géométrie [P] ; feuille de route « design à un toucher » et flux agentiques [P, annoncée, non livrée] ; Scanifly × IronRidge (01/2026) [R] ; PV*SOL premium 2026 et import 3D via Rexplorer (05/2026) [R].

---

## C. Proposition de langage visuel v2

### Principe
« Atelier nocturne » : la coque est un bleu nuit profond, la carte reste la lumière, l'or marque UNE action par écran. Tout est généré de 3 entrées (constat 2). Deux modes complets, pas un mode sombre bricolé.

### Palette — mode sombre (par défaut sur carte)
Contrastes [CALC] : calculés par script WCAG ici.
- canvas coque : `#0A0F2A` (très proche du `#0c1335` de la marque, un cran plus sombre pour mettre le panneau en relief)
- panneau d'étape / bandeau : `#0C1335` ; carte surélevée : `#121A3F` ; survol : `#1A2350`
- ligne : `rgba(255,255,255,0.08)` ; ligne forte : `rgba(255,255,255,0.16)`
- texte 1 : `#F3F5FB` (17,3:1 sur #0A0F2A) ; texte 2 : `#A4ABCB` (8,3:1) ; texte 3 : `#8087A9` (5,3:1 sur #0A0F2A, 4,8:1 sur #121A3F)
- or (accent) : `#E2B54A` (9,8:1 sur #0A0F2A) ; texte sur or : `#0C1335` (9,4:1)
- info / sélection : `#6C86F2` (5,7:1) ; succès : `#3DBE8B` ; alerte : `#F2A33A` ; erreur : `#F26B5B` (les 3 dernières à valider en contraste sur fonds réels : non calculées).

### Palette — mode clair
- canvas : `#F6F5F2` (gris chaud léger, voir Linear 12/03/2026 : bleuté → plus chaud, sans « boueux ») ; surface : `#FFFFFF` ; surface 2 : `#EFEEEA`
- ligne : `rgba(12,19,53,0.10)` ; ligne forte : `rgba(12,19,53,0.18)`
- texte 1 : `#0C1335` (16,6:1 sur canvas) ; texte 2 : `#4A5072` (7,8:1 sur blanc) ; texte 3 : `#656B8C` (5,2:1 sur blanc, 4,8:1 sur canvas)
- or : fond de bouton `#E2B54A` avec texte `#0C1335` (9,4:1) ; or en TEXTE/trait sur blanc : `#8A6A12` (5,1:1) — l'or vif `#B98A1E` seul n'atteint que 3,1:1 sur blanc : trait de graphique oui (≥ 3:1), texte non.
- info `#1F4FD8` (6,6:1 sur blanc) ; succès `#1E7A57` (5,3:1) ; erreur/alerte `#C2410C` (5,2:1).
- Règle d'accessibilité : composants d'interface et objets graphiques ≥ 3:1 contre leur voisin ; les barres/tranches de graphique doivent aussi se distinguer entre elles ; si les valeurs sont écrites en texte, l'exigence tombe pour la partie graphique [P https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html].

### Typographie (toutes sur Google Fonts, vérifiées dans le dépôt google/fonts)
- **Archivo** (variable, axes `wght` 100-900 et `wdth` 62-125 ; ajoutée 03/12/2016) : titres et chiffres héros ; options : largeur 100-112 pour les gros chiffres.
- **Hanken Grotesk** (variable `wght` 100-900 ; ajoutée 16/11/2022) : interface et texte courant.
- Chiffres/tableaux/cotes : **Geist Mono** (variable `wght` 100-900 ; ajoutée 03/10/2024) ou **Geist** (ajoutée 02/10/2024) si `tnum` manque dans les deux premières (non vérifié).
- Titre éditorial optionnel pour la présentation client : **Instrument Serif** (400 normal et italique ; ajoutée 22/03/2023) ; à ne pas utiliser dans l'outil.
- Échelle (px / hauteur de ligne / graisse), base 4 px, ratio ~1,2 ; en pas de la grille [PROP] :
  - 12/16/500 légendes de carte, 13/18/500 étiquettes, 14/20/400 texte (taille par défaut interface), 16/24/400 texte du panneau, 18/26/600 titre de carte, 24/30/600 titre d'étape, 32/38/600 chiffre secondaire, 48-56/1,0/600 chiffre héros, 64-72/1,0/600 présentation client.
  - Unités à 0,32-0,36 de la taille du chiffre, minimum 12 px.
  - Crénage : −2 % ≥ 48 px, −1 % 24-47 px, 0 en dessous ; tabular-nums partout où un chiffre change.

### Rayons, ombres, grille
- Rayons : 6 px (champs, puces), 10 px (cartes, boutons), 14 px (dock, bulles), 20 px (feuille du bas mobile). Une seule famille ; imbrication : rayon intérieur = extérieur − marge.
- Ombres (3 niveaux, teinte bleu nuit pas noir) : e1 `0 1px 2px rgba(5,8,30,.20)` ; e2 `0 6px 20px rgba(5,8,30,.28)` ; e3 `0 18px 48px rgba(5,8,30,.40)` ; en clair, opacités ÷ 2.
- Grille 4 px ; marges 16 px ; panneau d'étape 360-400 px ; rail 72 px ; bandeau 56 px ; dock 48 px de haut, à 16 px du bord bas.
- Densité : lignes de liste 40/48/56 (compact/normal/aéré), défaut 48.

### Mouvement
- Tokens : 120 ms (survol, bascule), 220 ms (panneaux, popovers), 320 ms (changement d'étape, apparition des chiffres avec comptage 600 ms maximum une seule fois).
- Courbes : entrée `cubic-bezier(0.05, 0.7, 0.1, 1)`, sortie `cubic-bezier(0.3, 0, 0.8, 0.15)`, déplacement de carte `cubic-bezier(0.4, 0, 0.2, 1)`.
- Jamais ≥ 500 ms sur une action fréquente (NN/g). `prefers-reduced-motion` : fondu 80 ms.
- Squelettes : balayage de luminosité 1,2 s, pas de spinner > 400 ms sans squelette.

### Carte
- Satellite : −15 % de saturation, −6 % de luminosité en mode sombre (+0 en clair) ; voile bleu nuit à 12-18 % uniquement sous les panneaux flottants (jamais sur la zone de travail).
- Toit : contour 2 px or `#E2B54A` ; pans en remplissage or à 14 % d'opacité ; panneaux : remplissage `#0C1335` à 78 %, filet blanc 0,75 px à 30 % pour voir les cellules ; sélection : contour `#6C86F2` 2 px + halo 4 px à 25 %.
- Ombres portées dessinées par le soleil du curseur (constat 9) ; jamais d'ombre aveugle.
- Étiquettes de carte : texte 12 px, halo 3 px de la couleur de fond pour rester lisible sur l'image.

### Carte d'ensoleillement (accessible aux daltoniens)
- Pas d'arc-en-ciel (rouge-vert : illisible pour les daltoniens ; l'article cividis le confirme [R https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6070163/]).
- Échelle recommandée : cividis (conçue pour la vision des couleurs altérée ; presque identique pour tous ; luminosité linéaire) [R, même source]. Valeurs lues ici dans matplotlib local [CALC] (7 pas, du moins au plus ensoleillé) : `#00224E` `#2A3F6D` `#575D6D` `#7D7C78` `#A59C74` `#D2C060` `#FEE838`. L'or de marque est proche du haut de l'échelle : cohérence naturelle « jaune = beaucoup de soleil ».
- Alternative plus colorée (moins sûre pour tous) : viridis `#440154` `#443983` `#31688E` `#21918C` `#35B779` `#90D743` `#FDE725` [CALC].
- Opacité de la nappe 55-65 % sur le satellite ; légende horizontale en bas du dock : « % d'ensoleillement annuel » avec bornes chiffrées (ex. 60 % → 100 %) ; lecture par panneau en chiffre aussi (le texte reconduit l'exigence graphique WCAG).
- Ne jamais mélanger deux échelles dans une même vue ; unité explicite. Le Solar API de Google fournit un flux annuel en kWh/kW/an avec -9999 pour les valeurs invalides : masquer avant d'appliquer l'échelle [R https://developers.google.com/maps/documentation/solar/geotiff].

### Graphiques
- Un seul accent par graphique (or) + neutres ; production = or, consommation = bleu `#6C86F2`/`#1F4FD8`, excédent = gris froid ; pertes = dégradé de gris sauf la plus grosse en or foncé.
- Axes sans quadrillage lourd : lignes horizontales à 6-8 % d'opacité, valeurs en texte 2, tabular-nums ; étiquette directe au bout de la courbe plutôt qu'une légende.
- Anneau : épaisseur 14 % du diamètre, bouts arrondis, chiffre au centre en 32/600, unité 14 px.
- Cascade de pertes : 6-8 barres, chacune avec « % de quoi » en sous-texte (constat 10).
- Interaction : infobulle à 120 ms, curseur vertical, tout chiffre copiable.

---

## D. Ce qu'il ne faut PAS copier

- **Tout faire flotter** (UI3 de Figma) : abandonné par Figma lui-même après tests ; gaspille la carte sur petit écran [P].
- **Réfraction / verre très translucide partout** (Liquid Glass) : Linear l'a abandonnée pour la lisibilité des écrans denses [P].
- **Échelles arc-en-ciel / rouge-vert** pour l'ensoleillement : illisibles pour les daltoniens [R].
- **Chiffres de vitesse non vérifiés** (« 3D en 10 s », « 15 s », « 80-90 % ») : affirmations d'éditeur ; ne pas les promettre à l'écran.
- **Surcharge de fonctions de bureau d'études** (PVcase Roof Mount dans AutoCAD, PV*SOL) : puissants mais pas simples ; PVcase n'a pas de 2026 documenté [R].
- **Assistant vocal / chat** comme chemin principal (OpenSolar Ada voix) : original, mais je n'ai trouvé aucune preuve d'usage ni d'exactitude ; à laisser en bonus [E].
- **Largeur de 5 formulaires** de qualification devant le résultat : Aurora garde seulement adresse + facture comme obligatoires [R].
- **Reproduction littérale de Stripe/Notion** d'après des sites tiers : valeurs non officielles [T].
- **Nuées de badges, gradients lourds, ombres noires pures, bords de 1 px à 100 % de contraste** : datent et surchargent ; Linear a justement réduit séparateurs et icônes [P].

---

## E. Non vérifié / pages inaccessibles

- Aucune capture ni vidéo vue (outil texte seulement) : mise en page réelle de Design Mode d'Aurora, Pylon, Arka 360, Enact, Lyra, K2 Base, Otovo/Enpal, HelioScope, RatedPower rooftop : NON vérifiée.
- Aurora : centre d'aide « What's New » et article « How to leverage an irradiance map » = HTTP 403 ; palette de la carte d'irradiance d'Aurora : NON trouvée (inconnue). Notes de version Aurora 2026 non lues ; seules ses notes 2025 apparaissent en résultat de recherche [R].
- Pylon, PVcase, Scanifly, Arka 360, Enact, SolarEdge Designer, RatedPower, PV*SOL : seulement des résultats de recherche ou communiqués ; aucune nouveauté 2026 d'interface confirmée sauf PV*SOL premium 2026 (11/2025) et import 3D Rexplorer (05/2026) [R].
- Solargraf : un blog 2025 lu ; pas de nouveauté 2026. Lyra, K2 Base, Otovo, Enpal : rien d'utile (Enpal : parcours en « quelques étapes » [R], sans nombre).
- OpenSolar : liste de versions 3.5 → 3.13 lue sur la page officielle ; une recherche a donné une date différente pour OS 3.10 (17/09 contre 21/08/2026 sur la page officielle ; j'ai retenu la page officielle) ; page auto-design sans date.
- Linear : l'usage d'Inter Display en 2026 vient d'un tiers ; sa propre page 2024 le dit pour les titres. Les mesures de Linear n'ont aucun chiffre publié.
- Figma, Felt, Rayon, Framer, Arc/Dia, Notion Calendar, Stripe, Apple Maps (3D), Apple HIG Materials : Apple HIG renvoie du contenu non lisible (page JavaScript) ; Apple Maps et Framer non étudiés ; Arc/Dia et Notion Calendar seulement par recherche/tiers ; Felt : refonte 2.0 du 30/11/2023, rien de daté 2026. Stripe : aucune source officielle, tiers uniquement.
- Polices : présence dans Google Fonts vérifiée via le dépôt github.com/google/fonts (METADATA.pb) ; support `tnum` d'Archivo et de Hanken Grotesk NON vérifié.
- Google Photorealistic 3D Tiles : qualité des toits et couverture au Maroc non documentées par la page lue (« nombreuses zones peuplées »).
- Aucune source publique trouvée pour un motif d'interface « valeurs supposées » : section simplicité = [PROP].
