# Critique indépendante — vague C, 1re partie (PR #1530), code seul

**Verdict : FUSIONNABLE APRÈS CORRECTION DE ACAL1905 (b)** — `ecrireOuRelire` prend toute empreinte changée pour SA réussite.
Relu le 23/11/2026, lecture seule, `git diff origin/main...HEAD` hors `docs/`. Aucun test lancé (rien n'a demandé de trancher un doute par l'exécution).

## 1. Site public — aucun effet visiteur (prouvé)
- `/devis/mon-toit` ne charge ni `roof-tool-pro11` ni `estimatorBrainV6/V7/V8` : les seuls importeurs de V6/V7/V8 sont `scripts/roof-tool-pro11.ts`,
  chargé seulement par `pages/preview/toiture-3d-pro-11.astro` (privée, `noindex`) et par l'ERP. `roofPro11/*` : même périmètre.
- `roofPro2.ts::retraitsSaisis` : faux quand les trois retraits valent `PERIMETER_SETBACK_M` (0,5) ; `roof-tool-pro11.ts` part de
  `uniformSetbacks()` → balayages V6/V7/V8 identiques tant qu'aucun retrait n'est tapé (la page de prévisualisation seule a ces champs).
- `roofConfig.ts::themeSombreActif` : lit `html.dark`, que `apps/web` ne pose jamais ; `pages/api/roof-config.ts` appelle `styleSansImagerie`
  sans 2e argument → `#e7e5df` comme avant.
- `panExistant.ts::poseTenue` : `opts.chiffrage === undefined` sur la prévisualisation → toujours faux. `repliLeadDailyKwh` : `factureMensuelleMad` absent → 0.
- Changement réel pour la prévisualisation seule : bouton Annuler/Rétablir hors mode disposition (ACAL1901) et « au plus N » (ACAL1903). Non client.

## 2. BLOQUANT
**B1 — ACAL1905 : « Enregistré » sur l'écriture de QUELQU'UN D'AUTRE, garde `If-Match` contournée, brouillon effacé** (lu).
`frontend/src/features/calepinage/delaiReseau.js::relireEmpreinteApresDelai` rend toute empreinte ≠ celle envoyée ; `ToitureDesign.jsx`
(branche succès) fait alors `setEmpreinteEcrite(relue)`, `effacerEtAmorcer()` du brouillon local, `marquerSceneEnregistree(layout)`.
Scénario : onglet B (ou un collègue) enregistre ; onglet A enregistre ensuite avec l'ancienne empreinte → le serveur rend 409 `document_modifie`,
mais la réponse dépasse le délai (5-17 s sur une pile chargée, le cas même du constat) → A relit, voit l'empreinte de B, dit « Enregistré ».
La pose de A n'est écrite nulle part, son brouillon est effacé, et son prochain enregistrement porte l'empreinte de B → il écrase B sans 409.
Correction : `GET layout/` sert aussi `roof_layout` : ne conclure « abouti » que si le document relu = le document envoyé (même comparaison
que `empreinteSansVue`/`sansVue`) ; sinon passer par la bannière `document_modifie` (Recharger), jamais par la réussite. Test : relecture
dont l'empreinte a changé mais dont le document diffère → pas « Enregistré », brouillon gardé.

