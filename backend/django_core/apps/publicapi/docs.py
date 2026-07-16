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
from .constants import SCOPE_CHOICES, EVENT_CHOICES
from .auth import AUTH_KEYWORD
from .delivery import SIGNATURE_HEADER, EVENT_HEADER, TIMESTAMP_HEADER

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


def public_api_reference():
    """Construit la référence FR de l'API publique (dict sérialisable en JSON)."""
    return {
        'titre': "API publique Taqinor — Référence",
        'version': '1',
        'base_url': '/api/public/',
        'introduction': (
            "API REST authentifiée par clé d'API et scopée à votre société. "
            "Principalement en lecture seule ; un sous-ensemble d'écriture "
            "existe (voir « endpoints_ecriture », scopes dédiés `*:write`). "
            "Aucun prix d'achat / marge n'est jamais renvoyé."
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
                'chemin': '/api/public/leads/',
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
                'chemin': '/api/public/devis/',
                'scope': 'read:devis',
                'description': "Devis (avec lignes, prix de vente uniquement).",
                'filtres': ['statut', 'mode_installation', 'client', 'lead'],
                'tri': ['date_creation', 'id'],
                'updated_since': 'date_creation',
            },
            {
                'chemin': '/api/public/factures/',
                'scope': 'read:factures',
                'description': "Factures (avec lignes).",
                'filtres': ['statut', 'type_facture', 'client', 'devis'],
                'tri': ['date_emission', 'id'],
                'updated_since': 'date_emission',
            },
            {
                'chemin': '/api/public/chantiers/',
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
                'chemin': '/api/public/produits/',
                'scope': 'read:stock',
                'description': (
                    "Disponibilité produit (SKU/nom/marque/catégorie/quantité "
                    "disponible). Jamais de prix d'achat ni de coût."
                ),
                'filtres': ['sku', 'marque', 'categorie'],
                'tri': ['id', 'nom'],
                'updated_since': None,
            },
        ],
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
                    'chemin': '/api/public/leads-write/',
                    'methode': 'POST',
                    'scope': 'leads:write',
                    'description': "Crée un lead.",
                },
                {
                    'chemin': '/api/public/leads-write/<id>/',
                    'methode': 'PATCH',
                    'scope': 'leads:write',
                    'description': "Met à jour un lead existant.",
                },
                {
                    'chemin': '/api/public/leads-write/<id>/activites/',
                    'methode': 'POST',
                    'scope': 'activities:write',
                    'description': "Ajoute une note (chatter) sur un lead.",
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
                'horodatage': TIMESTAMP_HEADER,
                'evenement': EVENT_HEADER,
            },
            'evenements': [
                {'code': code, 'libelle': libelle}
                for code, libelle in EVENT_CHOICES
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
