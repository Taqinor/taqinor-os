# Vérifie ACRM — contre-visite de clôture du groupe crm (D1), 24/10/2026

Commande `vérifie ACRM` (METHODE §C.4.2, skill audit §5), lancée par `loop audit` (2ᵉ itération du 24/10, après ASAV).
`audit_registre.py --du` liste ACRM en clôture (≥ 95 % : 64/66). C'est la deuxième contre-visite du groupe, après celle de
mi-parcours du 11/10 (`docs/audits/2026-10-11-crm-verifie.md`) : 15 tâches, 14 ok, 1 partielle (ACRM49, écart S3 déposé en
ACRM69, aujourd'hui coché et fermé).

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test rouge nommé et le code de `main` avec
les 7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Les écarts confirmés sont déposés en tâches v3 dans le
plan du propriétaire des fichiers. La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en
production.

## 0. Préconditions

- **SHA.** `origin/main` = `641a2266d` (re-fetch en début d'itération, inchangé depuis l'itération ASAV). Branche de claim :
  `verifie-acrm-cloture` (commit vide `7c278c5ad`, poussé).
- **Registre.** D1 `crm`, groupe ACRM, statut calculé `vérifié` avant ce dépôt (64/66, 96 %, mi-parcours sans écart S1-S2).
  Tâches réparties dans `PLAN_AUDIT_TRANSVERSE.md`, `PLAN_AUDIT_LEAD.md` et `PLAN_AUDIT_DEPLOY.md`.
- **Inventaire (déterministe).** 69 tâches ACRM, 64 `[x]`. Restent : ACRM55, ACRM57, ACRM62 `[BLOCKED: acceptation]`,
  ACRM60 (acceptation en direct du groupe), ACRM68.
- **Échantillon (graine = SHA `641a2266d9c6a9ce33fd2c0ca2eb7248c4e13326`).** Aucune P0/S1 cochée ; 25 % du reste tirées par
  `random.Random(int(sha, 16)).sample` (16 sur 64) : ACRM14, 15, 16, 18, 20, 23, 25, 40, 43, 47, 49, 53, 56, 61, 64, 65.

## 1. Vérificateurs (5 agents frais, opus, effort élevé, lecture seule, même répertoire, 2 à 4 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **8** | ACRM16, 18, 20, 23, 40, 43, 47, 49 |
| partiel | **8** | ACRM14 (S4), ACRM15 (S3), ACRM25 (S4), ACRM53 (S3), ACRM56 (S3), ACRM61 (S3 + S4), ACRM64 (S3), ACRM65 (S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

Points saillants des tâches ok : ACRM49 (la garde des routes crm passe, 172 routes, et mord : un mutant sans le mode strict
fait échouer son test ; le trou du 11/10 est fermé par ACRM69 et le retrait de `clients/segments`) ; ACRM16/18 (opposition
et plafond du réveil saisonnier filtrés AVANT la troncature, deux passages ne resélectionnent rien) ; ACRM47 (garde du
placement fermée : 503 et rien d'écrit si ventes est illisible).

## 2. Sondes

Aucune : aucun écart S1-S2. Le seul écart qui aurait pu en être un (ACRM56, audiences publicitaires sans filtre
d'opposition) a été vérifié par l'orchestrateur : les quatre fonctions `adsengine/audiences.py` qui consomment ces
sélecteurs n'ont aucun appelant de production (grep : définitions et docstrings seulement) et l'envoi reste soumis au
consentement `custom_audience_consent_enabled`. C'est donc une garde dormante (S3), pas une fuite active.

## 3. Écarts retenus

| Constat | Tâche | Écart de | Crit. | Grav. | Emplacement | Observé → attendu | Sonde |
|---|---|---|---|---|---|---|---|
| C-ACRM-VER-002 | ACRM70 | ACRM15 | C10 | S3 | `apps/crm/fiche_funnel.py::_corps_whatsapp_en_masse` | le gabarit traduit est cherché par nom et langue alors que `MessageTemplate` est unique par (société, nom) : la langue préférée n'est jamais rendue → unicité (société, nom, langue) | STATIQUE |
| C-ACRM-VER-003 | ACRM71 | ACRM53 | C5 | S3 | `apps/crm/tests_acrm_garde_pii.py::GardePiiTests` | 4 actions rejouées dans un état qui ne sert aucun numéro, sans exiger de 2xx : retirer un masque laisse la garde verte → fixtures qui servent le numéro, 2xx exigé | STATIQUE |
| C-ACRM-VER-004 | ACRM72 | ACRM56 | C8 | S3 | `apps/ventes/selectors_publicite.py::devis_view_tracking_segments` | trois sélecteurs d'audience (vues de devis, devis expirés, vente croisée) sans filtre d'opposition, garde dormante → opposé exclu (D-ACRM-5) | STATIQUE |
| C-ACRM-VER-005 | ACRM73 | ACRM61 | C10 | S3 | `frontend/src/pages/crm/PlacementAnciensLeadsCard.jsx` | badges écrits à la main : `rappel_manuel_a_venir` jamais affiché, aucun test ne lit la clé imbriquée, échantillon incohérent (277 ≠ 270 + 9) → rendu générique des `ignores`, test qui importe l'échantillon | STATIQUE |
| C-ACRM-VER-006 | ACRM74 | ACRM64 | C4 | S3 | `apps/crm/cadence_selectors.py::_conversion_par_stage` | le calcul des routes retirées survit (code mort ré-exporté par la façade) → supprimé | STATIQUE |
| C-ACRM-VER-007 | ACRM75 | ACRM65 | C4 | S3 | `apps/crm/clients_views.py::LeadClientsActionsMixin.salle_vente_analytics_view` | salles de vente parquées : la route d'analytique sert encore titre et nombre de vues, le badge du devis les affiche → réponse inerte quand le réglage est éteint | STATIQUE |

**Constats S1-S2 : 0.** Pas de critique Fable (réservée aux écarts S1). Les nouvelles tâches entrent dans le périmètre de
l'acceptation de groupe ACRM60, toujours ouverte.

Sans tâche (S4, optionnel) : ACRM14, la priorité « haute » et le délai lus sur le formulaire Meta sont écrits à la création
sans ligne ancien → nouveau au chatter ; ACRM25, un libellé en usage supprimé répond 409 `{detail}` au lieu du 400 du texte
de la tâche (l'écran lit `detail` : c'est le texte qui est périmé) ; ACRM61, la clause « seul sur main d'abord » n'a pas été
tenue (contrat entré dans la même PR que ses consommateurs, sans effet aujourd'hui).

## 4. Optionnel (non déposé)

- ACRM16/18 : le refus « déjà réveillé en saison » regarde le MOIS du dernier réveil J30/J60, pas l'année (antérieur à la
  tâche, reproduit à l'identique).
- ACRM47 : la commande `placer_anciens_leads` sort sur une trace de pile, pas sur un message en français.
- ACRM14 : depuis AMET19, le test de la tâche passerait même sans le saut sur marqueur (il ne discrimine plus la garde).
- ACRM15 : la clause client « wa.me = `message_pour_etape` » n'est pas testée (deux catalogues de gabarits distincts).
- ACRM56 : `records/serializers.py::get_target_phone` lit `lead_contact_identifiers` : les boutons appel/WhatsApp de « Mes
  activités » disparaissent pour un lead opposé (effet probablement voulu, non déclaré) ; CAPI n'exclut pas l'opposé (hors
  D-ACRM-5, ce n'est pas une audience).
- ACRM53 : la garde ne cherche que le numéro (conforme au texte), pas l'e-mail, l'adresse ni le GPS.
- ACRM64 : commentaires périmés citant encore `kpi_adherence` (crm, front).
- ACRM65 : aucun interrupteur `salles_vente_actif` dans Paramètres (réglage modifiable par l'API du profil seulement).
- ACRM25 : les étiquettes standard ajoutées plus tard ne sont plus posées chez une société existante (conforme au texte).

## 5. Couverture et non-couvert

- **Couvert.** 16 tâches sur 64 cochées (25 %), commits, tests nommés (lus ; `check_routes_appelees.py`, son test et
  `check_api_shapes.py` exécutés en lecture seule), code de `main`, décisions D-ACRM-5/6.
- **Non couvert.** Les 48 autres tâches cochées ; aucun aller-retour en direct (ACRM60 ouverte ; 4 des tâches échantillonnées
  figurent dans la dette gelée `docs/audits/acceptation/ACRM/_dette.yml`).
- **Statut du registre.** Après ce dépôt : 64 cochées sur 72 constructibles (89 %, ACRM70-75 ajoutées) ; contre-visite de
  clôture **sans écart S1-S2**. Le statut calculé redescend à `audité` tant que les 6 écarts S3 ne sont pas construits.

## 6. Coût

- 5 vérificateurs opus (effort élevé) : ≈ 0,83 M de jetons, 169 appels d'outil. 1 rédacteur opus : ≈ 0,28 M (6 tâches v3,
  clauses calculées par `audit_tache.py`, fronts et contrats au grep, goldens de scission repérés). Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 16 verdicts, contrôle des appelants de production des audiences
  publicitaires (ACRM56), routage par propriétaire (LEAD, ACQUISITION), rédaction.
- H0 S0 O6 F0 · jetons sous-agents ≈ 1,1 M

<!-- verifie | groupe: ACRM | pct: 96 | ecarts_s1_s2: 0 -->
