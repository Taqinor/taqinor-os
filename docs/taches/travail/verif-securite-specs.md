# Revue contradictoire sécurité et vie privée — specs 2 à 6b

Lecture seule ; chemins relatifs à `backend/django_core/` ; rien exécuté. Les points V2 déjà corrigés par le socle ne sont pas repris.

Bilan : **0 BLOQUANT, 6 MAJEUR, 15 MINEUR**.

## 1. Règles du socle §2 × specs

| Règle | 2 | 3 | 4 | 5a | 5b | 6a | 6b |
|---|---|---|---|---|---|---|---|
| 1 `taches_de` + ids | m15 | m4 | **M4** | m15 | ✓ | **M1**, m5 | m1 |
| 2 corbeille | ✓ | ✓ | m15 | — | ✓ | ✓ | — |
| 3 étiquettes / pas de chatter | ✓ | — | — | — | — | ✓ | — |
| 4 pas de recherche globale | ✓ | — | — | — | ✓ | ✓ | — |
| 5 jetons | m3 | — | — | — | — | — | m1, m2 |
| 6 donnée ≠ consigne, journal | ✓ | — | — | — | **M3**, m8, m9, m11 | — | — |
| 7 vérité, confidentiel | **M2** | **M2** | **M2** | **M2**, m14 | **M2** | **M6** | **M2** |
| 8 notifications sans titres | — | ✓ | — | ✓ | — | — | ✓, m10 |

## 2. MAJEUR

**M1 (6a §3.1, §5) — Un lien ERP lit le nom des clients hors portée.**
- Seul `crm.lead` est filtré par ligne (`apps/records/serializers.py:94-102`) ; pour toute autre cible, seul le droit du module est vérifié (`:105`).
- Or clients et devis sont filtrés par portée : `apps/crm/clients_views.py:692`, `apps/ventes/views/devis.py:233-239`.
- La réponse renvoie `libelle = str(obj)`. Pour un client, c'est « nom prénom » (`apps/crm/models_clients.py:1038`).
- Un commercial restreint qui énumère `{"cible":"crm.client","id":n}` lit donc tous les noms de clients.
- Correction (`taches`) : vérifier la visibilité par le sélecteur de l'app cible.
  - leads : `leads_visibles` ;
  - devis et factures : `apps/ventes/selectors_libelles.py:35-60`, déjà utilisé par l'assistant ;
  - clients : `scope_client_queryset` ;
  - cible sans sélecteur = non liable ;
  - test : refus avec le même message qu'un id inconnu.

**M2 (2, 3, 4, 5a, 5b, 6b) — « Confidentiel » ne masque pas tout.**
- (a) Rien n'est hérité. Le flux, la tuile, les push (6b §3-§6), les rappels (3 §3.9) et l'assistant (5b §1) ne testent que `tache.confidentiel`. Une tâche d'un projet confidentiel, ou la sous-tâche d'une tâche confidentielle, part en clair. Le socle §2.7 vise pourtant « tâche ou projet ».
- (b) Des phrases composées citent d'AUTRES objets :
  - « « C » (basse) a avancé de 1 » (4 §F) ;
  - « attend X » (4 §H) ;
  - « Tes tâches « Admin » » (5a C6) ;
  - « déjà dans X » et le projet suggéré à l'aperçu (2 §3.3) ;
  - `proposition{avant}` (5b §2) ;
  - `LignePlanJour.titre_fige` (`docs/taches/travail/design-s1-modele.md:97-98`).
- (c) `X-Taqinor-Assistant` sera posé dans une seule fonction. Il est absent des en-têtes actuels (`fastapi_ia/app/services/action_tools.py:173-178`) : un chemin oublié sert du clair.
- Correction :
  - `est_confidentielle()` = la tâche, son projet ou son parent ;
  - `nom_pour(obj, requete)` dans tout générateur de phrase ;
  - l'en-tête dans `internal_headers()` (`fastapi_ia/app/core/config.py:68-80`) ;
  - un test « canari » : un projet confidentiel au nom unique ; son nom ne doit apparaître dans aucun corps des routes de l'assistant, ni dans `flux/`, `tuile/` ou les push.

