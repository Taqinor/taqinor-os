"""Copilote vague 2 (lane VAD) — schémas OpenAPI des routes de l'assistant.

Formes PUBLIÉES des réponses et des corps des routes de
``views/assistant.py`` (contrats ``contract_samples/assistant_*.json``). Ici
plutôt que dans ``openapi_docs.py`` (1 830 lignes) : un fichier proche de la
borne ne grossit pas.
"""
from rest_framework import serializers as s

from .openapi_docs import _ser, options_devis_assistant

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

#: 21/11/2026 — ``GET ventes/devis/assistant-liste/``
#: (``assistant_devis_liste.json``) : les devis de la portée de l'écran.
DevisListeAssistantResponse = _ser('DevisListeAssistantResponse', {
    'total': s.IntegerField(),
    'limite': s.IntegerField(),
    'lignes': s.ListField(child=_ser('DevisListeAssistantLigne', {
        'devis_id': s.IntegerField(),
        'reference': s.CharField(),
        'statut': s.CharField(),
        'client': s.CharField(allow_blank=True),
        'lead_id': s.IntegerField(allow_null=True),
        'total_ttc': s.CharField(allow_null=True),
        'cree_le': s.DateField(),
        'envoye_le': s.DateField(allow_null=True),
        'accepte_le': s.DateField(allow_null=True),
        'lien': s.CharField(),
    })),
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
    'options': options_devis_assistant(),
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
    'options': options_devis_assistant(),
    'composition': s.ListField(child=_ser('TailleAssistantLigne', {
        'designation': s.CharField(),
        'quantite': s.FloatField(),
        'prix_unitaire_ttc': _MONTANT,
        'total_ttc': _MONTANT,
        'variante': s.CharField(allow_blank=True),
    })),
})

ErreurTailleAssistant = _ser('ErreurTailleAssistant', {
    'detail': s.CharField(required=False), 'field': s.CharField(required=False),
    'code': s.CharField(required=False)})

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
    'detail': s.CharField(required=False), 'code': s.CharField(required=False)})

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

# ── 20/11/2026 — les LIGNES d'un devis changées par l'assistant ─────────────
# ``POST ventes/devis/<pk>/assistant-lignes/<operation>/`` (contrat
# ``assistant_devis_lignes_modifier.json``, ``domain/lignes_assistant.py``).
# Quatre corps EXACTS (un par opération) : désignation et prix viennent du
# catalogue, jamais du corps ; quantité en nombre JSON OU en texte.


def _quantite_assistant(**kwargs):
    from decimal import Decimal

    from core.champs_stricts import DecimalSouple
    return DecimalSouple(max_digits=10, decimal_places=2,
                         min_value=Decimal('0.01'),
                         max_value=Decimal('99999999.99'), **kwargs)


def _variante_assistant():
    # Motif plutôt qu'un ``enum`` : un énuméré « variante » de plus entrerait
    # en collision de nom avec ceux du schéma (avertissement du générateur).
    return s.RegexField(r'^(sans|avec|les_deux)$', required=False)


def _id_assistant():
    return s.IntegerField(min_value=1, max_value=2 ** 31 - 1)


LigneAjouterAssistantRequest = _ser('LigneAjouterAssistantRequest', {
    'produit': _id_assistant(),
    'quantite': _quantite_assistant(required=False),
    'variante': _variante_assistant(),
})
LigneModifierAssistantRequest = _ser('LigneModifierAssistantRequest', {
    'ligne': _id_assistant(),
    'quantite': _quantite_assistant(),
    'variante': _variante_assistant(),
})
LigneSupprimerAssistantRequest = _ser('LigneSupprimerAssistantRequest', {
    'ligne': _id_assistant(),
    'variante': _variante_assistant(),
})
LigneRemplacerAssistantRequest = _ser('LigneRemplacerAssistantRequest', {
    'ligne': _id_assistant(),
    'produit': _id_assistant(),
    'quantite': _quantite_assistant(required=False),
    'variante': _variante_assistant(),
})

LignesAssistantResponse = _ser('LignesAssistantResponse', {
    'devis_id': s.IntegerField(),
    'reference': s.CharField(),
    'statut': s.CharField(),
    # ajouter | modifier | supprimer | remplacer (texte : aucun énuméré de
    # plus dans le schéma, voir ``_variante_assistant``).
    'operation': s.CharField(),
    'corrige_apres_envoi': s.BooleanField(),
    'ancien_total_ttc': _MONTANT,
    'nouveau_total_ttc': _MONTANT,
    'options': options_devis_assistant(avec_ancien=True),
    'lignes_touchees': s.ListField(child=_ser('LignesAssistantLigne', {
        'ligne_id': s.IntegerField(),
        'etat': s.CharField(),  # ajoutee | modifiee | retiree
        'designation': s.CharField(),
        'quantite': s.FloatField(),
        'variante': s.CharField(allow_blank=True),
        'total_ttc': _MONTANT,
    })),
    # Une instance NEUVE de la MÊME classe (un champ enfant ne se lie qu'une
    # fois ; drf-spectacular identifie un composant par sa classe).
    'alertes': s.ListField(child=type(_ALERTE)()),
    'lien': s.CharField(),
})
ErreurLignesAssistant = _ser('ErreurLignesAssistant', {
    'detail': s.CharField(required=False), 'field': s.CharField(required=False),
    'code': s.CharField(required=False)})
