# D6 — Parcours, simplicité, explications, partage (juge de consolidation, tour 1, 21/11/2026)

Dépôt lu en LECTURE SEULE : `C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5` (HEAD `5a75a182b`).
Aucun fichier du dépôt modifié, aucun test, aucun docker. Chaque verdict « chez nous » repose sur un grep ou une
lecture faite dans cette session (cités `fichier::symbole`) ; ce qui ne l'est pas est dans « Non vérifié ».
Chemins courts : `SV` = `backend/django_core/apps/calepinage/services`, `CE` = `backend/django_core/core/electrique`,
`FC` = `frontend/src/features/calepinage`, `RP` = `apps/web/src/scripts/roofPro11`.
Constats des relecteurs du produit réel : `registre/constats/T1-S1.jsonl` (27, simplicité), `T1-F1.jsonl` (26,
fonction) ; `T1/B1.md` = arrêt (l'atelier ne démarre pas sans clé MapTiler : défaut d'instrument, aucun constat).

Barème de score (le même pour toutes les fiches) : **preuves** = 2 points par lane distincte à voix réelles
(forums, avis), 1 point par lane à pages éditeur / notes de version, +2 par constat de relecteur (produit réel) lié,
plafonné à 20 · **adéquation** 1-3 (3 = commerciale non ingénieure sur toit marocain, chaque projet) · **effort**
S = 1, M = 2, L = 3. **Score = preuves × adéquation ÷ effort.** Les PRÉSENT SANS ÉCRAN passent en tête (consigne).

---

## 0. Inventaire des nombres et verdicts qui demandent une explication

Inventaire fait par lecture des écrans réels (lecture déléguée à un éclaireur, recoupée par mes greps sur les points
cités ici). Périmètre lu : `FC/**` (Production, Bandeau de provenance, Diagramme de pertes, Économie, Batterie, Verdict
électrique, Raccordement, Cheminement, Affectation, Masse/lestage, Pompage, Course du soleil, Horizon, Coupe des rangées,
Ombrière, Saisie de pente, AtelierPanneaux, Fiche, Variantes, Comparaison, Pertes, Remplissage prouvé, Allées,
Provenance, Réglages), `frontend/src/pages/ventes/ToitureDesign.jsx`, `RP/*.ts` (cartes « Recommandation », « Total »).

**195 grandeurs ou verdicts affichés** ; **84** ont une explication à côté (source, motif, provenance, formule),
**15** seulement dans un état limite (« non publié » + motif), **96 n'ont rien**.

| Groupe | Total | Expliqués | Seulement si « non publié » | Sans rien | Exemples sans explication |
|---|---|---|---|---|---|
| Toit | 27 | 14 | 0 | 13 | Hauteur maxi d'horizon ; Inclinaison / Pas / Hauteur hors-tout / Longueur d'ombre (`FC/atelier/OngletCoupeRangees.jsx`) |
| Panneaux | 15 | 9 | 0 | 6 | « Panneaux posés / Puissance / Emplacements libres / Couverture besoin » (`FC/atelier/BuilderDom.jsx`, remplis par `RP/layoutEditor.ts`) |
| Électrique | 25 | 13 | 0 | 12 | Élévation de tension, marge, puissance injectée, déséquilibre (`FC/electrique/Raccordement.jsx`) ; chutes DC/AC cumulées, sections, métré (`FC/electrique/CheminementCables.jsx`) ; « Alertes non bloquantes » |
| Production | 30 | 10 | 7 | 13 | P50, variabilité σ, productible, kWc, pertes totales, mensuel, par pan (`FC/production/PanneauProduction.jsx::TotalKpis`) |
| Pertes | 10 | 5 | 1 | 4 | Énergie avant / après / restante, total (`FC/production/DiagrammePertes.jsx`) |
| Ombrage | 6 | 6 | 0 | 0 | — (accès solaire et retrait proposé ont leur méthode : `RP/shadingUi.ts::renderSolarAccess`) |
| Autoconsommation + batterie | 25 | 3 | 2 | 20 | Capacité utile, énergie stockée / restituée, 6 flux d'énergie, hors-réseau (défaillance, pire mois, jours d'autonomie) (`FC/atelier/PanneauBatterie.jsx`) |
| Économie | 9 | 2 | 5 | 2 | Horizon retenu, flux annuel (`FC/economie/PanneauEconomie.jsx`) |
| Comparatifs | 4 | 0 | 0 | 4 | Modules, kWc, P50, écarts (`FC/VariantesCompare.jsx`) |
| Atelier 3D (cartes) | 24 | 14 | 0 | 10 | « Puissance », « N × 720 W », « Couverture facture » (`RP/optimizer.ts::paintCard`) ; P50/P90/PR (`RP/prodWindow.ts`) ; conso/autoconso/batteries (`RP/consumptionMarkup.ts`) |
| Documents | 7 | 2 | 0 | 5 | pages par pièce, statut et avancement du dossier |
| Pompage | 10 | 3 | 0 | 7 | Débit à la HMT, pompe, variateur, autonomie du réservoir, m³ mensuels, couverture (`FC/pompage/PompagePanel.jsx`) |
| Autres | 3 | 3 | 0 | 0 | — |

Faits sous l'inventaire (vérifiés) :
- `HelpTip` existe (`frontend/src/ui/HelpTip.jsx::HelpTip`, bouton « ? » + lien « Voir le lexique complet ») et sert
  15 fichiers ERP ; **aucun** sous `FC/` ni `ToitureDesign.jsx`. Un lexique PAR TERME existe
  (`frontend/src/pages/aide/LexiquePage.jsx::TERMES`, route `/aide/lexique`, lien `FC/atelier/Rail.jsx` testid
  `cal-rail-lexique`) ; aucune table « clé de résultat → phrase ».
- Aucun « Mode expert / essentiel » dans `FC/` (grep `expert|essentiel|avancé` : faux positifs seulement).
- Aucun écran ne dit « heure légale » / « heure solaire » (`FC/CourseSoleil.jsx`, `FC/SunDiagram.jsx` : 0).
- Le ratio DC/AC n'est affiché nulle part comme RÉSULTAT (seuls les libellés de saisie
  `FC/electrique/SaisiesElectriques.helpers.js` l. 21-24) ; le taux d'autoconsommation n'est pas un KPI de Production.
- Deux vocabulaires pour un même statut : `omis` = « Non vérifié » (`FC/electrique/Raccordement.helpers.js::LIBELLES_STATUT`)
  contre « Non calculé, motivé » (`FC/electrique/VerdictElectrique.helpers.js::STATUTS`).
- Cinq libellés pour la « couverture » : « Couverture facture » (page `toiture-3d-pro-11.astro`), « Couverture besoin »
  (`BuilderDom.jsx`), « Couverture » (`ToitureDesign.jsx`), « Taux de couverture » (`PanneauBatterie.jsx`), « Couverture »
  mensuelle (`PompagePanel.jsx`).
- Le relecteur S1 a relevé **61 mots qu'une commerciale ne comprend pas** (T1/S1.md §2.3), dont des clés internes
  (« zones[].geometry.solarAccess », « services/norme.py::norme_applicable », « CH_IMP_CUMULE_ECRETAGE »).

Non inventorié (à ne pas croire couvert) : Étiquettes, Relevé, Séries, Versions/Diff, Activité, Bibliothèque,
création, calages photo/plan, Schéma unifilaire, saisies électriques, Vue 2D, Calques, 2 cases de `ModeTerrain.jsx`,
détail des dossiers.

---

## 1. Fiches de capacité (classées)

