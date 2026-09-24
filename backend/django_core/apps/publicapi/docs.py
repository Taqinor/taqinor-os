"""FG105 — Référence STATIQUE de l'API publique (N89), en français.

Une page de référence servie par l'API elle-même (endpoint JSON), sans aucune
dépendance d'auto-génération (pas de drf-spectacular / Swagger). La structure
décrit : l'authentification par clé (`Authorization: Api-Key …`), les scopes,
les endpoints de données en lecture seule avec leurs filtres/tri/synchro
(FG104), les évènements webhook et la recette de vérification de la signature
HMAC `X-Taqinor-Signature`.

La source de vérité des scopes/évènements reste `constants.py` : on lit
`SCOPE_CHOICES`/`EVENT_CHOICES` pour ne jamais diverger de l'implémentation.
"""
from .constants import (
    SCOPE_CHOICES, EVENT_CHOICES, EVENT_CALEPINAGE_SIMULE,
    SCOPE_READ_FIABILITE,
)
from .auth import AUTH_KEYWORD
from .delivery import (
    SIGNATURE_HEADER, SIGNATURE_HEADER_V2, EVENT_HEADER, TIMESTAMP_HEADER,
    IDEMPOTENCY_HEADER, DEFAULT_SIGNATURE_TOLERANCE_SECONDS,
)

# Recette de vérification de la signature HMAC, identique à `delivery.sign_payload`
# (YAPIC8 : HMAC-SHA256 de `f"{timestamp}.".encode() + body`, où body est le
# corps HTTP brut reçu et timestamp l'en-tête X-Taqinor-Timestamp). Rejeter un
# horodatage hors tolérance protège du rejeu.
_HMAC_RECIPE_PYTHON = (
    "import hmac, hashlib, time\n"
    "# `secret` = secret du webhook (affiché une seule fois à la création).\n"
    "# `body` = corps HTTP brut reçu (bytes), tel quel.\n"
    f"timestamp = request.headers['{TIMESTAMP_HEADER}']\n"
    "# Rejette un horodatage hors tolérance (anti-rejeu), ex. 5 minutes :\n"
    "assert abs(time.time() - int(timestamp)) <= 300\n"
    "signe = f'{timestamp}.'.encode('utf-8') + body\n"
    "expected = hmac.new(secret.encode('utf-8'), signe, hashlib.sha256).hexdigest()\n"
    f"recu = request.headers['{SIGNATURE_HEADER}']\n"
    "valide = hmac.compare_digest(expected, recu)\n"
    "# `event_id` (dans le corps JSON) est stable : dédupliquez dessus."
)

# NTAPI9 — recette V2 (auto-suffisante, façon Stripe) : horodatage + signature
# dans le SEUL en-tête `X-Taqinor-Signature-V2`. Le calcul du HMAC est
# IDENTIQUE à la recette legacy ci-dessus — seul le transport (un en-tête au
# lieu de deux) change.
_HMAC_RECIPE_V2_PYTHON = (
    "import hmac, hashlib, time\n"
    "# `secret` = secret du webhook (affiché une seule fois à la création).\n"
    "# `body` = corps HTTP brut reçu (bytes), tel quel.\n"
    f"entete = request.headers['{SIGNATURE_HEADER_V2}']  # 't=<epoch>,v1=<hex>'\n"
    "parts = dict(p.split('=', 1) for p in entete.split(','))\n"
    "timestamp, recu = parts['t'], parts['v1']\n"
    "# Rejette un horodatage hors tolérance (anti-rejeu) :\n"
    f"assert abs(time.time() - int(timestamp)) <= {DEFAULT_SIGNATURE_TOLERANCE_SECONDS}\n"
    "signe = f'{timestamp}.'.encode('utf-8') + body\n"
    "expected = hmac.new(secret.encode('utf-8'), signe, hashlib.sha256).hexdigest()\n"
    "valide = hmac.compare_digest(expected, recu)\n"
    "# `event_id` (dans le corps JSON) est stable : dédupliquez dessus."
)


