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

_ALERTE = _ser('TailleAssistantAlerte', {
    'code': s.CharField(), 'message': s.CharField()})
_TAILLE_COMMUN = {
    'devis_id': s.IntegerField(),
    'reference': s.CharField(),
    'statut': s.CharField(),
    'corrige_apres_envoi': s.BooleanField(),
    'nb_panneaux': s.IntegerField(),
    'kwc': s.FloatField(allow_null=True),
    'ancien_total_ttc': _MONTANT,
    'nouveau_total_ttc': _MONTANT,
    'alertes': s.ListField(child=_ALERTE),
    'lien': s.CharField(),
}

#: VAD7 — ``GET ventes/devis/<pk>/assistant-taille/apercu/``
#: (``assistant_devis_taille_apercu.json``) : aucune écriture.
TailleAssistantApercuResponse = _ser('TailleAssistantApercuResponse', {
    **_TAILLE_COMMUN,
    'nb_panneaux_avant': s.IntegerField(allow_null=True),
    'kwc_avant': s.FloatField(allow_null=True),
    'a_faire': s.ChoiceField(choices=['proposer', 'rien']),
})

#: VAD7 — corps de ``POST ventes/devis/<pk>/assistant-taille/`` : le nombre de
#: panneaux (et de modules) et les DEUX totaux recopiés de l'aperçu. Rien
#: d'autre : ni prix, ni remise, ni forçage.
TailleAssistantRequest = _ser('TailleAssistantRequest', {
    'nb_panneaux': s.IntegerField(min_value=1, max_value=200),
    'batterie_nb_modules': s.IntegerField(min_value=1, required=False),
    'ancien_total_ttc': s.RegexField(r'^\d{1,9}(\.\d{1,2})?$'),
    'nouveau_total_ttc': s.RegexField(r'^\d{1,9}(\.\d{1,2})?$'),
})

#: VAD7 — réponse de l'écriture (``assistant_devis_taille.json``).
TailleAssistantResponse = _ser('TailleAssistantResponse', {
    **_TAILLE_COMMUN,
    'composition': s.ListField(child=_ser('TailleAssistantLigne', {
        'designation': s.CharField(),
        'quantite': s.FloatField(),
        'prix_unitaire_ttc': _MONTANT,
        'total_ttc': _MONTANT,
        'variante': s.CharField(allow_blank=True),
    })),
})

ErreurTailleAssistant = _ser('ErreurTailleAssistant', {
    'detail': s.CharField(), 'field': s.CharField(), 'code': s.CharField()})

#: VAD8 — ``POST ventes/assistant/factures/<pk>/relance-whatsapp/`` : la
#: langue seulement (le modèle « relance » est FORCÉ, aucun texte libre).
RelanceWhatsappRequest = _ser('RelanceWhatsappAssistantRequest', {
    'langue': s.ChoiceField(choices=['fr', 'darija'], required=False)})
RelanceWhatsappResponse = _ser('RelanceWhatsappAssistantResponse', {
    'facture_id': s.IntegerField(),
    'reference': s.CharField(),
    'texte': s.CharField(allow_blank=True),
    'wa_url': s.CharField(allow_null=True),
    'langue_servie': s.CharField(),
    'lien': s.CharField(),
})
ErreurRelanceWhatsapp = _ser('ErreurRelanceWhatsappAssistant', {
    'detail': s.CharField(), 'code': s.CharField()})

#: VAD3 — ``GET ventes/assistant/factures/`` (``assistant_factures.json``).
FacturesAssistantResponse = _ser('FacturesAssistantResponse', {
    'q': s.CharField(allow_blank=True),
    'statut': s.CharField(allow_blank=True),
    'total': s.IntegerField(),
    'limite': s.IntegerField(),
    'lignes': s.ListField(child=_ser('FacturesAssistantLigne', {
        'facture_id': s.IntegerField(),
        'reference': s.CharField(),
        'client_nom': s.CharField(allow_blank=True),
        'nature': s.CharField(),
        'statut': s.CharField(),
        'total_ttc': _MONTANT,
        'montant_du': _MONTANT,
        'date_emission': s.DateField(allow_null=True),
        'date_echeance': s.DateField(allow_null=True),
        'jours_retard': s.IntegerField(),
        'a_faire': s.ChoiceField(choices=[
            'emettre', 'encaisser', 'relancer', 'rien']),
        'lien': s.CharField(),
    })),
})

#: VAD2 — ``GET ventes/assistant/impayes/`` (``assistant_impayes.json``).
ImpayesAssistantResponse = _ser('ImpayesAssistantResponse', {
    'total_du': _MONTANT,
    'nb_factures': s.IntegerField(),
    'tranches': _ser('ImpayesAssistantTranches', {
        cle: _MONTANT for cle in ('b0_30', 'b31_60', 'b61_90', 'b90_plus')}),
    'limite': s.IntegerField(),
    'lignes': s.ListField(child=_ser('ImpayesAssistantLigne', {
        'facture_id': s.IntegerField(),
        'reference': s.CharField(),
        'client_id': s.IntegerField(allow_null=True),
        'client_nom': s.CharField(allow_blank=True),
        'montant_du': _MONTANT,
        'jours_retard': s.IntegerField(),
        'niveau': s.CharField(allow_null=True),
        'promesse': _ser('ImpayesAssistantPromesse', {
            'statut': s.CharField(), 'date_promise': s.DateField()},
            allow_null=True),
        'contestee': s.BooleanField(),
        'a_faire': s.ChoiceField(choices=[
            'relancer', 'attendre_promesse', 'traiter_contestation', 'rien']),
        'lien': s.CharField(),
    })),
    'lien': s.CharField(),
})
