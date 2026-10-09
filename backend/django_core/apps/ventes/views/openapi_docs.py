"""ENF5 — formes OpenAPI EXACTES des actions ventes / facturation.

Aucun comportement : ces sérialiseurs ne servent QU'À la description du
schéma (``@extend_schema``). Corps optionnels = tous les champs
``required=False`` (drf-spectacular ne marque un corps requis que s'il porte
un champ requis). Le moteur de devis (règle #4) n'est pas touché.
"""
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers as s

from ..serializers import DevisSerializer, PlanCommissionSerializer


def _ser(name, fields):
    return inline_serializer(name, fields)


# ---------------------------------------------------------------- devis
GAMME_ENVOI = s.CharField(required=False, allow_blank=True)

ShareLinkRequest = _ser('DevisShareLinkRequest', {
    'niveau': s.CharField(required=False),
    'otp_lecture': s.BooleanField(required=False),
    'sections': s.DictField(child=s.BooleanField(), required=False),
    'gamme_envoi': GAMME_ENVOI,
    'envoi': s.CharField(required=False),
})
ShareLinkResponse = _ser('DevisShareLinkResponse', {
    'token': s.CharField(),
    'path': s.CharField(),
    'token_interne': s.CharField(),
    'path_interne': s.CharField(),
    'gamme': s.DictField(allow_null=True),
    'niveau': s.CharField(),
    'otp_lecture': s.BooleanField(),
    'sections': s.DictField(),
})

EnvoyerEmailRequest = _ser('DevisEnvoyerEmailRequest', {
    'to_email': s.CharField(required=False, allow_blank=True),
    'sujet': s.CharField(required=False, allow_blank=True),
    'corps': s.CharField(required=False, allow_blank=True),
    'pdf_mode': s.CharField(required=False),
    'gamme_envoi': GAMME_ENVOI,
})
EnvoyerEmailResponse = _ser('DevisEnvoyerEmailResponse', {
    'detail': s.CharField(),
    'log_id': s.IntegerField(),
    'email_statut': s.CharField(),
    'devis_statut': s.CharField(),
    'proposal_path': s.CharField(required=False, allow_null=True),
})
EnvoyerEmailEchec = _ser('DevisEnvoyerEmailEchec', {
    'detail': s.CharField(),
    'log_id': s.IntegerField(),
    'email_statut': s.CharField(),
    'devis_statut': s.CharField(),
})

WhatsappRequest = _ser('DevisWhatsappRequest', {
    'langue': s.CharField(required=False),
    'gamme_envoi': GAMME_ENVOI,
})
WhatsappResponse = _ser('DevisWhatsappResponse', {
    'wa_url': s.CharField(),
    'phone': s.CharField(),
    'message': s.CharField(),
    'url': s.CharField(),
    'devis_statut': s.CharField(),
})
WhatsappPreviewResponse = _ser('DevisWhatsappPreviewResponse', {
    'wa_url': s.CharField(),
    'phone': s.CharField(),
    'message': s.CharField(),
    'url': s.CharField(),
    'devis_statut': s.CharField(),
    'preview': s.BooleanField(),
    'gamme': s.DictField(allow_null=True),
})

PdfPartageResponse = _ser('DevisPdfPartageResponse', {
    'devis_statut': s.CharField(),
})
ContacterSuperieurRequest = _ser('DevisContacterSuperieurRequest', {
    'message': s.CharField(required=False, allow_blank=True),
})
ContacterSuperieurResponse = _ser('DevisContacterSuperieurResponse', {
    'detail': s.CharField(),
    'recipients': s.ListField(child=s.CharField()),
})
RevoquerLienPublicResponse = _ser('DevisRevoquerLienPublicResponse', {
    'revoques': s.IntegerField(),
    'revoque_le': s.DateTimeField(allow_null=True),
})

PdfTaskResponse = _ser('PdfTaskResponse', {
    'task_id': s.CharField(),
    'detail': s.CharField(),
})

DupliquerVarianteRequest = _ser('DevisDupliquerVarianteRequest', {
    'scales': s.ListField(child=s.FloatField(), required=False),
    'variante_pct': s.FloatField(required=False),
})
DupliquerVarianteGammeRequest = _ser('DevisDupliquerVarianteGammeRequest', {
    'nom': s.CharField(required=False, allow_blank=True),
    'nom_source': s.CharField(required=False, allow_blank=True),
    'recommandee': s.BooleanField(required=False),
})

PrefillSiteResponse = _ser('DevisPrefillSiteResponse', {
    'client': s.IntegerField(),
    'profil': s.DictField(allow_null=True),
})