#: CALX369 — les champs de ``GET calepinages/<id>/resultat/``, un par un, dans
#: l'ordre de ``PublicCalepinageResultatSerializer`` (un test vérifie que les
#: deux listes ne divergent jamais). ``openapi.py`` les projette en propriétés
#: déclarées : la forme publiée n'est jamais « un objet ».
CHAMPS_RESULTAT_CALEPINAGE = [
    {'nom': 'calepinage_id', 'type': 'integer', 'nullable': False,
     'description': "Identifiant du calepinage."},
    {'nom': 'simule', 'type': 'boolean', 'nullable': False,
     'description': (
         "Vrai seulement si une production simulée est servie ET décrit "
         "encore la conception d'aujourd'hui.")},
    {'nom': 'production_annuelle_kwh', 'type': 'number', 'nullable': True,
     'description': (
         "Énergie annuelle simulée (année médiane) — même grandeur que "
         "`p50_kwh`.")},
    {'nom': 'rendement_specifique_kwh_kwc', 'type': 'number',
     'nullable': True,
     'description': "kWh produits par kWc installé et par an."},
    {'nom': 'ratio_performance', 'type': 'number', 'nullable': True,
     'description': "Ratio de performance (PR), en fraction (0,80 = 80 %)."},
    {'nom': 'p50_kwh', 'type': 'number', 'nullable': True,
     'description': "Production annuelle P50."},
    {'nom': 'p75_kwh', 'type': 'number', 'nullable': True,
     'description': "Production annuelle P75."},
    {'nom': 'p90_kwh', 'type': 'number', 'nullable': True,
     'description': "Production annuelle P90."},
    {'nom': 'pertes', 'type': 'array', 'nullable': True,
     'description': (
         "Chaîne de pertes appliquée : `{code, libelle, pourcentage, "
         "source, gain, motif}` par poste ; `pourcentage` null pour une "
         "étape omise (son `motif` dit pourquoi). Null si non simulé.")},
    {'nom': 'calcule_le', 'type': 'string', 'nullable': True,
     'description': "Horodatage (UTC) enregistré par la simulation servie."},
    {'nom': 'simulation_perimee', 'type': 'boolean', 'nullable': False,
     'description': (
         "Vrai quand une simulation existe mais que la conception a changé "
         "depuis : ses grandeurs ne sont alors pas publiées.")},
    {'nom': 'motif', 'type': 'string', 'nullable': False,
     'description': "Pourquoi rien n'est publié (vide quand `simule`)."},
]

#: CALX368 — la charge utile de ``calepinage.simule``, clé par clé, dans
#: l'ordre de ``calepinage_event_receivers.CLES_CHARGE_SIMULE`` (garde de
#: test). Plus ``event_id``, posé par la livraison sur tout évènement.
CHARGE_CALEPINAGE_SIMULE = [
    {'nom': 'id', 'type': 'integer', 'nullable': False,
     'description': "Identifiant du calepinage."},
    {'nom': 'titre', 'type': 'string', 'nullable': False,
     'description': "Titre du calepinage."},
    {'nom': 'statut', 'type': 'string', 'nullable': False,
     'description': "Statut du calepinage (inchangé par la simulation)."},
    {'nom': 'lead_id', 'type': 'integer', 'nullable': True,
     'description': "Lead rattaché."},
    {'nom': 'client_id', 'type': 'integer', 'nullable': True,
     'description': "Client rattaché."},
    {'nom': 'devis_id', 'type': 'integer', 'nullable': True,
     'description': "Devis rattaché."},
    {'nom': 'appel_offre_id', 'type': 'integer', 'nullable': True,
     'description': "Affaire rattachée."},
    {'nom': 'layout_hash', 'type': 'string', 'nullable': False,
     'description': "Empreinte de la conception simulée."},
    {'nom': 'version_moteur', 'type': 'string', 'nullable': False,
     'description': "Version du moteur de calepinage."},
    {'nom': 'kwc', 'type': 'number', 'nullable': True,
     'description': "Puissance crête réellement calculée."},
    {'nom': 'modules', 'type': 'integer', 'nullable': True,
     'description': "Nombre de modules réellement calculé."},
    {'nom': 'p50_kwh', 'type': 'number', 'nullable': True,
     'description': "Production annuelle P50 simulée."},
    {'nom': 'performance_ratio', 'type': 'number', 'nullable': True,
     'description': "Ratio de performance simulé, en fraction."},
]