**M3 (5b §1) — Un texte piégé crée des tâches sans tap.**
- Le texte tiers arrive par les sorties d'outil :
  - libellés de leads venus de formulaires publics ;
  - notes CRM lues sous claude ;
  - pages capturées par la feuille de partage.
- La politique « non fiable » n'est qu'une consigne (`fastapi_ia/app/services/sql_agent_service.py:333-339`).
- Pire cas : 3 tâches par tour (« virer l'acompte au nouveau RIB… », priorité haute, aujourd'hui). Elles apparaissent dans Ma journée, l'agenda et la tuile comme les siennes.
- Plafond et Annuler bornent le volume, pas la tromperie.
- Correction :
  - dès que le relais a étiqueté un contenu non fiable dans le tour (`_etiqueter_non_fiable`, `sql_agent_service.py:557`), `tache.creer`, `projet.creer`, `preference.noter` et `rappel.poser` ne rendent plus qu'une carte-écho ;
  - les tâches de l'assistant portent `source='assistant'` et un badge visible.

**M4 (4 §5) — `decaler/annuler` applique des opérations fournies par le navigateur.**
- Le corps est `{"annulation":[{objet, id, champ, avant, apres}]}`, et aucune liste blanche ne borne `champ`.
- On peut donc écrire `proprietaire`, `projet_id`, `parent_id` (vers un objet d'un collègue, sans contrôle de FK) ou `company`.
- Correction : supprimer ce corps.
  - Le seul chemin est `annulations/{id}/appliquer/` (5b §4), qui lit l'état gardé côté serveur.
  - Champs admis : `jour_prevu`, `echeance`, `date_debut`, `date_fin`, `reports`.

**M5 (6a §3.2, §3.7) — L'effacement loi 09-08 garde des noms.**
- Le titre stocké de la suggestion contient `{client}`, et il « reste » après `lead_erased`. Ce texte vient de la machine, pas d'une frappe.
- Un client anonymisé n'émet aucun événement (6a §10).
- `titre_fige` garde aussi une copie.
- Correction :
  - titre « Appeler le client — devis {reference} accepté », le nom venant du lien à la lecture ;
  - un fournisseur DSR `taches` (`core/dsr.py:86`) qui réécrit `lien_libelle`, `SuggestionTache` et `titre_fige`.

**M6 (toutes) — Règle 7 : aucune spec n'écrit le texte de vérité.**
- Une recherche sur « fournisseur d'IA », « sauvegarde », « super-utilisateur » et « prise en main » ne trouve rien.
- Correction : les Réglages de 6a portent la liste §6 mot pour mot, figée par un test.

## 3. MINEUR

- **m1 (6b §1)**
  - `CookieJWTAuthentication` est la classe par défaut (`erp_agentique/settings/base.py:685-687`). Elle lit aussi `Bearer` (`authentication/cookie_auth.py:88-95`) et rejetterait `tqc_…`. Exiger `JetonAccesAuthentication` SEULE sur les 3 vues, et nulle part ailleurs (test).
  - À chaque usage, revérifier `taches_voir`, le compte interne et l'appartenance à `jeton.company`. La lecture aussi passe par `jeton.company`.
  - `jetons/<id>/revoquer/` d'un autre → 404.
- **m2 (6b)** La garde d'inventaire ne lit que `permission_classes` (`core/tests/test_endpoint_permission_inventory.py:39-63`). `docs/rbac-endpoint-inventory.md` doit être régénéré ; il manque à la liste des fichiers étrangers (sinon CI rouge).
- **m3 (2 ↔ 6b)** La capture de la spec 2 analyse la date (critère 9) ; celle de 6b « ni date ni analyse ». Un jeton volé programmerait Ma journée. Retenir 6b.
- **m4 (3 §5)** Les lignes `type:"activite"` de `journee/planifier/` ne sont pas vérifiées : `titre_fige` copierait l'activité d'un collègue. Passer par `activites_ouvertes_pour(user)`.
- **m5 (6a §5)** `convertir-activite` sans `assigned_to=user` (exigé en 2 §3.8) clôt l'à-faire d'un collègue.
- **m6 (6a §3.7)** Le destinataire d'une suggestion n'est pas confronté à l'objet : le responsable du lead apprend « chantier réceptionné » sans droit `installations`. Contrôle M1 avec `user=destinataire`, sinon rien.
- **m7 (6a §3.2)**
  - Le libellé reste affiché après `inaccessible`/`introuvable`.
  - `str(lead)` contient l'étape (`apps/crm/models.py:2027-2028`).
  - Vider le libellé hors `ok`, avec une fonction de libellé propre.
- **m8 (5a ↔ 5b)**
  - Les clés `Preference` divergent (`heure_limite` / `heure_limite_rappels`…).
  - Sous l'en-tête assistant, refuser `titres_notifications` et `comprendre_mon_rythme`.
  - `accepter_palier` sans tap contredit le socle §6.
- **m9 (5b + 3 §3.9)** Un rappel sonne à toute heure, même en congé (100 au plus par utilisateur) : une injection pose des sonneries nocturnes. Hors fenêtre, un rappel de l'assistant passe par une carte-écho.
- **m10 (6b §3)** Si l'e-mail ou WhatsApp est activé pour `TACHES_*`, `_audit_notify` écrit une ligne d'audit lisible des admins, avec l'utilisateur (`apps/notifications/services.py:851-879`). L'envoi conditionné au plan (5a §3.9) trahit son comportement, et le corps part chez Meta. Garder `TACHES_*` en push + in-app.
- **m11 (5b §8)** `AssistantEvent` garde l'heure, les noms d'outils (sans entrées, `fastapi_ia/app/services/sql_agent_service.py:1794`) et le coût, lisibles des admins. Un tour hors `/taches` sans outil n'est pas masqué.
- **m12 (5b §5)**
  - Les clés Redis n'ont pas de société (`fastapi_ia/app/services/moteur_natif.py:58`, `sql_agent_service.py:1455`) : la conversation suit d'une société à l'autre.
  - `action_tools.py:195` journalise le chemin avec `?q=`.
- **m13 (6a §5, socle §8)** L'export, « Tout effacer » et la purge à 30 jours ne listent pas leurs tables.
  - Tables : `Projet`, `Section`, `Tache`, `ElementChecklist`, `Etiquette`, `EtiquetteTache`, `RegleRecurrence`, `PlanJour`, `LignePlanJour`, `ReglagesRythme`, `Preference`, `IncitationCoach`, `JetonAcces`, `GesteAnnulable`, `VueEnregistree`, `Rappel`, `ModeleProjet`, `RevueProjet`, `Annulation`, `SuggestionTache`.
  - Copies hors de l'app : `Notification`, Redis, cache navigateur (« NON VÉRIFIÉ » en 6b §8).
  - `LignePlanJour.tache` est en SET_NULL : le titre purgé survit.
  - Deux mécanismes d'annulation coexistent : `GesteAnnulable` à 7 jours (2 §4), `Annulation` à 30 jours (5b §4). En garder un.
  - La tâche de purge n'est spécifiée nulle part. Rien ne dit que `calculer_rythme` et le balayage des rappels (chaque minute) parcourent `active_companies()`.
- **m14 (5a §3.8)** L'interrupteur ne coupe que les constats. Restent calculés : la capacité « habituelle » (3 §3.4), F28 (4 §E), la journée type. Les champs dérivés stockés (`tenir_reference`, `ref_taille_min`) ne sont pas effacés.
- **m15 (2, 4, 5a)**
  - Le balayage doit nommer : `section_id`, `parent_id`, `etiquettes`, `recurrences/<id>`, `propositions/<id>/repondre/`, `revue/projets/{id}`, `modeles/{id}/instancier/`.
  - La suppression de projet (4 §3.I) se fait en `record=False`.
  - `__str__` neutre partout : `_audit_notify` écrit `str(instance)` (`apps/notifications/services.py:877`).

## 4. Vérifié sans constat

- Les abonnés sont isolés en point de sauvegarde, erreurs avalées (`core/events/__init__.py:166-188`). Une panne de `taches` ne fait pas échouer l'acceptation d'un devis. `lead_erased` part après commit (`apps/crm/dsr_provider.py:357-364`).
- ICS : `_ics_escape` neutralise `\n`, `\r`, `;`, `,`, `\` (`apps/reporting/calendar.py:505-509`) sur SUMMARY (`:566`). Un titre ne forge pas d'événement.
- Jetons : 256 bits, recherche par empreinte (`apps/publicapi/auth.py:89-90`).
- Les notifications in-app sont réservées à leur destinataire (`apps/notifications/views.py:166`).
- KPI fédérés : un fournisseur reçoit `company` seule (`apps/reporting/reports.py:550-555`) ; la pastille n'y passe pas.
- Le script Scriptable n'a aucun secret ; le jeton va dans le Keychain.

## 5. OPTIONNEL

- DRF limite le débit après l'authentification (de mémoire) : un jeton refusé n'est pas compté. Ajouter un `limit_req` nginx.
- Masquer le jeton du flux dans les journaux nginx ; Caddy non vérifié.
- Un mot-clé `Jeton` plutôt que `Bearer`.
- Une taille de corps propre à `capture/` (15 Mo aujourd'hui, `base.py:665`).
- `ignore_result` sur les tâches Celery (résultats dans Redis, `base.py:1186`).
- Aucun `kpi_providers` dans `taches/platform.py`, aucun admin Django.
- Le cache de la tuile, avec les titres, est sauvegardé avec le téléphone (de mémoire).

## 6. À dire franchement au fondateur

1. Qui a le serveur, la base ou les sauvegardes lit tout : les sessions Claude sous l'accord de lecture de la prod, `export_tenant`, le support qui agit en votre nom, un super-utilisateur sans société. « Confidentiel » masque, il ne chiffre pas.
2. Le fournisseur d'IA (Groq ou Anthropic) reçoit à chaque tour du coach :
   - vos titres, vos projets, votre profil et `note_libre` ;
   - les libellés ERP liés, donc des noms de clients.
   C'est un transfert hors du Maroc (CNDP : de mémoire, non vérifié).
3. Les administrateurs voient l'heure, les outils et le coût de chaque tour du coach, jamais le texte. Le commentaire d'un 👎 reste lisible.
4. L'URL du calendrier vaut une clé. Elle se retrouve dans :
   - les journaux nginx ;
   - l'historique de Safari ;
   - iCloud, si vous vous abonnez par iCloud.
   Les titres y sont visibles par défaut, comme dans la tuile.
5. Le raccourci Siri contient le jeton de capture et peut passer par iCloud : qui l'a peut AJOUTER des tâches, pas les lire.
6. Scriptable, app tierce, détient le jeton de la tuile et une copie des titres du jour.
7. Apple ne voit que des push chiffrés. L'écran verrouillé affiche des comptes ; les titres, seulement si vous l'activez.
8. « Tout effacer » ne touche ni les journaux, ni les sauvegardes, ni le téléphone.
9. Une notification de tâche envoyée par e-mail ou WhatsApp, si vous l'activez, laisse une trace d'audit visible des administrateurs.
10. Changer de société change d'espace de tâches, mais la conversation avec l'assistant vous suit d'une société à l'autre.

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.
