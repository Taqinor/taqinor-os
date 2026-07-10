"""SCA49 — snapshot du contrat JSON du Devis (docs/devis-json-contract.md).

Gèle la forme lecture-seule du Devis sérialisé (etude_params inclus) pour que
la future API partenaires existe sans schéma nouveau (leçon Aurora : les
financeurs sont des LECTEURS de l'objet devis — il suffit de geler la forme).

Sémantique du gel (voir la doc) :
  * une clé du contrat DISPARUE ou RENOMMÉE → le test devient ROUGE (rupture) ;
  * une clé AJOUTÉE au serializer → le test reste VERT (rétro-compatible).

Concrètement : l'ensemble gelé doit rester un SOUS-ENSEMBLE des clés réellement
exposées par le serializer. Aucune base de données requise (inspection de la
forme du serializer uniquement).
"""
from django.test import SimpleTestCase

from apps.ventes.serializers import DevisSerializer, PaiementSerializer

# ── Ensemble GELÉ des clés du contrat Devis (docs/devis-json-contract.md) ──
# Inclut prix_par_kwc (SCA47) : exposé sur l'API interne (BI NTDATA46/47),
# hors contrat partenaire externe mais gelé dans la forme du serializer.
DEVIS_CONTRACT_KEYS = frozenset({
    # Identité & entête
    'id', 'reference', 'statut', 'date_creation', 'date_validite',
    'client', 'client_nom', 'lead',
    # Montants
    'taux_tva', 'remise_globale', 'total_ht', 'total_tva', 'total_ttc',
    'total_affiche', 'nb_options', 'devise',
    # Lignes
    'lignes',
    # Étude / simulation
    'mode_installation', 'etude_params',
    # Interne BI (SCA47) — gelé : sa disparition casserait NTDATA46/47.
    'prix_par_kwc',
})

# ── Ensemble GELÉ des clés du Paiement (addendum SCA45 de la doc) ──
# provider_ref / idempotency_key : les champs provider-agnostiques (SCA45)
# sont exposés par PaiementSerializer (fields='__all__') et gelés ici.
PAIEMENT_CONTRACT_KEYS = frozenset({
    'id', 'facture', 'montant', 'date_paiement', 'mode', 'statut',
    'provider_ref', 'idempotency_key',
})

# Clés de coût INTERDITES au niveau racine du Devis sérialisé (données
# revendeur/marge — jamais exposées, même sur l'API interne du devis).
FORBIDDEN_TOP_LEVEL_KEYS = frozenset({'prix_achat', 'marge'})


class DevisContractShapeTests(SimpleTestCase):
    def test_devis_contract_keys_all_present(self):
        """Une clé gelée absente/renommée = rupture du contrat → rouge."""
        current = set(DevisSerializer().fields.keys())
        missing = DEVIS_CONTRACT_KEYS - current
        self.assertFalse(
            missing,
            'RUPTURE du contrat JSON du Devis (docs/devis-json-contract.md) : '
            f'clé(s) gelée(s) disparue(s)/renommée(s) : {sorted(missing)}. '
            'Renommer/supprimer une clé du contrat exige une décision '
            'explicite (versionner l\'API partenaire) — jamais un renommage '
            'silencieux.')

    def test_added_keys_do_not_break_contract(self):
        """Sémantique « ajouter = OK » : le gel est un test de sous-ensemble,
        le serializer peut exposer PLUS de clés que le contrat sans rougir."""
        current = set(DevisSerializer().fields.keys())
        # Le serializer expose bien des clés au-delà du contrat gelé (preuve
        # que le gel n'est pas une égalité stricte).
        self.assertTrue(DEVIS_CONTRACT_KEYS < current)

    def test_paiement_contract_keys_all_present(self):
        """Addendum SCA45 : provider_ref + idempotency_key (et les clés cœur
        du paiement) sont gelés dans la forme de PaiementSerializer."""
        current = set(PaiementSerializer().fields.keys())
        missing = PAIEMENT_CONTRACT_KEYS - current
        self.assertFalse(
            missing,
            'RUPTURE de la forme lecture du Paiement (addendum SCA45 de '
            'docs/devis-json-contract.md) : clé(s) gelée(s) disparue(s) : '
            f'{sorted(missing)}.')

    def test_no_cost_keys_at_devis_top_level(self):
        """Jamais de prix_achat/marge au niveau racine du Devis sérialisé."""
        current = set(DevisSerializer().fields.keys())
        leaked = FORBIDDEN_TOP_LEVEL_KEYS & current
        self.assertFalse(
            leaked,
            f'Clé(s) de coût interne exposée(s) sur le Devis : {sorted(leaked)}'
            ' — prix_achat/marge ne doivent JAMAIS être sérialisés sur le '
            'devis (règle générateur-interne).')
