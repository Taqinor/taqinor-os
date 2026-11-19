"""Copilote vague 2 (lane VAD) — schémas OpenAPI des routes de l'assistant.

Formes PUBLIÉES des réponses et des corps des routes de
``views/assistant.py`` (contrats ``contract_samples/assistant_*.json``). Ici
plutôt que dans ``openapi_docs.py`` (1 830 lignes) : un fichier proche de la
borne ne grossit pas.
"""
from rest_framework import serializers as s

from .openapi_docs import _ser

_MONTANT = s.CharField()

#: VAD1 — ``GET ventes/devis/<pk>/vente-assistant/`` (``assistant_vente_etat.json``).
VenteEtatAssistantResponse = _ser('VenteEtatAssistantResponse', {
    'devis_id': s.IntegerField(),
    'reference': s.CharField(),
    'statut': s.CharField(),
    'client': s.CharField(allow_blank=True),
    'est_tete': s.BooleanField(),
    'tete_id': s.IntegerField(),
    'revision_en_cours': _ser('VenteEtatAssistantRevision', {
        'id': s.IntegerField(), 'reference': s.CharField()}, allow_null=True),
    'date_validite': s.DateField(allow_null=True),
    'prix_convenu_ttc': _MONTANT,
    'emis_ttc': _MONTANT,
    'brouillons_ttc': _MONTANT,
    'paye_ttc': _MONTANT,
    'reste_a_facturer_ttc': _MONTANT,
    'reste_a_payer_ttc': _MONTANT,
    'prochaine_action': s.ChoiceField(choices=[
        'acompte', 'intermediaire', 'solde', 'complete', 'aucune']),
    'raison_bloquee': s.CharField(allow_blank=True),
    'prochaines_echeances': s.ListField(child=_ser(
        'VenteEtatAssistantEcheance', {
            'cle': s.CharField(), 'libelle': s.CharField(),
            'montant_ttc': _MONTANT})),
    'factures': s.ListField(child=_ser('VenteEtatAssistantFacture', {
        'facture_id': s.IntegerField(),
        'reference': s.CharField(),
        'nature': s.CharField(),
        'statut': s.CharField(),
        'total_ttc': _MONTANT,
        'montant_paye': _MONTANT,
        'montant_du': _MONTANT,
        'date_emission': s.DateField(allow_null=True),
    })),
    'a_faire': s.ChoiceField(choices=[
        'facturer', 'emettre_brouillon', 'encaisser', 'reviser', 'rien']),
    'lien': s.CharField(),
})
