# Taqinor OS — Build Plan & Progress (priority queue, PLAN2)

> **This queue is drained BEFORE `docs/PLAN.md`.** A run works every pending `[ ]` task here first, and only falls through to `docs/PLAN.md` once this file has none left.

This is the **priority queue**, worked **before** `docs/PLAN.md`. A run drains every `[ ]` task
in this file FIRST — the same way (verify it isn't already built, build it completely with
tests, obey every STANDING RULE in `PLAN.md`, then commit it to a worktree branch, tick it `[x]`,
and append a DONE LOG line as it lands; **run `python scripts/plan_lanes.py docs/PLAN2.md` to get
the maximally-parallel cross-category wave plan and build those lanes in parallel with concurrent
worktree subagents up to the session ceiling (default 8, raised as high as the session can sustain
via `--max-lanes`), continuously refilled (work-stealing), coupled tasks in sequence inside a
lane**) — and only
once this file has no pending `[ ]` task left does it fall through to `docs/PLAN.md`. Every
worktree branch is folded into one `dev`, CI runs once over the whole batch, and the run
self-merges `dev` → `main` exactly once at the very end — **no per-agent PR, no per-task merge**.
All the HOW TO RUN and STANDING RULES in `docs/PLAN.md` apply here unchanged — including the
default **workflow-with-review engine** (one worktree subagent per task plus a separate
adversarial review agent that must pass before a change is merge-eligible), the
**parallel-subagent fallback** when no workflow engine is available (never a single serial
one-task-at-a-time agent), and the **sync-safe single merge** (integrate the latest
`origin/main` first, re-run CI, push without forcing). This file only adds tasks.

> Added 2026-06-17 while the field-execution batch (PLAN.md F1–F24) was running on
> `dev-field-exec`. Per the founder's "add to plan" convention, new tasks go here while a
> run is in progress so `PLAN.md` is never touched mid-batch.

---

> **Web session note (2026-06-18):** a world-class audit of the public site (`apps/web`) was run and its
> fixes built — **W62–W66 shipped** (social proof scaffold, homepage guarantee band, founder photo-ready
> block, brand strip +Jinko/Huawei/Nexans, « réponse sous 48 h ») and the **W67 EN/AR i18n foundation**
> laid (Astro i18n + dictionary + switcher + RTL/hreflang, FR byte-identical). Full detail in
> `docs/WEB_PLAN.md` + `docs/DONE.md`; web work stays out of this OS queue per the OS/web split. Logged
> here at the founder's request — this note adds no OS task.

## BUILD QUEUE — Module Calepinage autonome (CRM + AO + devis) — 19/09/2026 (Groupe CAL : CAL1-CAL248, 220 tâches, lots A « Fondation » / B « Conception » / C « Ingénierie & simulation » / D « Livrables, intégrations & pilotage »)

> **Provenance.** Demande fondateur du 19/09/2026 (session « calepinage module »), instruite par les scouts R1 de cette session : inventaire de l'atelier 3D ventes (`r1-ventes3d.md`), surface calepinage AO (`r1-ao-summary.md`), moteur pur `core/calepinage` (`r1-engine.md`), conventions de plan + câblage d'une app neuve sur le patron `apps/ao` (`r1-plans-conventions.md`). Décisions d'architecture D1-D7 arrêtées dans `r2-architecture-brief.md`. Tout constat ci-dessous a été relu file:line dans le dépôt pendant la rédaction.

> **FOUNDER DECISION (Reda, 19/09/2026, verbatim).** 1. « i want to create a calpinage module, i already have one calpinage tool, i want it to be a standalone module that can be also used inside the CRM module and also linked to appel d'offre module. » 2. « look at what a calpinage tool have as options and all those as tasks to plan » 3. « the new calpinage module should work exactly the same as it is right now in the CRM just have more features. and of course we can access it from the standalone module, and pick whatever client or lead and make its calpinage. » Conséquence directe : la parité CRM est un INVARIANT (le geste « Concevoir la toiture (3D) » de la fiche lead garde exactement sa sémantique 1/N/0/422), le module autonome est une PORTE SUPPLÉMENTAIRE, jamais un remplacement, et un calepinage sans devis est un objet de première classe.

> **Notes de non-duplication.** Ce groupe ne recouvre AUCUNE tâche pendante : les groupes AOF (AOF1-AOF194, archivés dans `docs/done_task.md`, ledger `AOF=194`), PV/PVG (« Toiture 3D + calepinage direction PVsyst »), QJR (reconstruction du parcours devis) et VT (visite technique) sont tous `[x]` ou archivés, et un balayage exhaustif des fichiers de plan n'a retourné zéro tâche calepinage/toiture/roof/ombrage/PVGIS/onduleur ouverte. Les DEUX systèmes existants restent en place et ne sont PAS fusionnés : (a) le système 2D « opposable » AO (`ToitureAO`/`ObstacleAO`/`ChaineCotes`/`ZoneAO`/`VarianteCalepinage`, `apps/ao/calepinage_service.py`, studio SVG) garde ses modèles et sa chaîne de migrations mono-écrivain ; (b) l'atelier 3D ventes (`frontend/src/pages/ventes/ToitureDesign.jsx`, `Devis.roof_layout`) garde ses endpoints `from-layout`/`sync-layout`/`roof-image` et son arbitrage villa A/B (`apps/ventes/domain/geometrie.py:387-679`). Le noyau pur `core/calepinage` reste partagé et n'est JAMAIS recopié (contrat import-linter `calepinage-est-un-noyau-pur`, `backend/django_core/.importlinter:596`). Règle #4 intacte : le moteur de devis ne fait que RENDRE — aucune tâche ici n'ouvre un second chemin de PDF client ni ne change un statut de devis.

> **DÉCISIONS DE STRUCTURE ARRÊTÉES À LA VÉRIFICATION (19/09/2026) — elles priment sur toute formulation contraire ci-dessous.**
> 1. **Modèle client = `crm.Client`** (`apps/crm/models.py:13`) : `ventes.Client` n'existe pas et `Devis.client` pointe déjà `'crm.Client'` (`apps/ventes/models.py:33-34`). Toutes les FK-string du module le citent ainsi.
> 2. **Structure posée UNE fois par CAL233** : `apps/calepinage/services/` et `apps/calepinage/views/` sont des PAQUETS (`__init__.py` ré-exportant, précédent `apps/ventes/services.py`), jamais des modules `services.py`/`views.py` — les deux ne peuvent pas coexister en Python. Chaque tâche déclare son SOUS-MODULE, ce qui rend les lanes réellement file-disjointes.
> 3. **Une seule forme d'URL** : `/api/django/calepinage/calepinages/<pk>/…` (routeur DRF, sous-ressources en `@action`) ; réglages société sous `/api/django/calepinage/parametres/`.
> 4. **Une seule migration initiale** : `Calepinage`, `CalepinageVersion`, `CalepinageVariante` et `ParametresCalepinage` naissent dans `0001_initial` (CAL7). Les ajouts de schéma ultérieurs sont CHAÎNÉS contre les collisions de numéro : CAL7 → CAL52 → CAL64 → CAL130 → CAL139 → CAL149 → CAL163 → CAL190 → CAL212.
> 5. **Le document `roof_layout` a un contrat v2 publié SEUL d'abord (CAL232)** ; les sept tâches qui l'étendent (CAL57, CAL59, CAL66, CAL67, CAL68, CAL72, CAL248) portent `@after: CAL232` et NOMMENT le champ ajouté ; les consommateurs ventes (`builder.py:1876-1902`, `domain/geometrie.py:456-506`, page publique `#roof3d`) ont leur test de non-régression dans CAL232.
> 6. **La parité CRM est tenue CÔTÉ SERVEUR (CAL39)** : `apps/calepinage` s'abonne à `layout_finalise` (`core/events.py:523`, émis `apps/ventes/views/devis.py:590,672`) et l'action « best-effort » `layout` (`:3208-3227`) émet le même événement ; aucune ligne de `LeadWorkspace.jsx` ni du mode `devis` de `ToitureDesign.jsx` n'est modifiée.
> 7. **Pertes PVGIS (CAL238)** : `loss` est une ENTRÉE d'appel — le module passe TOUJOURS la somme explicite de ses postes (chacun sourcé ou saisi) et affiche la valeur passée ; jamais un 14 % ni un 20 % caché.
> 8. **Normes électriques (CAL130)** : pour `pays=ma` AUCUNE norme n'est supposée — le calcul concerné est OMIS tant que la société n'a pas choisi la sienne ; NF C 15-100 / UTE C 15-712-1 ne s'appliquent que si elles sont sélectionnées. Idem dégagements (CAL71) : les constantes actuelles s'affichent « valeur atelier actuelle, non sourcée ».
> 9. **Préséance AO (CAL239)** : la variante 2D RETENUE reste la source opposable du bordereau ; le calepinage 3D est le document de travail — la nomenclature CAL185 n'alimente jamais un bordereau AO.
> 10. **Sorties images** : le serveur produit du PDF (WeasyPrint) et du SVG ; le PNG est produit PAR LE NAVIGATEUR (`frontend/src/features/ao/studio/svgToPng.js`) — aucun rasteriseur SVG n'est installé, aucune dépendance ajoutée.
> 11. **Lanes** : toute tâche touchant `apps/web/**` porte `@lane: web/roofpro` ; toute tâche touchant `frontend/src/pages/ventes/ToitureDesign.jsx` sans `apps/web` porte `@lane: frontend/atelier` ; les écrans `frontend/src/features/calepinage/**` portent `@lane: frontend/calepinage` ; le backend est éclaté en lanes thématiques (`backend/calepinage-site`, `-equip`, `-elec`, `-prod`, `-conso`, `-pompage`, `-meca`, `-biblio`, `-sorties`, `-reglementaire`, `-cycle`, `-moteur`).
> 12. **IDs fondus/supprimés à la vérification (19/09) :** CAL65→CAL64 (relevé terrain : API seule, les surfaces terrain existantes suffisent) ; CAL77→CAL2 ; CAL85→CAL167 ; CAL90 (suiveur : supprimée, non chiffrable) ; CAL105→CAL42 ; CAL108/CAL109 (site public : hors périmètre, relèvent de `docs/WEB_PLAN.md`) ; CAL133→CAL195 ; CAL137→CAL92+CAL93 ; CAL146→CAL23 ; CAL161/CAL162 (groupe électrogène : supprimées, CAL160 seule) ; CAL168→CAL167 ; CAL169→CAL198 ; CAL186→CAL24 ; CAL187→CAL38 ; CAL202→CAL8 ; CAL203→CAL20+CAL207 ; CAL204→CAL26 ; CAL217→CAL110 ; CAL219/CAL220 (tableau de bord : supprimées, CAL218 suffit) ; CAL225 (i18n AR de l'atelier : supprimée, le constructeur n'est pas internationalisable) ; CAL226→CAL44 ; CAL227→CAL43 ; CAL228/CAL229/CAL230 (suggestions IA : supprimées, non demandées).
>
> **Tâches neuves de la vérification** : CAL45 (réglages société), CAL231 (contexte de conception), CAL232 (schéma v2 `roof_layout`), CAL233 (structure + URL), CAL234 (chaînage manuel), CAL235 (retrait des modules ombragés), CAL236 (panneau Production), CAL237 (LiDAR IGN, France), CAL238 (politique de pertes PVGIS), CAL239 (préséance AO), CAL240/CAL241/CAL242 (import de contour bidirectionnel), CAL243 (endpoint équipements), CAL244 (contrat résultat), CAL245 (endpoint chantier), CAL246 (endpoint bibliothèque), CAL247 (contrat dossiers réglementaires), CAL248 (accès solaire persisté).

### Groupe CAL — Conception (lot B)

