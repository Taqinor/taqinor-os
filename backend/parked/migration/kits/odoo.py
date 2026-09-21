"""NTMIG8 — kit Odoo : mappings prédéfinis par entité.

Réutilise/étend ``ODOO_FIELD_MAP`` déjà présent dans
``apps.crm.management.commands.import_odoo_leads`` pour l'entité ``leads``
(import PARESSEUX — cette commande n'est jamais importée au chargement du
paquet ``kits``, seulement quand le kit ``leads`` est effectivement demandé,
et l'échec de l'import est absorbé : le kit ``leads`` retombe alors sur son
mapping minimal ci-dessous plutôt que de faire échouer tout le registre).

Colonnes d'export Odoo courantes (noms techniques ``res.partner``/
``product.template``/``crm.lead``/``sale.order``/``account.move``) ET leurs
étiquettes FR usuelles d'un export utilisateur — les deux mappent vers le
MÊME champ cible ``dataimport``.
"""


def _leads_mapping():
    """Mapping ``leads`` = ``ODOO_FIELD_MAP`` existant, best-effort.

    Le module de la commande peut être absent d'un déploiement minimal (AI
    service seul, tests isolés) : dans ce cas le kit ``leads`` retombe sur un
    mapping minimal plutôt que de faire échouer l'import du paquet ``kits``.
    """
    try:
        from apps.crm.management.commands.import_odoo_leads import (
            ODOO_FIELD_MAP)
        return dict(ODOO_FIELD_MAP)
    except Exception:  # pragma: no cover - dépend de l'environnement
        return {
            'name': 'nom', 'contact_name': 'nom', 'email_from': 'email',
            'phone': 'telephone', 'street': 'adresse', 'city': 'ville',
            'id': 'external_id',
        }


from . import Kit, cle_kit  # noqa: E402  (après _leads_mapping : évite tout cycle)

KIT_REGISTRY = {
    # crm.lead → leads. `id` (identifiant technique Odoo) sert de clé de
    # rapprochement stable (rejeu idempotent, NTMIG15).
    cle_kit('odoo', 'leads'): Kit(
        mapping={**_leads_mapping(), 'id': 'external_id'},
        cle_dedup='id',
        regles_format={'email': ['email'], 'telephone': ['telephone']},
    ),
    # res.partner → clients.
    cle_kit('odoo', 'clients'): Kit(
        mapping={
            'name': 'nom', 'contact_name': 'nom',
            'email': 'email',
            'phone': 'telephone', 'mobile': 'telephone',
            'street': 'adresse', 'street2': 'adresse',
            # ICE marocain — Odoo ne porte pas de champ standard ICE ; les
            # exports marocains le déclarent le plus souvent via `vat` (assujetti
            # TVA) ou un champ personnalisé `x_ice` — les deux mappent au même
            # champ cible.
            'vat': 'ice', 'x_ice': 'ice',
            'id': 'external_id',
        },
        cle_dedup='id',
        regles_format={'email': ['email'], 'telephone': ['telephone'],
                       'ice': ['ice']},
    ),
    # product.template → products.
    cle_kit('odoo', 'products'): Kit(
        mapping={
            'name': 'nom', 'default_code': 'sku', 'barcode': 'sku',
            'list_price': 'prix_vente', 'standard_price': 'prix_achat',
            'qty_available': 'quantite_stock',
            'description_sale': 'description',
            'id': 'external_id',
        },
        colonnes_montant=('list_price',),
        cle_dedup='id',
        regles_format={'prix_vente': ['montant'], 'prix_achat': ['montant']},
    ),
    # sale.order → devis (en-têtes seulement — lignes en NTMIG11).
    cle_kit('odoo', 'devis'): Kit(
        mapping={
            'name': 'reference_source',
            'partner_id': 'client_nom', 'partner_id/id': 'client_external_id',
            'partner_email': 'client_email',
            'state': 'statut',
            'date_order': 'date_creation',
            'amount_untaxed': 'montant_ht_source',
            'amount_total': 'montant_ttc_source',
            'id': 'external_id',
        },
        colonnes_montant=('amount_untaxed',),
        cle_dedup='id',
        regles_format={'client_email': ['email']},
        transformations={'date_creation': ['parser_date_multi_format']},
    ),
    # account.move (type facture client) → factures (en-têtes seulement).
    cle_kit('odoo', 'factures'): Kit(
        mapping={
            'name': 'reference_source',
            'partner_id': 'client_nom', 'partner_id/id': 'client_external_id',
            'partner_email': 'client_email',
            'state': 'statut', 'payment_state': 'statut_paiement',
            'invoice_date': 'date_emission',
            'amount_untaxed': 'montant_ht_source',
            'amount_total': 'montant_ttc_source',
            'id': 'external_id',
        },
        colonnes_montant=('amount_untaxed',),
        cle_dedup='id',
        regles_format={'client_email': ['email']},
        transformations={'date_emission': ['parser_date_multi_format']},
    ),
}
