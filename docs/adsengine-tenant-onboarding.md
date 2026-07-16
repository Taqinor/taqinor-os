# Runbook — Onboarding d'un client sur le moteur publicitaire (adsengine)

Ce runbook décrit comment brancher un NOUVEAU client (tenant) sur le moteur
publicitaire Meta Ads (`apps/adsengine`) **sans jamais mélanger les données entre
clients**. Il complète l'audit multi-tenant automatisé
(`apps/adsengine/tests/test_tenancy.py`, ENG30) : le code garantit le scoping,
ce runbook garantit la conformité côté Meta + l'accord écrit.

> Règle d'or : **une société ERP = un tenant = un ad account Meta séparé.**
> Aucune donnée (leads, dépense, créatifs, tokens) n'est jamais partagée entre
> deux clients. Le moteur est déjà scopé par `authentication.Company` (chaque
> modèle ENG hérite de `core.TenantModel`, FK `company` obligatoire) ; l'isolement
> côté Meta doit être posé manuellement en suivant les étapes ci-dessous.

## 1. Côté Meta — Business Portfolio & Partner access

1. Le client garde la **propriété** de son Business Portfolio (Meta Business
   Manager), de sa Page et de son ad account. On ne recrée jamais ses actifs
   dans notre propre portfolio.
2. Le client nous accorde un **accès Partenaire** (Partner access) sur SON ad
   account + SA Page, depuis *Paramètres du Business > Partenaires*. On demande
   le rôle minimal nécessaire (gestion des annonces), jamais la propriété.
3. On génère un **token System-User long-lived** côté NOTRE business, restreint à
   CET ad account partagé. Jamais un token de session navigateur (il expire vite
   et ne convient pas à un service serveur).
4. Le token est stocké **write-only** dans `MetaConnection.credentials`
   (`{"access_token": "…"}`) de la société correspondante — jamais relu par
   l'API (un GET n'expose que sa présence, cf. ENG2).

## 2. Côté ERP — un tenant, un ad account

- Créer / confirmer la `Company` du client dans l'ERP.
- Renseigner **une seule** `MetaConnection` pour cette société :
  `ad_account_id`, `page_id`, `pixel_id` propres au client, `enabled=True` une
  fois le token posé. Tant que `enabled` est faux ou que le token manque, le
  moteur no-ope proprement (aucun appel réseau).
- Poser les garde-fous du client (`GuardrailConfig`) et sa policy créative
  (`CreativePolicy`) via `python manage.py seed_adsengine` (idempotent — ne
  touche jamais une config existante) puis ajuster au besoin.
- **Ne jamais** réutiliser l'ad account, le pixel ou le token d'un autre client.
  Un `ad_account_id` ne doit apparaître que sur UNE seule `MetaConnection`.

## 3. Accord écrit — checklist avant la première campagne

Avant toute activité publicitaire pour un client, obtenir un **accord écrit**
couvrant :

- [ ] Mandat de gestion des annonces sur l'ad account du client (périmètre,
      durée, résiliation).
- [ ] Budget mensuel plafond + qui paie Meta (moyen de paiement sur l'ad account
      du client, jamais le nôtre).
- [ ] Propriété des actifs : la Page, l'ad account, le pixel et les audiences
      restent au client.
- [ ] Traitement des données personnelles (leads) conforme à la loi 09-08 / CNDP :
      finalité, conservation, jamais de partage entre clients.
- [ ] Politique créative validée (aucun faux chantier / client / témoignage ni
      chiffre non vérifié — check-list ENG16 confirmée règle par règle par un
      humain avant diffusion).
- [ ] Règle permanente respectée : **les campagnes naissent PAUSED** et le moteur
      **n'active jamais** une campagne automatiquement (invariant produit).

## 4. Ce que le code garantit déjà (rappel)

- Chaque modèle ENG porte une FK `company` (audit `test_tenancy.py`).
- Chaque ViewSet est scopé `request.user.company` (`CompanyScopedModelViewSet`) —
  `perform_create` force la société côté serveur, jamais depuis le corps de
  requête.
- Les lectures cross-app (leads CRM pour le coût-par-signature) passent par
  `apps/crm/selectors.py`, scopées société — jamais un import de modèles.
- Les secrets (token Meta, clés fabrique) ne fuient jamais : l'endpoint santé du
  câblage (ENG12) ne rapporte que leur PRÉSENCE.

## 5. Off-boarding

- Retirer l'accès Partenaire côté Meta (le client révoque, ou nous nous retirons).
- Passer `MetaConnection.enabled=False` et vider `credentials` (le moteur no-ope).
- Conserver l'historique (miroirs, actions, briefs) scopé à la société pour
  l'audit, ou le supprimer sur demande du client (droit à l'effacement).
