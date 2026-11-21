# B4 — La voix des utilisateurs (benchmark communautaire) — 21/11/2026

Lane lecture seule. Méthode : ~32 recherches web + ~75 pages lues (WebFetch). Aucune connexion, aucun compte. Les sites qui refusent les lecteurs automatiques ont été abandonnés (liste en section 7).

## 0. Honnêteté sur les sources

- **Lisibles et riches (vraies voix d'utilisateurs)** : forum Valentin (PV*SOL) forum.valentin-software.com ; forum-photovoltaique.fr (rubrique PVSYST, 108 sujets, et « Logiciel ou site Internet de Calcul ») ; energiesparhaus.at ; akkudoktor.net ; un fil Trustpilot Reonic (4 avis, tous positifs).
- **Pauvres en voix indépendantes** : Aurora, HelioScope, OpenSolar, Solargraf, Pylon, Scanifly, archelios, Sunny Design, K2 Base, PVcase, Reonic. Pour ceux-là, presque tout vient de blogs de concurrents (SurgePV, Solar Proof, Heaven Green Energy qui dit lui-même utiliser SurgePV), d'articles sponsorisés (Scanifly dans Solar Power World) ou de résumés de moteur de recherche sur des pages G2/Capterra que je n'ai PAS pu ouvrir. Chaque ligne indique « type » : `forum` (vraie voix), `article-vendeur/concurrent` (à pondérer), `résumé-recherche` (page refusée, je ne vois que l'extrait).
- Compte « sources indépendantes » = nombre de sources distinctes LUES qui disent la même chose (1 / 2-3 / beaucoup). Il est bas partout, c'est le reflet réel de ce que j'ai pu lire, pas une mesure de la communauté.
- Aucune citation > 15 mots ; tout est paraphrasé. Les opinions sont marquées (op.).

Abréviations d'URL : `VF` = https://forum.valentin-software.com/topic/ · `FP` = https://forum-photovoltaique.fr/viewtopic.php?t= .

---

## 1. FONCTIONNALITÉS ADORÉES

| Outil | Fonction | Ce que les utilisateurs disent pouvoir faire | URL | Type | Sources |
|---|---|---|---|---|---|
| PVsyst | Diagramme de pertes complet (irradiation → énergie injectée) | Voir où part chaque % ; comparer des variantes sauvegardées ; c'est la référence d'une étude bancable | https://www.lefixea.com/article/what_is_pvsyst14 ; https://www.pvsyst.com/pdf/pdf-tutorials/pvsyst-8/pvsyst-tutorial-v8-grid-connected-en.pdf (via recherche) | article-praticien / tutoriel | 2-3 |
| PVsyst | Ombrage proche en 3D avec effet électrique par chaîne | Un installateur le juge capable « jusqu'au niveau de la chaîne » | FP27905 | forum | 2-3 (FP27905, FP64776) |
| PVsyst | Astuce de l'horizon pour des arbres irréguliers | Modéliser une rangée d'arbres comme un horizon lointain (limites en azimut/hauteur) donne un masque utilisable, écart ~1 % | FP64776 | forum | 1 |
| PVsyst | Standard de crédibilité | Choix par défaut des bureaux d'études et de ceux à l'aise en anglais ; « a bien évolué » | FP25823, https://www.solar-training.org/what-is-the-best-pv-design-software/ | forum / article | 2-3 |
| PV*SOL | Visualisation 3D avec ombrage par module + 3D-vers-simulation | Ombrage à 10 min calculé par module puis moyenné à l'heure | VF2219, https://valentin-software.com (via recherche) | forum | 1-2 |
| PV*SOL | Plan de câblage / plan de chaînes généré | À partir des « zones de modules » nommées (chaîne 1, MPPT 1…) il sort le plan de chaînes et le point de départ du routage | VF10527 | forum (réponse support) | 1 |
| PV*SOL | Comparaison de projets (jusqu'à 6 versions) | Enregistrer chaque option de rétrofit puis comparer | VF10736 | forum (support) | 1 |
| PV*SOL | « Config check » : alerte de tension MPP trop basse, taux de dimensionnement | Un DIY le cite comme garde-fou à la conception | https://akkudoktor.net/t/planung-solaranlage-mit-pv-sol-premium/3534 ; VF2164 | forum | 2-3 |
| PV*SOL | Éditeur de diagrammes (série temporelle / tapis) | Vérifier la puissance réseau heure par heure pour juger un écrêtage | VF6915, VF10826 | forum (support) | 2-3 |
| PV*SOL | Outil « remplacer les modules » (même dimensions) | Passer 300 modules de 430 à 440 W sans refaire le plan | VF6842 | forum | 1 |
| OpenSolar | Gratuit + design/CRM/devis/signature dans un seul outil | Petits installateurs : zéro licence | https://solarproof.com.au/blog/opensolar (concurrent) ; FP57259 | article-concurrent + forum | 2-3 |
| OpenSolar | Maison réelle compliquée modélisée en 3D | 3 pans + 2 toits plats + arbre : prévision « réaliste » après un an ; autoconso prédite 39 % vs 40 % mesurée (utilisateur) | FP57259 | forum | 1 |
| OpenSolar | Import de la conso du fournisseur + tarifs français + devis avec ROI | Devis d'ordre de grandeur rapides pour un commercial (op. d'un installateur) | FP57259 | forum | 1 |
| Aurora | Modèle de toit LIDAR avec hauteurs d'obstacles mesurées | Deux concepteurs sortent le même chiffre ; « avait raison » quand le client contestait | https://www.heavengreenenergy.com/blog/aurora-solar-review ; résumé G2 https://www.g2.com/compare/helioscope-vs-pv-sol-vs-aurora-solar | article-concurrent / résumé-recherche | 2-3 |
| Aurora | Chaîne vente → permis (devis, financement, e-signature, plans permis) | Un seul outil du lead au dossier de permis (US) | https://www.heavengreenenergy.com/blog/aurora-solar-review ; https://sacra.com/chat/h/c37a4c89-992b-4836-962c-6d9d9cef7123/ | article | 2-3 |
| HelioScope | Arbre des pertes + export CSV niveau module | « La raison d'acheter » (op. du blog) : expliquer un rendement ligne par ligne ; relecture par un tiers | https://www.heavengreenenergy.com/blog/helioscope-review | article-concurrent | 1 |
| HelioScope | Implantation rapide de toiture commerciale + stringing + collaboration cloud | Le « cheval de trait » du C&I rapide | https://www.solar-training.org/what-is-the-best-pv-design-software/ | article (op. auteur, distributeur PV*SOL) | 1-2 |
| SolarEdge Designer | Gratuit, auto-remplissage selon carte d'irradiance, zone « orange » tolérée avec avertissement | Mesurer la perte de rendement d'un tracé ; un utilisateur a ramené -2 % à -0,3 % en optimisant | https://www.energiesparhaus.at/forum-planung-einer-anlage-mit-dem-solaredge-designer/68694 | forum | 1 |
| Pylon | Devis haute résolution en ~2 min, 4 $ par projet | Pas d'abonnement, bon pour débutants | https://www.capterra.com/p/217697/Pylon/reviews/ (résumé-recherche, page refusée) | résumé-recherche | 2-3 (agrégé) |
| Reonic | Conception PV + stockage + borne + PAC dans un même parcours, devis < 15 min | Interface claire, support réactif, offres plus pro | https://uk.trustpilot.com/review/reonic.de | avis | 1 (4 avis, un seul 1 étoile non lisible) |
| archelios | Import d'implantation depuis SketchUp ; calcul de besoins plus précis | « Même niveau que PVsyst », un installateur le préfère ; en français | FP25823, FP27905 | forum (2012-2013, ancien) | 2-3 |
| K2 Base | Gratuit, 5 étapes, liste de pièces directe vers webshops ; garantie système 12 → 20 ans si calculé dans l'outil | Planifier la structure avec liste de matériel | https://k2-systems.com/en/digital-services/k2-base/ ; https://akkudoktor.net/t/anlagenplanung-im-selbstbau-24kwp/36809 | vendeur + forum | 2-3 (vendeur surtout) |
| Scanifly | Ombrage par drone « en secondes » remplaçant SunEye/ruban | Plus besoin de grimper ; le client voit le soleil de n'importe où | https://scanifly.com/shading-case-study | témoignage vendeur | 1 |
| PVcase | Tourne dans AutoCAD → interface familière, automatisation | Peu de courbe d'apprentissage pour ceux qui connaissent AutoCAD | résumé G2 via recherche (https://www.g2.com/products/pvcase/reviews, refusé) | résumé-recherche | 2-3 (agrégé) |
| Fabricants (SMA, Fronius, K2…) | Outils en ligne de dimensionnement | Les utilisateurs DIY y recourent pour valider le matériel avant de payer un logiciel | https://akkudoktor.net/t/anlagenplanung-im-selbstbau-24kwp/36809 | forum | 1 |

---

## 2. POINTS DE DOULEUR (les pièges à éviter)

| Outil | Problème | Détail (paraphrase) | URL | Type | Sources |
|---|---|---|---|---|---|
| PVsyst | Courbe d'apprentissage, anglais technique | Plusieurs utilisateurs bloqués par les termes anglais ; l'un a mis longtemps à s'y faire ; interface « franglais » | FP25823 | forum | 2-3 |
| PVsyst | Interface ancienne, semaines de prise en main, Windows seul, pas de devis | Revendication de concurrents (op. non vérifiée) | https://qbitsenergy.com/blog/pvsyst-alternative/ (résumé-recherche) | article-concurrent | beaucoup mais tous concurrents |
| PVsyst | Étude d'ombrage moins « directe » que PV*SOL ; erreur récurrente avec deux orientations | Un essayeur compare les deux essais gratuits | FP27905 | forum | 1 |
| PVsyst | Où mettre l'origine/l'orientation de la scène 3D ? | Orienter la scène entière, pas objet par objet ; origine sans effet sur la course du soleil | FP21692, FP25823 | forum | 2-3 |
| PVsyst | Calepinage grisé, « nombre de sheds », écart modules/chaînes | Le lien entre champ, zone PV et calepinage n'est pas évident | FP38731 | forum | 1 |
| PVsyst | Onduleur à 2 MPPT forcé à 2 entrées ; impossible de dire quelles chaînes vont sur quelle entrée | Contournements manuels pondérés à la main (¼ non ombré, ¾ ombré) | FP38731, FP27653 | forum | 2-3 |
| PVsyst | Micro-onduleurs : schéma qui ne donne pas la répartition attendue | 12 micros → « 11 + 1 » au lieu de 6+6 | FP68814 | forum | 1 |
| PVsyst | Bifacial vertical est-ouest non reproduit (deux pics) | Utilisateur sans réponse d'expert | FP73753 | forum | 1 |
| PVsyst | Rapport : diagramme d'horizon absent 2 fois sur 3 (2012) | Il faut cocher une option d'impression | FP24475 | forum | 1 |
| PVsyst | Base de modules à tenir à la main (fichiers PAN) | Les membres s'échangent des PAN faits main, avec risques de fautes de saisie | FP66690, FP36152 (titre) | forum | 2-3 |
| PVsyst | 3D limité sur les grandes centrales ; import 3D (PVcase) → orientation décalée | Messages d'aire PV ≠ aire du système | https://help.pvcase.com/en/articles/8536198-troubleshoot-pvcase-design-in-pvsyst | article-vendeur | 2-3 |
| PV*SOL | Plantage mémoire (32 bits, ~1,2 Go) même avec 64 Go de RAM | Modèle 3D lourd = crash ; recommandation de simplifier avec MeshLab | VF10889, VF11088 | forum (support) | 2-3 |
| PV*SOL | Plafonds : 7 500 modules surélevés / 10 000 sur toit ; carte 200 × 200 m | Les grands toits (13 000 modules) ne passent qu'en 2D | VF2219, VF10736 | forum | 2-3 |
| PV*SOL | Ombrage irréaliste (acrotère) ; ombrages faux sur modèles importés | Bugs de longue date puis corrigés en 2022 ; les faces arrière d'un cube 3DS | VF2219, VF10797 | forum | 2-3 |
| PV*SOL | Pas d'annulation (Ctrl+Z) en 2D/3D | Demandé de 2019 à aujourd'hui | VF1094, VF1096 | forum | 2-3 |
| PV*SOL | Retirer un module ou changer la pente efface le câblage / la configuration | Demandé depuis 2023, solution = découper en sous-systèmes | VF6842, VF10692 | forum | 2-3 |
| PV*SOL | Plan de câbles seulement en 3D, pas en 2D ; export vers K2 Base : un projet par pan | Aucun changement prévu | VF11167, VF7308 | forum | 2-3 |
| PV*SOL | Imagerie Google périmée ; modèles Rexplorer avec zones hachées inutilisables | Seul recours : redessiner à la main | VF11006, VF10856 | forum | 2-3 |
| PV*SOL | « Pas intuitif », outil de snap intermittent | Un DIY et un utilisateur pro | https://akkudoktor.net/t/anlagenplanung-im-selbstbau-24kwp/36809 ; VF11107 | forum | 2-3 |
| PV*SOL | Courbe de charge : mois de 31 jours plus chargés que février ; pas de plafond de soutirage réseau ; MPPT global uniquement | Comportements « normaux » mais surprenants | VF10825, VF10826, VF11087 | forum (support) | 3 |
| SolarEdge Designer | Accès réservé aux sociétés (numéro de TVA) ; avertissements incohérents | Un particulier n'a pas pu l'utiliser ; limites tantôt acceptées tantôt refusées | https://www.energiesparhaus.at/forum-planung-einer-anlage-mit-dem-solaredge-designer/68694 | forum | 1 |
| OpenSolar | Pas de schéma unifilaire natif → CAD externe ; API devenue payante (04/2026) | Pour installateurs soucieux de conformité | https://solarproof.com.au/blog/opensolar | article-concurrent | 1-2 (concurrents) |
| OpenSolar | Inscription avec données perso ; autoconso jugée fausse par un modérateur ; pas d'étude d'ingénierie | Méfiance sur les données (société australienne) | FP57259 | forum | 1 |
| Aurora | Prix par siège, plans de permis facturés à part, orienté États-Unis, lourd dans le navigateur | Les fonctions utiles dans l'offre haute | https://www.heavengreenenergy.com/blog/aurora-solar-review | article-concurrent | 1-2 |
| Aurora | Relief et végétation imprécis en zones reculées ; courbe d'apprentissage mitigée | Résumé d'avis G2 | https://www.g2.com/products/aurora-solar (résumé-recherche, refusé) | résumé-recherche | 2-3 |
| HelioScope | Stringing / calibre des fils / plusieurs segments pour tester des onduleurs ; gels occasionnels ; licence par siège | Un avis G2 (résumé) | https://www.g2.com/products/helioscope/reviews (refusé) | résumé-recherche | 1-2 |
| Pylon | Pas adapté à l'iPad ; images pas toujours récentes ; limité > 100 kW | Avis Capterra/G2 | https://www.capterra.com/p/217697/Pylon/reviews/ (refusé) | résumé-recherche | 2-3 |
| PVcase | Tracé de tranchées pas toujours respecté, ressources lourdes, licence non flottante | Avis G2 | https://www.g2.com/products/pvcase/reviews (refusé) | résumé-recherche | 2-3 |
| Scanifly (op.) | Drone imposé (marge matériel) ; pensé pour vendre l'enquête sur site | Article sponsorisé par Scanifly lui-même | https://www.solarpowerworldonline.com/2024/08/5-reasons-to-combine-your-drone-program-and-design-software/ | article sponsorisé | 1 |
| Tous (imagerie satellite) | Un quart des conceptions révisées ; un tiers des toits modélisés à distance ratent > 10 % | Chiffre d'un article sponsorisé → à pondérer | https://www.solarpowerworldonline.com/2024/09/why-solar-shade-analysis-is-so-subjective-how-to-fix-it/ | article sponsorisé | 1 |

---

## 3. LISTE DE SOUHAITS (ce que personne ne fait bien)

Source principale : fils « PV*SOL Wishlist » (82 réponses, 42 800 vues) et « Wunschliste » (89 réponses, 34 100 vues) — j'ai lu la page 1 sur 4 de chacun. Les autres lignes viennent de forums ou de sources secondaires.

| # | Souhait | Ce que l'utilisateur veut faire | URL | Type | Sources |
|---|---|---|---|---|---|
| 1 | Annuler / rétablir partout, verrouiller bâtiments pour éviter les faux clics | Ne plus perdre un tracé | VF1094, VF1096 | forum | 2-3 |
| 2 | Cotes précises au tracé : longueur saisie, aimantation 10 cm, 90°, milieu de faîtage | Dessiner un toit réel sans « deviner » | VF1094 | forum | 1 |
| 3 | Remplacer module / onduleur en gardant câblage et chaînes | Mise à jour de catalogue ou chantier modifié | VF1096, VF6842 | forum | 2-3 |
| 4 | Câblage module par module manuel + chaînes sur plusieurs surfaces / plan de câbles pour toit plat | Plan de chaînes réaliste | VF1094, VF1096 | forum | 2-3 |
| 5 | Importer un plan de chaînes dessiné à la main ou d'un autre logiciel | Ne pas ressaisir | VF10527 | forum | 1 |
| 6 | Rapport : photos de visite, texte libre, pages de présentation modifiables, explications pour des clients qui ne comprennent pas les graphiques | Un document client unique | VF1094 (utilisateur « Sander ») | forum | 1 |
| 7 | Envoi d'une présentation électronique avec suivi de ce que le client regarde | Savoir si le client a lu | VF1094 | forum | 1 |
| 8 | Presets de forme de toit (2 pans, L, T), toits en L, lucarnes plus faciles | Gagner du temps de modélisation | VF1096, VF10794 | forum | 2-3 |
| 9 | Pivoter tout un site ou plusieurs bâtiments d'un coup | Plan de masse orienté | VF10941 | forum | 1 |
| 10 | Variantes : onduleurs, avec/sans optimiseurs, échange de module à conditions égales | Comparer sans refaire | VF1096 | forum | 1 |
| 11 | Rapport d'ombrage : une capture automatique, échelle de couleur fixe d'un toit à l'autre, % et kWh par zone | Documenter l'ombrage | VF1094, VF1096 | forum | 2-3 |
| 12 | Dégradation des modules dans la simulation ; horizon d'exploitation distinct | Rendement sur 25 ans | VF1096 | forum | 1 |
| 13 | Profils de charge plausibles (pas d'octobre plus bas que juillet), moyennes de logements plutôt qu'un seul foyer, choix mensuel/journalier | Autoconsommation crédible | VF1096, VF10825 | forum | 2-3 |
| 14 | Simuler stockage AC et DC dans les mêmes conditions, au pas de la minute | Choix de batterie | VF1096 | forum | 1 |
| 15 | Batterie par MPPT (couplage DC) | Hybride | VF1094 | forum | 1 |
| 16 | Plafond de soutirage réseau et injection nulle | Modéliser une limite de raccordement | VF10826 | forum | 1 |
| 17 | Bâtiments et sous-systèmes réutilisables entre projets ; sous-système « existant » pour montrer l'économie d'une extension | Rétrofit | VF1096, VF10736 | forum | 2-3 |
| 18 | Carport, trackers à un axe, supports de toit « léger/ballast » | Autres structures | VF1094, VF1096 | forum | 2-3 |
| 19 | Plus d'espace de carte ; modèles 3D plus gros ; 64 bits ; moins de CPU/GPU | Grands sites | VF1094 | forum | 1 |
| 20 | Accès hors-ligne à la base | Voyager sans réseau | VF1094 | forum | 1 |
| 21 | Rafraîchir l'imagerie ; carte régionale locale (Bayernatlas…) | Voir le vrai toit | VF11006, VF1096 | forum | 2-3 |
| 22 | Aide pour pente / hauteur quand le toit est mal vu (Rexplorer faux, Google Solar jugé mauvais) | Obtenir une géométrie fiable | VF10794, VF10856 | forum | 2-3 |
| 23 | Aucun guide de bout en bout « drone → modèle 3D → import » | Utiliser le photogrammétrique | VF11088 | forum (réponse support : « il n'existe pas ») | 1 |
| 24 | Un seul clic pour « conception complète depuis l'adresse » | Aller plus vite | https://devpost.com/software/kill-the-site-survey (refusé) ; recherche | résumé-recherche | 1 |
| 25 | Visite sur site : fiche structurée avec photos obligatoires, intégrée au design (pas de ressaisie) | Moins d'aller-retour | recherche greenlancer / Scanifly (résumé-recherche, vendeurs) | article | 2-3 (vendeurs) |
| 26 | Schémas unifilaires et plans de site pour installateurs / permis, sans CAD externe | Dossier complet | https://www.opensolar.com/post/your-vote-matters-your-feedback-what-were-doing-about-it/ (vendeur) ; FP75652 | forum + vendeur | 2-3 |
| 27 | Planification pour les FR : un schéma unifilaire sans acheter un CAD (utilisateurs bricolent avec QElectroTech) | Dossier de conformité | FP75652 | forum | 1 |
| 28 | Explications d'une perte inattendue (sizing factor 154 %, tension 519 V, azimut du soleil faux) directement dans l'outil | Ne plus poser la question au support | VF2164, VF10806, VF8531 | forum | 3 |

---

## 4. FLUX DE TRAVAIL RÉELS ET TRANSFERTS MANUELS

| # | Flux décrit | Ce qui se déplace à la main (= opportunité) | Source (type) |
|---|---|---|---|
| 1 | Aurora pour la vente, PVsyst pour le rapport bancable ; « la plupart des équipes C&I paient les deux » | Hypothèses (pertes, météo, horizon) à réaligner entre les deux outils ; chiffres divergents | https://www.surgepv.com/compare/aurora-solar-vs-pvsyst (concurrent) |
| 2 | HelioScope pour l'implantation rapide, export PVsyst en offre haute | Modèle, hypothèses de pertes | https://www.heavengreenenergy.com/blog/helioscope-review (concurrent) |
| 3 | OpenSolar pour la vente, CAD externe pour le schéma unifilaire | Schéma, nomenclature | https://solarproof.com.au/blog/opensolar (concurrent) |
| 4 | PV*SOL : Bing/SketchUp/OBJ drone/Rexplorer → PV*SOL ; puis export par pan vers K2 Base | Géométrie du toit, obstacles proches (Bing ne les amène pas), un projet K2 par pan | VF10794, VF11088, VF10856, VF7308 |
| 5 | DIY : Sunny Design/Designer pour l'implantation, PV*SOL 3D d'essai, SketchUp, crayon, K2 Base pour la structure | Tout, y compris la liste de matériel | https://akkudoktor.net/t/anlagenplanung-im-selbstbau-24kwp/36809 |
| 6 | PVsyst pour la production + archelios Pro pour l'implantation + archelios Calc ou Lise PV pour le dimensionnement électrique | Résultats électriques recopiés vers la simulation | FP69285 |
| 7 | PVsyst : pré-dimensionner l'électrique avec l'outil du fabricant (SMA Design) | Limites MPPT/tension | FP38731 |
| 8 | PVsyst : relever les arbres au compas, rapporteur et fil à plomb, puis tracer un horizon à la main | Hauteurs/angles d'obstacles | FP64776 |
| 9 | PVsyst : cas ombré / non ombré pondérés à la main (¼ / ¾) pour des micro-onduleurs | Pondération, au tableur | FP27653 |
| 10 | PV*SOL : tableur correctif pour la courbe de charge mensuelle | Profil de charge | VF10825 |
| 11 | Débutant : PVGIS + Excel, puis outils fabricants ; PVGIS sert de contrôle de réalité | Rendement recopié | https://www.solar-training.org/what-is-the-best-pv-design-software/ ; FP55271 |
| 12 | Drone/enquête → design : photos et notes ressaisies, shading recalculé | Mesures de toit, hauteurs | https://www.solarpowerworldonline.com/2024/08/5-reasons-to-combine-your-drone-program-and-design-software/ (sponsorisé) |
| 13 | PVcase (AutoCAD) → scène 3D → PVsyst ; orientation et aires à recaler | Orientation, aire PV | https://help.pvcase.com/en/articles/8536198-troubleshoot-pvcase-design-in-pvsyst |
| 14 | Schéma unifilaire dessiné dans QElectroTech (forum FR) | Tout le schéma | FP75652 |

---

## 5. MOTIFS DE QUESTIONS PVsyst / PV*SOL (chaque confusion = endroit où notre module doit expliquer ou décider)

Limite : le forum officiel de PVsyst (forum.pvsyst.com) a refusé la lecture. Pour PVsyst j'ai lu les 108 titres de la rubrique du forum FR et ~14 de ses fils, plus des tutoriels. Les motifs ne sont pas classés par fréquence mesurée ; l'ordre est mon jugement (op.) d'après récurrence des thèmes dans ce que j'ai lu.

### PVsyst
| # | Question récurrente | Source | Ce que notre module devrait faire |
|---|---|---|---|
| P1 | Où placer l'origine et l'orientation de la scène 3D ? | FP21692, FP25823 | Orienter tout le site d'un seul réglage ; aucune origine à choisir |
| P2 | Pourquoi mon ombrage proche est-il élevé (3,9 %) ? Combien est « acceptable » ? | FP21692 | Séparer l'auto-ombrage des rangées de l'ombrage d'objets, et le dire |
| P3 | Comment modéliser des arbres irréguliers ? | FP64776 | Arbre = cylindre/cône avec hauteur et diamètre ; sinon masque d'horizon proposé |
| P4 | Modèle linéaire ou par chaîne ? paysage ou portrait, diodes bypass ? | FP21692 | Choisir automatiquement et afficher la raison ; ne pas demander |
| P5 | Nombre de sheds, calepinage grisé, écart modules/chaînes | FP38731 | Une seule vérité : la disposition posée donne le compte, partout |
| P6 | Combien de rangées/espacement sur toit plat ? | FP38731 | Optimiseur de pas déjà présent (`estimatorBrainV2`) — le rendre visible |
| P7 | Onduleur 2 MPPT avec une seule chaîne ; quelles chaînes sur quelle entrée ? | FP38731, FP27653 | Affectation chaîne → MPPT automatique et visible |
| P8 | Micro-onduleurs : répartition des branches et gain réel attendu | FP27653, FP68814 | Expliquer quand les micros paient (ombrage partiel seulement) |
| P9 | Quel effet du surdimensionnement de l'onduleur sur le rendement ? | FP16494 | Courbe « rendement perdu selon DC/AC » en un graphique |
| P10 | Écrêtage : PNom en kVA, horaire vs sous-horaire (résumé de la doc, fil non lu) | https://forum.pvsyst.com/topic/3160-clipping-loss/ (titre seul) | Nommer la perte « écrêtage » avec sa cause |
| P11 | Diagramme de pertes bifacial : pourquoi les % ne se multiplient pas ? (titre seul) | https://forum.pvsyst.com/topic/4303-can-someone-please-explain-the-diagram-loss-for-bifacial/ | Afficher la base de chaque % |
| P12 | Bifacial vertical est-ouest : deux pics non reproduits | FP73753 | Dire clairement ce qui n'est pas modélisé |
| P13 | Nouveau module : où trouver le PAN, quel coefficient de température ? | FP66690, FP36152 | Fiche module avec les champs essentiels seulement |
| P14 | Pourquoi les estimations divergent selon les sources (PVGIS applique 14 % par défaut) | FP55271 | Montrer la politique de pertes et l'écart avec PVGIS (déjà : `services/validation.py`) |
| P15 | Le diagramme d'horizon n'apparaît pas dans le rapport | FP24475 | Toujours l'imprimer s'il existe |
| P16 | Neige | FP16383 | Perte neige saisie par la société (déjà prévue) |
| P17 | Quel jeu météo choisir ? Les pertes se compensent-elles deux fois ? | https://www.lefixea.com/article/what_is_pvsyst14 | Un seul endroit par perte (règle CALX déjà là) |
| P18 | P50/P90 : quand sont-ils valables ? | https://www.pvsyst.com/pdf/pdf-tutorials/pvsyst-8/pvsyst-tutorial-v8-grid-connected-en.pdf (via recherche) | Texte court d'aide près du P90 |
| P19 | Rendement réel mesuré vs simulé : lequel croire ? (titre seul, fil non lu) | FP35032 | Écart simulé/PVGIS déjà publié (`BE validation.py`) ; ajouter l'écart mesuré quand l'installation tourne (`PoseReelle`) |

### PV*SOL
| # | Question récurrente | Source | Ce que notre module devrait faire |
|---|---|---|---|
| S1 | Taux de dimensionnement « 154,9 » : est-ce normal ? | VF2164 | Expliquer DC/AC et l'écrêtage prévu en une phrase |
| S2 | Pourquoi une Voc maxi de 519 V alors que 9 × 52,9 V = 476 V ? | VF10806 | Afficher la température froide utilisée (nôtre : TMY du site, pas 10 °C par défaut) |
| S3 | Pente 22° saisie mais inclinaison 27° | VF10692 | Dire « faîtage décentré : 22° côté sud, 25° côté nord » |
| S4 | Position du soleil fausse de 12° (heure d'été) | VF8531 | Afficher l'heure légale et l'heure solaire |
| S5 | Impossible de poser des panneaux sur le toit (mode terrain) | VF10745 | Un seul mode, le toit est actif par défaut |
| S6 | Deux chaînes Est + Ouest : où saisir deux orientations ? polystring | VF10850 | Une chaîne = un pan ; les deux orientations sur un MPPT sont gérées (`polystring.py`) |
| S7 | Ombrage irréaliste avec un modèle SketchUp/drone, simulation qui ne termine pas | VF2219, VF4147 | Messages de géométrie nommés et refus propres |
| S8 | Cycles batterie / profondeur de décharge : quelle valeur saisir ? | VF10712 | Prendre la valeur de la fiche, expliquer l'hypothèse |
| S9 | La courbe de charge ne colle pas au tableau (mois à 31 jours) | VF10825 | Choisir et afficher la répartition |
| S10 | Comment modéliser un raccordement « sans injection » ou plafonné ? | VF10826 | Réglage d'injection nulle déjà présent |
| S11 | Quelle puissance maximale estimée ? règle de surdimensionnement E-O ? | VF6915 | Donner la puissance max simulée et la courbe classée |
| S12 | Retirer un module sans effacer le câblage | VF6842 | Garder l'affectation, re-compter proprement |
| S13 | Modèle de toit complexe : comment assembler pans et noues ? | VF10794 | Presets de forme (ACAL410 planifié) |
| S14 | Toit L, pivoter le bâtiment, copier les locaux techniques | VF10941 | Pivoter l'ensemble ; copier-coller |

---

## 6. VÉRIFICATION CONTRE NOTRE MODULE

Preuves : inventaires `r1/a1-backend.md`, `a2-frontend-erp.md`, `a3-atelier-3d.md`, constats des lots `plan/lot-W*.md`, et `git grep` (existence des fichiers vérifiée). Les tâches ACAL citées sont dans `docs/plans/PLAN_AUDIT_CALEPINAGE.md` (case non cochée = planifié).
Chemins courts : `BE` = `backend/django_core/apps/calepinage/services/` ; `CE` = `backend/django_core/core/` ; `FE` = `frontend/src/features/calepinage/` ; `W` = `apps/web/src/`.

### 6.1 Les 44 éléments contrôlés

| # | Élément (origine) | Statut | Preuve / tâche |
|---|---|---|---|
| 1 | Arbre de pertes nommé (PVsyst, HelioScope) | PRÉSENT | `BE diagramme_pertes.py`, `FE production/DiagrammePertes.jsx` ; lecture en lignes → ACAL444 |
| 2 | Ombrage proche 3D par module + carte de chaleur (PVsyst, PV*SOL) | PRÉSENT | `W lib/shadingEngine.ts`, `W scripts/roofPro11/shadingUi.ts::refreshHeatmap` |
| 3 | Effet électrique de l'ombrage par chaîne (PVsyst) | PARTIEL | `BE etapes/mismatch_ombrage.py` ; modèle diode/sous-module jamais prévu (ACAL462 n'imprime que les bornes) |
| 4 | Ombrage du diffus / facteur de vue du ciel | DÉJÀ PLANIFIÉ | ACAL460, ACAL461 |
| 5 | Table d'ombrage azimut × hauteur (iso-ombrage) | DÉJÀ PLANIFIÉ | ACAL459, ACAL449, ACAL467 |
| 6 | Horizon PVGIS ou saisi ; import fichier | PRÉSENT / PLANIFIÉ | `BE horizon.py` ; import fichier ACAL458 |
| 7 | Stringing auto avec limites réelles de l'onduleur (Voc froid, fenêtre MPPT, courant) | PRÉSENT | `CE electrique/chaines.py`, `BE chaines.py::concevoir_par_pan`, températures du site (TMY) |
| 8 | Plusieurs orientations sur un MPPT (E-O) | PRÉSENT | `BE polystring.py` |
| 9 | Longueurs de câble qui collent à la réalité, chute de tension | PARTIEL | `BE troncons.py`, `cables.py` (mètres des tracés dessinés) ; routage auto ACAL472 |
| 10 | Schéma unifilaire modifiable + DXF | PRÉSENT | `BE sld.py`, `sld_export.py` |
| 11 | Plans que l'équipe peut suivre (pose, câblage, manuel propriétaire) | PRÉSENT | `BE documents/plan_cablage.py`, `documents/manuel_proprietaire.py`, `plan-pose.pdf` |
| 12 | Variantes + comparaison | PRÉSENT | `BE variantes.py`, `FE VariantesCompare.jsx` |
| 13 | Variantes « en un clic » / balayage inclinaison × azimut | PARTIEL / PLANIFIÉ | matrice dans le navigateur (`W lib/estimatorBrainV6.ts`) ; serveur ACAL468, ACAL469, ACAL477 |
| 14 | P50/P75/P90/P95 | PRÉSENT | `BE incertitude.py::bloc_incertitude` ; P99 décidé hors périmètre (ACAL457 [SKIP]) |
| 15 | Écrêtage et rapport DC/AC | PRÉSENT | `BE etapes/ecretage.py`, `CE electrique/onduleurs.py::ratios` |
| 16 | Stockage : stratégies et dimensionnement | PRÉSENT | `BE batterie.py` (6 stratégies) ; courbe d'état de charge ACAL447 |
| 17 | Injection nulle / plafond d'injection | PRÉSENT | stratégie `plafond_injection`, `BE raccordement.py` ; plafond de soutirage : non trouvé |
| 18 | Fichier météo EPW/TMY3 horizontal | DÉJÀ PLANIFIÉ | ACAL454, ACAL455, ACAL456 |
| 19 | Import PAN/OND pour préremplir une fiche module/onduleur | ABSENT | `git grep` PAN/OND = 0 hors migrations ; aucune tâche (voir proposition) |
| 20 | Bifacial heure par heure | DÉJÀ PLANIFIÉ | ACAL465 (aujourd'hui gain mensuel simplifié) |
| 21 | Toit proposé depuis l'adresse | PARTIEL | empreinte OSM seulement (`calepinage_empreinte_osm.json`, `apps/crm/roof_detect.py`) ; IA ACAL485, ACAL488 ; ACAL486/487 [GATED] |
| 22 | Toit esquissé par ses dimensions | DÉJÀ PLANIFIÉ | ACAL422 |
| 23 | Relevé sur site (téléphone/tablette) qui nourrit la conception | PARTIEL | `BE releve.py`, modèle `ReleveTerrain`, `FE atelier/PanneauReleve.jsx`, `solveur_cotes.py` ; téléphone ACAL423, ACAL482 |
| 24 | Orthophoto de drone géoréférencée | DÉJÀ PLANIFIÉ | ACAL424 (fichier monde) |
| 25 | Parcours guidé par étapes | DÉJÀ PLANIFIÉ | ACAL392, ACAL393, ACAL394 |
| 26 | Annuler partout / copier-coller / aligner | PARTIEL / PLANIFIÉ | undo limité au mode disposition (`W roofPro11/layoutEditor.ts`) ; ACAL411, ACAL412, ACAL413, ACAL425 ; **coller : non planifié** |
| 27 | Palette de commandes, raccourcis unifiés | DÉJÀ PLANIFIÉ | ACAL414, ACAL415 |
| 28 | Pertes expliquées à un client en mots simples | ABSENT | rapport d'étude interne (`BE rapport/`) ; ACAL419 ne traite que les onglets ; aucune tâche |
| 29 | Contrôles qui rattrapent les erreurs avant le devis | PARTIEL | `FE BoutonDevis.jsx` (bloquants électriques, passer outre avec motif) ; ACAL426 (pentes non confirmées), ACAL392, ACAL397 |
| 30 | Comparaison au PVGIS / à un outil de référence | PARTIEL / PLANIFIÉ | `BE validation.py` (informatif) ; ACAL474, ACAL475 |
| 31 | Changer module/onduleur en gardant le câblage | PARTIEL (à vérifier) | affectation recalculée par pan (`BE chaines.py`), affectation manuelle `FE plan/AffectationChaines.jsx` — je n'ai pas prouvé qu'elle survit à un changement de module |
| 32 | Lien client en lecture seule (vue 3D) | PRÉSENT | `W scripts/roofPro11/viewerFullBoot.ts`, page `/proposition/[token]` |
| 33 | Structure : lestage et liste de fixation | PRÉSENT | `BE lestage.py`, `BE fixation.py` ; calcul vent/neige exclu par décision |
| 34 | Autoconsommation mensuelle en graphique | DÉJÀ PLANIFIÉ | ACAL445, ACAL453, ACAL446 |
| 35 | Import de conso au pas de 15 min | PRÉSENT | contrat `calepinage_consommation_proposee.json` (« pas de 15 minutes agrégé à l'heure »), `BE courbe_charge.py` |
| 36 | Extension d'une installation existante (sous-système « existant ») | ABSENT | `git grep` : rien dans le module ni dans les lots ; aucune tâche |
| 37 | Modules différents par pan | PRÉSENT | `W roofPro11/moduleSelect.ts`, `rp9-pan-module-select` |
| 38 | Rapport avec photos du site | PARTIEL | `PhotoSite` + `BE photos.py` ; rapport d'étude : rien trouvé sur les photos dans `BE rapport/` |
| 39 | Presets de forme de toit (2 pans, L, T) | DÉJÀ PLANIFIÉ | ACAL410 (code existant sans bouton) |
| 40 | Brouillon/hors-ligne | PARTIEL | brouillon local (`FE brouillon.js`) ; ACAL400 (brouillon serveur) |
| 41 | Détail à portée d'un geste « Je ne connais pas la pente » | DÉJÀ PLANIFIÉ | ACAL416, ACAL417 |
| 42 | Import d'un plan de chaînes dessiné ailleurs | ABSENT | `BE import_plan.py` lit un plan DXF/PDF vectoriel (contour), pas un plan de chaînes ; aucune tâche |
| 43 | Rapport de pertes sans jargon (explication par poste) | PARTIEL | postes nommés dans la cascade ; textes d'aide sur les paramètres : `HelpTip` non utilisé dans le module (a2 §5) |
| 44 | Suivi de lecture de la présentation client | ABSENT | non trouvé ; hors du périmètre « module de conception » (à rapprocher du suivi de devis ailleurs) |

### 6.2 CAPACITÉS PROPOSÉES (absentes ou partielles, non planifiées), classées

Exclusions fondateur respectées : aucun logiciel/donnée payant, pas de trackers, aucun montant dans le module de conception, rien qui change le PDF devis client (règle #4).

| Rang | Capacité (une ligne) | Preuve | Plus petite version crédible |
|---|---|---|---|
| 1 | « Pourquoi ce chiffre ? » : une phrase plain-française sous chaque grandeur qui fait poser une question (rapport DC/AC, Voc à froid avec la température du site, écrêtage, pertes) | S1, S2, S3, S4, P9, P14 : 8+ questions de forum sur des chiffres corrects mais non expliqués | Table de phrases courtes par clé de résultat, affichée dans les onglets Électrique et Pertes (le module n'utilise pas `HelpTip`) |
| 2 | Pertes expliquées pour un client, en 6 postes lisibles | VF1094 (« clients ne comprennent pas les graphiques ») ; aucune tâche | Vue du diagramme de pertes regroupée en 6 postes + phrases, hors PDF devis |
| 3 | Chaînes qui survivent à un changement de module, d'onduleur ou à un retrait de panneau | VF6842, VF1096 (3 demandes), VF10692 | Vérifier d'abord le comportement actuel ; puis recalcul qui garde les affectations non touchées |
| 4 | Pré-remplissage d'une fiche module/onduleur depuis un fichier PAN/OND public | FP66690, FP36152, VF10024/10719 : saisie de fiches = douleur récurrente | Lecture d'un fichier PAN (champs de base + coefficient de température) → brouillon de FicheTechnique à valider |
| 5 | Annuler/rétablir sur tout l'atelier (tracé, obstacles, zones), plus « coller » | VF1094, VF1096 ; a3 §5 pt 6 | Pile d'historique atelier existante (`createWorkshopHistory`) branchée sur tous les gestes ; coller = dupliquer avec décalage au curseur |
| 6 | Contrôle d'erreurs « avant le devis » regroupé en une liste de 6-8 vérifications avec la cause et le geste | P2, S7, SolarEdge « click-through » (energiesparhaus) ; ACAL397 couvre seulement « ce qui manque » | Cinq contrôles de cohérence servis par le parcours (ACAL392) : GPS, pente confirmée, DC/AC, tension froide, ombrage |
| 7 | Extension d'une installation existante (modules déjà posés, comptés à part) | VF1096 (« sous-système existant »), OpenSolar 3.0 l'a ajouté, très courant au Maroc | Marquer un pan « existant » : son énergie compte, ses modules ne vont pas au BOM |
| 8 | Import d'un plan de chaînes/câblage d'un autre outil (CSV ou DXF) | VF10527, FP75652 | CSV module → chaîne ; réutilise `import_plan.py` |
| 9 | Plafond de soutirage réseau dans le raccordement | VF10826 | Un champ de plus dans `BE raccordement.py`, appliqué au dispatch `peak_shaving` |
| 10 | Rapport d'ombrage : capture automatique et échelle de couleur fixe | VF1094, VF1096 | Échelle de la carte de chaleur fixée de 0 à 100 % ; export d'une image par pan |
| 11 | Diode de dérivation (bypass) comme explication simple du paysage/portrait | FP21692, P4 | Sans modèle cellule : règle « paysage = perte limitée à un tiers de module » citée, nommée hypothèse |
| 12 | Heure légale vs heure solaire visibles sur la course du soleil | VF8531 | Une ligne d'information sur le diagramme (course du soleil) |
| 13 | Photos de visite dans le rapport d'étude interne | VF1094 | Section « photos du site » dans `BE rapport/` à partir de `PhotoSite` |
| 14 | Pivoter tout le site d'un coup ; copier-coller de bâtiments | VF10941 | Une rotation autour du centre appliquée à tous les objets du document |
| 15 | Aide à la saisie d'un module « maison » : liste courte des 8 champs indispensables, le reste facultatif | VF10719, VF10024 | Étiquettes « nécessaire / facultatif » dans la fiche équipement |
| 16 | Explication « pourquoi ce n'est pas modélisé » (bifacial vertical, MPPT local, trackers) | FP73753, VF11087 | Liste de limites connues au bas du rapport interne |
| 17 | Mode hors-ligne pour le relevé de chantier | VF1094 (« accès base hors-ligne ») ; réseau Maroc inégal | Brouillon local déjà présent ; ajouter file d'attente d'envoi des photos |
| 18 | Suivi de lecture de la vue client | VF1094 | Réutiliser le suivi « devis ouvert » existant côté ventes, hors module |
| 19 | Mode « téléphone » du relevé avec photos obligatoires (angles minimaux) | recherche relevés (vendeurs) | Liste de 6 photos nommées dans `PanneauReleve` ; téléphone déjà dans ACAL423 |
| 20 | Garde-fou « limite connue » quand le modèle importé est trop lourd | VF10889, VF11088 | Refus nommé au-delà de N sommets avec conseil de simplification |

---

## 7. CE QUE JE N'AI PAS PU LIRE

- **Reddit** (r/solar, r/SolarDIY…) : domaine refusé par l'outil de recherche ; aucun contenu lu.
- **forum.pvsyst.com** : erreur 405 à la lecture ; seuls deux titres de fils sont apparus dans des résultats de recherche (non lus).
- **DIY Solar Forum** : 403. **Mike Holt**, **forum.solar-electric.com**, **electriciansforums**, **powerforum.co.za**, **devpost** : 403.
- **G2, Capterra, SoftwareAdvice, GetApp** : 403 sur lecture directe ; je n'ai que des résumés de moteur de recherche.
- **photovoltaikforum.com** : page 404 / aucun résultat ; **Eng-Tips**, **SolarPanelTalk**, **Stack Exchange** : aucun résultat exploitable ; **ResearchGate** : titres/extraits seulement ; **SAM (NREL)** : hôte introuvable.
- **YouTube / chapitres de vidéos, LinkedIn, Medium** : aucun résultat exploitable obtenu.
- **Arabe** : une recherche, rien de spécifique au Maroc. **Espagnol** : une recherche, rien d'utile.
- **Valentin PV*SOL** : lu seulement la page 1/4 des fils de souhaits et ~25 fils parmi ~1 100 ; **forum-photovoltaique.fr PVsyst** : ~14 fils sur 108 (fils de 2010 à 2024, certains anciens).