def public_api_reference():
    """Construit la référence FR de l'API publique (dict sérialisable en JSON)."""
    return {
        'titre': "API publique Taqinor — Référence",
        'version': '1',
        'base_url': '/api/public/v1/',
        'introduction': (
            "API REST authentifiée par clé d'API et scopée à votre société. "
            "Principalement en lecture seule ; un sous-ensemble d'écriture "
            "existe (voir « endpoints_ecriture », scopes dédiés `*:write`). "
            "Aucun prix d'achat ni donnée de rentabilité interne n'est jamais renvoyé."
        ),
        'authentification': {
            'methode': "Clé d'API dans l'en-tête HTTP Authorization.",
            'entete': f"Authorization: {AUTH_KEYWORD} <votre_cle>",
            'obtention': (
                "Créez une clé dans Paramètres → API & Webhooks. La clé "
                "complète n'est affichée qu'une seule fois, à la création."
            ),
            'note_scope': (
                "Chaque clé est limitée aux scopes cochés ; appeler un endpoint "
                "hors scope renvoie 403."
            ),
            'note_societe': (
                "La société est déduite de la clé : il n'existe aucun moyen de "
                "lire les données d'une autre société."
            ),
            # NTAPI19 — second schéma accepté, en PLUS de la clé d'API (jamais
            # à sa place : aucune intégration existante n'est touchée).
            'oauth2': (
                "Alternative recommandée pour une intégration d'entreprise : "
                "`POST /api/public/v1/oauth/token/` (grant "
                "`client_credentials`) échange, une fois, `client_id` + "
                "`client_secret` contre un jeton COURT, présenté ensuite en "
                "`Authorization: Bearer <jeton>`. Un secret permanent ne "
                "circule donc plus à chaque appel. Les scopes du jeton sont "
                "ceux du client (ou le sous-ensemble demandé via `scope`) ; "
                "retirer un scope au client prend effet IMMÉDIATEMENT, sans "
                "attendre l'expiration des jetons déjà émis."
            ),
        },
        'scopes': [
            {'code': code, 'libelle': libelle}
            for code, libelle in SCOPE_CHOICES
        ],
        'parametres_communs': {
            'pagination': "?page=<n>&page_size=<n> (pagination DRF standard).",
            'tri': (
                "?ordering=<champ> ou ?ordering=-<champ> (décroissant). Seuls "
                "les champs listés par endpoint sont autorisés ; un champ non "
                "autorisé est ignoré."
            ),
            'filtres': (
                "Filtre par égalité sur les champs en liste blanche (ex. "
                "?statut=payee). Un paramètre inconnu renvoie 400."
            ),
            'synchro_incrementale': (
                "?updated_since=<ISO-8601> (ex. 2026-06-30 ou "
                "2026-06-30T12:00:00Z) ne renvoie que les enregistrements "
                "modifiés depuis cet horodatage — idéal pour un polling "
                "incrémental sans re-scanner toute la liste."
            ),
        },
        'endpoints': [
            {
                'chemin': '/api/public/v1/leads/',
                'scope': 'read:leads',
                'description': "Leads CRM (pipeline commercial).",
                'filtres': [
                    'stage', 'canal', 'priorite', 'perdu', 'source',
                    'type_installation', 'ville',
                ],
                'tri': ['date_creation', 'date_modification', 'id'],
                'updated_since': 'date_modification',
            },
            {
                'chemin': '/api/public/v1/devis/',
                'scope': 'read:devis',
                'description': "Devis (avec lignes, prix de vente uniquement).",
                'filtres': ['statut', 'mode_installation', 'client', 'lead'],
                'tri': ['date_creation', 'id'],
                'updated_since': 'date_creation',
            },
            {
                'chemin': '/api/public/v1/factures/',
                'scope': 'read:factures',
                'description': "Factures (avec lignes).",
                'filtres': ['statut', 'type_facture', 'client', 'devis'],
                'tri': ['date_emission', 'id'],
                'updated_since': 'date_emission',
            },
            {
                'chemin': '/api/public/v1/chantiers/',
                'scope': 'read:chantiers',
                'description': "Chantiers / installations.",
                'filtres': [
                    'statut', 'raccordement', 'type_installation', 'client',
                    'devis', 'lead',
                ],
                'tri': ['date_creation', 'date_modification', 'id'],
                'updated_since': 'date_modification',
            },
            {
                'chemin': '/api/public/v1/produits/',
                'scope': 'read:stock',
                'description': (
                    "Disponibilité produit (SKU/nom/marque/catégorie/quantité "
                    "disponible). Jamais de prix d'achat ni de coût."
                ),
                'filtres': ['sku', 'marque', 'categorie'],
                'tri': ['id', 'nom'],
                'updated_since': None,
            },
            {
                'chemin': '/api/public/v1/calepinages/',
                'scope': 'read:calepinages',
                'description': (
                    "CAL214 — calepinages (conceptions de toiture) : identité, "
                    "rattachement lead/client/devis, statut, empreinte du "
                    "layout, puissance (kWc) et nombre de modules RÉELLEMENT "
                    "calculés, liens de sorties. Jamais la géométrie brute "
                    "(`roof_layout`, plans/rangées du moteur), jamais un coût "
                    "interne."
                ),
                'filtres': ['statut', 'lead_id', 'client_id', 'devis_id'],
                'tri': ['created_at', 'updated_at', 'id'],
                'updated_since': 'updated_at',
            },
            {
                'chemin': '/api/public/v1/saved-views/',
                'scope': 'read:vues',
                'description': (
                    "NTUX33 — vues sauvegardées (NTUX1). Sans ?owner=, "
                    "uniquement les vues déjà partagées à l'équipe ; avec "
                    "?owner=<id>, les vues de CET utilisateur (personnelles "
                    "incluses — le paramètre est le proxy de son consentement)."
                ),
                'filtres': ['ecran', 'owner'],
                'tri': ['id', 'ecran', 'nom'],
                'updated_since': 'updated_at',
            },
            {
                'chemin': '/api/public/v1/favoris/',
                'scope': 'read:favoris',
                'description': (
                    "NTUX33 — favoris épinglés (NTUX12), STRICTEMENT "
                    "personnels : ?owner=<id> est OBLIGATOIRE (400 sans lui), "
                    "c'est le consentement explicite de l'utilisateur."
                ),
                'filtres': ['owner'],
                'tri': ['id', 'ordre'],
                'updated_since': 'updated_at',
            },
            {
                'chemin': '/api/public/v1/achats/demandes-achat/',
                'scope': 'lecture_achats',
                'description': (
                    "NTP2P39 — demandes d'achat (réquisitions, FG310) : "
                    "référence, objet, statut, priorité, date de besoin, "
                    "chantier/programme et montant ESTIMÉ (ordre de grandeur "
                    "d'engagement). Les LIGNES ne sont pas exposées : leur "
                    "prix unitaire estimé est un prix d'achat interne."
                ),
                'filtres': [
                    'statut', 'priorite', 'chantier', 'programme', 'reference',
                ],
                'tri': ['date_creation', 'date_modification', 'id'],
                'updated_since': 'date_modification',
            },
            {
                'chemin': '/api/public/v1/achats/rfq/',
                'scope': 'lecture_achats',
                'description': (
                    "NTP2P39 — demandes de prix (RFQ, FG311) : référence, "
                    "objet, statut, date limite, fournisseurs CONSULTÉS (avec "
                    "« a répondu ») et offre RETENUE par son identité "
                    "(fournisseur + délai). Jamais le montant d'une offre "
                    "(prix d'achat interne), jamais le jeton de consultation "
                    "(il ouvre la page de réponse sans login)."
                ),
                'filtres': ['statut', 'demande', 'reference'],
                'tri': ['date_creation', 'date_modification', 'id'],
                'updated_since': 'date_modification',
            },
        ],
        # CALX369 — sous-ressources en LECTURE d'une ressource ci-dessus,
        # sous le MÊME scope (aucune nouvelle famille d'URL).
        'sous_ressources': {
            'description': (
                "Sous-ressources en lecture seule d'un objet déjà publié, "
                "servies sous le scope de lecture de leur ressource."
            ),
            'liste': [
                {
                    'chemin': '/api/public/v1/calepinages/<id>/resultat/',
                    'methode': 'GET',
                    'scope': 'read:calepinages',
                    'description': (
                        "CALX369 — résultat de SIMULATION d'un calepinage : "
                        "production annuelle, rendement spécifique, ratio de "
                        "performance, P50/P75/P90, postes de pertes (libellé, "
                        "pourcentage, source) et horodatage du calcul. Non "
                        "simulé ou simulation périmée (la conception a changé "
                        "depuis) ⇒ grandeurs à null, jamais 0, et `motif` dit "
                        "pourquoi. Le scope `read:calepinages` ne permet NI "
                        "d'écrire NI de lancer une simulation : le calcul "
                        "reste déclenché depuis l'atelier. La série horaire "
                        "n'est pas publiée ici (volume : 8 760 points par "
                        "année simulée). Jamais la géométrie, jamais un coût."
                    ),
                    'champs': CHAMPS_RESULTAT_CALEPINAGE,
                },
            ],
        },
        'endpoints_ecriture': {
            'description': (
                "XPLT5 — endpoints d'ÉCRITURE (scopes dédiés `leads:write` / "
                "`activities:write`). Société forcée depuis la clé, jamais "
                "du corps. En-tête optionnel `Idempotency-Key` : un rejeu "
                "identique (même clé, même corps) renvoie la réponse "
                "mémorisée sans recréer l'objet ; un corps différent → 409."
            ),
            'entete_idempotence': 'Idempotency-Key',
            'liste': [
                {
                    'chemin': '/api/public/v1/leads-write/',
                    'methode': 'POST',
                    'scope': 'leads:write',
                    'description': "Crée un lead.",
                },
                {
                    'chemin': '/api/public/v1/leads-write/<id>/',
                    'methode': 'PATCH',
                    'scope': 'leads:write',
                    'description': "Met à jour un lead existant.",
                },
                {
                    'chemin': '/api/public/v1/leads-write/<id>/activites/',
                    'methode': 'POST',
                    'scope': 'activities:write',
                    'description': "Ajoute une note (chatter) sur un lead.",
                },
                {
                    'chemin': '/api/public/v1/devis-write/',
                    'methode': 'POST',
                    'scope': 'devis:write',
                    'description': (
                        "NTAPI18 — crée un devis BROUILLON rattaché à un lead "
                        "existant (corps : `lead`, plus `numero`/`montant_ht`/"
                        "`montant_tva`/`montant_ttc`/`date` en aide à la "
                        "saisie). Le client est résolu côté serveur depuis le "
                        "lead, sans doublon. Aucune ligne n'est créée et aucun "
                        "statut aval n'est touché : le devis reste `brouillon` "
                        "et le PDF client reste servi par `/proposal`."
                    ),
                },
                {
                    'chemin': '/api/public/v1/tickets-write/',
                    'methode': 'POST',
                    'scope': 'tickets:write',
                    'description': (
                        "NTAPI18 — ouvre un ticket SAV correctif (corps : "
                        "`client`, `description`, `installation` optionnelle). "
                        "Toutes les entités liées sont bornées à la société de "
                        "la clé."
                    ),
                },
            ],
        },
        'endpoints_bulk': {
            'description': (
                "NTAPI14/15/16/43 — jobs BULK (export/import) traités HORS "
                "requête : la réponse est 202 immédiate (jamais de time-out "
                "HTTP même sur un très gros volume), suivie via `jobs/`. Le "
                "scope requis dépend de l'entité demandée (même scope que la "
                "lecture/écriture synchrone de cette ressource)."
            ),
            'liste': [
                {
                    'chemin': '/api/public/v1/exports/',
                    'methode': 'POST',
                    'description': (
                        "Lance un export bulk asynchrone (leads/devis/"
                        "factures/chantiers/produits, CSV ou JSONL). Corps : "
                        "entite, format, filtres (mêmes filtres que la "
                        "ressource lue en synchrone)."
                    ),
                    'success_status': '202',
                    'request_body': True,
                },
                {
                    'chemin': '/api/public/v1/imports/',
                    'methode': 'POST',
                    'description': (
                        "Lance un import bulk asynchrone (leads/activités) "
                        "depuis un fichier CSV/JSONL (multipart, champ "
                        "`file`). Corps : entite, mode (create/upsert), "
                        "dedup_key (email/telephone) si upsert."
                    ),
                    'success_status': '202',
                    'request_body': True,
                },
                {
                    'chemin': '/api/public/v1/jobs/',
                    'methode': 'GET',
                    'description': "Liste paginée des jobs bulk de la société.",
                    'success_status': '200',
                    'request_body': False,
                },
                {
                    'chemin': '/api/public/v1/jobs/<id>/',
                    'methode': 'GET',
                    'description': (
                        "Suivi d'un job bulk : statut, progression %, "
                        "compteurs, liens résultat/erreurs (présignés, "
                        "courte durée)."
                    ),
                    'success_status': '200',
                    'request_body': False,
                },
                {
                    'chemin': '/api/public/v1/jobs/<id>/relancer/',
                    'methode': 'POST',
                    'description': (
                        "Reprend un job en échec depuis son curseur "
                        "persistant — jamais de doublon, jamais de saut."
                    ),
                    'success_status': '200',
                    'request_body': False,
                },
                {
                    'chemin': '/api/public/v1/exports/<entite>.csv',
                    'methode': 'GET',
                    'description': (
                        "NTAPI30 — pull CSV live SYNCHRONE (leads/devis/"
                        "factures/chantiers/produits), exploitable par "
                        "=IMPORTDATA() de Google Sheets/Excel Web. "
                        "Authentification par ?token=<clé> (query string — "
                        "aucun en-tête possible côté tableur), scope "
                        "lecture seule strict."
                    ),
                    'success_status': '200',
                    'request_body': False,
                    'query_token_auth': True,
                    'response_csv': True,
                },
                {
                    'chemin': '/api/public/v1/events/',
                    'methode': 'GET',
                    'description': (
                        "NTAPI17 — flux d'évènements consommable par CURSEUR "
                        "(`?after=<sequence>&limit=<n>`), alimenté par les "
                        "mêmes signaux que les webhooks. NTAPI32 — "
                        "`?type=facture.paid` (plusieurs codes séparés par une "
                        "virgule) restreint le flux à ces évènements, pour un "
                        "trigger no-code abonné à UN évènement ; un code inconnu "
                        "du vocabulaire renvoie 400, un code non couvert par les "
                        "scopes de la clé reste simplement absent. "
                        "Pendant PULL du push : "
                        "pour une intégration qui ne peut pas exposer d'URL "
                        "publique, et comme filet de rattrapage. Scope "
                        "`read:events` pour ouvrir le canal ; chaque évènement "
                        "reste filtré par le scope de lecture de SA famille "
                        "(`lead.*` → `read:leads`, `facture.*` → "
                        "`read:factures`…) — le flux n'est jamais un "
                        "contournement des scopes de lecture."
                    ),
                    'success_status': '200',
                    'request_body': False,
                },
                {
                    'chemin': '/api/public/v1/oauth/token/',
                    'methode': 'POST',
                    'description': (
                        "NTAPI19 — échange `client_id`/`client_secret` contre "
                        "un jeton COURT (grant `client_credentials`). Corps : "
                        "`grant_type=client_credentials`, `client_id`, "
                        "`client_secret`, `scope` optionnel (sous-ensemble). "
                        "Le jeton s'utilise ensuite en "
                        "`Authorization: Bearer <jeton>` sur TOUS les "
                        "endpoints publics, en alternative à "
                        "`Authorization: Api-Key <clé>`. Identifiants "
                        "invalides → 401, message identique quel que soit le "
                        "motif."
                    ),
                    'success_status': '200',
                    'request_body': True,
                },
            ],
        },
        'endpoints_lecture_simple': {
            'description': (
                "NTADM42 — endpoints de lecture simple : un OBJET UNIQUE "
                "(jamais une liste paginée), scopé société. Pas de "
                "pagination/tri/filtre."
            ),
            'liste': [
                {
                    'chemin': '/api/public/v1/licence/statut/',
                    'scope': 'read:licence',
                    'description': (
                        "Statut de licence de la société (plan_code, "
                        "modules_inclus, sieges_max, sieges_utilises). "
                        "Aucun champ interne (prix, historique)."
                    ),
                },
                # NTOBS27 — gouvernance fournisseur : les trois ressources
                # Fiabilité, chacune scopée à la société de la clé.
                {
                    'chemin': '/api/public/v1/fiabilite/sauvegardes/',
                    'scope': SCOPE_READ_FIABILITE,
                    'description': (
                        "Dernière sauvegarde et dernier drill de restauration "
                        "(NTOBS5) — ``{derniere_sauvegarde, dernier_drill, "
                        "rpo_planifie, rto_annonce_heures}``, chaque champ "
                        "``null`` quand la donnée n'existe pas encore. Les "
                        "runs système-wide ne rendent que date + statut : "
                        "jamais l'artefact, la clé d'objet de stockage, la "
                        "taille ou le manifeste interne."
                    ),
                },
                {
                    'chemin': '/api/public/v1/fiabilite/sla/{periode}/',
                    'scope': SCOPE_READ_FIABILITE,
                    'description': (
                        "Rapport SLA mensuel (NTOBS3) de la période "
                        "``{periode}`` au format ``YYYY-MM`` — disponibilité, "
                        "latence P95, crédit dû et son statut. Format de "
                        "période invalide → 400 ; aucun rapport pour ce mois "
                        "→ 404 (jamais un objet vide). ``latence_p95_ms`` et "
                        "``credit_du_montant`` valent ``null`` quand la "
                        "mesure ou le montant facturé est inconnu."
                    ),
                },
                {
                    'chemin': '/api/public/v1/fiabilite/usage/',
                    'scope': SCOPE_READ_FIABILITE,
                    'description': (
                        "Limites & usage (NTOBS8) — ``{ressources: [...], "
                        "genere_le}``. Une ressource dont la source est "
                        "indisponible est simplement OMISE, jamais remplie "
                        "d'une valeur inventée."
                    ),
                },
            ],
        },
        'webhooks': {
            'description': (
                "Notifications HTTP POST signées (HMAC-SHA256) vers une URL "
                "https que vous fournissez, sur abonnement par évènement. "
                "Configuration dans Paramètres → API & Webhooks."
            ),
            'entetes': {
                'signature': SIGNATURE_HEADER,
                # NTAPI9 — format auto-suffisant recommandé pour toute
                # intégration NEUVE ; le legacy ci-dessus reste valide.
                'signature_v2': SIGNATURE_HEADER_V2,
                'horodatage': TIMESTAMP_HEADER,
                'evenement': EVENT_HEADER,
                # NTAPI10 — même valeur sur TOUTES les tentatives d'une même
                # livraison (dédup côté consommateur).
                'idempotence': IDEMPOTENCY_HEADER,
            },
            'evenements': [
                {'code': code, 'libelle': libelle}
                for code, libelle in EVENT_CHOICES
            ],
            # CALX368 — évènements dont la charge utile est décrite clé par
            # clé (et projetée dans `webhooks` du document OpenAPI).
            'charges_utiles': [
                {
                    'code': EVENT_CALEPINAGE_SIMULE,
                    'description': (
                        "Une simulation de calepinage vient d'aboutir et son "
                        "résultat est enregistré (jamais pour un « déjà "
                        "calculé », un refus ou un calcul à blanc). POST JSON "
                        f"signé ({SIGNATURE_HEADER_V2} + {TIMESTAMP_HEADER}) "
                        "— aucune valeur n'est portée dans l'URL. Même scope "
                        "de lecture que la ressource : `read:calepinages` "
                        "pour le flux. Ni géométrie, ni coût."
                    ),
                    'champs': CHARGE_CALEPINAGE_SIMULE,
                },
            ],
            'verification_signature': {
                'algorithme': (
                    "HMAC-SHA256 de `f\"{timestamp}.\".encode() + body` (corps "
                    "HTTP brut reçu préfixé de l'en-tête "
                    f"{TIMESTAMP_HEADER}), avec le secret du webhook ; comparez "
                    f"le résultat hexadécimal à l'en-tête {SIGNATURE_HEADER} "
                    "(comparaison à temps constant), et rejetez un horodatage "
                    "hors tolérance (anti-rejeu)."
                ),
                'exemple_python': _HMAC_RECIPE_PYTHON,
            },
            'verification_signature_v2': {
                'algorithme': (
                    f"Recommandé (NTAPI9) — l'en-tête {SIGNATURE_HEADER_V2} "
                    "porte à lui seul `t=<epoch>,v1=<hex>` : même calcul HMAC "
                    "que le format legacy, mais horodatage + signature dans "
                    "UN SEUL en-tête. Rejetez un `t` hors tolérance (défaut "
                    f"{DEFAULT_SIGNATURE_TOLERANCE_SECONDS} s) — le format "
                    f"legacy {SIGNATURE_HEADER} reste envoyé EN PARALLÈLE, "
                    "sans changement, pour toute intégration existante."
                ),
                'exemple_python': _HMAC_RECIPE_V2_PYTHON,
            },
            'livraison': (
                "Chaque évènement porte un `event_id` stable (uuid4) dans le "
                "corps, identique sur toutes les tentatives (backoff "
                "exponentiel, jusqu'à 8 reprises) — dédupliquez dessus."
            ),
            'securite': (
                "Le secret n'est affiché qu'à la création (ou rotation). Les "
                "cibles internes/loopback et le schéma http sont refusées."
            ),
        },
    }