# -------------------------------------------------------------- facture
FactureAnnulerRequest = _ser('FactureAnnulerRequest', {
    'acompte': _ser('FactureAnnulerAcompte', {
        'action': s.ChoiceField(choices=['transferer', 'rembourser'],
                                required=False),
        'facture_cible': s.IntegerField(required=False),
    }),
})
ExclureRelanceRequest = _ser('FactureExclureRelanceRequest', {
    'exclu': s.BooleanField(required=False),
})
FactureWhatsappRequest = _ser('FactureWhatsappRequest', {
    'modele': s.ChoiceField(choices=['facture', 'relance'], required=False),
    'langue': s.CharField(required=False),
})
FactureWhatsappResponse = _ser('FactureWhatsappResponse', {
    'wa_url': s.CharField(),
    'phone': s.CharField(),
    'message': s.CharField(),
    'url': s.CharField(),
})
LienPaiementRequest = _ser('FactureLienPaiementRequest', {
    'provider': s.CharField(required=False),
})
LienPaiementResponse = _ser('FactureLienPaiementResponse', {
    'token': s.CharField(),
    'statut': s.CharField(),
    'montant': s.CharField(),
    'montant_a_payer': s.CharField(),
    'provider': s.CharField(),
    'pay_url': s.CharField(allow_null=True),
    'expires_at': s.DateTimeField(),
})
RevoquerLienPaiementResponse = _ser('FactureRevoquerLienPaiementResponse', {
    'detail': s.CharField(),
    'revoque': s.BooleanField(),
    'token': s.CharField(required=False),
    'statut': s.CharField(required=False),
})
CreerNoteDebitRequest = _ser('FactureCreerNoteDebitRequest', {
    'motif': s.CharField(required=False, allow_blank=True),
    'lignes': s.ListField(child=s.DictField(), required=False),
})

# ------------------------------------------------------- relevé bancaire
ReleveDryRunRequest = _ser('ReleveImportDryRunRequest', {
    'file': s.FileField(),
})
ReleveCommitRequest = _ser('ReleveImportCommitRequest', {
    'token': s.CharField(),
    'lignes': s.ListField(child=s.JSONField(), required=False),
})

# --------------------------------------------------------------- divers
ResoudrePlanResponse = _ser('PlanCommissionResoudreResponse', {
    'owner': s.IntegerField(allow_null=True),
    'source': s.CharField(),
    'plan': PlanCommissionSerializer(allow_null=True),
})

GammeResponse = _ser('DevisDupliquerVarianteGammeResponse', {
    'source': DevisSerializer(),
    'gamme': DevisSerializer(),
    'gammes': s.ListField(child=s.DictField()),
})

PrixApplicableResponse = _ser('PrixApplicableResponse', {
    'produit': s.IntegerField(),
    'quantite': s.CharField(),
    'prix': s.CharField(),
    'unite': s.CharField(),
    'source': s.CharField(),
    'liste_nom': s.CharField(allow_null=True),
    'remise_volume': s.DictField(),
})

VarianteConfigRequest = _ser('DevisVarianteConfigRequest', {
    'variante_pct': s.DecimalField(max_digits=5, decimal_places=2,
                                   required=False),
})
VarianteConfigResponse = _ser('DevisVarianteConfigResponse', {
    'variante_pct': s.CharField(),
})

ConceptionElectriqueRequest = _ser('DevisConceptionElectriqueRequest', {
    cle: s.JSONField(required=False) for cle in (
        'dc_m', 'ac_m', 'phases', 'regime', 'batterie', 'zone_keraunique',
        'temp_froid_c', 'temp_chaud_c', 'longueur_chaine_forcee',
        'plafond_kwc_par_onduleur', 'inclure_prise_terre')
})

PdfOptionsRequest = _ser('DevisPdfOptionsRequest', {
    'pdf_mode': s.ChoiceField(choices=['full', 'onepage'], required=False),
    'show_monthly': s.BooleanField(required=False),
    'devis_final': s.BooleanField(required=False),
    'include_etude': s.BooleanField(required=False),
    'include_calepinage': s.BooleanField(required=False, allow_null=True),
    'include_note_calcul': s.BooleanField(required=False),
    'kit_agrege': s.BooleanField(required=False),
    'variante_option': s.CharField(required=False),
    'include_annexe_technique': s.JSONField(required=False),
    'langue_sortie': s.CharField(required=False),
})

EnregistrerAvanceRequest = _ser('PaiementEnregistrerAvanceRequest', {
    'client': s.IntegerField(),
    'montant': s.DecimalField(max_digits=12, decimal_places=2),
    'date_paiement': s.DateField(required=False),
    'mode': s.CharField(required=False),
    'reference': s.CharField(required=False, allow_blank=True),
    'note': s.CharField(required=False, allow_blank=True),
})
VentilerRequest = _ser('PaiementVentilerRequest', {
    'facture': s.IntegerField(),
    'montant': s.DecimalField(max_digits=12, decimal_places=2),
})