### CAP-D6-01 — Le voyant « ce chiffre est-il plausible ? » (l'écart à PVGIS est déjà calculé, aucun écran ne le montre)
- **Besoin** : « 34 000 kWh/an ? 3 % d'ombrage ? est-ce crédible ? » ; « quel chiffre croire quand deux outils divergent ».
- **Preuves** : B5-de P1 (13 fils), K09 (29 fils en passe 2), K14 (48 fils, « prévision 20 % au-dessus du réel ») ;
  B5-fr 3 (14 sources) ; B5-es K03 (10 fils) ; B4 P14/P19 ; B7 U27 (partiel) ; relecteur **T1-F1-026** (productibles
  de l'atelier : Marrakech sous Casablanca). URL : https://www.photovoltaikforum.com/thread/248527-pv-sol-experte-f%C3%BCr-projektpr%C3%BCfung-kontrolle-gesucht/ ;
  https://forum-photovoltaique.fr/viewtopic.php?t=11987
- **Qui le fait** : PVGIS sert de « contrôle de réalité » chez tous ; PV*SOL « config check » ; personne n'affiche un
  voyant avec la cause.
- **Chez nous** : **PRÉSENT SANS ÉCRAN.** `SV/simulation.py` pose `blocs['validation'] = ecart_vs_pvcalc(...)`
  (`SV/validation.py::ecart_vs_pvcalc`, « aucun seuil codé : le VERDICT n'existe que si la société a SAISI sa
  tolérance ») ; le bloc est dans `contract_samples/calepinage_resultat.json` ; grep `validation` dans `FC/production` :
  0 lecture. Seul son `avertissement` tombe dans la liste brute des avertissements.
- **Plus petite version** : sous le chiffre de production, une ligne « Comparé à PVGIS au même endroit : +x % » ; voyant
  vert/orange SEULEMENT si la tolérance société est saisie (sinon « écart publié sans verdict — tolérance non réglée »).
  Entrées : le bloc servi ; rien de nouveau calculé.
- **Simplicité** : étape Résultats, « essentiel » ; silencieux quand vert.
- **Tâches** :
  1. Afficher le bloc `validation` sous le chiffre de production ; fini quand l'exemple du contrat rend la ligne d'écart
     et, sans tolérance, la mention « sans verdict ». Fichier : `FC/production/BandeauProvenanceProduction.jsx` (calepinage).
  2. Le voyant (vert/orange) lit la tolérance saisie ; fini quand une tolérance saisie fait passer l'exemple en orange
     au-delà de l'écart. Même fichier + test vitest du module. Dépend : rien (bloc déjà servi).
- **Score** : preuves 16 × 3 ÷ 1 = **48** · rang 1.

### CAP-D6-02 — « Ce que ce calcul ne modélise pas » et le chemin de calcul, en clair
- **Besoin** : « l'écran le dit, au lieu de me laisser chercher sur le web » ; « fonctions grisées sans explication ».
- **Preuves** : B5-de P7 (6 fils), K36 ; B4 r16 ; B5-en 14 (4 fils) ; B7 U22 (IEA PVPS T13) ; B5-es K11 (18 fils, ABSENT).
  URL : https://forum.valentin-software.com/topic/9482-berechnung-der-ausrichtung-zur-bezugskante/ ;
  https://iea-pvps.org/wp-content/uploads/2020/01/Uncertainties_in_PV_System_Yield_Predictions_and_Assessments_by_Task_13.pdf
- **Qui le fait** : personne à l'écran ; PVsyst le documente dans l'aide.
- **Chez nous** : **PRÉSENT SANS ÉCRAN (en partie visible).** `SV/chaine_pertes.py` porte les étapes toujours omises
  avec leur motif (« Étape non modélisée en v1 », `diodes`, `spectral`) ; `DiagrammePertes.jsx` montre la colonne
  « Motif » étape par étape ; l'annexe du rapport `SV/rapport/annexe_hypotheses.py` (« hypothèses, sources et omissions »)
  l'imprime. Aucun bloc unique « ce qui n'est pas modélisé » à l'écran.
- **Plus petite version** : un bloc replié « Ce que ce calcul ne prend pas en compte » sous le diagramme de pertes,
  lu des étapes omises du résultat ; + un lien « comment c'est calculé » par étape vers la phrase de la fiche CAP-D6-03.
- **Simplicité** : Résultats, replié, « expert » ouvert d'un clic.
- **Tâches** : 1. Lister au bas de l'onglet Pertes les étapes omises du résultat avec leur motif ; fini quand
  l'exemple du contrat montre `diodes` et `spectral` avec leur motif. `FC/production/DiagrammePertes.jsx`.
- **Score** : 12 × 2 ÷ 1 = **24** · rang 4.

### CAP-D6-03 — « Pourquoi ce chiffre ? » : une phrase simple sous chaque grandeur qui fait poser une question
- **Besoin** (le signal le plus fort des forums, dans toutes les langues) : « 519 V alors que 9 × 52,9 = 476 V ? »,
  « sizing factor 154 % normal ? », « PR 93 % plausible ? », « kW ou kWh ? », « pourquoi si bas ? ».
- **Preuves** : B4 r1 (8+ fils), r28 (3) ; B5-fr R1 (12) ; B5-en 1 (12 + 5 en passe 2) ; B5-es 1 (26 fils) et K35 (11) ;
  B5-de P1, P7 ; B7 U19 ; B6 R23 (4 outils : info-bulle par élément), R39 ; B3 N29 (en partie). Relecteurs : **T1-S1-019**
  (langage de développeur), **T1-S1-026** (« (non vendue) » inexpliqué), **T1-F1-014** (alerte ×3 + clés internes),
  T1-S1 §2.3 (61 mots). URL : https://forum.valentin-software.com/topic/10806-max-open-circuit-voltage/ ;
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-aislados-la-red/41818-sombra-paneles.html ;
  https://forum-photovoltaique.fr/viewtopic.php?t=14413
- **Qui le fait** : PVcase 1.53 (info-bulles d'éléments), Pylon (« live stringing tooltip ») ; personne ne fait la phrase
  par résultat.
- **Chez nous** : **PARTIEL.** Le mécanisme existe sans être branché : `frontend/src/ui/HelpTip.jsx::HelpTip` (0 importeur
  dans `FC/`), lexique par terme `LexiquePage.jsx::TERMES`. Le serveur publie déjà les entrées d'une phrase juste :
  températures et motif des bornes de chaîne (`CE/chaines.py::fenetre_admissible`), sources et motifs d'omission des
  étapes, `Provenance` (`FC/commun/Provenance.jsx`). 96 grandeurs sans rien (§0). ACAL419 ne couvre que les 36 ONGLETS.
- **Plus petite version** : UNE table de phrases par clé de résultat (≈ 40 clés au départ : P50, P90, PR, productible,
  pertes totales, chaque étape de la cascade, Voc à froid, Vmp chaud, DC/AC, écrêtage, chute DC/AC, élévation de
  tension, accès solaire, autoconsommation, couverture, capacité utile, jours d'autonomie, HMT, débit à la HMT) ; chaque
  phrase dit la CAUSE et le GESTE, insère les valeurs servies (température utilisée, source) et jamais un chiffre à elle.
  Composant « ? » à côté du chiffre (réutilise `HelpTip`). Une clé sans phrase = test rouge.
- **Simplicité** : rien à saisir ; le « ? » est replié ; « essentiel » sur les 12 chiffres de l'étape Résultats.
- **Tâches** :
  1. Poser le contrat des phrases `contract_samples/calepinage_explications.json` (clé, phrase, valeurs insérées, geste)
     SEUL sur `main` ; fini quand l'échantillon est déclaré dans `test_cal223_contrats.py` (PACT10).
  2. Monter le « ? » sur l'onglet Production, le diagramme de pertes et la Batterie ; fini quand chaque chiffre de
     `TotalKpis` et chaque étape ont leur phrase. `FC/production/PanneauProduction.jsx`, `DiagrammePertes.jsx`,
     `FC/atelier/PanneauBatterie.jsx` + un `FC/commun/Pourquoi.jsx` (importe `HelpTip`, propriétaire deploy — import
     seulement, aucune édition).
  3. Même chose pour l'électrique (Raccordement, Cheminement, Verdict) et le Pompage ; fini quand les 12 + 7 grandeurs
     sans explication de ces écrans en ont une. `FC/electrique/*.jsx`, `FC/pompage/PompagePanel.jsx`.
  4. Réécrire en mots du métier les motifs serveur qui montrent une clé ou un chemin de code (« services/norme.py »,
     « zones[].geometry.solarAccess », « dans ce dépôt ») et unifier les libellés de statut `omis` ; fini quand une garde
     (test) ne trouve plus `::`, `[]` ni `.py` dans les textes des échantillons de contrat. `SV/norme.py`, `SV/electrique.py`,
     `FC/electrique/Raccordement.helpers.js`.
  5. Les termes du solaire absents du lexique (Voc, Vmp, Isc, DC/AC, HMT…) : à router vers `PLAN_AUDIT_DEPLOY.md`
     (`LexiquePage.jsx` → propriétaire deploy).
  Dépendances : ACAL419 (bulles d'onglets — même composant, à faire ensemble), ACAL443 (hiérarchie de l'onglet Production).
- **Score** : 20 × 3 ÷ 2 = **30** · rang 2.

### CAP-D6-04 — « Prêt à envoyer ? » : un seul panneau de contrôles avant le devis, chacun avec sa cause et son geste
- **Besoin** : « aucun des 5 devis n'a de plan », « 40 × 455 Wp = 18,2 et non 17,9 kWc », « 2 MPPT pour 4 orientations »,
  « rendement invraisemblable », « ombrage jamais chiffré ». Pour la commerciale : savoir avant d'envoyer.
- **Preuves** : B5-de P20 + §11 (**98 fils, 199 lignes** de reproches aux offres), K52 ; B3 N6 (Reonic « Check before
  you send », PVcase Audit) ; B4 r6 ; B6 R15 (3 outils), K57 (5 outils, 2025-26) ; B5-es 5.2 (renvoyé à ACAL397/426).
  Relecteurs : **T1-S1-007** (villa à 131 kWc sans facture, aucun garde-fou), **T1-S1-020** et **T1-F1-010** (« Publiable »
  à côté de 11 « Non vérifiable » et d'un écrêtage permanent), **T1-S1-008** (retour de génération en jargon),
  **T1-S1-003** (même avertissement ×2), **T1-F1-021** (obstacle à cheval sur la rive accepté). URL :
  https://docs.reonic.com/docs/en/offers-overview-check-a-project-before-you-send-it ;
  https://www.photovoltaikforum.com/board/41-angebote-eeg-photovoltaikanlage/
- **Chez nous** : **PARTIEL — les contrôles existent, dispersés ; aucun panneau.** Voir la liste §3 (16 contrôles déjà
  calculés, 7 manquants, 1 planifié). Portes réelles : `SV/feu_vert.py::verifier_avant_publication` (visite + approbation),
  `SV/electrique.py::verdict_publiable` (bloquants / sans source ; « indéterminé » publiable par D-ACAL-9),
  `FC/BoutonDevis.jsx` (bloquants mot pour mot, « Passer outre » avec motif, avertissements). Planifié et à FUSIONNER, pas
  à doubler : ACAL386 (contrat du parcours), ACAL392 (« ce qui manque » dédupliqué), ACAL397 (chaque ligne ouvre le champ),
  ACAL426 (pentes non confirmées).
- **Plus petite version** : sur « Générer le devis », un panneau de 10-12 lignes vert / orange / rouge : rouge = ce qui
  bloque déjà (inchangé), orange = « indéterminé » et contrôles d'avertissement, vert replié en « prêt ». Chaque ligne :
  phrase de cause + bouton qui ouvre le champ (mécanisme d'ACAL397). Seuils d'orange = réglages société saisis AVEC
  source ; sans seuil, la ligne publie la valeur sans verdict. Aucun prix. Aucun statut de devis touché.
- **Simplicité** : un voyant en tête du rail ; tout vert = une ligne « Prêt à envoyer » ; étape Documents, « essentiel ».
- **Tâches** :
  1. Étendre le contrat d'ACAL386 (avant sa construction) d'une liste `controles_envoi[]` {code, etat, cause, geste,
     cible_champ, seuil_source} ; fini quand l'échantillon porte un vert, un orange, un rouge. `contract_samples/` (calepinage).
  2. Servir l'agrégat dans `GET calepinages/<pk>/parcours/` (ACAL392) en lisant les portes existantes, sans recalcul ;
     fini quand un calepinage sans onduleur désigné rend « orange : matériel non désigné » au lieu de « Publiable ».
     `SV/` nouveau module `pret_a_envoyer.py` + `views/`. @after ACAL392.
  3. Ajouter les contrôles manquants calculables sans rien inventer : taille sans facture (« le toit est rempli : N kWc »),
     cohérence nombre × Wp = kWc affiché, obstacle hors du pan, pans laissés vides sans motif ; fini quand chacun a son
     test sur un document d'exemple. `SV/pret_a_envoyer.py`, lecture de `SV/mesures.py::mesures_du_document`.
  4. Monter le panneau dans `FC/BoutonDevis.jsx` (avant l'appel de génération) et la carte de succès « Devis DEV-… créé
     — Voir le devis » (lien vers le DEVIS, pas l'atelier) ; fini quand les 14 lignes techniques de T1-S1-008 sont
     repliées « pour le technicien ». (T1-S1-008, T1-S1-009.)
  5. Lire la compatibilité optimiseur/onduleur/batterie de ventes via un sélecteur ; fini quand une incompatibilité
     déclarée sort en orange. `apps/ventes/compatibilites.py` est hors calepinage → ajouter la fonction de lecture dans
     `apps/ventes/selectors*.py` = **PLAN_AUDIT_DEVIS.md** (propriétaire devis/ventes, non vérifié par le script pour ce fichier).
- **Score** : 20 × 3 ÷ 3 = **20** · rang 6 (le plus de preuves ; l'effort L le recule ; à faire en tête des M si le
  planificateur range par valeur absolue).

### CAP-D6-05 — Un seul chiffre par grandeur, le même sur tous les écrans, avec sa source (« quel chiffre croire »)
- **Besoin** : « une seule vérité : la disposition posée donne le compte, partout » (B4 P5) ; la débutante voit
  2 productions, 2 puissances et des économies à 0 MAD ici et 208 381 MAD là.
- **Preuves** : relecteurs **T1-S1-005** (154 312 et 162 678 kWh/an), **T1-S1-017** (S1 : 0 MAD contre TRI 39,88 %),
  **T1-S1-018** (131,04 contre 129,22 kWc), **T1-S1-023** (S1 : facture saisie, couverture « — », 0 MAD), **T1-S1-006**,
  **T1-F1-004 / T1-F1-024** (S1 : « 8 × 720 W » pour un module de 710 W), **T1-F1-006**, **T1-F1-007** (deux provenances
  contradictoires dans la même carte) ; lanes B4 P5 ; B5-de K09 ; B5-es K03 ; B5-fr 3.
- **Chez nous** : **PARTIEL.** Règle déjà décidée (D-ACAL-6 : la production du client est celle du devis ; écart
  affiché par `FC/production/BandeauProvenanceProduction.jsx::EcartDevis`). Causes trouvées dans le code :
  `RP/optimizer.ts::paintCard` écrit `${fmt(d.count)} × 720 W` EN DUR (l. 955) quel que soit le module, et écrit les
  économies même à zéro (l. 958) alors que la couverture voisine rend « — » (l. 957) ; les cartes « Recommandation » et
  « Total » sont deux calculs navigateur distincts (`RP/zones.ts`). ACAL401 (barre de résumé) et ACAL480 (parité atelier
  ↔ serveur) couvrent une partie, pas l'unicité entre cartes.
- **Plus petite version** : chaque carte d'atelier lit UNE estimation nommée (« estimation de l'atelier, avant
  simulation » / « simulation du <date> »), la même pour Recommandation, Total et la barre ACAL401 ; Wp lu sur le module
  posé ; sans facture : « — facture inconnue — la saisir » (champ sur place), jamais 0 MAD.
- **Simplicité** : invisible ; supprime une source de confusion.
- **Tâches** :
  1. Afficher le Wp du module réellement posé dans « N × … W » ; fini quand le module Jinko 710 W rend « 8 × 710 W ».
     `RP/optimizer.ts` (calepinage).
  2. Sans facture (ou couverture nulle), « Économies » rend « — » et un lien « Saisir la facture » ; fini quand le lead
     sans facture n'affiche plus « 0 MAD ». `RP/optimizer.ts`, `ToitureDesign.jsx`. (T1-S1-006, T1-F1-006.)
  3. Les cartes « Recommandation » et « Total — toutes les zones » affichent la MÊME production pour un seul pan ; fini
     quand une spec rejoue le tracé de T1-S1-005 et lit un seul nombre. `RP/zones.ts`, `RP/optimizer.ts`.
  4. Une seule provenance par carte (pas « PVGIS » dans l'en-tête si la table committée a servi) ; fini quand T1-F1-007
     ne se reproduit plus. `FC/production/BandeauProvenanceProduction.jsx`, `RP/prodWindow.ts`.
  Note : T1-S1-017 (TRI 39,88 % sans facture, onglet Économie) vient de `apps/ventes` (l'argent est servi par ventes) →
  router vers **PLAN_AUDIT_DEVIS.md** ; T1-S1-023 (couverture « — » avec facture saisie) : cause non trouvée dans cette
  passe (non vérifié).
- **Score** : 20 × 3 ÷ 2 = **30** · rang 3.

### CAP-D6-06 — Mode « salon » du vendeur et fin de parcours lisible
- **Besoin** : « par défaut on ne fait qu'activer ou retirer des modules, des rangées, des pans » ; « l'action
  principale toujours visible » ; « Ouvrir le devis ouvre le devis ».
- **Preuves** : B3 N5 (Scanifly SimpleDesign, SolarEdge), §5 parcours de référence ; B6 R7 (4 outils), K70 (4 outils) ;
  B5-fr 12 (8 sources, « prise en main ») ; relecteurs **T1-S1-002, 010, 011, 012, 014, 015**, **T1-F1-022**,
  **T1-S1-001 / 027** (porte du lead). URL : https://scanifly.com/blog/introducing-simpledesign/ ;
  https://docs.reonic.com/docs/en/offers-plan-pv-plan-modules
- **Chez nous** : **DÉJÀ PLANIFIÉ en grande partie** — ACAL393 (rail 5 étapes), ACAL394 (Mode expert), ACAL395
  (Électrique en un écran), ACAL399 (barre d'enregistrement), ACAL401, ACAL402 (studio), ACAL418, ACAL420, ACAL478
  (budget de simplicité). **ABSENT** et non planifié : l'étape Panneaux réduite aux bascules (le déplacement libre sous
  Expert), la carte de succès du devis, le lien vers le vrai devis, la sortie des réglages SOCIÉTÉ hors de l'atelier
  (`FC/PanneauAllees.jsx` montre « Défaut de la société » dans un projet, T1-S1-015).
- **Plus petite version** : en mode guidé, l'étape Panneaux n'offre que « Remplir », « Retirer la sélection », « Annuler »
  et clic sur un pan = basculer ; tout le reste sous Expert ; la barre fixe porte l'action principale de l'étape.
- **Tâches** :
  1. Étape Panneaux guidée = 3 actions + bascule de pan ; fini quand la spec de mesures (ACAL385) compte ≤ 5 contrôles
     dans l'étape. `ToitureDesign.jsx`, `FC/atelier/BuilderDom.jsx`. @after ACAL393, ACAL394, ACAL418.
  2. La barre fixe d'ACAL399 porte l'action principale de l'étape (« Créer le devis » à l'étape Documents) ; fini quand
     « Créer le devis » se voit sans défiler (T1-S1-014). @after ACAL399.
  3. Sortir « Défaut de la société » (allées par pays, contraintes d'assureur) de l'atelier vers les Réglages ; fini quand
     l'atelier n'a plus de bouton qui écrit un réglage société. `FC/PanneauAllees.jsx`, `FC/reglages/*`.
  4. Fiche du lead : une seule porte visible « Dessiner le toit », et « Concevoir la toiture (3D) » ouvre le toit au lieu de
     tenter un devis auto (T1-S1-001, 027) → `frontend/src/features/crm/workspace/IdentityRail.jsx` = propriétaire **lead**
     → **PLAN_AUDIT_LEAD.md**.
  (La carte de succès et le lien vers le devis sont dans CAP-D6-04 tâche 4.)
- **Score** : 20 × 3 ÷ 2 = **30** · rang 3 ex aequo (classé après CAP-05 : moitié déjà planifiée).

### CAP-D6-07 — Diagnostics nommés : « Pourquoi aucun module ici ? » et « Pourquoi ma production est basse ? »
- **Besoin** : quand « Remplir » ne pose rien ou que le kWh/kWc déçoit, une phrase qui nomme la cause et le remède.
- **Preuves** : B3 N28 (HelioScope « Troubleshooting an empty Field Segment »), N29 (« Troubleshooting Low Yield ») ;
  B4 r2, B6 R39 (SolarEdge « Yield Factor Loss Indication ») ; B5-es 2 (14 fils, ombre partielle expliquée) ; relecteur
  **T1-F1-026** (productible bas inexpliqué). URL : https://help-center.helioscope.com/hc/en-us/articles/8536952588435 ;
  https://help-center.helioscope.com/hc/en-us/articles/8536842520851-Troubleshooting-Low-Yield
- **Chez nous** : **ABSENT.** La cascade est servie (`resultat.cascade`, pertes dominantes dans `SV/comparaison.py`) ;
  le refus d'un GESTE nomme sa raison (`RP/layoutEditor.ts`), pas un remplissage vide (grep « aucun module » : rien d'un
  diagnostic).
- **Plus petite version** : (a) remplissage vide → test dans l'ordre de 4 causes calculables (retrait > largeur utile,
  module plus grand que le pan, seuil d'accès solaire, zones interdites) et une phrase ; (b) bouton « Pourquoi si bas ? »
  qui lit les 3 plus gros postes de la cascade et donne le geste (aucun chiffre nouveau). Les « plages normales » des
  pertes (N30/U14) ne sont PAS dans la version minimale : sans source publiée, elles seraient inventées.
- **Tâches** :
  1. Remplissage vide → phrase de cause ; fini quand chacun des 4 cas a son test. `RP/optimizer.ts` / `RP/layoutEditor.ts`.
  2. « Pourquoi si bas ? » sous le P50 : 3 postes dominants + geste ; fini quand l'exemple du contrat rend 3 lignes.
     `FC/production/PanneauProduction.jsx`. @after CAP-D6-03 t1 (les phrases).
- **Score** : 14 × 3 ÷ 2 = **21** · rang 5.

### CAP-D6-08 — Heure légale et heure solaire visibles sur la course du soleil et les ombres
- **Besoin** : « de quel midi parle-t-on ? » ; « soleil faux de 12° ».
- **Preuves** : B4 r12 / S4 (VF8531) ; B5-es 8 / K29 (3 fils) ; B6 R57 (2 outils). URL :
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-conectados-red/3099-sombras-autocad-formula.html
- **Chez nous** : **ABSENT à l'écran** (0 match dans `FC/CourseSoleil.jsx`, `FC/SunDiagram.jsx`) ; le fuseau est décidé
  (`CompanyProfile.fuseau_horaire`, « IAM en heure légale marocaine », défauts du plan) et affiché seulement dans
  Réglages (`FC/reglages/ReglagesSite.jsx`, « Fuseau effectif ») ; `CE`… `core/calepinage/soleil.py` a l'équation du temps.
- **Plus petite version** : une ligne « Heure affichée : heure légale (fuseau X) ; midi solaire du site à HH:MM ».
- **Tâches** : 1. Afficher heure légale et midi solaire sous la course du soleil et dans la coupe des rangées ; fini quand
  l'exemple montre les deux heures. `FC/CourseSoleil.jsx`, `FC/atelier/OngletCoupeRangees.jsx`.
- **Score** : 7 × 2 ÷ 1 = **14** · rang 9.

### CAP-D6-09 — Calepinages d'exemple et premier contact guidé
- **Besoin** : « réussir un premier projet sans formation » ; « Essayer avec un exemple ».
- **Preuves** : B1 C18 ; B7 U4 (10 sources) ; B6 R52 (3 outils), K69 ABSENT (2 outils) ; B5-fr 12 (8) ; B5-es K27 ;
  relecteur **T1-S1-002** (premier écran muet). URL : https://github.com/SunPower/PVMismatch/issues/128 ;
  https://forum-photovoltaique.fr/viewtopic.php?t=18770 (cité par B5-fr, non rouvert ici)
- **Chez nous** : **ABSENT.** Aucune commande d'exemple (`apps/calepinage/management/commands/` : 4 commandes de dry-run
  et d'anonymisation seulement) ; modèles société existants (`SV/modeles.py::creer_depuis_modele`) ; aide du tracé ACAL420.
- **Plus petite version** : 3 exemples (villa à toit incliné, toit-terrasse C&I est-ouest, pompage) tirés des projets de
  référence d'ACAL382, créés À LA DEMANDE dans la société par « Essayer avec un exemple », marqués « exemple », jamais
  liés à un lead ni à un devis.
- **Tâches** : 1. Service + route « créer un exemple » depuis les goldens d'ACAL382 ; fini quand l'exemple s'ouvre,
  marqué, sans lead. `SV/creation.py`, `views/`. @after ACAL382. 2. Bouton sur la liste vide ; fini quand la liste vide
  le montre. `FC/CalepinageList.jsx`.
- **Score** : 12 × 2 ÷ 2 = **12** · rang 11. **À confirmer par le fondateur** (données d'exemple dans la société de
  production — cf. incident « comptes de démo » clos le 30/09).

### CAP-D6-10 — Variantes en un clic, à conditions égales : « le plus de panneaux » / « couvrir ma facture »
- **Besoin** : comparer sans refaire ; deux propositions d'un geste ; « comparer des dispositions à pertes identiques ».
- **Preuves** : B2 r2 (OpenSolar Max Offset/Max Fit, Solargraf) ; B6 R16 (3 outils) ; B4 wishlist 10 ; B5-nl 6 (4 fils) ;
  B5-de K28 ; B5-en I (13 fils). URL : https://www.opensolar.com/?p=14292
- **Chez nous** : **PARTIEL.** Variantes et comparaison PRÉSENTES (`SV/variantes.py::creer_variante`,
  `FC/VariantesCompare.jsx`, `SV/comparaison_projets.py`) ; les deux optimiseurs existent côté navigateur
  (`apps/web/src/lib/layoutVariability.ts::fillAll`, `apps/web/src/lib/estimatorBrainV2.ts::neededPanelsForTarget`) ;
  aucun bouton ne crée les deux variantes. Le comparatif n'explique aucune colonne (§0, 4 grandeurs nues).
- **Plus petite version** : « Comparer : le plus de panneaux / couvrir la facture » crée deux variantes avec les MÊMES
  réglages de pertes et la même météo, puis ouvre le comparatif existant ; colonnes expliquées (CAP-D6-03).
- **Tâches** : 1. Bouton qui crée les deux variantes ; fini quand le comparatif s'ouvre sur deux colonnes de même
  météo. `ToitureDesign.jsx`, `FC/VariantesCompare.jsx`. 2. Le comparatif imprime « mêmes hypothèses de pertes et de
  météo » ou nomme ce qui diffère ; fini quand deux variantes à réglages différents le disent. `SV/comparaison.py`.
  (Le choix du dimensionnement PAR DÉFAUT sur la facture relève de D2 : voir §4.)
- **Score** : 12 × 3 ÷ 2 = **18** · rang 7.

### CAP-D6-11 — Dossier par distributeur (pièces exigées, version du formulaire, date de vérification)
- **Besoin** : « les exigences du distributeur changent le dossier » ; « formulaire périmé = refus ».
- **Preuves** : B5-de P9 + K47 (43 fils en passe 2), K15 ; B5-es 3 (21 fils) ; B7 U15 ; B5-nl 3 (8 fils). URL :
  https://canalsolar.com.br/projetos-7-5-kw-podem-ser-reprovados-por-inversao-de-fluxo/ ;
  https://forum.valentin-software.com/topic/10077-kabel-schaltplan-vnb-w%C3%BCnsche/
- **Chez nous** : **PARTIEL.** Gabarits de dossier FOURNIS par la société avec clés préremplies
  (`apps/calepinage/models.py::GabaritDossierReglementaire`), dossiers et statut d'avancement (`DossierReglementaire`,
  `FC/documents/DossiersReglementaires.jsx`) ; aucun champ « distributeur » (grep ONEE / Lydec / Redal / Amendis /
  distributeur dans `SV/gabarits.py`, `SV/reglementaire.py`, `models.py` : 0).
- **Plus petite version** : la société range un gabarit par distributeur (nom, version, « vérifié le ») ; le calepinage
  choisit le distributeur (saisi, pas déduit de la ville) et le pack signale les pièces manquantes. Aucune exigence
  marocaine écrite dans le code.
- **Tâches** : 1. Champs `distributeur`, `version_formulaire`, `verifie_le` sur le gabarit (migration additive) ; fini
  quand deux gabarits du même type coexistent pour deux distributeurs. `models.py`, `SV/gabarits.py`. 2. Choix du
  distributeur dans Documents et contrôle « pièces manquantes » repris par CAP-D6-04 ; fini quand un gabarit vérifié il y
  a plus de N jours (N saisi par la société) sort en orange. `FC/documents/DossiersReglementaires.jsx`.
- **Score** : 16 × 2 ÷ 2 = **16** · rang 8. **Entrée à fournir par Reda / la société** : la liste des distributeurs et de
  leurs pièces (aucune source marocaine lue par les lanes).

### CAP-D6-12 — Partage avec le client hors du PDF : vidéo d'orbite pour WhatsApp, modules sur la photo du site, pertes en mots simples
- **Besoin** : « montrer l'ombre et le toit au client » ; « un aperçu du toit équipé » ; « mes clients ne comprennent pas
  les graphiques ».
- **Preuves** : B3 N32 (Arka « Video Recorder ») ; B6 R18 (4 outils, lien 3D), K50 (5 outils) ; B1 C12, B5-fr 33 / R18,
  B5-es 19 (photo-simulation, page éditeur seule) ; B4 r2, wishlist 6 ; B5-es K35 (11 fils) ; B5-nl 17 ; B4 r18 et
  wishlist 7 (suivi de lecture).
- **Chez nous** :
  - Lien 3D en lecture seule avec jeton : **PRÉSENT** — la page client `apps/web/src/pages/proposition/[...token].astro`
    monte la visionneuse 3D (`buildViewerModel`, `viewerConfig`, l. ~1781-1805, `RP/viewerFullBoot.ts`) ; le suivi
    « devis ouvert » existe (`backend/django_core/apps/ventes/public/lecture_views.py`). Soleil animé dedans : ACAL487
    GATED (autre propriétaire : web).
  - Vidéo d'orbite : **ABSENT** (grep `MediaRecorder|captureStream` : seulement `frontend/src/features/ia/voice/` et
    `installations`).
  - Modules sur la photo : **ABSENT** — `FC/PhotoSiteCalage.jsx` drape la PHOTO sur la carte (« aucune reconstruction
    3D : un aperçu 2D drapé »), pas les modules sur la photo.
  - Pertes en mots simples pour le client : **ABSENT** (rapport interne seulement).
- **Plus petite version** : (a) bouton « Vidéo 10 s » dans l'atelier : orbite de la scène enregistrée en WebM, fichier
  téléchargé que la commerciale envoie elle-même ; (b) « Voir sur la photo » : projection inverse du calage 4 coins,
  PNG ; (c) feuille « vos pertes en 6 postes » d'abord INTERNE (rapport d'étude), version client seulement par `/proposal`.
- **Tâches** (toutes GATED sur la confirmation du fondateur, visibles du client) : 1. Vidéo d'orbite téléchargeable ;
  fini quand le fichier fait 10 s et ne contient aucun prix. `RP/` (nouveau `videoOrbite.ts`), `ToitureDesign.jsx`.
  2. Modules projetés sur la photo calée, export PNG ; fini quand les 4 coins d'une photo calée donnent l'image.
  `FC/PhotoSiteCalage.jsx`, `frontend/src/lib/calage/apercuDrape` (propriétaire non vérifié). 3. Section « pertes en mots
  simples » dans le rapport d'étude interne ; fini quand l'exemple l'imprime. `SV/rapport/pertes.py`.
- **Ce qu'il réutilise** : la page `/proposition/<token>` (propriétaire **web**) et son suivi de lecture (ventes) pour
  tout ce qui irait au client EN LIGNE ; rien de nouveau public. Règle n° 4 : rien ne change le PDF `/proposal`.
- **Score** : 14 × 2 ÷ 2 = **14** · rang 9 ex aequo.

### CAP-D6-13 — Confiance dans l'outil : feuille de vérification « à la main » et mesuré contre simulé
- **Besoin** : « pouvoir refaire le calcul dans mon Excel et le justifier » ; « le réel est 20 % sous la prévision ».
- **Preuves** : B5-es 4 (6 fils) et K09 (6) ; B1 C08 ; B7 U5 (8 sources) ; B5-fr R2 (7) ; B4 P19 ; B5-de K14 (48 fils).
  URL : https://www.solarweb.net/forosolar/fotovoltaica-sistemas-conectados-red/2407-pros-contras-pvsyst-pvsol.html ;
  https://forum-photovoltaique.fr/viewtopic.php?t=66634
- **Chez nous** : **ABSENT.** `SV/export_tableur.py` : 3 feuilles + provenance, formules neutralisées contre l'injection,
  aucune feuille de vérification (« formule » : 0 dans `SV/note_calcul.py`) ; l'as-built compare le POSÉ au prévu
  (`SV/asbuilt.py`), pas l'énergie ; la recette avec Pmax attendu vit côté ventes (`apps/ventes/commissioning.py`, cité
  par B5-es, non rouvert).
- **Plus petite version** : (a) feuille « Vérification » de l'export : Voc à froid = N × Voc × (1 + β × (Tmin − 25)),
  écrite en TEXTE avec les valeurs de la fiche ; (b) page « Livré vs prévu » : 12 valeurs mensuelles collées, écart % au
  P50 ; réservée SAV/gérant.
- **Tâches** : 1. Feuille « Vérification » (chaînes, DC/AC, chute de tension) avec formules en texte ; fini quand un
  ingénieur retrouve la Voc à froid de l'écran à 0,1 V. `SV/export_tableur.py`. 2. Saisie de 12 valeurs mesurées et écart ;
  fini quand l'exemple rend 12 écarts. `SV/asbuilt.py`, `FC/atelier/PoseReelle.jsx`.
- **Score** : 16 × 2 ÷ 2 = **16** · rang 8 ex aequo.

### CAP-D6-14 — Pack de remise et de sécurité pour l'équipe de pose
- **Besoin** : « le plan, les strings et les écarts DOIVENT être sur le chantier » ; tension DC « sous tension dès
  qu'éclairé » ; QR vers le dossier.
- **Preuves** : B5-de K51 (13 fils en passe 2), P13, P5 ; B3 N9, N10 ; B5-es 7 (7 fils) ; B6 R50 (3 outils), K80 (6 outils) ;
  B2 r4, B6 R44 (repères, ancrages). URL : https://www.energiesparhaus.at/forum-pv-anlageninstallation-typische-maengel/78984
- **Chez nous** : **PARTIEL.** `SV/pack_technique.py::SPEC_PIECES` (8 pièces dont plan de pose terrain ACAL237),
  `construire_dossier_fin_chantier`, `manuel_proprietaire`, `document_asbuilt` ; le chantier reçoit `planche_url` et un
  `plan_pose_url` qui pointe la page 3D du devis (`backend/django_core/apps/installations/calepinage_retenu.py`, l. 42-43) ;
  aucun QR (grep), aucune légende de tension DC par chaîne sur le plan de pose (non vérifié finement).
- **Plus petite version** : légende « tension DC maxi à froid par chaîne » (valeur déjà calculée) + QR vers le dossier
  sur la planche ; le PDF du plan de pose joint à la fiche chantier (pas un lien).
- **Tâches** : 1. Légende de tension DC par chaîne sur le plan de pose ; fini quand le PDF d'exemple porte une ligne par
  chaîne. `SV/planche.py`. 2. QR vers le dossier de l'ouvrage (jeton existant) ; fini quand le QR se lit. `SV/planche.py`.
  3. Plan de pose consultable hors ligne dans la fiche chantier → `apps/installations/` = propriétaire **chantiers**
  → **PLAN_AUDIT_CHANTIERS.md**.
- **Score** : 14 × 2 ÷ 2 = **14** · rang 9 ex aequo. (Recoupe D2 pour le contenu du plan de pose — P5 — et D3 pour la
  fiche de mesures de réception P22 : non pris ici.)

### CAP-D6-15 — File de demandes « calepinage à faire » entre commerciale et technicien
- **Besoin** : la commerciale demande, le technicien dessine, chacun voit où en est la demande.
- **Preuves** : B2 r10 (OpenSolar Design Request queue) ; B6 K58 (5 outils, « travail d'équipe »).
  URL : https://www.opensolar.com/rolesandpermissions/
- **Chez nous** : **PARTIEL.** `Calepinage.responsable` (FK, `apps/calepinage/models.py` l. 157) ; l'assistant liste
  « Calepinages à traiter » de l'utilisateur (`apps/calepinage/agent_actions.py::A_TRAITER`, route `a-traiter/`) ; aucun
  geste « Demander un calepinage à … » ni liste « demandes reçues ».
- **Plus petite version** : depuis le lead, « Demander le dessin à » (un utilisateur du rôle choisi) crée ou ouvre LE
  calepinage du lead (D-ACAL-12) avec ce responsable et une notification ; la liste a un filtre « Mes demandes ».
- **Tâches** : 1. Route « demander » (responsable + note + notification) ; fini quand le technicien reçoit la
  notification et la voit dans « Mes demandes ». `SV/creation.py`, `views/`, `FC/CalepinageList.jsx`. 2. Bouton sur la
  fiche du lead → `IdentityRail.jsx` (lead) → **PLAN_AUDIT_LEAD.md**.
- **Score** : 4 × 2 ÷ 2 = **4** · rang 15 (preuve d'éditeur seule).

### CAP-D6-16 — La taille maximale mesurée, publiée, et un refus nommé au-delà
- **Besoin** : « pas de plantage à 3 MWc » ; « refus nommé quand le modèle importé est trop lourd ».
- **Preuves** : B5-en 20 (5 fils), D (19 fils) ; B5-de K07 (12) ; B4 r20 ; B6 K79 (5 outils). URL :
  https://forum.valentin-software.com/topic/7087-i-want-to-zoom-out-more-to-see-the-entire-model-with-modules/
- **Chez nous** : **PARTIEL.** Budget de coût PUR à 10 000 modules dans node, sans GPU (`RP/perf.test.ts`, CALX388) ;
  fluidité WebGL à 500 modules planifiée (ACAL440) ; aucune limite publiée ni refus nommé (grep `MAX_MODULES|trop de
  modules` : rien).
- **Plus petite version** : mesurer une fois au vrai rendu (ACAL440 étendue à 2 000 / 5 000 / 10 000), publier la limite
  dans l'aide et refuser au-delà avec un message qui la cite.
- **Tâches** : 1. Étendre la spec d'ACAL440 à trois tailles et écrire la limite mesurée ; fini quand la limite est un
  nombre committé issu de la mesure. 2. Refus nommé au-delà ; fini quand un pavage au-delà affiche la limite.
  `RP/optimizer.ts`. @after ACAL440.
- **Score** : 12 × 1 ÷ 1 = **12** · rang 11 ex aequo.

### CAP-D6-17 — Relevé de terrain en réseau faible : photos mises en file et envoyées à la reconnexion
- **Besoin** : « l'écran dit "en attente" puis "envoyé" ».
- **Preuves** : B7 U2 (12 sources, applis d'installateurs) ; B4 r17 ; B6 R12 (3 outils) ; B4 wishlist 20.
  URL : https://apps.apple.com/us/app/solaredge-mapper/id432768469
- **Chez nous** : **PARTIEL.** Brouillon local de l'atelier (`FC/brouillon.js`, ACAL84) ; brouillon serveur ACAL400 et
  téléphone ACAL423/482 planifiés ; la file hors ligne existe pour le CHANTIER (`apps/installations/field_sync.py`), pas
  pour le relevé du calepinage (non vérifié dans `FC/atelier/PanneauReleve.jsx`, non lu).
- **Tâches** : 1. File d'envoi des photos du relevé ; fini quand une photo prise hors ligne part à la reconnexion.
  `FC/atelier/PanneauReleve.jsx`. @after ACAL423.
- **Score** : 10 × 2 ÷ 2 = **10** · rang 13.

### CAP-D6-18 — Documents éditables (Word) et textes à variables du modèle société
- **Besoin** : « rendre le rapport en Word avec mon modèle » ; « insérer {nombre de modules} dans mes textes ».
- **Preuves** : B1 C19 ; B5-es 12 (2) ; B7 U26 (3) ; B5-de P19 (10 voix, 1 fil), K23 (10 fils). URL :
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-conectados-red/46544-software-diseno-autoconsumos-fv.html
- **Chez nous** : **ABSENT.** Aucun `docx` dans le module ni dans `requirements.txt` (weasyprint, openpyxl seulement) ;
  sections société `SV/rapport/sections_societe.py` sans variable (grep `{{|format(` : 0).
- **Plus petite version** : variables d'une liste fermée dans les sections société (aperçu rendu) ; DOCX du rapport
  INTERNE seulement si Reda le veut (nouvelle dépendance).
- **Tâches** : 1. Variables de liste fermée dans les sections société ; fini quand « {nombre_modules} » rend le nombre
  dans l'aperçu. `SV/rapport/sections_societe.py`. 2. (GATED fondateur : nouvelle dépendance) Export DOCX du rapport
  interne.
- **Score** : 8 × 1 ÷ 2 = **4** · rang 15 ex aequo.

### CAP-D6-19 — Pouce haut / bas sur le remplissage automatique, avec un motif
- **Besoin** : dire en un geste « cette pose auto est mauvaise, parce que… ».
- **Preuves** : B2 r17 (OpenSolar 3.3). URL : https://www.opensolar.com/product-updates/release-3-3-0/
- **Chez nous** : **ABSENT** (grep `pouce|thumb` : rien de tel) ; le journal accepte une note libre
  (`SV/journal.py::noter`).
- **Tâches** : 1. Deux boutons sous la recommandation qui écrivent une note de journal typée ; fini quand la note apparaît
  au journal. `RP/optimizer.ts`, `SV/journal.py`.
- **Score** : 2 × 1 ÷ 1 = **2** · rang 17.

---

## 2. Table de synthèse (rang, capacité, verdict, tâches, effort)

| Rang | CAP | Titre | Verdict | Tâches | Effort | Score |
|---|---|---|---|---|---|---|
| 1 | CAP-D6-01 | Voyant de plausibilité (écart à PVGIS) | PRÉSENT SANS ÉCRAN | 2 | S | 48 |
| 2 | CAP-D6-03 | « Pourquoi ce chiffre ? » par grandeur | PARTIEL (HelpTip non branché) | 5 | M | 30 |
| 3 | CAP-D6-05 | Un seul chiffre par grandeur, partout | PARTIEL (causes trouvées) | 4 | M | 30 |
| 3 | CAP-D6-06 | Mode salon + fin de parcours | DÉJÀ PLANIFIÉ en partie / ABSENT pour le reste | 4 | M | 30 |
| 4 | CAP-D6-02 | Ce que le calcul ne modélise pas | PRÉSENT SANS ÉCRAN (partiel) | 1 | S | 24 |
| 5 | CAP-D6-07 | Pourquoi aucun module / pourquoi si bas | ABSENT | 2 | M | 21 |
| 6 | CAP-D6-04 | « Prêt à envoyer ? » | PARTIEL (16 contrôles calculés, aucun panneau) | 5 | L | 20 |
| 7 | CAP-D6-10 | Variantes en un clic à conditions égales | PARTIEL | 2 | M | 18 |
| 8 | CAP-D6-11 | Dossier par distributeur | PARTIEL | 2 | M | 16 |
| 8 | CAP-D6-13 | Feuille de vérification + mesuré vs simulé | ABSENT | 2 | M | 16 |
| 9 | CAP-D6-08 | Heure légale / heure solaire | ABSENT à l'écran | 1 | S | 14 |
| 9 | CAP-D6-12 | Partage client hors PDF (vidéo, photo, pertes) | Lien 3D PRÉSENT, reste ABSENT | 3 (GATED) | M | 14 |
| 9 | CAP-D6-14 | Pack de remise chantier | PARTIEL | 3 (1 routée) | M | 14 |
| 11 | CAP-D6-09 | Calepinages d'exemple | ABSENT | 2 | M | 12 |
| 11 | CAP-D6-16 | Taille maximale mesurée et publiée | PARTIEL | 2 | S | 12 |
| 13 | CAP-D6-17 | Photos du relevé en file hors ligne | PARTIEL | 1 | M | 10 |
| 15 | CAP-D6-15 | File de demandes commerciale → technicien | PARTIEL | 2 (1 routée) | M | 4 |
| 15 | CAP-D6-18 | Word + variables de textes | ABSENT | 2 (1 GATED) | M | 4 |
| 17 | CAP-D6-19 | Pouce haut/bas sur la pose auto | ABSENT | 1 | S | 2 |

**19 fiches, 46 tâches** (dont 5 routées vers un autre propriétaire et 4 GATED fondateur).

---

## 3. La liste du panneau « prêt à envoyer ? » — déjà calculé vs manquant

Sources : B5-de §11 (18 reproches aux offres, 98 fils), B3 N6, B4 r6, constats des relecteurs. Le point « prix /
paiement » (87 fils) reste au devis (règle n° 4) et n'est pas dans le panneau.

| # | Contrôle | État chez nous | Preuve |
|---|---|---|---|
| 1 | Visite technique validée (si la société l'exige) | CALCULÉ (bloque) | `SV/feu_vert.py::verifier_avant_publication` |
| 2 | Approbation à jour (non périmée, pas l'auteur) | CALCULÉ (bloque si exigée) | `SV/approbation.py::est_approuve`, `approbation_perimee` |
| 3 | Verdict électrique : bloquants et valeurs sans source | CALCULÉ (bloque, dérogation tracée) | `SV/electrique.py::verdict_publiable` ; `FC/BoutonDevis.jsx` (bloquants, « Passer outre ») |
| 4 | Matériel non désigné / fiche incomplète | CALCULÉ mais affiché « Publiable » (D-ACAL-9 : ne bloque pas) → doit sortir ORANGE | `_rapport_publication` (STATUT_NON_VERIFIABLE) ; T1-F1-010, T1-S1-020 |
| 5 | Voc à froid sous la limite, avec la température utilisée | CALCULÉ | `CE/chaines.py::fenetre_admissible` |
| 6 | Une orientation par chaîne, MPPT par orientation | CALCULÉ | `SV/polystring.py`, `_motifs_du_polystring` |
| 7 | Ratio DC/AC dans la fourchette de la société | CALCULÉ (fourchette saisie) | `SV/electrique.py::_bloc_ratio_dc_ac` |
| 8 | Chutes de tension, tronçons calculables | CALCULÉ | `_motifs_des_troncons` (`SV/troncons.py`) |
| 9 | Terre, protections, régime de neutre | CALCULÉ | `_motifs_de_la_terre`, `MOTIF_REGIME_NON_PRECISE` |
| 10 | Productible spécifique recoupé avec PVGIS | CALCULÉ SANS ÉCRAN (verdict seulement avec tolérance société) | `SV/validation.py::ecart_vs_pvcalc` (→ CAP-D6-01) |
| 11 | kWh déclaré contredit par les factures | CALCULÉ (refus 409) | `SV/devis.py::_garde_kwh_declare` |
| 12 | Conception changée depuis le devis (périmé) | CALCULÉ | `layout_stale` (`apps/ventes/serializers.py`), `FC/BadgePerime.jsx` |
| 13 | Simulation absente ou périmée | CALCULÉ | bandeaux `simulation_perimee` (`FC/production/PanneauProduction.jsx`) |
| 14 | Perte d'ombrage par pan chiffrée | CALCULÉ (cascade, rapport d'ombrage) ; verdict de lecture ABSENT (seuils d'affichage à saisir) | `SV/rapport_ombrage.py` ; B3 N7 |
| 15 | Pièces du dossier réglementaire fournies | CALCULÉ | `DossierReglementaire` (statut, avancement) |
| 16 | Hypothèses de consommation nommées et datées | CALCULÉ selon B5-de §11 n° 17 (NON RELU ici) | `SV/consommation.py` |
| 17 | Pentes et faces jamais confirmées | PLANIFIÉ | ACAL417, ACAL426 |
| 18 | Taille sans facture : « le toit est rempli : N kWc » | MANQUANT | T1-S1-007 (131 kWc pour une villa) |
| 19 | Nombre × Wp = kWc annoncé, un seul Wp par module | Calcul présent (`SV/mesures.py::mesures_du_document`), affichage FAUX (`RP/optimizer.ts` l. 955 « × 720 W ») → MANQUANT comme contrôle | T1-F1-004, T1-F1-024 |
| 20 | Une seule production et une seule puissance entre écrans | MANQUANT | T1-S1-005, T1-S1-018 |
| 21 | Pans laissés vides / toit sous-garni : motif dit | MANQUANT (le maximum existe : `FC/RemplissageProuve.jsx`) | B5-de §11 n° 2 (14 fils) |
| 22 | Obstacle hors du pan ou à cheval sur la rive | MANQUANT (`core/calepinage/garde_fous.py::valider` contrôle les TABLES, chemin AO/moteur) | T1-F1-021 |
| 23 | Compatibilité optimiseur / onduleur / batterie | MANQUANT dans le calepinage (`apps/ventes/compatibilites.py` existe, non appelé) | B5-de §11 n° 16 (22 fils) |
| 24 | Schéma de secours si stratégie « backup » | MANQUANT (→ D3/D5, P21) | B5-de K53 (22 fils) |

**Bilan : 16 contrôles déjà calculés quelque part (dont 1 sans écran et 2 à montrer autrement), 1 planifié, 7 manquants.**

---

## 4. Motifs transversaux offerts aux autres domaines (D1-D5 ne sont pas pris ici)

| Domaine | Besoin du domaine | Motif D6 où il se branche |
|---|---|---|
| D1 Site / toit | erreur JS à la molette (T1-S1-004, T1-F1-001), double-clic qui perd un coin (T1-S1-025), cadrage après tracé (T1-F1-003), « Bâtiment sans id » (T1-S1-012), garde-fous de saisie (60° contre 60 %, lat/long inversés : B5-fr R7, B7 U27), horizon au téléphone | CAP-D6-03 (phrase + champ nommé), CAP-D6-04 ligne 17/22, messages d'erreur qui nomment le champ |
| D2 Pose / fixation | cible de la facture perdue après « Effacer » (T1-S1-024), dimensionner par défaut sur la facture (T1-S1-007, OpenSolar Max Offset), plan de pose complet (P5), planche à fausse échelle (T1-F1-020), châssis et acrotère (T1-F1-025), recommandation 35° sur lest (T1-F1-023) | CAP-D6-04 lignes 18, 21 ; CAP-D6-10 (présentation des deux options) ; CAP-D6-14 |
| D3 Électrique | tableau de dimensionnement visible (T1-F1-011), unifilaire complet (T1-F1-012), deux saisies des phases (T1-F1-013), plan de chaînes sur le toit (T1-F1-015), aide en direct pendant le chaînage (B3 N18), comparer 2-3 onduleurs (C10/N31/U6), « nécessaire / facultatif » sur la fiche (B4 r15), fiche de réception P22 | CAP-D6-03 (Voc, Vmp, DC/AC, écrêtage), CAP-D6-04 lignes 3-9, 23 ; CAP-D6-10 (comparatif) |
| D4 Simulation / rapport | mode météo refusé puis 2e refus (T1-F1-016/017, T1-S1-016), 37 réglages (T1-S1-022), 409 à l'ouverture de Production (T1-S1-021, T1-F1-018), rapport qui expire à 20 s (T1-F1-019), synthèse 1 page (C04), Sankey (C01), verdict d'ombrage en une phrase (N7), seconde source météo (C06) | CAP-D6-01, 02, 03, 07 ; CAP-D6-04 lignes 10, 13, 14 ; profil de départ = ACAL387/403-405 (déjà planifié) |
| D5 Stockage / pompage | batterie « inutilisée 99,98 % du temps », secours, pompage (données manquantes avant chiffrage, B5-fr R10) | CAP-D6-03 (capacité utile, autonomie, HMT, débit), CAP-D6-04 ligne 24, CAP-D6-07 (« pourquoi si bas » appliqué aux m³) |

---

## 5. Correspondance : chaque proposition des lanes → son sort

| Id d'origine | Sort |
|---|---|
| B1 C04 synthèse 1 page | → D4 (rapport) |
| B1 C08 mesuré vs simulé | CAP-D6-13 |
| B1 C10 comparer onduleurs | → D3 (comparatif présenté par CAP-D6-10) |
| B1 C12 photo + modules | CAP-D6-12 |
| B1 C13 liste des objets | → D1 |
| B1 C18 exemples | CAP-D6-09 |
| B1 C19 DOCX / arabe | CAP-D6-18 (DOCX) ; arabe → écarté (§6) |
| B2 r2 deux propositions | CAP-D6-10 |
| B2 r10 file de demandes | CAP-D6-15 |
| B2 r17 pouce | CAP-D6-19 |
| B2 r19 voix | DÉJÀ PRÉSENT (agent d'actions, §7) |
| B2 r20 drone vs design | → D1 |
| B3 N5 mode salon | CAP-D6-06 |
| B3 N6 prêt à envoyer | CAP-D6-04 |
| B3 N7 verdict d'ombrage | → D4 (motif CAP-D6-03) |
| B3 N9 / N10 fiche de pose, plan hors ligne | CAP-D6-14 (+ D2 pour le contenu) |
| B3 N15 devis rapide → atelier | CAP-D6-06 (porte unique, routée lead) ; le pont de valeurs = extension d'ACAL421 (DÉJÀ PLANIFIÉ en partie) |
| B3 N16 verrou à l'acceptation | DÉJÀ PRÉSENT (§7) |
| B3 N17 photo de facture | → D4 / ventes (consommation) |
| B3 N18 aide en direct au chaînage | → D3 (motif CAP-D6-03) |
| B3 N24 préliminaire vs relevé | → D1 |
| B3 N28 / N29 | CAP-D6-07 |
| B3 N30 plages « normales » des pertes | écarté tant qu'aucune source publiée (§6) |
| B3 N31 comparer onduleurs | → D3 |
| B3 N32 vidéo WhatsApp | CAP-D6-12 |
| B4 r1, r28 | CAP-D6-03 |
| B4 r2 pertes au client | CAP-D6-12 (interne d'abord) |
| B4 r6 contrôles avant devis | CAP-D6-04 |
| B4 r15 nécessaire / facultatif | → D3 (motif) |
| B4 r16 limites | CAP-D6-02 |
| B4 r17, r19 hors ligne / téléphone | CAP-D6-17 ; téléphone = ACAL423/482 (DÉJÀ PLANIFIÉ) |
| B4 r18 suivi de lecture | DÉJÀ PRÉSENT côté ventes (`lecture_views.py`) |
| B4 r20 refus du modèle trop lourd | CAP-D6-16 |
| B4 r12 heure légale | CAP-D6-08 |
| B4 P5 « une seule vérité » | CAP-D6-05 |
| B4 P14/P19, S1-S14 (questions) | CAP-D6-01 / 03 |
| B5-de P1 | CAP-D6-01 + 03 |
| B5-de P7 | CAP-D6-02 |
| B5-de P9 | CAP-D6-11 |
| B5-de P13 | CAP-D6-14 |
| B5-de P14 fiche de relecture | CAP-D6-04 (exportable) — pas de fiche à part |
| B5-de P19 variables | CAP-D6-18 |
| B5-de P20 | CAP-D6-04 |
| B5-de P21 secours, P22 réception | → D3 / D5 (ligne 24 du §3 pour P21) |
| B5-de K08 premier contact | CAP-D6-09 + ACAL420 |
| B5-fr R1 | CAP-D6-03 |
| B5-fr R2 | CAP-D6-13 |
| B5-fr R7 garde-fous de saisie | → D1 (motif CAP-D6-03/04) |
| B5-fr R18 photo | CAP-D6-12 |
| B5-fr R19 documents en arabe | écarté (§6) |
| B5-en 1 | CAP-D6-03 |
| B5-en 6 diagnostic de fichier refusé | → D4 (météo, charge) ; motif « erreur qui nomme la ligne » |
| B5-en 14 | CAP-D6-02 |
| B5-en 20 | CAP-D6-16 |
| B5-es 1, K11, K35 | CAP-D6-03 (+ CAP-D6-12 pour le client) |
| B5-es 3 | CAP-D6-11 |
| B5-es 4 | CAP-D6-13 |
| B5-es 7 consignes DC | CAP-D6-14 |
| B5-es 8 | CAP-D6-08 |
| B5-es 12 DOCX | CAP-D6-18 |
| B5-es 19 photo-simulation | CAP-D6-12 |
| B5-nl 4 contrôle sans dessin | → D3 |
| B5-nl 6 / 17 / 27 | 6 → D4 ; 17 = lien 3D PRÉSENT ; 27 langue → écarté |
| B5-nl 8 interface arabe | écarté (§6) |
| B6 R7 | CAP-D6-06 |
| B6 R15 | CAP-D6-04 |
| B6 R16 | CAP-D6-10 |
| B6 R18 lien 3D | PRÉSENT (corrige B6) |
| B6 R23 info-bulle par élément | CAP-D6-03 |
| B6 R35 passerelle devis rapide | CAP-D6-06 / ACAL421 |
| B6 R39 | CAP-D6-07 / 12 |
| B6 R49 graphes du rapport au choix | → D4 |
| B6 R50 QR | CAP-D6-14 |
| B6 R52 | CAP-D6-09 |
| B6 R57 | CAP-D6-08 |
| B6 R63 voix | DÉJÀ PRÉSENT (§7) |
| B6 R44 repères de sécurité | → D2 (plan de site) |
| B7 U2 | CAP-D6-17 |
| B7 U4 | CAP-D6-09 |
| B7 U5 | CAP-D6-13 |
| B7 U11 | → D4 (motif) |
| B7 U14 plages normales | écarté sans source (§6) |
| B7 U19 | CAP-D6-03 |
| B7 U22 | CAP-D6-02 |
| B7 U26 | CAP-D6-18 |
| B7 U27 | → D1 (motif) |
| Relecteurs S1-001/027 | CAP-D6-06 t4 (routé lead) |
| S1-002, 010, 011, 012, 014, 015 ; F1-022 | CAP-D6-06 (+ ACAL393/394/399/402 planifiées) |
| S1-003 | CAP-D6-04 (dédoublonnage = ACAL392) |
| S1-005, 006, 017, 018, 023 ; F1-004, 006, 007, 024, 026 | CAP-D6-05 (F1-026 aussi CAP-D6-01) |
| S1-007, 008, 009, 020 ; F1-010, 021 | CAP-D6-04 |
| S1-013 confirmation hors de vue | ACAL399 (DÉJÀ PLANIFIÉ) |
| S1-016, 022 ; F1-016, 017 | profil de départ ACAL387/403-405 (DÉJÀ PLANIFIÉ) ; boucle de refus → D4 |
| S1-019, 026 ; F1-014 | CAP-D6-03 |
| S1-004, 021, 024, 025 ; F1-001-003, 005, 008, 009, 011-013, 015, 018-020, 023, 025 | → D1-D4 (voir §4) |

---

## 6. Écarté (raison en une ligne)

- **Plages « normales » des pertes (B3 N30, B7 U14)** : sans source publiée, ce serait un chiffre inventé ; ne revient
  que si une source est apportée (et alors comme repère d'affichage saisi, D-ACAL-31).
- **Interface et documents en arabe (B1 C19 arabe, B5-fr R19 : 0 fil, B5-nl 8 : 0 voix, B3 §4)** : aucune preuve
  d'utilisateur ; `SV/documents/libelles_document.py::LANGUES_SERVIES = ('fr', 'en')` ; à demander à Reda, rien à planifier.
- **« Ask AI » pour retoucher le schéma (B3 §4)** : coût d'IA par retouche et risque électrique ; les phrases déterministes
  rendent le service.
- **Indicateurs d'argent dans le calepinage (retour, TRI en direct ; K44, K71)** : l'argent reste dans `apps/ventes`.
- **Pages client à chapitres et jetons `{…}` dans le PDF (B3 §4)** : règle n° 4 (`/proposal` seul chemin du PDF client).
- **Export DWG (B5-nl 7)** : une page éditeur seule ; DXF existe.
- **Commande vocale au-delà de l'existant (B2 r19, B6 R63)** : déjà servi par l'agent ; la voix ne confirme jamais (règle AG).

---

## 7. Déjà présent ou déjà planifié (ne pas reconstruire)

| Capacité | Où |
|---|---|
| Verrou à l'acceptation + « dupliquer pour modifier » | PRÉSENT : `SV/verrou.py::est_verrouille` = prédicat ventes (accepté → « Réviser (v2) ») ; D-ACAL-2, D-ACAL-3, ACAL42, ACAL92 cochées |
| Lien 3D en lecture seule à jeton + suivi « devis ouvert » | PRÉSENT : `apps/web/src/pages/proposition/[...token].astro` (visionneuse), `apps/ventes/public/lecture_views.py` |
| Modèles et bibliothèques de la société | PRÉSENT : `SV/modeles.py::creer_depuis_modele`, `SV/presets.py::jeux_de_societe`, `SystemeFixation` |
| Rôles / approbation | PRÉSENT : `SV/approbation.py` (droit `calepinage_approuver`, refus de l'auto-approbation) |
| Assistant / voix | PRÉSENT : `apps/calepinage/agent_actions.py` (11 actions dont `calepinage.du_lead`, `resume`, `simuler`, `a_traiter`) ; voix `frontend/src/features/ia/voice/` |
| Parcours 5 étapes, mode expert, barre d'enregistrement, studio, aide de tracé, bulles d'onglets | PLANIFIÉ : ACAL386, 392-395, 399, 401, 402, 419, 420, 478 |
| Profil de départ sourcé (37 réglages) | PLANIFIÉ : ACAL387, 403-405 (D-ACAL-31) |
| « Ce qui manque » → champ exact ; pentes non confirmées | PLANIFIÉ : ACAL397, ACAL417, ACAL426 |
| Conception automatique depuis le lead | PLANIFIÉ : ACAL421 (le pont « devis rapide → atelier » en est l'extension) |
| Téléphone | PLANIFIÉ : ACAL423, ACAL482 |

---

## 8. Contradictions entre lanes tranchées par le code

1. **Verrou du dessin à l'acceptation** — B3 N16 : « aucun verrou (grep `verrouill` : 0 dans apps/calepinage) ». **Faux** :
   `SV/verrou.py` existe (prédicat ventes, « Réviser (v2) » seul geste de réouverture). Aucune décision à demander.
2. **Lien client 3D à jeton** — B6 R18 : « aucun jeton public côté backend, NOUVEAU ». **Faux** : la page
   `/proposition/<token>` monte la visionneuse 3D et ventes trace la lecture ; B4 n° 32 (« PRÉSENT ») avait raison.
3. **Garde-fous « 9 contrôles » (B5-fr 23)** — cités comme garde de saisie : `core/calepinage/garde_fous.py::valider` contrôle
   des TABLES posées (chevauchement, rives, dégagements), appelé par `apps/calepinage/moteur_service.py` et
   `core/calepinage/orientation.py` ; ce n'est ni un contrôle de saisie ni un contrôle d'obstacle hors pan (T1-F1-021).
4. **« Pourquoi ce chiffre » ABSENT (B5-es) vs PARTIEL (B4, B5-en)** : les deux disent vrai à moitié — le composant
   `HelpTip` et le lexique EXISTENT (0 branchement dans le module), les motifs serveur existent : verdict PARTIEL.
5. **« Publiable » avec 11 « Non vérifiable » (T1-F1-010)** — conforme au code et à D-ACAL-9 (« indéterminé » ne bloque
   pas) : ce n'est pas un faux verdict mais un affichage trompeur ; la correction est un ORANGE dans le panneau, pas un
   changement de règle (aucune décision fondateur nécessaire).
6. **« Mode expert » « planifié D-ACAL-32 » (B6 R7) vs « NON planifié » (B3 N5)** : le mode expert est planifié (ACAL394) ;
   le mode SALON (bascules seules à l'étape Panneaux) ne l'est pas : B3 a raison pour N5.
7. **« 0 MAD » des économies (T1-S1-006/023, T1-F1-006)** — cause dans le code : `RP/optimizer.ts::paintCard` écrit les
   économies sans garde de zéro (l. 958) quand la couverture voisine rend « — » ; et « × 720 W » est écrit en dur (l. 955).

---

## 9. À confirmer par le fondateur

- Tout ce qui est **vu par le client hors du PDF** : vidéo d'orbite envoyée par WhatsApp, image des modules sur la photo
  du site, feuille de pertes en mots simples (CAP-D6-12) — à rattacher, si en ligne, à la page `/proposition/<token>`
  (propriétaire web) et à son suivi de lecture ; rien ne touche `/proposal`.
- **Exemples dans la société de production** (CAP-D6-09) — données marquées « exemple », créées à la demande.
- **Nouvelle dépendance Word** pour le rapport interne (CAP-D6-18).
- **Distributeurs marocains et leurs pièces** (CAP-D6-11) : la liste est une entrée de Reda / de la société.
- **Dimensionner par défaut sur la facture** quand elle existe et AVERTIR (sans bloquer) quand elle manque (T1-S1-007) :
  la mise en garde est dans CAP-D6-04 ; le changement du comportement par défaut de la pose (D2) touche ce que le devis
  vend — à faire trancher.
- Documents en arabe : aucune preuve, question ouverte.

---

## 10. Non vérifié

- Le contenu exact de `total.definition` de la Batterie, de la ligne d'autonomie, et la cause de T1-S1-023 (couverture
  « — » avec facture saisie).
- Le contrôle n° 16 du §3 (hypothèses de consommation datées) repose sur B5-de §11, pas sur ma lecture.
- `apps/ventes/commissioning.py` (recette, Pmax attendu) et `apps/ventes/compatibilites.py` : cités, non ouverts ; le
  propriétaire de `apps/ventes/selectors*.py` n'a pas été demandé au script.
- `FC/atelier/PanneauReleve.jsx` (file hors ligne) et le propriétaire de `frontend/src/lib/calage/apercuDrape` : non lus.
- La légende de tension DC sur le plan de pose (`SV/planche.py`) : non lue finement.
- Les écrans hors inventaire (§0, « Non inventorié »).
- Aucune exécution : tous les « PRÉSENT » sont du code lu, pas un comportement observé (sauf les constats des relecteurs).
- Le relecteur B1 (beauté) n'a rien produit (atelier non démarré sur l'instrument) ; les dossiers `T1/S2` et `T1/T1`
  existent sans rapport `.md` au moment de la lecture.