## 3. APRÈS (tâches à écrire)
- **A1 — ACAL1902, retrait contourné par une marge épinglée** (probable) : `estimatorBrainV7.ts::marginCandidates` rend `[locked]` avant
  `retraitsSaisis` ; marge « pleine rive » épinglée (puce Marge ou document relu) + retraits tapés → la note dit « Retraits appliqués », la pose
  garde la pleine rive (le constat d'origine). Même chose pour un `jointM` tapé seul : `retraitsSaisis` ignore `jointM`, `remove` = `uniformSetbacks(0)` l'annule.
- **A2 — ACAL1902, anciens dossiers à retrait tapé** (lu) : un document enregistré avec retraits ≠ 0,5 et gagnant « remove » n'a plus cette
  candidate ; « Comparer les poses » et tout nouveau balayage donnent moins de panneaux qu'avant (pose relue tenue par ACAL1900). Voulu par la
  mission, mais à dire en dry-run sur les dossiers existants (règle « devis envoyés : nouveaux rendus seulement »).
- **A3 — ACAL1913, besoin réduit à tort** (probable) : `consumption.ts::applyConsumptionToSizing` retranche `repliLeadDailyKwh()*365` de la
  courbe ; une courbe RELUE d'un document antérieur (non recomposée, `cibleRelue` = repli) ou éditée à la main ne contient pas ce repli →
  `consNeeded` baisse (jusqu'à 0) en mode besoin auto. Retrancher seulement quand la courbe a été composée depuis le repli.
- **A4 — ACAL1910, nom du module posé sur la fiche du défaut** (lu) : `simulation.py::_module_pose` rend `({}, désignation du pan)` quand la
  fiche du produit dominant n'a pas de `specs` ; `niveau_irradiance.py::appliquer` / `qualite_module.py::appliquer` font
  `fiche_module_pose or fiche_module` → chiffres du module par défaut, nom du module posé. Plusieurs modules : seul le dominant compte (inchangé).
- **A5 — ACAL1904, refus de « Date de la photo » invisible** (lu) : `50-coque-atelier.css` cache `.rp9-image-capture` hors `:focus-within`
  (Guidé sans toit) ; le refus (`rp9-image-capture-erreur`, posé au `change`, donc au départ du focus) vit dans ce label → masqué dès qu'on sort.
  Champs atteignables au clavier (Tab depuis l'adresse) et au doigt (après focus de l'adresse) ; `select`/`a` non listés dans `:is(...)` mais absents de la carte.
- **A6 — ACAL1908, hauteur qui ne fait que rétrécir** (probable) : `DemarrageRapide.jsx` cumule `excesRef` sans jamais le remettre à zéro ;
  tout débordement passager (message affiché, contenu plus haut que la carte) retire sa hauteur définitivement, jusqu'au plancher 360 px.
  La boucle converge (plancher 360), mais vers une carte trop courte. Mesurer l'excès à chaque `mesurer()` au lieu de l'accumuler.

## 4. Vérifié sans constat
- ACAL1900 : les re-poses de fond (`liveResolveFlat(false)` : PVGIS d'inclinaison, matrice ; `liveResolvePitched(false)`) sautent une pose tenue ;
  tout geste (toit, obstacle, retrait → `recalc()` → `liveResolveFlat()`), « + », Réinitialiser re-posent, et `scene3d.ts` remet `layoutState` à
  `null` → pas de panneau hors toit après un changement de géométrie. Pose = cible : `noteEcartPoseRelue` → `null`.
- ACAL1903 : gagnant à `need = clampNeeded(MAX)` = 400 ; `departageBase` maximise l'énergie, donc « + » sature au même `placedCount` → maximum annoncé = maximum atteint.
- ACAL1911 : fenêtres retirées hors `decalage` → plus de `StrategieInvalide` ; avertissement ajouté seulement si saisies ; chiffre = batterie sans fenêtres, cohérent.
- ACAL1912 : `0 < n < len(table)` → rien à 0 ni en tout-micro ; doublon avec `plans_raccordes` filtré par `_avertissements_uniques` (même texte).
- `toastsAtelier.js` : attribut retiré au démontage ; règles CSS sous `body[data-cal-atelier]` seulement. Aucun PDF de devis touché, aucun `prix_achat`.

## 5. OPTIONNEL
- `toastsAtelier.js` : deux coques montées en même temps → le premier démontage retire le repère de l'autre (compteur de références).
- `simulation.py::construire_contexte` appelle `_module_pose` deux fois (deux `pans_du_document`).
- `optimizer.ts::etatCarte` : getter `maxSens` qui relance un solveur complet à chaque lecture (une par frappe aujourd'hui).

## 6. Non lu / non vérifié
Chemins synchrones de réouverture (catalogue, `documentRelu`) qui pourraient re-poser après l'hydratation ; écriture « sans geste » de
l'empreinte (ACAL1900, clause 2) ; régime mixte micro + chaînes (ACAL1912) ; ACAL1901/1906/1907/1909 en détail ; tests et goldens du lot.