> Surface de CONCEPTION du module calepinage : tout ce qu'un outil de design PV moderne expose et que l'atelier actuel (`apps/web/src/scripts/roofPro11/*`, 23 modules, importé par l'ERP via l'alias Vite `@roofbuilder`) n'a pas, ou n'a qu'à moitié. Chaque constat est vérifié dans le code de cette session (file:line) et chaque parité cite sa source concurrente. Les CHIFFRES de production/simulation restent au rédacteur W3 (CAL111+) : ici on ne fait que produire/consommer la géométrie.
> Invariants : zéro chiffre inventé (tout défaut est SAISI PAR LA SOCIÉTÉ ou SOURCÉ — PVGIS, fiche produit, texte cité — sinon OMIS) ; OpenSolar JAMAIS intégré (CGU) ; Google Solar API uniquement derrière un flag et JAMAIS au Maroc (couverture non confirmée) ; le moteur pur `core/calepinage/` reste importé, jamais dupliqué ; `apps.calepinage` lit crm/ventes/ao/stock uniquement via leurs `selectors.py`.
> Fondations supposées : CAL4 (app `apps/calepinage`) + CAL233 (paquets `services/`/`views/`, forme d'URL unique), CAL7 (modèles + `0001_initial`), CAL232 (schéma v2 de `roof_layout`), CAL13 (service `enregistrer_layout`) et CAL18 (action HTTP `layout`), CAL231 (contexte de démarrage), CAL37 (`ToitureDesign` en `mode="calepinage"`).

#### (a) Site & imagerie

- [ ] CAL51 [GATED: clé + coût Google Solar — accord fondateur requis ; Maroc non couvert] — **Brancher Google Solar `buildingInsights` derrière un flag, et seulement là où la couverture est confirmée.** Constat : le dépôt documente DÉJÀ que Google Solar n'a aucune couverture au Maroc (`backend/django_core/apps/crm/roof_detect.py:11-12`) et n'appelle `buildingInsights` nulle part ; parité : l'endpoint renvoie segments de toit, dimensions et potentiel solaire avec 3 niveaux de qualité d'imagerie (https://developers.google.com/maps/documentation/solar/building-insights). Ajouter un service backend optionnel, DÉSACTIVÉ par défaut, refusant l'appel quand le pays du projet n'est pas dans la liste de couverture vérifiée (le Maroc n'y est PAS — non confirmé par Google), stockant la réponse brute comme SUGGESTION horodatée et jamais comme vérité : l'utilisateur valide ou jette, la provenance « Google Solar » reste affichée sur chaque pan repris. Done = flag absent → 404 et zéro requête sortante ; pays non couvert → refus explicite en français ; test prouvant qu'aucun pan n'est créé sans validation humaine ; coût/clé notés en DONE LOG. Files: `backend/django_core/apps/calepinage/services/google_solar.py`, `backend/django_core/apps/calepinage/views/google_solar.py`, `backend/django_core/apps/calepinage/tests/test_google_solar.py` (COST) (@lane: backend/calepinage-site) (@model: opus) (@after: CAL47)

## BUILD QUEUE (do top-down — highest value first)

### Groupe VTA — L'app VISITES autonome : sortie du CRM, utilisateur terrain sans accès CRM, vraie app « Ma journée » (VTA0-VTA17 + porte, fondateur 2026-09-12, corrigé par vérification adversariale R3)

*Commande fondateur 2026-09-12 (L3) : « sortir la visite du CRM — l'utilisateur qui la fera n'aura
probablement pas l'accès CRM — et en faire une VRAIE app, bien liée aux données CRM ». Enquête L3
4 lanes + vérification adversariale (9 constats intégrés). DÉCISIONS DE CONCEPTION (vérifiées
contre le code) : (1) app NEUVE `apps/visites` — pré-vente (rattachée au Lead) ≠
`apps/installations` (post-vente, possédée par le contrat PLAN_SERVICE) ; (2) move des modèles
par le pattern ODX `SeparateDatabaseAndState` state-only, `db_table` conservé
(`crm_visiteterrain`/`crm_visitemedia`), AVEC la FK `lead` passée en STRING `'crm.Lead'` (elle
est aujourd'hui une référence de classe — models.py:3609) et la migration ContentType compagnon
pattern ODX15 (frais/0002) ; (3) permissions RENOMMÉES `visites_voir/creer/modifier/valider` +
data migration des Role.permissions + les 3 listes de rôles en dur (RESPONSABLE :506,
COMMERCIAL_RESP :635, COMMERCIAL :675) + le dict-property PERMISSIONS_ECRITURE (invisible aux
gardes génériques — réécriture des fixtures de tests OBLIGATOIRE) ; (4) NOUVEAU rôle seedé
« Commercial terrain » porteur de visites_voir/creer/modifier + `app_visites_voir` (liste
blanche → il ne voit QUE l'app Visites) — on NE TOUCHE PAS au rôle Technicien existant (il
porte ~25 droits post-vente et sa route d'accueil /ma-journee appartient à installations) ;
(5) retour au lead par ÉVÉNEMENT `visite_validee` (bus M6, catalogue + parité payload
test_event_coverage, kwargs user + recap) ; (6) blueprint recherche : accueil « Ma journée »
de l'app (route /visites — la route /ma-journee est PRISE par installations), portée DURE
« mes visites », progression au pouce, offline via LA primitive plateforme
`lib/offlineOutbox.js`/apps/offlinesync (NTMOB1 — JAMAIS un second outbox, garde de
composition) + compression photo NTMOB16 réutilisée, lien navigation, total TTC visible /
marge jamais. RESTENT côté crm/ventes : PhotoToitOverlay/photoToit/traceToit, l'endpoint lead
`photo-toit` (appel lazy crm→visites.selectors — VÉRIFIÉ autorisé : le contrat independence ne
porte que sur les *.models), ; `roofTextureWarp.js` déménage en lib partagée (2 importeurs des deux côtés — Fable B2). NE PAS toucher : VisiteExterne/T-TRACE
(homonyme) ; ses index `crm_visite_comp_*` sont des faux positifs du grep final.*

> Contraintes (toutes tâches) : frontière M3 — `apps/visites` lit crm/ventes UNIQUEMENT via
> selectors/services (lazy) ; `apps.visites.models` s'ajoute au contrat `independence` ET
> `apps.visites` à la liste `tiers-is-a-base-layer` de `.importlinter` ; multi-tenant ; jamais
> prix_achat/marge côté terrain ; move STATE-ONLY puis additif ; checklist startapp_erp
> complète ; fumée pattern veille_ao + test de parité du move pattern frais/test_odx15 ;
> l'allowlist QX11 (apps/ventes/tests/test_qx11_beat_reachability.py) suit le rename Celery ;
> actions de progression nommées `demarrer-route`/`arriver` PARTOUT (contrat = implémentation) ;
> erreurs nommant le champ ; `step="any"`+`noValidate`.

GATED (fondateur) :
- [ ] VTAG1 — **[GATED: décision fondateur]** Rattacher `apps/visites` au contrat de propriété d'un domaine (PLAN_CRM_VENTES, cohérent pré-vente) OU la laisser plateforme — une ligne au contrat choisi. (@blocked: choix fondateur) (@lane: founder-verify)

#### DONE LOG — Groupe VTA

### Groupe VT — Visite technique terrain : checklist photos/mesures guidée, feu vert bureau d'études, toit réaliste par photos assemblées drapées sur la carte (VT0-VT11 + VTG1, fondateur 2026-09-09)

*Commande fondateur 2026-09-09 : un module de visite où le commercial terrain voit la fiche client
et le devis reçu, capture les photos du toit, du tableau électrique et de l'emplacement onduleur
(avec mesures de dégagement), optionnellement le cheminement de câbles, et où l'outil lui montre en
direct ce qui MANQUE jusqu'au feu vert du constructeur 3D/calepinage. Recherche 2 lanes 2026-09-09
(pratiques SiteCapture/Scanifly/Aurora + faisabilité photogrammétrie) — constats clés vérifiés :
le pattern industrie = slots photo NOMMÉS obligatoires par catégorie, « si une photo est requise,
la visite n'est pas finie sans elle », et la checklist de visite EST la porte qui débloque le
design ; la reconstruction 3D du TOIT depuis des photos prises AU SOL ne marche physiquement pas
(le plan de toit n'est jamais vu de ≥2 points de vue — tous les outils commerciaux exigent du
drone/aérien) ; la voie fiable = checklist guidée + mesures saisies. PIVOT fondateur 2026-09-10 :
PAS de vraie 3D — les photos du toit sont ASSEMBLÉES entre elles (stitching panorama OpenCV,
tâche Celery serveur) puis CALÉES sur la vue carte/atelier EXISTANTE (drapage de l'image par ses
4 coins sur le contour du toit) pour rendre le toit du client beaucoup plus réaliste que
l'orthophoto. Réutiliser l'existant : `records.Attachment` (MinIO erp-uploads),
`CameraCapture.jsx` (PWA), `LeadActivity` (chatter), Atelier 3D `ToitureDesign.jsx` (three.js),
`Lead.visite_prevue_le/visite_effectuee/visite_notes`.*

> Contraintes (toutes tâches) : multi-tenant (company FK + CompanyScopedModelViewSet) ; lecture du
> devis via `apps/ventes` selectors/services UNIQUEMENT (frontière M3) ; `prix_achat` jamais
> visible ; zéro chiffre inventé — AUCUN verdict automatique « dégagement suffisant » avec des
> seuils inventés : le module MONTRE les mesures, le bureau d'études JUGE à la validation ;
> statuts de la visite = layer document interne (comme Devis), jamais mêlés au funnel STAGES.py ;
> erreurs qui pointent le champ fautif ; inputs numériques `step="any"` + `noValidate` ;
> JAMAIS de photogrammétrie serveur depuis photos au sol (constat de recherche — voie interdite).

  API complètes (visite avec statuts `brouillon/en_cours/terminee/validee/a_refaire`, checklist
  de slots par catégorie `toiture/tableau/local_onduleur/cheminement/general` avec `requis`,
  `min_photos`, état par slot `manquant/ok/a_refaire+motif`, bloc `mesures` typé par catégorie,
  bloc `completude` serveur {complet: bool, manquants: [...]}, médias avec slot+GPS, panneau
  lecture seule client+devis). Vérifié par `check_api_shapes.py`. À LANDER SEUL sur `main` avant
  le reste du groupe. Files: apps/crm/contract_samples/visite_terrain.json (@lane: contrat-visite) (@model: sonnet)
  (`brouillon/en_cours/terminee/validee/a_refaire` — layer interne, PAS le funnel), date_prevue,
  date_realisee, notes, `mesures` JSONField (structure typée du contrat VT0), `photo_toit_key`
  (clé MinIO de l'image assemblée, nullable), `assemblage_etat` (`aucun/en_cours/ok/echec` +
  `assemblage_erreur` texte), `texture_calage` JSONField (4 coins du drapage sur le contour,
  nullable) ; modèle `crm.VisiteMedia` (visite FK, attachment FK vers
  `records.Attachment`, slot_code, commentaire, a_refaire bool + motif_refaire, gps_lat/gps_lng
  nullable) ; définition de checklist en module code `apps/crm/visite_checklist.py` (catégories,
  slots, requis/min_photos, mesures obligatoires par catégorie — libellés FR) ; migration
  additive ; chatter auto (LeadActivity) à création/terminaison/validation/renvoi. (@after: VT0)
  Files: apps/crm/models.py, apps/crm/visite_checklist.py, apps/crm/migrations (@lane: backend/crm-visite) (@model: sonnet)
  (MinIO erp-uploads via le service records, taille max, mime image/*), suppression média,
  saisie mesures par catégorie (validation champ par champ, erreurs nommant le champ),
  `completude` calculée SERVEUR (slots requis manquants + mesures obligatoires manquantes,
  liste explicite), transition `terminer` REFUSÉE tant que la complétude n'est pas atteinte
  (message = la liste des manquants).
  Permissions : nouveaux codes `crm_visite_voir/creer/modifier/valider` câblés dans roles.
  (@after: VT1) Files: apps/crm/views.py, apps/crm/serializers.py, apps/crm/urls.py (@lane: backend/crm-visite) (@model: sonnet)
  `crm_visite_valider`) et action `renvoyer` avec marquage par-slot/par-mesure « à refaire +
  motif » → statut `a_refaire`, le commercial voit exactement quoi refaire ; notification au
  commercial (primitive notifications existante) au renvoi et à la validation ; à la validation,
  visite en lecture seule. Panneau lecture seule client+devis dans l'API visite : contact/adresse/
  GPS du lead + devis du lead (numéro, statut, lignes SANS prix_achat) via selectors ventes.
  (@after: VT2) Files: apps/crm/views.py, apps/crm/services.py, apps/ventes/selectors.py (@lane: backend/crm-visite) (@model: opus)
  liste des manquants ; accepté quand tout y est), boucle renvoi→re-upload→re-terminer,
  permissions valider, aucun prix_achat dans le panneau devis, upload slot inconnu refusé,
  chatter auto présent. (@after: VT3) Files: apps/crm/tests/test_visite_terrain.py (@lane: backend/crm-visite) (@model: sonnet)
  filtrées sur l'utilisateur assigné, badge complétude) + création depuis la fiche lead
  (pré-remplit `visite_prevue_le`) ; écran visite = wizard par catégorie (toiture → tableau →
  local onduleur → cheminement (optionnel) → général) avec tuiles photo par slot (état
  manquant/ok/à refaire + motif visible), CameraCapture PWA, texte-guide par slot (quoi cadrer),
  barre de progression = complétude serveur. (@after: VT2) Files: frontend/src/pages/crm/visites,
  frontend/src/features/crm (@lane: frontend/crm-visite) (@model: sonnet)
  principal A, mono/tri, emplacements libres), local onduleur (largeur×hauteur mur libre cm,
  profondeur de dégagement cm, distance au tableau m, local abrité/ventilé), toiture (dimensions
  zone utile m, pente ° ou plat, orientation, type de couverture, état), cheminement (longueur
  estimée m — optionnel) ; `step="any"` + `noValidate`, normalisation d'unités évidentes,
  erreurs serveur affichées SOUS le champ fautif. (@after: VT5) Files:
  frontend/src/pages/crm/visites (@lane: frontend/crm-visite) (@model: sonnet)
  (lien navigation), devis du lead en lecture seule (numéro, statut, total TTC, lignes) —
  consomme le panneau API VT3. (@after: VT3) Files: frontend/src/pages/crm/visites (@lane:
  frontend/crm-visite) (@model: sonnet)
  par catégorie plein écran, mesures récapitulées, boutons Valider (feu vert) / Renvoyer avec
  sélection des slots/mesures à refaire + motif obligatoire ; après feu vert, bouton « Ouvrir
  l'atelier 3D » qui ouvre ToitureDesign pré-rempli des dimensions/pente/orientation mesurées
  (mêmes clés que `Lead.roof_outline`/params atelier existants — ne rien inventer si non mesuré).
  (@after: VT3) Files: frontend/src/pages/crm/visites, frontend/src/pages/ventes/ToitureDesign.jsx
  (@lane: frontend/crm-visite) (@model: opus)
  assemble les photos du slot toiture en UNE image (OpenCV Stitcher, `opencv-python-headless` —
  nouvelle dépendance GRATUITE, à noter au DONE LOG), stockée dans MinIO (`photo_toit_key`),
  `assemblage_etat` en_cours→ok/echec avec message d'erreur HONNÊTE (le stitching échoue si les
  photos ne se recouvrent pas ~50 %+ — le message le dit et propose de reprendre des photos qui
  se chevauchent, ou de choisir UNE seule photo comme texture) ; endpoint de polling ; tests de
  la machine à états (mock du stitcher). Guide de prise de vue dans le wizard toiture : balayer
  le toit d'un point haut avec fort recouvrement entre photos. (@after: VT2) Files:
  apps/crm/tasks.py, apps/crm/views.py, apps/crm/tests/test_visite_assemblage.py (@lane:
  backend/crm-visite) (@model: opus)
  assemblée (ou une photo choisie si l'assemblage a échoué) est DRAPÉE sur le contour du toit
  par 4 poignées de coins déplaçables (transformation perspective canvas), sauvegarde
  `texture_calage` ; l'overlay calé s'affiche ensuite dans la vue carte du lead ET comme
  texture du pan de toit dans l'atelier ToitureDesign (mode existant, à la place de
  l'orthophoto floue) — le toit du client devient réaliste pour le calepinage. Jamais de
  reconstruction 3D. (@after: VT9) Files: frontend/src/pages/crm/visites,
  frontend/src/pages/ventes/ToitureDesign.jsx (@lane: frontend/crm-visite) (@model: opus)
  serveur les liste, tuile « à refaire » montre le motif, terminer désactivé tant que incomplet
  avec la liste visible, panneau devis sans prix_achat, formulaire mesures n'avale/rejette
  jamais un nombre tapé. (@after: VT6, VT7) Files: frontend/src/pages/crm/visites (@lane:
  frontend/crm-visite) (@model: sonnet)

  whole ERP ») : à la VALIDATION (feu vert), le serveur écrit en retour sur le lead —
  `visite_effectuee=True`, `visite_notes` reçoit un récap court (date + mesures clés), déjà
  chatterisé ; nouvel endpoint `GET /api/django/crm/leads/<pk>/photo-toit/` (selector
  `texture_toit_pour_lead` : dernière visite VALIDÉE du lead → {visite_id, url, texture_calage},
  valeurs nulles sinon — jamais une visite d'une autre société) pour que l'atelier 3D et la
  carte lead lisent la texture SANS connaître le module visite. Tests. (@after: VT3) Files:
  apps/crm/services.py, apps/crm/selectors.py, apps/crm/views_visite.py (@lane: backend/crm-visite) (@model: opus)
  ToitureDesign consomme `photo-toit` du lead et affiche l'image calée comme underlay du contour
  du toit dans SA vue carte/plan de travail (couche image sous le tracé, transformation
  perspective depuis les 4 coins — sans toucher au builder vendored) ; la carte de la fiche lead
  (MapView) affiche le même overlay ; l'aperçu canvas de VT11 reste l'écran de calage. Mocks =
  formes de VT12. Tests. (@after: VT12, VT11) Files: frontend/src/pages/ventes/ToitureDesign.jsx,
  frontend/src/pages/crm/visites, frontend/src/features/crm (@lane: frontend/crm-visite) (@model: opus)

#### DONE LOG — Groupe VT

GATED (fondateur) :
- [ ] VTG1 — **[GATED: décision fondateur coût/infra]** Photogrammétrie serveur phase 2
  (OpenDroneMap CPU en tâche Celery sur photos d'orbite prises d'un point haut ou drone,
  gate qualité min photos/recouvrement, viewer three.js). NE PAS construire sans porte
  explicite : voie écartée par le pivot fondateur 2026-09-10 (pas de vraie 3D), lente sur CPU
  (dizaines de min à heures), sujette à échec opérateur — l'assemblage VT9 + calage VT11
  couvre le besoin. (@blocked: porte fondateur) (@lane: founder-verify)

### Groupe QX ROUND 7 — 4 MODÈLES DE DEVIS : split industriel/commercial, 4 renderers, moteur agricole FAO-56, injection 82-21 (QX43-QX52 + QXG6, fondateur 2026-07-16)

*Commande fondateur 2026-07-16 : séparer industriel et commercial (4 modes réels avec
résidentiel/agricole), UN moteur de devis (règle #4) avec 4 rendus distincts visibles sur la
page proposition ET les PDF, questions par catégorie commerciale, moteur agricole eau→pompe
mondial-best-practice. Recherche 5 volets 2026-07-16 (commercial 9 catégories, industriel
MT/82-21, agricole FAO-56, courbes de charge MA + batteries, audit codebase) — constats clés :
`Lead.TypeInstallation.COMMERCIAL` et l'alias webhook `commercial` EXISTENT déjà
(crm/models.py:296-300, webhooks.py:185-196) ; le trou est côté Devis/moteur/web. Le décret
82-21 (2-25-100, BO 9 mars 2026, en vigueur 9 juin 2026) rend l'injection MT/HT RÉELLE :
tarif ANRE 0,21/0,18 DH/kWh (mars 2026-févr 2027), plafond 20 % de la production (en
révision), frais réseau ≈6,07+6,38 c/kWh à déduire.*

> Contraintes (toutes tâches) : règle #4 — le moteur RE ND seulement, jamais de statut ;
> nouveaux renderers DANS apps/ventes/quote_engine/ ; migrations additives ; zéro chiffre
> inventé — chaque constante tarifaire/Kc porte sa source en commentaire + flag « à vérifier
> fondateur » quand estimée ; prix_achat jamais client-facing.

GATED (fondateur — vérifications avant durcissement des constantes) :
- [ ] QXG6 — **[GATED: vérifs fondateur avant hard-coding]** (a) tarifs MT ONEE exacts
  (pointe/pleines/creuses TTC) contre le simulateur one.org.ma ; (b) bande prix/kWc C&I
  >100 kWc contre les vraies offres fournisseurs (l'estimation recherche = 6 000-9 000
  DH/kWc HT) ; (c) seuil déclaration/autorisation 82-21 (5 MW vs 1 MW selon sources) ;
  (d) statut du plafond d'injection 20 % (décret en révision). Chaque valeur validée
  remplace le flag « à vérifier » dans constants_82_21.py / la table day-share QX44.
  (@blocked: vérifs fondateur tarifs/seuils) (@lane: founder-verify)

*Notes de cohérence : dépendances QX44/QX46/QX49/QX50/QX52 → QX43 ; QX47 → QX48 ; aucune
circularité. QXG3 (prix des 11 pompes à courbe) reste LE gate du devis agricole chiffré ;
QXG1 (BSP WhatsApp) gate l'envoi automatisé ; QXG4 (contenu confiance réel) vaudra pour les
3 nouveaux renderers. Les moitiés web (WJ117-WJ126) vivent dans docs/WEB_PLAN.md.*

---

### GATED — Groupe PUB (ne PAS auto-construire — chaque item attend sa porte fondateur)

- [ ] PUB107 — **[GATED: décision WhatsApp Cloud API (même porte qu'ADSENG34)] Boîte de réception WhatsApp d'équipe** : conversations CTWA assignables, notes internes, SLA par conversation, funnel conversation→qualifié→devis→signature — le standard Wati/Trengo. Ne se construit qu'à la levée de la porte Cloud API. Files: `apps/adsengine/`+front. (@blocked: décision fondateur WhatsApp Cloud API) (DEP) (@model: opus)
- [ ] PUB108 — **[GATED: décision WhatsApp Cloud API] Réponse instantanée + qualification WhatsApp Flows** : auto-réponse <1 min sur lead Meta/CTWA (gabarits approuvés), formulaire Flows structuré (type toiture/facture/ville) alimentant le Lead et un brouillon de Devis. (@blocked: décision fondateur WhatsApp Cloud API) (DEP) (@model: opus)
- [ ] PUB109 — **[GATED: décision WhatsApp Cloud API] Relances drip marketing WhatsApp** : cadences 1h/1j/3j pour FOLLOW_UP/COLD et devis expirés (opt-out géré, fenêtres de coût 2026 respectées) — distinct des relances transactionnelles existantes. (@blocked: décision fondateur WhatsApp Cloud API) (DEP) (@model: sonnet)
- [ ] PUB110 — **[GATED: clé LLM + revue anti-hallucination (même porte que le commentaire LLM des briefs)] Stratège conversationnel sur données pub** : chat « pourquoi cette ad gagne ? que tester ensuite ? » au-dessus des métriques internes — réponses citant les chiffres réels uniquement (pattern FactTable). (@blocked: clé LLM + revue anti-hallucination fondateur) (DEP) (@model: opus)
- [ ] PUB111 — **[GATED: budget fondateur — dépendance payante] Tier vidéo AI-UGC (Arcads/Creatify-style)** : adaptateur `creative_factory` supplémentaire pour avatars parlants + speech-to-speech (voix réelle Darija du fondateur sur acteur IA — aucun outil n'a de Darija natif) ; nés en backlog, jamais publiés sans approbation. (@blocked: budget fondateur dépendance payante) (DEP) (@model: sonnet)
- [ ] PUB112 — **[GATED: décision fondateur — touche le cœur décisionnel] Bandit « toujours actif » au niveau adset** : étendre la logique Thompson hors des expériences déclarées pour réallouer en continu le budget entre adsets vivants (propose-only au début). À n'ouvrir qu'après PUB15/PUB18 en production et un historique de regret (PUB86) propre. (@after: PUB15, PUB18, PUB86) (@blocked: décision fondateur cœur décisionnel) (DECISION) (@model: opus)
- [ ] PUB114 — **[GATED: numéro dédié + coût télécom] Suivi d'appels par annonce + rappel SMS d'appel manqué** : numéros de suivi par source, missed-call-textback — une partie des leads marocains arrive encore par téléphone. Dépendance opérateur/API télécom payante à choisir avec le fondateur. (@blocked: dépendance télécom payante fondateur) (DEP) (@model: sonnet)

### GATED — dépendances payantes PUB-P8 (ne PAS auto-construire — chaque item attend son budget fondateur)

- [ ] PUB132 — **[GATED: budget fondateur fal.ai ~50-150 MAD/mois] Adaptateur images fal.ai dans la fabrique** : lane `fal` de `creative_factory` (FLUX schnell/dev, ~$0.003-0.05/image) pour visuels statiques ancrés (composés avec les textes PUB124), coût tracé `cost_cents` (le ROI par lane PUB81 le lit déjà), étiquette IA PUB126 automatique, sortie = assets en attente d'approbation, key-gated NO-OP propre sans `FAL_API_KEY`. **Done =** clé posée → asset image généré + coûté + étiqueté, en approbation ; sans clé → NO-OP FR. Files: `apps/adsengine/creative_factory.py`, tests. (@blocked: budget fondateur fal.ai) (DEP) (@model: sonnet)
- [ ] PUB133 — **[GATED: budget fondateur json2video/Bannerbear ~200-500 MAD/mois] Pont template-vidéo** : rendre les scripts ancrés EXISTANTS (`video_queue.build_grounded_script`, beats persistés PUB82) en vidéos template (slideshow photos chantier + textes — PAS d'avatar : distinct de la porte AI-UGC PUB111), lane dédiée coûtée, étiquette IA, sortie en backlog d'approbation, key-gated NO-OP. **Done =** clé posée → script mock rendu (mock API) en asset vidéo étiqueté en approbation ; mapping beat↔scène conservé pour la rétention PUB82. Files: `apps/adsengine/{creative_factory.py,video_queue.py}`, tests. (@blocked: budget fondateur template-vidéo) (DEP) (@model: sonnet)

---

#### DONE LOG — Vague 3 lane frontend/data (2026-07-12)

### Groupe QX — Quote journey best-in-world ROUND 6: verified defects + conversion loop (2 audit rounds × 24 agents, adversarially verified + Fable design pass, 2026-07-10)

*A 2-round deep audit of the whole web→ERP quote journey (10 code lanes + 4 researchers, then 10
adversarial verifiers + Fable completeness critic + Fable target-state designer). 52 of 53 round-1
findings were CONFIRMED or PARTIAL under adversarial re-verification against real code; every task
below carries a verified fix spec. Three cross-cutting truths the whole group serves: (1) there is
NO single owner of the money number — six independent computations of a quote's value coexist and
three ignore `remise_globale`; (2) the dominant failure mode is UNWIRED features — built, tested,
then never scheduled/routed/linked; (3) client-facing URLs are minted ad hoc with two confirmed
404s at moments of maximum client intent. Rule #4 intact throughout: PDF fixes go INSIDE the
vendored engine; the engine only renders. Research anchors: Storydoc 1.3M sessions (82% of opens
happen <1h; 46% of signers sign <48h of open; losing proposals get viewed 3.5×), Proposify 2025
(e-sign path = 4× close, images +72%), MIT/Oldroyd speed-to-lead (21× qualification <5 min).
E-signature legal basis: cite **Law 43-20 (2020, BO n°6970 2021)** which superseded loi 53-05.*

**A — ONE MONEY MODEL (the critical: client sees discounted TTC, is billed full price)**

**B — THE CLIENT PDF (rule #4 — all fixes INSIDE the vendored engine)**

**C — E-SIGN & ACCEPTANCE (the decision moment)**

**D — WIRE THE DEAD AUTOMATION (built, tested, never scheduled/linked)**

**E — WEBHOOK & CRM INTAKE FIDELITY**

**F — SELLER QUOTE CREATION (the generator)**

**G — SELLER DAY-IN-THE-LIFE**

**H — THE CONVERSION LOOP (research-anchored)**

**I — ONE TRUE MATH (screen == PDF == proposal)**

**J — PUBLIC SURFACE HARDENING & RETENTION**

**GATED — founder decisions/accounts/data (queue, do NOT build the gated part)**
- [ ] QXG1 — **[GATED: founder account]** WhatsApp BSP evaluation, 360dialog-first (flat $59/€49/mo, zero markup on Meta per-template pricing — 2026 model is per-template-message, the old free tier is gone). Needs Meta Business verification + Morocco rate confirmation from the dashboard (not blogs). Unlocks: automated template sends for QX30's nudges, real OTP channel (QX10), proposal delivery. Until then everything ships degraded via wa.me drafts. (@blocked: founder account WhatsApp BSP) (@lane: whatsapp-bsp)
- [ ] QXG2 — **[GATED: founder account]** PayZone-first merchant onboarding (reported 5-10 day onboarding, no deposit, ~2-3% fees — verify primary-source), CMI later if volume justifies. Activates QX33's card-payment slot + facture PaymentLinks with a REAL provider (QX3 keeps everything fail-closed meanwhile). (@blocked: founder account PayZone/CMI) (@lane: ventes-pay)
- [ ] QXG3 — **[GATED: founder data]** Price the 11 OSP 30-series curve pumps (today ALL curve pumps are seeded price=0, so the intended HMT+débit agricole flow can never quote a buyable pump — the highest-impact single data entry in the journey) + verify/correct the suspicious HMT seeds (7.5CV@220m, 10CV@250m must be nominal duty points, not shutoff head) + confirm/replace the archived estimated coffrets. Land QX40's phase check first. (@blocked: founder data pump prices) (@lane: backend/stock)
- [ ] QXG4 — **[GATED: founder content]** Real proof pack for the trust page: selected installation photos, named testimonials, certifications (checked-facts-only rule — omit what doesn't exist). Proposify 2025: images +72% close rate, testimonials near the price +73% win probability. Lands inline in `residential/trust.py` after QX4. (@blocked: founder content proof pack) (@lane: quote-engine)
- [ ] QXG5 — **[GATED: founder ops check, 10 minutes]** Production env sanity: confirm `WEBSITE_LEADS_COMPANY_ID` is set (else `_resolve_company()` falls back to first Company by pk — silent misrouting risk if a second Company row ever exists); confirm the outbound email backend keys (`EMAIL_BACKEND`/`SENDGRID_API_KEY` vs `SENDINBLUE_API_KEY`) so QW8/QX13's email legs are live; confirm `PUBLIC_MAPTILER_KEY` naming on Cloudflare. (@blocked: founder ops env check) (@lane: ops-config) [2026-07-13 code guard added: both `_resolve_company()` copies (`apps/crm/webhooks.py`, `apps/crm/public_chat_views.py`) now `logger.error` LOUDLY when `WEBSITE_LEADS_COMPANY_ID` is unset AND 2+ Company rows exist, or when it's set to a non-existent pk — safe fallback preserved (never breaks the public endpoint), misconfiguration is now visible in logs. Still `[ ]`: the founder ops confirmation (var actually set in prod) is unbuilt/unverifiable here.]

---

### Group S — Internal team chat ("Discuss") (founder request 2026-06-21)

*Goal: a best-in-class INTERNAL team chat inside the ERP — staff message each other
1-to-1 (DMs) and in named channels, with file/image/voice attachments, @mentions,
reactions, pinned messages, message search, edit/delete, and the ERP superpower of
dropping a record (lead/devis/chantier) into a conversation as a rich clickable card.
New messages arrive by smart polling while a conversation is open and by the existing
Web Push (iPhone/Windows) when the app is backgrounded; per-conversation mute is
supported. Voice memos are transcribed (FR/Arabic/Darija best-effort) by a self-hosted
faster-whisper model in the FastAPI AI service, degrading gracefully when disabled.
Approved in the 2026-06-21 brainstorm with Reda. Full design in
`docs/superpowers/specs/2026-06-21-internal-team-chat-module-design.md`.*

> **Safety model (applies to the whole group).** Strict multi-tenant isolation: every
> model carries a `company` FK forced server-side (never from the body), and every viewset
> is company-scoped AND membership-checked (a user can only read/post in conversations they
> belong to — non-member 403, cross-tenant 404). All migrations additive/nullable. Cross-app
> reads (lead/devis/chantier labels for the share-a-record card) go through the target app's
> `selectors.py` — never importing its models/views (CI import contract). Attachments reuse
> `apps/records/storage.py` (MinIO, type-validated, 10 MB). Notifications reuse the existing
> `notify()` entry point + Web Push. STAGES.py is not involved.

> **Real-time stays polling for v1 (founder choice 2026-06-21).** No WebSocket/Channels in
> v1 — new messages arrive by short-polling the open conversation (~3 s) plus the existing
> Web Push when backgrounded. Typing indicators + live presence + instant delivery are
> deferred to the GATED **S21** WebSocket upgrade (brand-new ASGI/Channels infra), which a
> plan-run must NOT build until the founder provisions it.

> **One founder-approved backend dependency.** S10 adds `faster-whisper` (self-hosted,
> CPU-efficient, no paid service) + a lazily-downloaded model to the FastAPI AI service,
> behind a `CHAT_TRANSCRIPTION_ENABLED` flag so existing deploys are unaffected when off.
> This single dependency is pre-approved (2026-06-21 brainstorm); no other new dependency
> (backend or frontend npm) is authorized — the frontend reuses the existing Radix / lucide /
> sonner / @dnd-kit kit and the browser `MediaRecorder` for voice.

- [BLOCKED: waits on founder-provisioned WS infra (ASGI server process + Redis channel layer + nginx WebSocket proxy) — a real external prerequisite a run can't satisfy] S21 — **Real-time WebSocket upgrade (Django Channels).** Instant message delivery, typing indicators and live presence via Django Channels + a Redis channel layer + an ASGI server (daphne/uvicorn) + an nginx WebSocket proxy, authenticated with the same JWT. (UNGATED from category-gating 2026-06-21; held only by the infra prerequisite. **MY RECOMMENDATION: DEFER — "Discuss" chat already works via 3 s short-polling (`useChatPolling.js`); the WS stack adds real ops complexity (sticky sessions, connection draining on deploy) for a marginal gain on a small internal team. Build it only on a concrete need (live dispatch / many concurrent users).** Files: `erp_agentique/asgi.py`, `apps/chat/consumers.py` (new), settings `CHANNEL_LAYERS`, nginx config, frontend socket client.) (ARCH) (@lane: realtime)

### Groupe QJR — Reconstruction du parcours devis (audit L3 du 29/08, décisions fondateur D1-D12 tranchées)

> **Ce que c'est.** L'audit L3 du 29/08/2026 (fleet de lanes lecture-seule + rondes de réfutation
> adversariales) a vérifié 91 constats sur 93 dans le code : sept chaînes monétaires qui donnent
> trois réponses différentes pour le même devis, un bloc `etude_params['dimensionnement']` mis en
> cache sur la PRÉSENCE de sa clé (rien ne l'invalide quand la facture du lead change), quatre
> mécanismes de surcharge incompatibles, cinq chemins de création de devis qui recomposent chacun à
> leur façon, et une famille de chiffres publiés au client qui décrivent une configuration que le
> devis ne vend pas. Le programme est ordonné **correction d'abord, structure ensuite** : on corrige
> les nombres faux AVANT d'extraire quoi que ce soit (sinon les tests golden de la vague pipeline
> figent les bugs d'aujourd'hui), puis on déplace par étranglement (strangler) — jamais de big-bang,
> jamais deux implémentations qui coexistent.
>
> **Le plan de merge (M0→M6, un merge par vague, jamais un merge par lane).**
> * **M0** — les contrats SEULS sur `main` (PACT10, ~2 min de CI docs-only) : QJR1-QJR3.
> * **M1** — gardes + corrections client-facing, aucune migration : QJR4-QJR41 (~38).
> * **M2** — entrées canoniques + API monnaie + contrat d'override, **LES 3 MIGRATIONS DANS UN SEUL
>   MERGE** (QJR52 données prix_par_kwc, QJR58 `Devis.overrides`, QJR59 `LigneDevis.quantite_manuelle`
>   + `prix_manuel`) : QJR42-QJR67. Seule vague à cache CI FROID → `preflight.ps1` complet avant push.
> * **M3** — décomposition de `services.py` (déplacements purs, zéro changement de comportement) :
>   QJR68-QJR78.
> * **M4** — étapes du pipeline + modules purs du front (ajoutés testés, importés par personne) +
>   la lane d'audit ciblé des surfaces jamais auditées : QJR79-QJR92.
> * **M5** — les bascules, **2-3 par merge**, une passe Fable AVANT chaque merge de bascule :
>   QJR93-QJR102.
> * **M6** — contrats de parcours, conversions de tests, orphelins et notes : QJR103-QJR113.
>
> **RÈGLES PERMANENTES DE CE GROUPE (non négociables).**
> 1. **Une tâche = corrige OU déplace OU crée — jamais deux.** C'est ce qui rend chaque commit
>    relisable et `git revert`-able seul. Un déplacement qui « corrige au passage » est refusé.
> 2. **Toute bascule SUPPRIME l'ancien code dans le MÊME commit.** Aucun double chemin, jamais
>    (le tunnel fr/ar/en est la preuve permanente de ce que devient un double chemin toléré).
> 3. **Jamais deux sessions en parallèle sur ce groupe** : les deux moitiés possèdent les mêmes
>    fichiers `apps/ventes/` (`services.py`, `models.py`, `migrations/`). Les lanes qui touchent
>    `services.py` / `models.py` / `migrations/` sont volontairement LONGUES et sérialisées —
>    écrivain unique, c'est voulu, ne pas les découper pour « paralléliser ».
> 4. **Les tâches apps/web-only vivent dans `docs/WEB_PLAN.md` (Groupe QJW)** et attendent le merge
>    M0 (contrats sur `main`). Rien de `apps/web/**` ne se construit ici.
> 5. **PACT11 mécanique :** `apps/ventes/selectors.py` n'est déclaré QUE par QJR8 et
>    `apps/crm/selectors.py` QUE par QJR9 — les deux sont en tête de M1 exprès. Toute tâche touchant
>    `frontend/src/{features,pages}/ventes/` porte donc `@after: QJR8`, et toute tâche touchant
>    `frontend/src/features/crm/` porte `@after: QJR9`. Ne pas retirer ces `@after` : `plan_lanes.py`
>    refuse la lane sans eux.
> 6. **QJR69 déplace la facturation à l'INTÉRIEUR de `apps/ventes` (`apps/ventes/domain/`)** — ce
>    n'est PAS le découpage cross-app ODX18 (bloqué), qui reste un chantier séparé et ultérieur :
>    aucun conflit aujourd'hui, ne pas les confondre.
> 7. **Zéro chiffre inventé** (règle fondateur absolue) : chaque tâche de ce groupe qui publie un
>    nombre au client soit le dérive et le trace, soit l'OMET — jamais un repli forfaitaire.
>
> Référence : rapport d'audit L3 (artifact « Radiographie du parcours devis », 29/08/2026) et
> `decisions_fondateur_20260829` (D1-D12, toutes tranchées le 29/08 — aucune n'est à re-poser).

#### M6 — les contrats de parcours, les conversions de tests, les orphelins et les notes

- [ ] QJR113 — **[GATED: chantier séparé post-programme — décision fondateur D10 du 29/08] Moteur serveur pour industriel / commercial / agricole** : le serveur ne possède le calcul que du marché RÉSIDENTIEL ; pour les trois autres marchés, `computeROI` / `computeEtudeIndustrielle` / la moitié pompage de `solar.js` ne sont pas un repli — ce sont le SEUL moteur d'économies qui tourne jamais (`etudeHoraireCorps` est verrouillé sur `modeInstallation === 'residentiel'`, `DevisGenerator.jsx:964, :984`). Étendre `POST /ventes/etude-horaire/preview/` à industriel / commercial / agricole est la sortie structurelle. **Décision fondateur D10 : chantier SÉPARÉ, APRÈS ce programme — industriel/commercial d'abord, agricole ensuite. NE PAS le construire dans le groupe QJR.** En attendant, la règle qui s'applique et que les tâches QJR35 / QJR89 mettent en place : **chaque chiffre du moteur JS est visiblement étiqueté « estimation » (règle du nombre signé) et n'est JAMAIS mêlé aux chiffres serveur.** Cette ligne existe pour que personne ne re-pose la question et pour que le chantier ait une ancre quand Reda l'ouvrira. **Done =** rien à construire ici ; la tâche reste `[ ]` GATED jusqu'à ce que le fondateur ouvre le chantier. **Calendrier tranché le 30/08 (menu de décisions Q2 : réponse b)** : lancement après 1-2 semaines d'usage réel du parcours résidentiel refait — sur le mot du fondateur « lance le chantier D10 ». Files: `docs/PLAN2.md`. (DECISION) (@blocked: chantier séparé post-programme, décision fondateur D10) (@model: opus)

# Taqinor OS — UI/UX overhaul ("prettier than Odoo")

*Goal: a calm, premium, data-first ERP — Linear/Stripe-tier polish, brand-matched to Taqinor, denser and cleaner than Odoo. Built on the existing React 19 + Vite + Tailwind 4 + recharts stack. Positioned ahead of Groups A–D so feature work inherits the new design language. Constraints: do NOT touch the devis/facture PDF templates, the public PDF pages, or the PdfCanvas PDF content (client-facing, gated separately); do NOT touch the apps/web marketing site; STAGES.py stays a fixed CI contract; schema changes additive/nullable only, every new value seeded from current in-code defaults.*

> **Renumbered on intake (2026-06-18):** the source proposal lettered these groups E–O, but `docs/PLAN2.md` already has a **Group E** (the E2E browser-test suite, tasks E1–E16). To keep every group/task id unique, the UI/UX-overhaul groups were shifted one letter to **F–P** (and their task ids re-prefixed to match) before being inserted here. Titles, content, and the running task numbers (14–69) are otherwise verbatim.

> **World-class look-and-feel wave (queued 2026-06-21, founder request "best-looking ERP in the world").**
> The design *foundation* already shipped (tokens.css, ~45 `src/ui` primitives, the hand-rolled
> `DataTable`, the app shell with sidebar/global-search/breadcrumbs/bottom-tab-bar) — so this wave is
> **adoption + refinement to Linear/Stripe/Vercel tier**, grounded in a fresh world-class audit (OKLCH
> tokens, premium tables, ⌘K command palette, restrained charts, tasteful motion, mobile/PWA polish,
> WCAG 2.2 AA). Tasks **F120–P171** fill the previously-empty Group F–P headers (the original 14–69
> series shipped/archived in `docs/DONE.md`; these continue the running number at 120 to stay unique).
> Hard constraints (unchanged): NEVER touch the devis/facture PDF templates, the public PDF pages, the
> `PdfCanvas` content, or the `apps/web` marketing site; import stage names from `STAGES.py` (never
> hardcode); schema changes additive/nullable seeded from current defaults; **no new npm dependency**
> (build on the already-installed Radix / recharts / @tanstack/react-table / @dnd-kit / sonner / lucide
> — anything else is gated). New user-facing text in French.

### Groupe VX — « Le plus bel ERP du monde » : signature visuelle, expérience Apps & craft + perfection technique (audits 16+11 agents, 2026-07-07/08)

*Provenance : demande du fondateur (2026-07-07) « make my ERP the best looking in the world + les modules
sont-ils mieux découpés façon Odoo ? ». Audit multi-agents à modèles étagés : 9 lanes de lecture du repo
(design-core, shell-nav, écrans CRM/ventes/ops/insight/fondation, mobile-PWA, scan de cohérence) + 5
recherches web best-in-class (Odoo 18/19, Linear/Attio/Stripe/Notion, data-viz, délice/motion,
field-service) + une carte anti-duplication sur TOUS les plans, puis synthèse Fable. Chaque constat est
vérifié dans le code (fichier:ligne) et re-vérifié par l'orchestrateur avant intégration.*

**VERDICT MODULES — la réponse à la question du fondateur.** Le découpage façon Odoo est le BON choix et il
est déjà à moitié fait : GARDER et TERMINER le plan ODX tel que queued (PLAN.md ODX1–23 — manifests, catalogue
+ fermeture de dépendances et enforcement déjà livrés ; les moves restants facturation/achats/ao/portail/frais
sont des migrations state-only, sûres et révertables) — ne jamais re-fusionner, revenir en arrière coûterait
plus cher que finir. MAIS le découpage backend seul ne donnera jamais l'effet « apps » perçu : ce que
l'utilisateur ressent comme des modules est une expérience de NAVIGATION. Aujourd'hui la sidebar empile ~106
destinations plates (45 codées en dur + 61 items de 16 `module.config.jsx`) toutes du même gris avec le même
accent — Compta, RH, QHSE et Litiges sont visuellement interchangeables. Ce groupe construit la couche
frontend manquante (accent par module, lanceur d'apps, favoris épinglés, breadcrumb→cockpit) en s'ADOSSANT à
ODX5/6/7 (queued), jamais en les dupliquant.

**Vision « Lumière sur Nuit ».** Un fond calme bleu nuit ; la lumière (brass) dépensée avec parcimonie
exactement là où l'énergie circule. Diagnostic central vérifié : la fondation de tokens (F120–P171) est
world-class sur le papier, mais l'app RENDUE est une installation shadcn slate générique — ~604 hex codés en
dur dans `index.css` (top : la palette slate par défaut de Tailwind, pas la marque), coquille Sidebar/Header
100 % figée hors tokens, QUATRE « ors » et TROIS « navys » concurrents, `<body>` en system-ui + `#f1f5f9`,
dark mode à moitié réel. Cette vague est de l'ADOPTION et de la SIGNATURE, pas une refonte de la fondation.

> **Contraintes (chaque tâche VX).** Zéro nouvelle dépendance npm (Radix / Tailwind 4 / recharts /
> @tanstack / @dnd-kit / sonner / lucide déjà installés suffisent — sinon flag [GATED: new dep]). Ne JAMAIS
> toucher les templates PDF devis/facture, les pages PDF publiques, PdfCanvas, `/proposal` (règle #4) ni
> `apps/web`. Clés de stage importées de STAGES.py, jamais codées (règle #2 — seules des COULEURS peuvent
> être tokenisées). UI en français ; hooks e2e (`ap-*`, `att-*`, `pp-*`) préservés et déplacés AVEC leurs
> éléments ; garde `noValidate`/`step="any"` du générateur intacte ; `prix_achat`/marge JAMAIS client-facing.
> Frontend-only — DEUX exceptions round 2, flaggées dans leur tâche : VX61 (endpoint de collecte web-vitals
> dans l'app `reporting` existante) et VX76 (templates d'email HTML, zéro logique) ; `prefers-reduced-motion` respecté partout ;
> contraste AA en clair ET en sombre. Le modèle conseillé par tâche est indicatif (l'orchestrateur arbitre).
> **Coordination inter-plans :** `docs/FRONTEND_GAP_PLAN.md` (câblage fonctionnel des backends X*/Z*, ajouté
> 2026-07-07 via fe-dev) partage trois fichiers avec ce groupe — `GedNavigator.jsx` (FE-XGED14 ↔ VX38),
> `TicketsPage.jsx` (FE-XSAV5/21/28 ↔ VX31), `DevisList.jsx` (FE-ZSAL8/XSAL16 ↔ VX7/20/40/44). Le run qui
> passe en second rebase sur le premier ; les deux plans sont complémentaires (câblage vs design), jamais
> en conflit d'intention.

**A — La signature : la coquille devient TAQINOR (le meilleur ratio qualité perçue ÷ effort de la vague) :**

**B — L'expérience « Apps » (la réponse frontend au verdict module-split ; s'adosse à ODX5/6/7, ne les duplique pas) :**

**C — Le chemin de l'argent (générateur, devis, factures — l'écran le plus stratégique doit être le plus soigné) :**

**D — CRM niveau Attio :**

**E — Cockpits & monitoring vivants :**

**F — Opérations (les îlots non migrés) :**

**G — Fondation, délice, mobile, voix :**

**H — Compléments (critique de complétude Fable, 2026-07-07 — deux espaces blancs confirmés absents de TOUS les plans) :**

---

**ROUND 2 (2026-07-08) — « le meilleur dans TOUS les aspects » : perfection appareils, vitesse, résilience, locale, portes CI.**
*Le fondateur a challengé : « êtes-vous sûrs qu'avec ces tâches ce sera le meilleur ? je veux le meilleur dans TOUS
les aspects, y compris marcher parfaitement sur téléphones et ordinateurs ». Réponse honnête : VX1-47 rend l'app la
plus belle et la mieux organisée — mais « belle » et « marche parfaitement partout » sont deux chantiers. Un second
balayage (11 agents : matrice appareils/Safari, performance réelle, résilience, locale, surfaces secondaires, portes
CI + recherche best-practices + carte anti-duplication + synthèse Fable) a trouvé des CASSES réelles prouvées dans le
code : sur iPhone Safari AUCUN PDF ne s'ouvre (window.open après un await = bloqué en silence, ~10 écrans) et la CI
mobile ne teste que Chrome donc ne peut pas l'attraper ; au-delà de 100 lignes les listes stock/devis/factures/clients
et les KPI du Dashboard MENTENT (troncature silencieuse page 1 DRF) ; le formulaire de devis (20 min de saisie) n'a
ni brouillon ni garde de sortie ; la liste factures sur téléphone empile des valeurs SANS étiquettes ; le sélecteur
de langue promet EN/AR mais ~2 % de l'app est traduite ; les emails partent en texte brut sans logo ; zéro style
d'impression. VX48-82 répare tout cela ET installe les portes CI (WebKit/iPad/zoom/régression visuelle/axe dynamique)
pour que « parfait » le RESTE. Dédupliqué contre YHARD7/8, YTEST, YAPIC, YDATA, FG386, QPERF1 (chacun cité là où on
s'y adosse). Les vérifs de l'orchestrateur ont corrigé les chemins des slices (`features/*/store/*Slice.js`).*

*Coordination avec le **Groupe ARC** (PLAN.md, ajouté 2026-07-08 via PR #333 — socle plateforme) : ARC a dédupliqué
contre VX1-47 nommément ; les points de contact round 2 sont (a) **ARC49/ARC53** (DevisList/FactureList → moteur
DataTable) possèdent désormais la migration que le NE PAS FAIRE round 1 différait — elles doivent atterrir APRÈS
les tâches VX touchant ces fichiers (VX7/20/21/40/44/48/50/52/63/79/80) et préserver leurs comportements ;
(b) **ARC45** (`useResource` fetch/état mutualisé) est la généralisation architecturale des fixes ciblés VX54/55/67 —
les fixes passent d'abord, ARC45 les absorbe ; (c) **ARC39** (plus d'email brut interne, routage notifications) est
complémentaire de VX76 (le TEMPLATE que les deux goulots rendent).*

**I — Cassé AUJOURD'HUI sur téléphone / Safari / tactile :**

**J — Vitesse réelle sur 3G/4G marocaine (et chiffres JUSTES) :**

**K — Ne JAMAIS perdre le travail :**

**L — Les portes CI qui verrouillent tout pour toujours (WORTH-IT uniquement, per recherche) :**

**M — Honnêteté de la langue et de la locale :**

**N — Surfaces secondaires (emails, impression, chrome navigateur, liens, fichiers) :**

---

**ROUND 3 (2026-07-09) — « le meilleur outil avec lequel un employé ait travaillé » : ergonomie par métier, vitesse de saisie, file de travail, droit à l'erreur, interop.**
*Le fondateur a re-challengé : « êtes-vous sûrs ? je veux que les EMPLOYÉS le classent comme le meilleur outil — couvrez TOUS les angles et pour chacun la MEILLEURE solution ». Rounds 1-2 = beau + techniquement parfait ; round 3 = au service de l'employé. Sweep 12 agents (journées du technicien/commercial/directeur/comptable ; vitesse de saisie ; file de travail personnelle ; droit à l'erreur ; interop Excel/WhatsApp/téléphone ; 2 recherches externes G2/Capterra/NN-g/Odoo/Linear/Superhuman ; carte anti-duplication) + synthèse Fable + dédup adversariale contre les 2 084 tâches NT (`docs/new_tasks_plan.md`, PR #345), VX1-82, ARC, FE-*. **L'insight n°1, tracé dans le code : l'intelligence déjà construite et payée n'atteint jamais un écran qui dit « fais ça maintenant »** — la tournée géo-optimisée (endpoint complet, jamais appelée par l'écran du technicien), la signature client (modèle+endpoint+offline construits, zéro UI), le journal d'appel typé du commercial (backend livré, zéro site d'appel), la file de relances FG31, le toast « Annuler » `toastWithUndo` (0 appelant), la délégation d'absence — tous orphelins côté écran. La majorité du round 3 est donc du CÂBLAGE, pas de la construction : le meilleur ratio valeur/effort des trois rounds. Dédup NT appliquée : 5 seeds réécrites/abandonnées (voir NE PAS FAIRE round 3). **Ce qu'aucun audit ne remplace — noté pour Reda, PAS une tâche : une vraie boucle de retour employés** (3 chiffres mesurés avant/après : temps « nouveau lead → 1er appel », taps pour clôturer une intervention, minutes de patrouille matinale ; 30 min d'observation/persona/mois ; un canal « signaler une friction » à un tap + les web-vitals réels de VX61).*

**O1 — La file, la confiance, les gestes quotidiens (tous les employés, plusieurs fois/jour) :**

**O2 — La vitesse de saisie (commerciaux + comptable, dizaines de fois/jour) :**

**O3 — Le droit à l'erreur (tous, la confiance au quotidien) :**

**O4 — Le directeur décide vite et juste (Reda + Meryem, quotidien) :**

**O5 — Le technicien finit sa boucle (1-3 employés, chaque intervention) :**

**O6 — L'harmonie avec le monde extérieur (Excel / WhatsApp / téléphone) :**

**O7 — Le comptable reste dans l'app (persona finance, wiring polish) :**

**NE PAS FAIRE (rejets délibérés de l'audit — ne pas re-proposer sans nouveau contexte) :**
- Ne pas rebâtir la fondation design (F120–P171 livrés et bons) — cette vague est de l'ADOPTION et de la signature.
- Ne pas dupliquer ODX5/6/7 (écran Applications, nav filtrée, extraction registre) — queued ; VX8/9/13 s'y adossent.
- Ne pas remettre en cause le découpage backend ODX ni re-fusionner des modules (verdict : continuer tel que planifié).
- ~~Pas de grille d'apps pleine page à la Odoo comme navigation obligatoire~~ — **INVERSÉ le 2026-08-01 par directive fondateur (« comme Odoo : je rentre, je vois mes apps, je clique, j'y suis, je dois sortir pour changer ») → Groupe ODY (ce fichier).** Le lanceur VX9 reste l'overlay de switch rapide ; les antidotes aux critiques d'origine (mono-app direct, transitions légères) sont ODY3/ODY11/ODY12.
- Aucune nouvelle dépendance npm : pas de framer-motion (CSS + Radix suffisent), pas de cmdk (palette maison livrée), pas de lib confetti (CSS-only), pas de leaflet-markercluster.
- Ne jamais toucher les templates PDF devis/facture, PdfCanvas, `/proposal`, `apps/web` (règle #4).
- Pas de funnel-chart branché sur un modèle de pipeline (règle #2 : le funnel STAGES.py n'a pas encore de modèle Lead/Opportunity backing) — seules les COULEURS de stage sont tokenisées (VX26).
- Pas de migration DevisList/FactureList vers le moteur `ui/datatable` dans cette vague (1 720/1 195 lignes, hooks e2e `ap-*` massivement accrochés au DOM actuel ; le gain ne vaut pas le risque sur le chemin de l'argent) — **désormais possédée par ARC49/ARC53 (PLAN.md, 2026-07-08)** : elles s'exécutent APRÈS les tâches VX touchant ces fichiers et en préservent les comportements.
- Pas de son (le silence est le bon choix pour un back-office partagé) ; l'haptique mobile (VX42) tient ce rôle.
- Pas de moteur de theming par tenant (coût élevé, un seul tenant dominant) ; le nom de société au login (VX34) suffit.
- Pas de WebSockets/indicateurs de frappe (précédent S21 [BLOCKED] — infra fondateur) ; le polling 3 s suffit.
- Pas de badges compteurs sur la BottomTabBar (exige un agrégat backend nouveau) — le bandeau « aujourd'hui » (VX27) couvre le besoin.
- Pas de refonte de Landing.jsx (page vitrine interne à faible trafic — la vraie vitrine est `apps/web`, intouchable).
- Pas de photo produit sur le catalogue dans cette vague (exige champ modèle + migration + pipeline d'upload — candidat à une future tâche BACKEND+UI dédiée). **AUTORISÉE par le fondateur le 2026-08-01 (« photos ok ») → la tâche dédiée est APX18.**
- Pas de clustering cartographique fait main ni d'endpoint de données de démo (hors périmètre frontend-first).

*Rejets round 2 (2026-07-08) :*
- Verrou optimiste Devis/Lead (409 concurrent) — vrai besoin mais exige modèle+serializer backend : territoire YDATA (PLAN.md), pas de doublon ici.
- Lighthouse CI sur le SPA authentifié — OVERKILL (personne ne « bounce » sur un outil interne) ; YHARD7 l'a déjà volontairement laissé optionnel ; VX61 (vitals RÉELS terrain) répond mieux.
- Second gate de budget bundle (BundleMon/size-limit) — YHARD7 possède déjà `check_bundle_budget.mjs` dans le job frontend-perf.
- Matrice Firefox toujours-active — aucun utilisateur Firefox connu ; VX68 = Chromium+WebKit PR-only, le bon ratio.
- Snapshots dark/RTL en matrice dédiée — OVERKILL tant que VX74 n'a pas tranché l'arabe ; si l'AR UI devient réel, ÉTENDRE VX70.
- Serveur de feature-flags + dashboard qualité BI — OVERKILL à 2-5 utilisateurs ; les toggles env existants suffisent.
- Couverture screenshot exhaustive — la taxe de baselines dépasse la valeur ; VX70 reste à 6-8 écrans.
- `useTransition`/virtualisation supplémentaire — aucun long-task MESURÉ ne le justifie (les gels prouvés sont réseau-sériels → VX54/55) ; attendre les données RUM de VX61.
- Service worker de cache API — interdit sur données authentifiées (fuite inter-sessions) ; le precache d'app-shell existe déjà.
- File offline nouvelle — N91/F21 livrés, FG386 possède l'extension ; jamais un second outbox. Snapshot visuel du PDF devis — YTEST10. N+1 devis — QPERF1. Enveloppe d'erreur API/X-Request-Id/429 — YAPIC.

*Rejets round 3 (2026-07-09 — dédup contre les 2 084 tâches NT `docs/new_tasks_plan.md`) :*
- **2FA « se souvenir de cet appareil »** — ABANDONNÉ : `NTSEC14` (« Device trust ») construit la MÊME feature avec un design STRICTEMENT MEILLEUR (modèle `TrustedDevice` révocable + gate société `allow_device_trust` + audit) ; bâtir une version cookie-only ici créerait un 2ᵉ mécanisme parallèle. Attendre/construire NTSEC14.
- **Composant Corbeille générique `<CorbeillePanel>` + écran `/parametres/corbeille`** — possédé par `NTUX7` (app `apps/trash`, `ElementSupprime`, hook event-bus, purge/permissions/audit) ; VX96 ne fait que rendre `Lead` premier adoptant du soft-delete + l'undo-toast.
- **Formulaire de saisie DemandeAchat avec recherche-catalogue** — possédé par `NTP2P3` ; VX102 se limite aux points de montage mobile.
- **Refonte du chatter / 14ᵉ classe `*Activity`** — VX23 (ChatterTimeline) + ARC8/ARC9 ; VX97/VX111 ne font que consommer/monter.
- **Unifier le moteur d'approbation / matrice objet×montant×département** — ARC10 + `NTWFL1` ; VX86/99/100/101/103 câblent l'inbox/signaux AU-DESSUS des 5 sources actuelles et se ré-évaluent si le moteur unifié passe d'abord.
- **Page « Ma journée commerciale » dédiée / bandeau SLA séparé** — 6ᵉ silo ; VX83 « Ma file » absorbe ces sources (relances FG31, leads chauds/SLA, devis expirants).
- **Inbox mentions dédiée `/mentions`** — `NTCOL17` ; VX85 ne fait que réparer le `link` manquant que NTCOL17 exige.
- **Optimiseur de tournée 2-opt avancé** — `NTFSM3` ; VX88 ne fait que consommer l'endpoint `ma-tournee` déjà livré.
- **Undo de l'édition en masse** — `NTUX6` ; VX95 câble `toastWithUndo` sur archive/kanban seulement.
- **Paste-grid Excel (coller 5 lignes)** — différé : à 2-10 employés, l'import fichier (VX109) + « Copier » TSV (VX110) couvrent le volume réel.
- **KPI perso « mes-stats » pour le rôle normal, classement inter-pairs** — différé : vraie motivation mais exige endpoint + RBAC ; re-proposer une fois « Ma file » prouvée, jamais de classement au rôle normal.
- **Correction de ligne de paiement / suppression** — DECISION fondateur (implications GL sous le verrou de période FG115) : logguer la décision (immutable-par-avoir vs endpoint de correction) avant tout build ; détail dans `persona-finance.md`.
- **Client-360 complet, import relevé bancaire OCR, recompute TVA depuis le GL** — logés dans `persona-finance.md`, différés : croisent NTFIN/NTTRE/NTCRD (146 tâches finance NT) → passer une dédup dédiée avant de construire.
- **Re-surfacer l'abonnement iCal (FG6)** — une ligne dans VX46 « Mes préférences » (extension par référence), pas une tâche : le feed + le bouton « Copier » existent déjà sur CalendarPage.
- **Attention fold cross-lane (critic Fable)** — `FactureList.jsx` (VX92/93/97/114), `NotificationBell.jsx` (VX84/86 + VX14/56), `Dashboard.jsx` (VX86/VX27) sont édités par plusieurs lanes : rebaser en séquence (les `@after`/`@coord` posés) ou fusionner par fichier au build — jamais deux lanes concurrentes sur le même fichier.

### Groupe VXD — approfondissement forensique (rework 3 axes, 2026-07-10)

Provenance : rework forensique en 3 axes (beauté / robustesse / amour-employé), ~30 lanes
d'audit + synthèses Fable par axe + une méta-critique Fable finale (`grand-verdict.md`) qui a
contre-vérifié ~20 claims dans le code réel, tué/fusionné/rogné les seeds en collision avec
VX1-116, et corrigé les constats survendus avant transcription. Verdict honnête du méta-critique :
cette passe ne « rapetisse » pas les 3 rounds précédents en VOLUME, mais l'axe robustesse (VXD-A/B)
trouve des bugs d'une gravité qu'aucun round n'avait atteinte — doublon fiscal au retry, paie qui
valide une période avec des bulletins avalés, signature client hors-ligne qui s'évapore, deux
intercepteurs de refresh concurrents qui déconnectent des sessions valides — et la famille
« surfaces fantômes » (VXD-D) prouve que deux features entières (chat Discuss, LeadExpressModal)
rendent sans un seul octet de CSS, qu'un kiosque TV affiche du JSON brut, et qu'un token de focus
soigné est du code mort — des angles morts qu'une lecture JSX-only ne peut pas voir. Axes 2 et 3
ont été livrés partiellement au premier passage (21/45 puis 11/45) et complétés après le
grand-verdict depuis les rapports de lane bruts (`r2-*`, `r3-*`) ; ce qui suit est l'état complet
tel que livré, corrections du grand-verdict déjà appliquées seed par seed. Contraintes héritées à
l'identique du bloc VX : frontend-first, aucune dépendance npm nouvelle sauf tâche taguée
[GATED], ne jamais toucher `apps/ventes/quote_engine/`, `/proposal`, PdfCanvas ni `apps/web`
(règle #4), toute clé de stage vient de `STAGES.py`/`features/crm/stages.js`, jamais un littéral
(règle #2), UI française partout, hooks e2e `ap-*/att-*/pp-*` préservés, `prix_achat`/marge jamais
client-facing, tout scoping multi-tenant côté serveur (`request.user.company`, `perform_create`
force `company`).

---

## AXE 2 — ROBUSTESSE (VX160–VX208, 49 tâches survivantes sur 49 seeds ; 0 tuée, 2 rognées —
SEED-14 re-scopé/SEED-17 rogné, corrections déjà appliquées dans le texte transcrit ci-dessous)

**Sous-groupe VXD-A — Intégrité des mutations & résilience réseau (le niveau sous la
présentation d'erreur)**

*Note : VX117 (au sommet de ce document) EST la transcription de SEED-01 de cette section — ne
pas la dupliquer ici, la numérotation continue directement à SEED-02.*

**Sous-groupe VXD-B — Formulaires : ne jamais perdre une saisie**

**Sous-groupe VXD-C — iOS Safari / WebKit / PWA (la longue traîne au-delà de VX48-53/68)**

**Sous-groupe VXD-C (suite) — Viewport & performance réelle**

**Sous-groupe VXD-C (suite) — Accessibilité forensique (WCAG 2.2 prouvée file:line)**

*Acquis vérifiés à NE PAS refaire : Radix (focus-trap/Échap/flèches), sonner déjà
`aria-live=polite`, anneau `:focus-visible` global + `scroll-margin` (`index.css:89-132`),
reduced-motion (`:67-87`), cibles 44px `pointer:coarse` (`:156-173`), DataTable exemplaire
(`aria-sort`/`scope`/live).*

- [BLOCKED: dev-dep manquante, npm install impossible dans ce worktree — `eslint-plugin-jsx-a11y` absent de package.json/eslint.config.js ; la tâche elle-même se marque [GATED si dev-dep à ajouter]] VX198 — **[GATED si dev-dep à ajouter] Garde statique jsx-a11y ciblée : empêcher d'ÉCRIRE (@lane: frontend/ios)
  la régression (complément build du scan runtime VX71).** Rien n'empêche la réintroduction des
  trous ci-dessus (label sans contrôle, rôle sans props ARIA requises, interactif non
  focalisable) — `eslint-plugin-jsx-a11y` absent de la config (à confirmer ; sinon [GATED]
  dev-dep). Fix : sous-ensemble ciblé en warn→error : `label-has-associated-control`,
  `role-has-required-aria-props`, `interactive-supports-focus`, `click-events-have-key-events`,
  `img-redundant-alt`. Files : `frontend/eslint.config.js` (aucun code métier). DoD : `npm run
  lint` signale un `<label>` sans contrôle associé ; `frontend-lint` échoue sur une régression
  neuve ; le build actuel reste vert. (T2 — S, sonnet) (@lane: frontend/ios)

**Sous-groupe VXD-A (suite) — Sécurité frontend & observabilité (les échecs que personne ne
voit)**

*Non-défauts vérifiés à NE PAS re-signaler : auth par cookie httpOnly (aucun jeton en
localStorage, `AUTH_LOCALSTORAGE_KEYS=[]`), rendus chat/KB/copilote en arbres React (pas
d'injection), `rel=noopener` présent (faux positif multi-ligne), `prix_achat` correctement masqué
partout côté client.*

*Note : la graine TOTP 2FA exfiltrée vers `api.qrserver.com` (SEED-41) est déjà transcrite en
détail en tête de document — voir **VX120**. Ne pas la reconstruire ici.*

- [BLOCKED: partiel — voir DONE LOG 2026-07-12 ; codemod ~104 fichiers + garde CI restent hors budget d'une session sans build/lint] VX203 — **Contrat d'erreur UNIQUE : fin du double-toast (35 pages), `getApiError` (@lane: frontend/data)
  canonique (259 clones), `iaApi` aligné (le 403 IA n'est plus muet).** Trois moitiés du même
  contrat, explicitement renvoyées à l'axe robustesse par la synthèse beauté : (a)
  `api/axios.js:63-70` toaste DÉJÀ toute erreur ≠401/404, mais ~35 pages re-toastent dans leur
  `catch` (3 fichiers seulement posent `suppressErrorToast`) → DOUBLE toast sur des centaines de
  chemins. Contrat : l'intercepteur est la source par défaut ; tout `catch` qui gère INLINE passe
  `{suppressErrorToast:true}` ; garde grep `scripts/check_double_toast.mjs` dans frontend-lint.
  (b) 259 extractions inline `.response?.data?.detail` ré-implémentent une version PARTIELLE du
  helper existant (`lib/toast.js:92-107`) — promouvoir `lib/apiError.js` (`{message,
  fieldErrors}`, cas `non_field_errors`/tableaux/429/500 HTML/timeout), codemod des sites vers
  l'import unique (VX171 en consomme `fieldErrors`). (c) `iaApi.js` ne toaste RIEN globalement
  hors 401 : un 403 du catalogue d'actions agentiques ou un 500 FastAPI est INVISIBLE — aligner
  sur le contrat (a) en préservant les dégradations volontaires (`available:false`) via
  `suppressErrorToast`. Files : `api/axios.js`, `api/iaApi.js`, `lib/apiError.js` (extrait de
  toast.js), les ~35 pages fautives, `scripts/check_double_toast.mjs` (nouveau). DoD : un 500
  forcé = EXACTEMENT un toast (test) ; grep `.response?.data?.detail` hors helper = 0 ; un 403 IA
  surface un toast FR ; tests des formes DRF. (T2 — M/L, sonnet) (@lane: frontend/data)

---

## AXE 3 — AMOUR-EMPLOYÉ (VX207–VX252, 46 tâches survivantes sur 47 seeds ; 1 tuée par le
grand-verdict — SEED-03 — dont le delta est reporté en note sur VX56/VX86, jamais transcrit
comme tâche)

**Sous-groupe VXD-I — Attention & handoffs (le badge redevient CROYABLE). @after
VX83-86/99-101 (round 3, non construit) — transcrire chaque @after tel quel.**

**Sous-groupe VXD-I (suite) — Handoffs cross-persona (la main gauche apprend ce que fait la
droite)**

**Sous-groupe VXD-K — Le commercial : chaque job compté en clics**

**Sous-groupe VXD-L — Le technicien terrain**

**Sous-groupe VXD-M — Le comptable : le mois compté en clics**

**Sous-groupe VXD-N — Le directeur/admin : contrôle et supervision**

**Sous-groupe VXD-O — La vélocité de saisie**

**Sous-groupe VXD-P — Forgiveness / historique / confiance**

**Sous-groupe VXD-Q — Interop & onboarding→maîtrise**

**Sous-groupe VXD-R — L'âme au quotidien**

- [BLOCKED: attend VX156 — celebrate.js non construit] VX252 — **[BACKEND additif léger] Maîtrise personnelle : milestones non comparatifs, KPI
  d'adoption clavier, garde anti-backfire de la gamification. @after VX156 (célébration devis
  signé), @coord NTCRM23/24/28, NTUX40.** Recherche 2026 (Trophy.so, Carnegie Mellon) : ~10 % des
  employés sont motivés par la compétition ; les 90 % restants sont ACTIVEMENT démotivés par un
  classement. Trois pièces : (a) étendre `celebrate.js` (VX156, CSS-only) d'un déclencheur
  « milestone personnel » à seuils déterministes et espacés (50ᵉ intervention signée, 25ᵉ devis
  signé) — célébré UNE fois, jamais visible d'un collègue/manager, reduced-motion → toast simple ;
  (b) KPI interne d'adoption clavier (« % actifs ayant utilisé ⌘K 1×/semaine », signal `POST
  /ux/usage-signal/` best-effort jamais bloquant) — gate Directeur/Admin, JAMAIS montré au
  commercial (@coord NTUX40 — métriques disjointes, vérifier) ; (c) garde anti-backfire à
  INSCRIRE sur NTCRM23/24 avant leur build : `metrique_qualite_associee` affichée à côté du score
  brut + participation réellement opt-in invisible — jamais un score de vitesse seul. Files :
  `ui/celebrate.js`, points d'appel `MaJourneePage.jsx`/`SigneDialog`, `apps/reporting/models.py`
  + endpoint léger, `providers/CommandPalette.jsx` (compteur), note sur NTCRM23/24. DoD : la 50ᵉ
  intervention signée célèbre une fois (pas au 51ᵉ, pas au reload) ; le KPI calcule un % réel et
  échoue gracieusement à 0 ; la note NTCRM est posée dans le plan ; tests. (T3 — M, sonnet)
  (@lane: backend/notify — @after VX156)

---

## NE PAS FAIRE (Groupe VXD) — fusion dédupliquée des trois axes

**Déjà possédé par VX1-116 (couches design/coquille/cockpits) :**
- Re-signature coquille/marque, accents module, lanceur, cockpits → VX1-8, VX9-12/ODX5-7,
  VX15/27/29-34. Couleurs de stage StatusPill → VX26 (règle #2).
- Palette catégorielle data-viz + annotations → VX41 (danger zone) ; la rampe « solaire »
  d'un rapport source est versée comme INPUT à VX41, jamais re-proposée.
- Illustrations SVG d'états vides + confetti générique → VX40 (« délice mesuré ») ; VX156 (axe1
  S40b, ex-« signé célébré ») ne câble QUE le moment signé, jamais le système d'illustration.
- Theming par tenant, refonte Landing → rejets fondateur explicites (la « photo produit
  catalogue », durcie ici en rejet, a été AUTORISÉE par mot fondateur le 2026-08-01 → APX18)
  (rounds 1-3, PLAN2 NE PAS FAIRE). La « grille d'apps pleine page à la Odoo », rejetée à ces
  mêmes rounds, a été INVERSÉE par directive fondateur du 2026-08-01 → Groupe ODY (les trois
  autres rejets restent en vigueur).
- Grain `feTurbulence` sur la sidebar, `@starting-style` (pattern de référence, pas un défaut),
  `content-visibility` sur les listes non virtualisées (territoire perf, pas beauté) → rejetés/
  hors-axe, non repris.
- Badge persistant d'échec PDF sur la ligne, identifiant support dans ErrorBoundary → possédés
  par VX172 / VX206 respectivement.

**Déjà possédé par VX48-72 (appareils/Safari/perf nommés) :**
- PDF iOS (onglet pré-ouvert), popup-block detection, `data-label` tables, clavier iOS
  VisualViewport, `title=` tactile, balayage compat → VX48/49/50/51/52/53.
- Troncature 100 lignes + pagination parallèle, timeout axios + annulation, poll onglet caché,
  cold-path, préchargement, chunk-name, e2e comptes-justes, Web Vitals → VX54-VX61.
- Brouillon auto DevisGenerator + garde de sortie → VX62 ; JSON brut DevisList → VX63 ; error
  boundaries routes nues → VX64 ; `?next=` login → VX65 ; anti-double-submit Button → VX66.
- Safari/iPad/zoom/visual-regression/axe/Sentry e2e → VX68/69/70/71/72.
- `.agent-sql` momentum-scroll → CSS mort (0 consommateur), retiré de VX175 ; sa suppression
  appartient à VX121.
- Rejets round 2 toujours en vigueur : verrou optimiste 409 (→YDATA), Lighthouse-CI sur le SPA
  authentifié, BundleMon 2ᵉ gate, Firefox en matrice, service-worker cache des RÉPONSES API, 2ᵉ
  outbox offline, virtualisation sans mesure. VX187/VX188 sont les seules exceptions MESURÉES
  (DoD Profiler à l'appui) ; VX179 cache des ASSETS/médias en lecture, jamais des réponses API.
  `animation-timeline: scroll()` non confirmé dans le code → ne pas construire spéculativement ;
  attribution LoAF dans le beacon → amendement du build de VX61 (même fichier `vitals.js`), pas
  une tâche séparée ; note HMR du singleton `fieldOutbox` → un commentaire de code, pas une
  tâche ; moteur de conflit offline / CRDT → le signal de conflit EST le message serveur par op de
  VX119.
- Gate visuel bloquant par PR → contredit la décision LIVRÉE de VX70, jamais un amendement sans
  raison.

**Déjà possédé par VX73-116 (locale, files, saisie, argent, amour-employé) :**
- Sélecteur de langue menteur + `Ctrl K` → VX73 ; arabe RTL décision → VX74 ; format
  argent/date + garde CI → VX75 (VX143 en est l'annexe d'exécution, pas un doublon) ; compression
  photo → VX77 ; 404 branché → VX78.
- « Ma file » unique + cloche AUTRES + plomberie records + signaux approbation → VX83-86,
  VX99-101 ; jamais un 2ᵉ agrégateur ni une 2ᵉ boîte de réception parallèle (VX214 l'atteste par
  reshape) ; jamais de hook de polling séparé pour la cloche (VX56 possède
  `useVisibilityAwarePolling`, cloche incluse).
- Journal d'appel un-geste + tournée géo + délégation absence + technicien + signature client +
  résumé client → VX87/88/103/105/106/107.
- LeadForm Escape/autofocus, « Ajouter ligne » focus, convergence FactureForm, « enregistrer et
  créer un autre », défauts intelligents, Enter-pour-ajouter → VX89-94.
- `toastWithUndo` câblé (archive/kanban), soft-delete Lead, « qui a fait quoi », lien Historique,
  `tel:`/`wa.me`, import fournisseurs, « Copier » TSV, pièce jointe note chatter → VX95-98,
  VX108-111.
- Drill-down relances, exercice fiscal, sélecteur dates export, KPI compta, relance en lot →
  VX112-116.
- « Mes préférences » (thème/densité/module d'atterrissage/mouvement) → VX46 ; HelpTip
  contextuel → VX47 ; emails de marque wrapper → VX76 ; export XLSX horodaté → VX81 ; liens
  partageables `?id=` → VX79 ; impression → VX80 ; chrome onglet + non-lus → VX82.
- Rejets round 3 : 2FA remember-device (→NTSEC14), Corbeille générique (→NTUX7), formulaire
  DemandeAchat catalogue (→NTP2P3), refonte chatter (→VX23/ARC8-9), moteur d'approbation unifié
  (→ARC10/NTWFL1), « Ma journée commerciale » silo (→VX83 absorbe), inbox mentions dédiée
  (→NTCOL17), optimiseur 2-opt (→NTFSM3), undo bulk-edit (→NTUX6), paste-grid Excel multi-cellules
  (différé — VX237 est le collage UNITAIRE), KPI perso PUBLIC/classement (différé — VX219 est
  privé, VX252 non-comparatif), correction de ligne de paiement (DECISION), iCal abonnement
  (VX46), Client-360/OCR relevé (persona-finance).

**Frontières NT/ARC intouchables (les trois axes) :**
- Vues serveur partagées / FilterBuilder ET/OU / bulk-edit preview-undo / corbeille transverse
  (`apps/trash`) / quick-create palette générique / favoris / peek-hover de LIGNE / densité par
  vue → NTUX (frontière explicite « pas de changement visuel/shell (Groupe VX) »,
  `new_tasks_plan.md:2436`).
- Boîte email par user / RDV Calendly / boîte partagée / inbox mentions `/mentions` / digest
  personnel → NTCOL.
- Offline multi-module / accueils mobiles par rôle / géofence / scan QR / onboarding mobile
  « Ma journée » → NTMOB, NTMOB33.
- i18n/RTL/langue par user/polices arabes → NTI18N (attention : NTI18N5/17/30 touchent le moteur
  `/proposal` — règle #4, ne jamais y toucher côté client).
- Leaderboard/défis d'équipe → NTCRM23/24 (seul le garde-fou de VX252 s'y greffe, jamais le
  système lui-même).
- Moteur d'approbation unifié → ARC10/NTWFL1 ; migration DataTable DevisList/FactureList →
  ARC49/53 (VX180/VX178/VX184 se corrigent AVANT que la migration n'hérite du défaut) ;
  `useResource` → ARC44/45 ; RecordShell → ARC46 (VX159/VX250 construits indépendants, migrables
  dedans ensuite) ; politique magasin-unique → ARC26.
- Verrou optimiste backend 409 → YDATA ; file photo binaire offline → FG386 (« jamais un 2ᵉ
  outbox », VX119 ne construit PAS de moteur CRDT).

**Mécanique transversale (toujours vraie, tous les VXD) :**
- Frontend-first ; aucune dépendance npm nouvelle sauf tâche taguée [GATED] (VX120 QR 2FA,
  VX198 jsx-a11y, VX247(e) seed_demo — tous soumis au fondateur avant tout build).
- Jamais toucher `apps/ventes/quote_engine/`, `/proposal`, PdfCanvas, `apps/web` (règle #4) — le
  moteur RESTITUE, ne change jamais un statut (VX250(a) est une LECTURE) ; les PDF
  d'intervention/contrat (WeasyPrint) sont hors règle #4 mais on n'y crée jamais un 2ᵉ mécanisme
  concurrent (VX246(b)).
- Toute clé de stage vient de `STAGES.py`/`features/crm/stages.js` (règle #2) — jamais un
  littéral (VX224, VX248 raccourcis `1..4`, VX211 `queueViews`).
- `prix_achat`/marge jamais client-facing ni dans un peek/notification/WhatsApp/milestone
  (VX213 montants DA, VX217 AttentionPeek, VX156 messages — tous montants client-safe).
- Jamais d'envoi WhatsApp/email automatique — aperçu-puis-clic partout (règle manuel-wa.me
  fondateur, VX222/VX245/VX252) ; jamais de mutation via lien email non authentifié (VX212).
  `api.qrserver.com` et tout rendu tiers de secrets sont interdits (VX120).
- Ne pas dé-gater `/reporting/commercial` (VX219 ajoute une carte personnelle, le reporting
  manager reste manager) ; ne pas élargir le Journal global (VX243 = lecture record-scopée,
  jamais un grant company-wide) ; ne JAMAIS déverrouiller un accès nav/rôle sans décision
  fondateur.
- Hooks e2e `ap-*/att-*/pp-*` préservés partout ; UN seul Toaster ; scoping tenant TOUJOURS
  serveur (`request.user.company`, `perform_create` force `company`) ; jamais `count()+1` pour
  une référence ; migrations additives/révertables ; noter AUTH au DONE LOG pour
  VX235/VX242/VX243 ; FR partout.

### Group QC — Moroccan company autocomplete on client creation (founder request 2026-07-01)

*From Reda: « in Odoo I can easily find Moroccan companies when I start typing their name as new clients — add this to my ERP. » Research verdict: Odoo's Partner Autocomplete is a paid IAP service backed by Clearbit WEB data — it does NOT return ICE/RC/IF for Morocco (Moroccan Odoo integrators install manual `partner_ice`/`l10n_ma_legal` field modules). There is NO free official API or open dataset (OMPIC DirectInfo has no API and its legal notice bans data reproduction; ice.gov.ma is CAPTCHA-gated; data.gov.ma has no company register). The ONLY compliant registry-backed API with Morocco depth is the paid Inforisk/Charika offer (~950k companies, licensed OMPIC data, quote-only pricing). Scraping any of these violates their ToS → rule #5 (risk file + founder approval) and is NOT pursued. Code side is ready: `Client` already has `ice`/`if_fiscal`/`rc` (and `Fournisseur` the identical trio — no migration), the generic async `Combobox` (`frontend/src/ui/Combobox.jsx`) is the typeahead, and the PVGIS proxy (`apps/parametres/pvgis.py`) is the cached-external-lookup pattern for the gated provider.*

- [BLOCKED: paid — needs founder-provisioned Inforisk/Charika account] QC2 — **[GATED: paid — Inforisk/Charika API] Registry-backed autocomplete (the true Odoo-style experience).** Behind a flag (default OFF), plug a licensed Moroccan-registry provider into the QC1 seam: type a name → provider suggestions (ICE/RC/IF/adresse from licensed OMPIC data) → pick → auto-fill, with server-side caching (24 h, PVGIS-proxy pattern), rate limiting, and a clean no-key degrade to QC1's own-data mode. NEEDS FOUNDER: an Inforisk/Charika account + contract/budget (pricing is quote-only) — OR a founder-led OMPIC licensed-feed inquiry. Never scrape OMPIC/ice.gov.ma/Charika (ToS-prohibited; rule #5). **Done =** with a provider key the autocomplete returns registry-backed Moroccan companies and fills the legal IDs; without it, behaviour is exactly QC1; tests cover the provider seam + the degrade + the never-leak of the key client-side. Files: a provider client in `apps/crm/` (or `apps/parametres/` beside pvgis), `apps/crm/views.py`, settings flag, tests. (DEP/COST — needs founder-provisioned Inforisk/Charika account; note in DONE LOG) (@lane: backend/crm) (@after: QC1)

### Groupe ODY — L'ERP-Apps : j'ouvre → MES apps ; j'entre → je suis DANS l'app ; je sors → j'en choisis une autre (paradigme Odoo assumé, en mieux — fondateur 2026-08-01)

*Provenance : directive fondateur 2026-08-01 (« comme Odoo : quand je rentre je vois des apps, je
clique sur une et j'y rentre, je dois sortir pour avoir l'autre — et je veux le plus bel ERP »).
Cette directive INVERSE deux rejets antérieurs, amendés chirurgicalement dans le commit d'insertion :
le NE PAS FAIRE VX (« pas de grille pleine page… ») et la ligne correspondante du NE PAS FAIRE VXD
(les rejets voisins — theming par tenant, refonte Landing — restent en vigueur ; la photo
produit a été autorisée le 2026-08-01 → APX18).
Le même commit ajoute `ODY` à `unmapped_ok` de `docs/BUILD_ORDER.yml` et re-tamponne le fingerprint
CODEMAP. Conception : 4 éclaireurs (balayage anti-duplication de tous les plans, état réel du code
fichier par fichier, recherche web Odoo 17/18 + SaaS best-in-class, contraintes CI machine) + critique
adversariale Opus (15 défauts corrigés, 5 manques comblés) + synthèse Fable.*

**LE PARADIGME (3 phrases).** (1) À l'ouverture de l'ERP on atterrit sur le **Menu d'accueil** :
une grille plein écran qui ne montre QUE les apps installées par la société (ModuleToggle) ET
autorisées pour le rôle — rien d'autre, pas de sidebar générale. (2) Cliquer une app = y **entrer
complètement** : toute la coquille devient celle de l'app (identité, accent, nav de SES écrans
uniquement — les autres apps n'existent plus à l'écran). (3) Pour changer d'app on **sort**
(bouton ⊞ / logo → Menu d'accueil) — exactement Odoo ; les raccourcis power-user (⌘K, launcher
overlay VX9, `g`+lettre) restent par-dessus comme « mieux qu'Odoo », jamais comme substitut du
paradigme.

**CE QUI EXISTE DÉJÀ (s'adosser, ne JAMAIS dupliquer).** Toute la tuyauterie est livrée : manifests
+ catalogue + fermeture de dépendances (ODX2/3, `core/modules.py`), écran Paramètres→Applications
fonctionnel (ODX5, `pages/parametres/ApplicationsSection.jsx`), `modules_desactives` au bootstrap
`/auth/me/` + nav filtrée + garde de route (ODX6, `router/moduleGating.js` + `moduleLoader`),
registre `module.config.jsx` de 41 modules + Sidebar générique partielle (ODX7/ARC48/ARC54 — les
routes sont migrées, la Sidebar garde des sections en dur : tête Dashboard/Ma file/Messages,
DOCUMENTS/ged, INTELLIGENCE, ADMINISTRATION, `Sidebar.jsx:150-208`), gating transversal par société
(ODX23 + ARC28/29/33 via `core/platform.py`), KPI fédérés (ARC40, `GET /reporting/reports/kpi-federes/`),
accents par module (VX8), launcher overlay (VX9), épinglés (VX10), breadcrumb→cockpit + dernier
module (VX11), grille mobile « Plus » (VX12), préférence module d'atterrissage (VX46,
`pages/preferences/prefs.js`), thème white-label société (SCA24), prefetch au survol
(`router/prefetchMap.js`), scaffold de module (`scripts/scaffold-module.mjs` — doit rester
compatible). ODY est la couche PARADIGME + BEAUTÉ posée sur ce socle : essentiellement
frontend/shell, zéro nouveau modèle backend (exceptions signalées tâche par tâche).

**Contraintes (chaque tâche ODY).** Celles du Groupe VX s'appliquent intégralement : zéro nouvelle
dépendance npm (sinon [GATED: new dep] — `@dnd-kit/sortable` N'EST PAS installé, seul `core` l'est),
règles #2 (STAGES.py) et #4 (/proposal) intouchées, jamais `apps/web`, hooks DOM e2e
(`.header-title`, `ap-*`/`att-*`/`pp-*`) préservés ou déplacés AVEC leurs éléments, garde
`noValidate`/`step="any"` du générateur, `prix_achat` jamais client-facing, UN seul Toaster,
contraste AA clair ET sombre, `prefers-reduced-motion` partout. En plus, propres à ODY :
**jamais un 2ᵉ registre** (l'unique source des apps = registre ODX moduleConfigs ∩ modules actifs ∩
rôles — toute tâche qui liste des apps consomme ODY1) ; **toute tâche qui change un comportement
asserté par un test (vitest OU spec Playwright) adapte ce test DANS la même tâche** — jamais une
spec cassée léguée à la suivante ; chaque piège Odoo documenté a son antidote nommé (grille = clic
en plus → ODY3 ; breadcrumb pile-vs-hiérarchie → ODY5 ; menus profonds → vague C ≤2 niveaux ;
lenteur perçue → ODY11/12 ; incohérence inter-apps → ODY9 un composant, quatre surfaces).

**A — LE PARADIGME (la coquille bascule) :**

**B — LE PLUS BEL ÉCRAN D'ACCUEIL (la signature) :**

**C — CHAQUE APP DEVIENT UN MONDE COMPLET (passes app par app — l'immersion n'est belle que si l'intérieur est complet).**
*Checklist commune : module.config COMPLET (tous les écrans de l'app accessibles depuis SA nav —
croiser avec `router/index.jsx`, zéro route orpheline), cockpit d'app digne d'une porte d'entrée
(ModuleHero VX15 + actions rapides + KPI), icône/accent/description FR justes dans le manifest ET
le config, sous-menus ≤2 niveaux, liens croisés conformes ODY7, hooks e2e intacts. Dashboard
devient l'app « Tableau de bord », le chat l'app « Messages ». Lanes disjointes par app.*

**D — L'APP STORE INTERNE (installer une app doit donner envie) :**

**E — LE TRANSVERSE : ce qui échappe à l'immersion (le systray, mieux qu'Odoo) :**

**F — QUALITÉ, BASCULE, RETRAIT DU LEGACY (« parfait » doit le rester) :**
- [ ] ODY33 — **Retrait du legacy : à la fin, UN seul shell dans le code.** Une fois ODY31/32 verts ET le paradigme validé par le fondateur en prod : retirer le chemin de rendu « sidebar globale » legacy, le flag ODY30 (et son triplet env) et le CSS mort ; noter l'allègement du bundle. **Done =** grep du chemin legacy vide, e2e complètes vertes, chiffre bundle au DONE LOG. Files: frontend/src/components/layout/Sidebar.jsx, frontend/src/components/layout/Layout.jsx, frontend/src/components/layout/Header.jsx, frontend/src/index.css. (ROUTINE — M, sonnet) (@lane: frontend/shell-ody) (@after: ODY31, ODY32) [GATED: validation fondateur du mode Apps en prod]

**NE PAS FAIRE (Groupe ODY) — anti-duplication vérifiée (aucun doublon sur 6 fichiers de plan) :**
- Ne PAS re-bâtir : le launcher overlay (VX9 — devient le switch rapide), l'écran Applications
  (ODX5 — ODY24 l'habille), le registre de modules (ODX2/3/7 + ARC28 — ODY1 n'est qu'une VUE
  croisée dessus), le gating backend (ODX6/23, ARC29/33/40), les accents (VX8), le breadcrumb
  cockpit (VX11), la préférence d'atterrissage (VX46), le thème par société (SCA24).
- Ne PAS maintenir deux UX en parallèle : le flag ODY30 est un kill-switch temporaire (chemin OFF
  = smoke d'urgence, non testé unitairement) dont le retrait est queued (ODY33).
- Ne PAS toucher : PDF/`/proposal` (règle #4), STAGES.py (règle #2), `apps/web`, le contrat DOM
  e2e (`ap-*`/`att-*`/`pp-*`/`.header-title`) autrement qu'en déplaçant hooks + specs ensemble.
- Ne PAS créer : de sous-menus > 2 niveaux, de 2ᵉ Toaster, de 2ᵉ clé localStorage de favoris,
  de liste d'apps locale hors ODY1, de tuile « Frais »/« Portail » (frais = section Compta ;
  portail = route publique à jeton), ni confondre la boutique ODY24 avec la marketplace
  d'extensions NTEXT14.

### Groupe EZ — L'ERP le plus FACILE : les 5 trajets quotidiens au budget de clics, gardés en CI (fondateur 2026-08-01 — « the easiest to use for employees »)

*Provenance : challenge fondateur 2026-08-01 (« are you sure it's the prettiest AND the easiest
for employees? look at what the best do and what users prefer, go extremely deep »). Réponse
honnête : le BEAU est couvert (VX livré, ODY/APX en file) et la FACILITÉ l'est largement (axe
amour-employé VX83-116 + VX207-252 livré : Ma file, défauts intelligents, raccourcis, undo
ponctuels, brouillon devis, quick-create, HelpTip…) — mais un audit Opus des 5 TRAJETS QUOTIDIENS
comptés en clics dans le code réel + 4 recherches web (plaintes G2/Capterra des utilisateurs
d'ERP, patterns des outils aimés Linear/Superhuman/Attio, recherche saisie NN/g-Baymard-Fiori,
terrain Jobber/ServiceTitan/Scandit) ont trouvé des frictions qu'AUCUN plan n'adresse et 2
capacités absentes de TOUT plan (undo universel, dictée inline). EZ = uniquement ces manques,
puis VÉRIFIÉ par une critique adversariale Opus (10 corrections bloquantes appliquées — dont 3
tâches rétrécies parce que l'infra existait déjà, et 1 fausse prémisse tuée). Chiffres d'audit :
appel+note+rappel = 5-7 clics ; devis 3 kWc→WhatsApp = 8-9 clics dont un ABANDON post-création ;
clôture intervention = 40-45 taps dont 10 de pure paperasse de statut ; réception+rangement = 2
modules non reliés (le flux scan construit-testé-jamais-monté appartient à NTWMS5) ; encaissement
= 3 clics (excellent) mais sans suite offerte. Le commit d'insertion ajoute `EZ` à `unmapped_ok`
de `docs/BUILD_ORDER.yml`, pose la frontière EZ15↔NTMOB30 dans new_tasks_plan.md, et régénère
CODEMAP §10 + fingerprints.*

**LA DOCTRINE (issue des recherches).** (1) Agir puis pouvoir ANNULER bat confirmer puis agir
(NN/g) — l'undo devient la règle, la confirmation l'exception réservée à l'argent, aux envois et
au destructif. (2) Le système fait la paperasse, jamais l'employé — un horodatage connu ne se
re-saisit pas. (3) Après chaque action, l'action SUIVANTE évidente est offerte (créer → envoyer ;
recevoir → ranger ; encaisser → voir l'encaissement). (4) Le travail n'est JAMAIS perdu
(brouillons, photos, files visibles). (5) Chaque budget de clics est un TEST CI, pas une intention.

**Contraintes (chaque tâche EZ).** Celles de VX/ODY/APX s'appliquent intégralement (zéro dep npm,
règles #2/#4, hooks e2e + specs dans la même tâche, `noValidate`/`step="any"`, prix_achat, UN
Toaster, AA, reduced-motion, tactile ≥44 px). En plus : l'undo ne s'applique JAMAIS aux actions
d'argent, aux suppressions dures ni aux envois (AlertDialog reste) ; la garde serveur
`transition_block_reason` n'est JAMAIS dupliquée côté client (décision VX105) ; JAMAIS un 2ᵉ
outbox (décision VX105 ×3 — on ÉTEND `features/installations/offline/*`) ; aucun backend nouveau
sauf mention explicite. Propriété : EZ7 touche `apps/installations` (PLAN_SERVICE) et EZ10/EZ11
`pages/stock`+`features/magasin` (PLAN_SUPPLY) — conflits de CODE possibles si une session
domaine tourne en parallèle, aucune migration dans leurs apps (celle d'EZ7 va dans `parametres`).

**A — LE TRAJET DU COMMERCIAL (chemin rapide ≤4, chemin daté libre ≤6) :**

**B — LE TRAJET DU DEVIS (plus jamais d'abandon après 20 min de saisie) :**

**C — LE TRAJET DU TECHNICIEN (40-45 taps → ≤15 hors photos, zéro photo perdue) :**

**D — LE TRAJET DU MAGASINIER (deux modules enfin reliés — le montage du scan appartient à NTWMS5) :**

**E — LE TRAJET DU COMPTABLE (le meilleur parcours de l'app, terminé jusqu'au bout) :**

**F — LES DEUX ABSENTS SYSTÉMIQUES + LES GARDES :**

**NE PAS FAIRE (Groupe EZ) — la carte de couverture + la critique font foi :**
- Ne RIEN re-construire de LIVRÉ : Ma file (VX83), défauts intelligents (VX93), quick-create
  (VX91/NTUX10), brouillon devis (VX62 — EZ4 corrige son angle mort), HelpTip (VX47), erreurs
  françaises DevisList (VX63), densité globale + par vue (NTUX17), recherche globale (VX13),
  inline edit DataTable (NTUX8), surlignage `?devis=` (déjà livré — EZ3 le consomme), conversion
  kWc (déjà écrite — EZ5 la réutilise), API casier effectif (déjà prête — EZ11 la branche).
- Ne PAS monter le flux scan (NTWMS5) ; ne PAS bâtir le moteur offline générique (NTMOB1/2/3 —
  EZ8 étend l'outbox EXISTANT aux binaires, jamais une 2ᵉ pile ni un 2ᵉ badge, et ne touche pas
  `frontend/src/lib/offlineOutbox.js` réservé par NTMOB1) ; ne PAS dupliquer
  `transition_block_reason` côté client (VX105) ; ne PAS trancher le contrat d'erreur unique
  (VX203, gaté — EZ16 est une garde mécanique) ; la dictée TERRAIN appartient à NTMOB30.
- Avant TOUT travail SavedView futur : réconcilier NTUX1 `[ ]` avec `crm.SavedView` (LB48 livré)
  — incohérence relevée (NTUX2/3/4 `[x]` référencent NTUX1 `[ ]`).
- Le paste-grid Excel reste rejeté (VXD) ; l'undo EZ14 jamais sur l'argent/suppressions/envois ;
  pas d'heure sur les relances sans tâche SCHEMA dédiée (DateField partout aujourd'hui).

### Groupe CRX — Radiographie du CRM : correctness + sécurité, puis architecture gated (audit L3 du 02/09, 29 agents / 4 rondes, chaque constat vérifié adversarialement ; décisions fondateur D-CRX1-4 tranchées le 02/09)

**Provenance.** Audit L3 complet du module CRM (intake site/Meta, workspace, pipeline, relances, sync Odoo, clients, surfaces publiques, multi-tenant) — rapport : artifact « Radiographie du CRM » ; corpus fichier:ligne dans le scratchpad de la session `crm-l3-code-review-263325`. Toutes les tâches découlent de constats VÉRIFIÉS (2-3 lentilles sur les critiques) ; les constats réfutés n'ont pas de tâche.

**Décisions fondateur gravées (02/09/2026 — ne pas re-demander) :** D-CRX1 Meta = toujours créer (fin de l'absorption, même non-archivés) ; D-CRX2 webhook Meta fail-closed + secret en prod ; D-CRX3 sync Odoo→ERP = avance-seulement + rapport des régressions, stage inconnu intouché ; D-CRX4 deux sous-groupes — CRX1-42 buildables, CRXB1-8 architecture GATED sur le mot « lance CRXB ».

**Séquencement (encodé dans les tags) :** CRX12 (primitive core) avant CRX13 ; CRXB2 (scission models.py) et CRX26 (balayage timezone) = vagues exclusives sur apps/crm ; les fixes Odoo (CRX7-11) se coordonnent avec la session « scripts bidirectionnels » du 01/09 (mêmes fichiers — une seule session à la fois dessus) ; CRX18 touche ventes. **Réconciliation QJR4 (intégrée au merge du 02/09) :** CRX6 RETIRÉ (couvert par QJR415) ; le fail-closed Meta est QJR414 (CRX4 = résidu leadgen_id, @after) ; la primitive IP est QJR416 (CRX30 = couche infra nginx, @after) ; le mot de passe salle-vente hors URL est QJR420 (retiré de CRX31) ; QJR427 précède CRX41 (même script) — ne JAMAIS construire ces paires en parallèle.

**NE PAS FAIRE (vérifié pendant l'audit) :** ne PAS retirer la garde cache QW10 de `_map_and_link_lead` (PORTEUSE pour le chemin replay — un constat « code mort » a été réfuté là-dessus) ; ne PAS toucher au push Odoo sortant (dry-by-default, `--apply`, stage_id only — correct) ; ne PAS « adoucir » D-CRX1 en excluant seulement les archivés ; ne PAS traiter Math.random d'apps/web ici (→ WJ130 dans WEB_PLAN) ; ne PAS construire le moteur indus/comm/agricole (chantier D10 séparé, décision du 29/08).

- [ ] CRX42 — **[OPS — action fondateur] Vérification .env prod (30 min)** : la tâche écrit la CHECKLIST dans docs/ ; l'exécution est à Reda : `META_LEAD_ADS_APP_SECRET` posé (après CRX4), `WEBSITE_LEADS_COMPANY_ID` posé, `RETENTION_AUTO_APPLY` décidé, realip nginx déployé (après CRX30). Files: `docs/checklists/crm-prod-ops.md`. (DECISION) (@blocked: action fondateur prod) (@model: haiku)
- [ ] CRXB1 — **[GATED: mot fondateur « lance CRXB »] Contrat d'abord (PACT10)** — leads-list + workspace : `list()`/`retrieve()` refactorés en enveloppes RÉSOLUBLES par `check_api_shapes` (dict explicite), `contract_samples/lead_list.json` + `lead_workspace.json` ; le contrat atterrit SEUL sur main avant le reste du sous-groupe. Files: `backend/django_core/apps/crm/views.py`, `backend/django_core/apps/crm/contract_samples/`. (ARCH) (@blocked: sous-groupe architecture gated D-CRX4) (@model: opus)
- [ ] CRXB2 — **[GATED] Scission models.py [VAGUE EXCLUSIVE]** — `models_lead`/`models_client`/`models_partenaire`/`models_playbook` + contrat importlinter style installations ; conversion de l'allowlist `check_naive_datetime` en clés SYMBOLIQUES dans le même commit (le pin `models.py:2402` remappé 11× meurt) ; aucune autre lane en vol sur apps/crm. Files: `backend/django_core/apps/crm/models.py`, `backend/django_core/.importlinter`, `scripts/check_naive_datetime.py`. (ARCH) (@after: CRXB1) (@blocked: gated D-CRX4) (@model: opus)
- [ ] CRXB3 — **[GATED] Fin de `__all__`** — whitelist explicite LeadSerializer/ClientSerializer ; `stage`/`owner`/`priorite`/`canal`/`tags`/`motif_perte`/`relance_date` pilotés service. Files: `backend/django_core/apps/crm/serializers.py`. (ARCH) (@after: CRXB1) (@blocked: gated D-CRX4) (@model: opus)
- [ ] CRXB4 — **[GATED] UN round-robin** — fusion des 6 implémentations (562 morte, 597, 676, 1064, la copie webhooks `_owners_habilites`, et territoires PRIORITAIRE documenté — découvert en R3c) en un service unique paramétré. Files: `backend/django_core/apps/crm/services.py`, `backend/django_core/apps/crm/webhooks.py`. (ARCH) (@blocked: gated D-CRX4) (@model: opus)
- [ ] CRXB5 — **[GATED] Façade chatter partout** — les 47 `LeadActivity.objects.create` bruts (compte re-vérifié R3c) passent par `activity.py` ; l'invariant user=None des chemins système machine-checké. Files: `backend/django_core/apps/crm/services.py`, `backend/django_core/apps/crm/webhooks.py`, `backend/django_core/apps/crm/questionnaire.py`, `backend/django_core/apps/crm/odoo_sync.py`, `backend/django_core/apps/crm/receivers.py`, `backend/django_core/apps/crm/intake_photo.py`. (ARCH) (@blocked: gated D-CRX4) (@model: opus)
- [ ] CRXB6 — **[GATED] Frontière sortante contractée** — importlinter : crm.views/selectors ne montent plus `ventes.models` (via `ventes.selectors`, y c. `display_totals` au lieu de `quote_engine.builder`) ; `_rang_funnel` exposé proprement pour recouvrement ; les 2 shims compta déclarés (retrait = ODX22). (Édite aussi `crm/selectors.py` — vague gated, hors Files exprès pour ne pas prendre en otage les tâches frontend buildables via PACT11.) Files: `backend/django_core/.importlinter`, `backend/django_core/apps/crm/views.py`, `backend/django_core/apps/crm/public_views.py`, `backend/django_core/apps/ventes/domain/recouvrement.py`. (ARCH) (@blocked: gated D-CRX4) (@model: opus)
- [ ] CRXB7 — **[GATED] Registres LeadsPage/ListView + tests de rendu** — colonnes/tris/filtres/bulk extraits en registres à la `draftCore` ; les 63 tests regex-sur-source réécrits en comportementaux par lots. Files: `frontend/src/pages/crm/leads/LeadsPage.jsx`, `frontend/src/pages/crm/leads/views/ListView.jsx`. (ARCH) (@after: CRX19, CRX26, CRX28, CRX37, MRY5, MRY7, MRY19, MRY21) (@blocked: gated D-CRX4) (@model: opus)
- [ ] CRXB8 — **[GATED] LeadViewSet dégonflé** — les 28 `@action` regroupés en modules par thème (workspace/dedup/relances/export). Files: `backend/django_core/apps/crm/views.py`. (ARCH) (@after: CRXB3) (@blocked: gated D-CRX4) (@model: opus)

## Pending Reda (carry these in the plan)
- Hard constraints (do not violate): never touch the devis/facture PDF templates, the public PDF pages, the PdfCanvas content, or the apps/web marketing site; STAGES.py stays a fixed CI contract; all schema changes additive/nullable, seeded from current in-code defaults.

---

## DONE LOG (agent appends one plain-language line per completed task)
