"""SPL142 — forme DÉCLARÉE de « Relances du jour » (``action-requise``),
déplacement pur depuis ``serializers.py`` : classes octet-identiques, noms
inchangés (les noms de composants OpenAPI sont les noms de classe : schéma
inchangé). Lue par ``views/devis_cadence.py``.
"""
from rest_framework import serializers


# ── QX29/QX30/PACT17 — forme DÉCLARÉE de « Relances du jour » ────────────────
# PACT7 : un endpoint agrégé déclare sa FORME, jamais « un objet ». Ces trois
# sérialiseurs ne servent QU'À DOCUMENTER (`@extend_schema(responses=...)`) la
# réponse de `DevisViewSet.action_requise` — la vue renvoie le dictionnaire du
# sélecteur tel quel, comme son miroir SAV (ZSAV6).

class DevisActionPanierSerializer(serializers.Serializer):
    """Un panier de la file d'action : son compte et les ids qu'il contient."""
    count = serializers.IntegerField(
        help_text="Nombre de devis dans ce panier.")
    ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="Identifiants des devis de ce panier, triés.")


class DevisActionBucketsSerializer(serializers.Serializer):
    """Les 5 paniers de « Relances du jour », TOUJOURS tous présents (un
    panier vide vaut `{'count': 0, 'ids': []}`, jamais une clé absente)."""
    envoyes_sans_reponse = DevisActionPanierSerializer()
    acceptes_non_factures = DevisActionPanierSerializer()
    refuses_sans_motif = DevisActionPanierSerializer()
    expirant_bientot = DevisActionPanierSerializer()
    engagement_relance = DevisActionPanierSerializer()


class ProchaineToucheCrmSerializer(serializers.Serializer):
    """CAD115 — prochaine touche CRM (``crm.RelanceEtape`` À FAIRE) déjà
    programmée pour le lead d'origine du devis. Évite que la file Ventes et
    la file calendaire du CRM réclament le même devis le même jour avec deux
    messages différents (SIG9)."""
    due_at = serializers.DateTimeField(
        allow_null=True, help_text="Échéance à la minute — absente sur les "
        "touches créées avant MRY5.")
    due_date = serializers.DateField(allow_null=True)
    cadence = serializers.CharField(allow_blank=True)
    canal = serializers.CharField(allow_blank=True)


class DevisActionLigneSerializer(serializers.Serializer):
    """De quoi RENDRE une ligne de la file : jamais un prix d'achat ni une
    marge (règle #4), seulement ce que le client voit déjà."""
    id = serializers.IntegerField()
    reference = serializers.CharField()
    client_nom = serializers.CharField(allow_blank=True)
    client_telephone = serializers.CharField(allow_blank=True)
    client_whatsapp = serializers.CharField(allow_blank=True)
    total_ttc = serializers.CharField(
        allow_null=True,
        help_text="Total TTC en TEXTE décimal (jamais un flottant).")
    prochaine_touche_crm = ProchaineToucheCrmSerializer(
        allow_null=True,
        help_text="CAD115 — prochaine touche CRM programmée pour le lead "
        "d'origine ; `null` sans lead ou sans touche À FAIRE.")


class DevisActionRequiseSerializer(serializers.Serializer):
    """PACT17 — réponse de `GET /ventes/devis/action-requise/`."""
    buckets = DevisActionBucketsSerializer()
    wa_drafts = serializers.DictField(
        child=serializers.CharField(),
        help_text=(
            "Brouillon WhatsApp par id de devis, UNIQUEMENT pour la file "
            "`engagement_relance` (QX30) ; vide partout ailleurs."),
    )
    devis = serializers.DictField(
        child=DevisActionLigneSerializer(),
        help_text=(
            "Ligne d'affichage par id de devis cité dans un panier — évite à "
            "l'écran de re-télécharger toute la liste des devis."),
    )
