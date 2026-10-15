"""ENF5 — formes OpenAPI EXACTES des actions ventes / facturation.

Aucun comportement : ces sérialiseurs ne servent QU'À la description du
schéma (``@extend_schema``). Corps optionnels = tous les champs
``required=False`` (drf-spectacular ne marque un corps requis que s'il porte
un champ requis). Le moteur de devis (règle #4) n'est pas touché.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError as _ErreurDjango
from django.core.validators import RegexValidator as _RegexValidator
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers as s

from core.champs_stricts import (
    BooleenStrict, ChaineStricte, DateStricte, DecimalSouple, DecimalStricte,
    EntierStrict,
)
from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE
from core.parseurs import ChoixDocumente
from ..models import Paiement
from ..payments.providers import providers_lien_actifs
from ..serializers import (
    DevisSerializer, DevisWriteSerializer, PlanCommissionSerializer,
)
from ..serializers_facturation import (
    AvoirSerializer, FactureListeSerializer, FactureSerializer, FactureWriteSerializer,
    NoteDebitSerializer, PaiementSerializer, RetenueSubieSerializer,
)


def _ser(name, fields, **kwargs):
    return inline_serializer(name, fields, **kwargs)


class _MotifEntier(_RegexValidator):
    """CI #997 fuzz — ``RegexValidator`` PUBLIÉ tel quel mais appliqué en
    ``fullmatch`` : ``$`` laisserait passer un saut de ligne final."""

    def __call__(self, value):
        if not isinstance(value, str) or not self.regex.fullmatch(value):
            raise _ErreurDjango(self.message, code=self.code)


# ---------------------------------------------------------------- devis
GAMME_ENVOI = ChaineStricte(required=False, allow_blank=True)

_SECTIONS_LIEN = ('roof3d', 'sld', 'pdf', 'bankable', 'economies',
                  'jour_type', 'gammes', 'taille_eco', 'taille_max')
ShareLinkRequest = _ser('DevisShareLinkRequest', {
    'niveau': s.ChoiceField(choices=['standard', 'confiance'],
                            required=False),
    'otp_lecture': s.BooleanField(required=False),
    # Clés fermées (ShareLink.SECTIONS_CLES) : toute autre clé = 400.
    'sections': _ser('DevisShareLinkSections', {
        cle: s.BooleanField(required=False) for cle in _SECTIONS_LIEN},
        required=False),
    'gamme_envoi': GAMME_ENVOI,
    'envoi': s.BooleanField(required=False),
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
    'to_email': ChaineStricte(required=False, allow_blank=True),
    'sujet': ChaineStricte(required=False, allow_blank=True),
    'corps': ChaineStricte(required=False, allow_blank=True),
    'pdf_mode': ChaineStricte(required=False, allow_blank=True),
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
    'langue': ChaineStricte(required=False, allow_blank=True),
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
    'message': ChaineStricte(required=False, allow_blank=True),
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


class NombreStrict(s.FloatField):
    """Tour 3 M1 — nombre JSON réel : ``"0.8"``, ``true`` → 400 (``FloatField``
    les convertissait en silence : corps hors schéma accepté)."""

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            self.fail('invalid')
        return super().to_internal_value(data)


# Échelle bornée (0,01 → ×10) : au-delà, ``Decimal(str(x)).quantize`` des
# quantités levait (500) sur un corps pourtant conforme.
DupliquerVarianteRequest = _ser('DevisDupliquerVarianteRequest', {
    'scales': s.ListField(child=NombreStrict(min_value=0.01, max_value=10),
                          required=False),
    'variante_pct': NombreStrict(required=False),
})
DupliquerVarianteGammeRequest = _ser('DevisDupliquerVarianteGammeRequest', {
    'nom': ChaineStricte(required=False, allow_blank=True),
    'nom_source': ChaineStricte(required=False, allow_blank=True),
    'recommandee': BooleenStrict(required=False),
})

PrefillSiteResponse = _ser('DevisPrefillSiteResponse', {
    'client': s.IntegerField(),
    'profil': s.DictField(allow_null=True),
})

# -------------------------------------------------------------- facture


@extend_schema_field({'type': 'integer', 'nullable': True,
                      'not': {'type': 'integer'}})
class _DevisNul(s.IntegerField):
    """``devis`` d'une facture NEUVE : toujours nul (VNT89)."""


class FactureCreationSerializer(FactureWriteSerializer):
    """CI #997 (2) — corps PUBLIÉ de ``POST factures/`` : une facture de
    devis ne naît que par « Facturer la vente » (VNT89, 400
    ``facture_de_devis``) — le schéma de création dit donc ``devis`` nul ;
    l'écriture reste ``FactureWriteSerializer`` (schéma seul)."""
    same_company_fields = tuple(
        c for c in FactureWriteSerializer.same_company_fields if c != 'devis')
    devis = _DevisNul(required=False, allow_null=True)


FactureAnnulerRequest = _ser('FactureAnnulerRequest', {
    'acompte': _ser('FactureAnnulerAcompte', {
        # VNT12 — ``garder_en_avance`` (contrat facture_annulation.json).
        'action': s.ChoiceField(
            choices=['transferer', 'rembourser', 'garder_en_avance'],
            required=False),
        'facture_cible': s.IntegerField(required=False),
    }, required=False),
})
#: ENF11 — « transferer » exige ``facture_cible`` (sinon 400 « La facture
#: cible est requise. ») ; les deux autres actions n'en portent pas.
CORPS_ANNULER_CIBLE_SI_TRANSFERT = {EXTENSION_CORPS_RESSERRE: {'properties': {
    'acompte': {'anyOf': [
        {'properties': {'action': {'enum': ['rembourser',
                                            'garder_en_avance']}}},
        {'not': {'required': ['action']}},
        {'required': ['facture_cible'],
         'properties': {'facture_cible': {'type': 'integer',
                                          'minimum': 1}}},
    ]}}}}
ExclureRelanceRequest = _ser('FactureExclureRelanceRequest', {
    'exclu': s.BooleanField(required=False),
})
FactureWhatsappRequest = _ser('FactureWhatsappRequest', {
    'modele': s.ChoiceField(choices=['facture', 'relance'], required=False),
    'langue': ChaineStricte(required=False, allow_blank=True),
})
FactureWhatsappResponse = _ser('FactureWhatsappResponse', {
    'wa_url': s.CharField(),
    'phone': s.CharField(),
    'message': s.CharField(),
    'url': s.CharField(),
})
LienPaiementRequest = _ser('FactureLienPaiementRequest', {
    # Liste blanche des fournisseurs qui savent ouvrir un lien (AFAC21).
    'provider': s.ChoiceField(choices=providers_lien_actifs(),
                              required=False),
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

# ------------------------------------------------------- relevé bancaire
ReleveDryRunRequest = _ser('ReleveImportDryRunRequest', {
    'file': s.FileField(),
})
ReleveCommitRequest = {
    'application/json': {
        'type': 'object',
        'required': ['token'],
        'properties': {
            # ENF11 — un jeton vide est refusé « Jeton de dry-run requis ».
            'token': {'type': 'string', 'minLength': 1, 'pattern': r'\S'},
            # Numéros de ligne validés, ou `{ligne, facture_reference}` pour
            # une ligne ambiguë résolue (AFAC6).
            'lignes': {
                'type': 'array',
                'items': {
                    'oneOf': [
                        {'type': 'integer'},
                        {'type': 'object',
                         'required': ['ligne'],
                         'properties': {
                             'ligne': {'type': 'integer'},
                             'facture_reference': {'type': 'string'}}},
                    ],
                },
            },
        },
    },
}

ReleveDryRunResponse = _ser('ReleveImportDryRunResponse', {
    'token': s.CharField(),
    'columns': s.DictField(child=s.CharField()),
    'unmapped': s.ListField(child=s.CharField()),
    'total_rows': s.IntegerField(),
    'preview': s.ListField(child=s.DictField()),
    'revue': s.ListField(child=s.DictField()),
    'matched': s.IntegerField(),
    'ambigus': s.IntegerField(),
    'already_paid': s.IntegerField(),
    'deja_importe': s.BooleanField(),
})
ReleveCommitResponse = _ser('ReleveImportCommitResponse', {
    'token': s.CharField(required=False),
    'created': s.IntegerField(),
    'skipped': s.IntegerField(),
    'errors': s.IntegerField(),
    'results': s.ListField(child=s.DictField()),
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
    # Strictement entre 0 et 100, deux décimales au plus — ENF11 : publié
    # DANS le motif (drf-spectacular n'émet aucune borne pour un
    # décimal-chaîne : « 0 » était conforme puis refusé).
    'variante_pct': s.RegexField(
        r'^0*(?:[1-9]\d?(?:\.\d{0,2})?|\.(?:[1-9]\d?|0[1-9]))$'),
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

ConceptionElectriqueResponse = _ser('DevisConceptionElectriqueResponse', {
    'chaines': s.ListField(child=s.DictField()),
    'conformite': s.DictField(),
    'ratio_dc_ac': s.FloatField(allow_null=True),
    'ratio_ac_dc': s.FloatField(allow_null=True),
    'protections': s.ListField(child=s.DictField()),
    'cables': s.ListField(child=s.DictField()),
    'bom': s.ListField(child=s.DictField()),
    'note': s.ListField(child=s.CharField()),
    'parametres': s.DictField(),
    'materiel': s.DictField(required=False),
    'version_moteur': s.CharField(required=False),
    'schema_version': s.IntegerField(required=False),
    'source_entree': s.DictField(required=False),
})

#: CI #997 — VALIDÉ par ``generer-pdf`` (``corps_valide``) : drapeaux
#: booléens JSON stricts, textes non blancs (``langue_sortie: ""`` passait).
PdfOptionsRequest = _ser('DevisPdfOptionsRequest', {
    'pdf_mode': s.ChoiceField(choices=['full', 'onepage'], required=False),
    'show_monthly': BooleenStrict(required=False),
    'devis_final': BooleenStrict(required=False),
    'include_etude': BooleenStrict(required=False),
    'include_calepinage': BooleenStrict(required=False, allow_null=True),
    'include_note_calcul': BooleenStrict(required=False),
    'kit_agrege': BooleenStrict(required=False),
    'variante_option': ChaineStricte(required=False),
    # Tri-état du moteur : ``null`` = auto (``clean_pdf_options``).
    'include_annexe_technique': s.JSONField(required=False, allow_null=True),
    'langue_sortie': ChaineStricte(required=False),
})

#: ENF11 (api-fuzz « rejected schema-compliant request ») — un montant
#: d'encaissement est STRICTEMENT positif (``"0"`` refusé « Le montant doit
#: être positif. ») : la règle est publiée dans le motif du décimal-chaîne
#: (drf-spectacular n'émet ni minimum ni maximum pour une chaîne), 12 chiffres
#: dont 2 décimales.
MOTIF_MONTANT_POSITIF = (r'^0*(?:[1-9]\d{0,9}(?:\.\d{0,2})?'
                         r'|\.(?:[1-9]\d?|0[1-9]))$')


def corps_resserre(regle):
    """Extension d'opération ``x-corps-resserre`` (``core.openapi_erreurs``) :
    ``regle`` est combinée en ``allOf`` au corps publié de CETTE opération."""
    return {EXTENSION_CORPS_RESSERRE: regle}


#: Le ``montant`` d'un encaissement est requis et strictement positif.
CORPS_MONTANT_POSITIF = corps_resserre({
    'required': ['montant'],
    'properties': {'montant': {'type': 'string',
                               'pattern': MOTIF_MONTANT_POSITIF}}})

#: AFAC32 — une note de débit porte des ``lignes`` (au moins une) OU un
#: ``montant`` HT strictement positif ; ``{}`` était « conforme » puis refusé
#: « Saisissez les lignes ou le montant de la note de débit. ».
#: CI #1000 — UN SEUL prédicat pour le ``montant`` HT et le ``taux_tva`` saisis :
#: la vue (``_montant_note_debit``) les applique en ``fullmatch`` sur la chaîne
#: BRUTE, ce motif est publié tel quel. ``Decimal(str)`` acceptait en plus
#: ``"1e1"``, ``"1_000"``, des blancs de bord et des chiffres non ASCII, que le
#: schéma déclarait invalides (« accepted schema-violating request »).
#: ``[0-9]`` et non ``\d`` : ``\d`` Python couvre aussi les chiffres Unicode.
MOTIF_MONTANT_NOTE_DEBIT = (r'^0*(?:[1-9][0-9]{0,7}(?:\.[0-9]{0,2})?'
                            r'|\.(?:[1-9][0-9]?|0[1-9]))$')
MOTIF_TAUX_NOTE_DEBIT = (r'^(?:|100(?:\.0{0,2})?'
                         r'|[0-9]{1,2}(?:\.[0-9]{0,2})?'
                         r'|\.[0-9]{1,2})$')
CORPS_NOTE_DEBIT_LIGNES_OU_MONTANT = corps_resserre({'anyOf': [
    {'required': ['lignes'],
     'properties': {'lignes': {'type': 'array', 'minItems': 1}}},
    {'required': ['montant'],
     'properties': {'montant': {'type': 'string',
                                'pattern': MOTIF_MONTANT_NOTE_DEBIT},
                    'taux_tva': {'type': 'string',
                                 'pattern': MOTIF_TAUX_NOTE_DEBIT}}},
]})

EnregistrerAvanceRequest = _ser('PaiementEnregistrerAvanceRequest', {
    'client': s.IntegerField(),
    'montant': s.RegexField(MOTIF_MONTANT_POSITIF),
    'date_paiement': s.DateField(required=False),
    # ENF11 — ce que la vue accepte : un mode de ``Paiement.Mode`` (sinon
    # 400 « Mode de paiement inconnu. »), une référence de 120 caractères.
    'mode': s.ChoiceField(choices=Paiement.Mode.choices, required=False),
    'reference': s.CharField(required=False, allow_blank=True,
                             max_length=120),
    'note': s.CharField(required=False, allow_blank=True),
})
VentilerRequest = _ser('PaiementVentilerRequest', {
    'facture': s.IntegerField(),
    'montant': s.DecimalField(max_digits=12, decimal_places=2),
})


# =============================================================== ENF11 — devis
# Corps et réponses RÉELS des actions de ``DevisViewSet`` que le fuzz a prises
# en défaut : sans déclaration, le schéma leur prêtait le sérialiseur du
# viewset (``Devis``) en entrée COMME en sortie.
#: Jeton d'édition optimiste (QJR545), optionnel sur toute écriture.
_JETON = s.CharField(required=False, allow_blank=True, allow_null=True)

ErreurDetail = _ser('DevisErreurDetail', {'detail': s.CharField()})
ErreurDevisFige = _ser('DevisErreurFige', {
    'detail': s.CharField(),
    'code': s.CharField(required=False),
})
ErreurGarde = _ser('DevisErreurGarde', {
    'detail': s.CharField(),
    'champ': s.CharField(required=False),
    'credit_hold': s.BooleanField(required=False),
    'sale_warning': s.BooleanField(required=False),
})

# -------------------------------------------------- composition / auto / layout
CompositionRequest = {
    'application/json': {
        'type': 'object',
        'description': (
            'Une puissance (`kwc`) OU un nombre de panneaux (`nb_panneaux`) '
            'est requis(e), strictement positif(ve).'),
        'properties': {
            'kwc': {'type': 'number', 'exclusiveMinimum': True,
                    'minimum': 0},
            'nb_panneaux': {'type': 'integer', 'minimum': 1},
            'panel_watt': {'type': 'number', 'exclusiveMinimum': True,
                           'minimum': 0},
            # CI #997 fuzz — les scénarios que la composition sait servir
            # (``creation_auto.SCENARIOS_DEMANDABLES`` ; vide = les deux) :
            # un autre texte était « conforme » puis refusé en 422.
            'scenario': {'type': 'string',
                         'enum': ['', 'sans', 'avec', 'les_deux']},
            'structure_produit_id': {'type': 'integer', 'nullable': True},
            'structure_type': {'type': 'string'},
            'taux_tva': {'type': 'number', 'minimum': 0, 'maximum': 100},
            'mppt_paires': {'type': 'integer', 'minimum': 1},
            'hors_reseau': {'type': 'boolean'},
            'lead': {'type': 'integer', 'nullable': True},
            'dimensionnement_avec': {
                'type': 'object',
                'properties': {
                    'nb_panneaux': {'type': 'number'},
                    'kwc': {'type': 'number'},
                    'batterie_kwh': {'type': 'number'},
                },
            },
        },
        'anyOf': [{'required': ['kwc']}, {'required': ['nb_panneaux']}],
    },
}
CompositionResponse = _ser('DevisCompositionResponse', {
    'lignes': s.ListField(child=s.DictField()),
    'scenario': s.CharField(allow_null=True),
    'nb_panneaux': s.IntegerField(),
    'panel_watt': s.FloatField(),
    'kwc_reel': s.FloatField(),
    'blocs': s.IntegerField(required=False),
    'variantes': s.BooleanField(required=False),
    'nb_panneaux_avec': s.IntegerField(required=False, allow_null=True),
    'kwc_reel_avec': s.FloatField(required=False, allow_null=True),
    'avertissements': s.ListField(child=s.CharField(), required=False),
    'marques_manquantes': s.ListField(child=s.CharField(), required=False),
})
ErreurComposition = _ser('DevisErreurComposition', {
    'detail': s.CharField(),
    'field': s.CharField(required=False, allow_null=True),
})


class NombreStrict(s.FloatField):
    """CI #997 fuzz — nombre JSON RÉEL (``"5"`` et ``true`` étaient lus par
    ``float()``), fini."""

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            self.fail('invalid')
        return super().to_internal_value(data)


def _pourcent_souple(**kwargs):
    """Pourcentage 0-100 à 2 décimales, CHAÎNE (l'écran envoie ``"0"``) ou
    NOMBRE JSON arrondi au centième (``DecimalSouple``), publié par LE motif
    de la remise d'en-tête (``conditions_ci.MOTIF_REMISE``, ``-0`` compris) :
    la règle de ``domain/bornes.pourcentage_saisi``, enfin publiée."""
    from ..domain.conditions_ci import MOTIF_REMISE, _decimal_borne
    classe = extend_schema_field(_decimal_borne(
        MOTIF_REMISE, 100, nullable=True))(
        type('PourcentSouple', (DecimalSouple,), {}))
    return classe(max_digits=5, decimal_places=2,
                  min_value=Decimal('0'), max_value=Decimal('100'),
                  required=False, allow_null=True, **kwargs)


AutoDevisRequest = _ser('DevisAutoRequest', {
    # CI #997 fuzz — corps validé tel que publié (la vue le relisait à la
    # main) ; « un lead OU un client » publié (``CORPS_LEAD_OU_CLIENT``).
    'lead': EntierStrict(required=False, allow_null=True, min_value=1),
    'client': EntierStrict(required=False, allow_null=True, min_value=1),
    'target_kwc': NombreStrict(required=False, allow_null=True),
    'scenario': ChaineStricte(required=False, allow_blank=True,
                              allow_null=True),
    'etude_params': s.DictField(required=False, allow_null=True),
    'taux_tva': _pourcent_souple(),
    'remise_globale': _pourcent_souple(),
    'structure_produit_id': EntierStrict(required=False, allow_null=True),
    'structure_type': ChaineStricte(required=False, allow_blank=True,
                                    allow_null=True),
})
#: CI #997 fuzz — un devis naît d'un LEAD ou d'un CLIENT (« Un client ou un
#: lead est requis. ») : règle publiée sur ``POST devis/`` et ``devis/auto/``.
CORPS_LEAD_OU_CLIENT = corps_resserre({'anyOf': [
    {'required': ['lead'], 'properties': {'lead': {'type': 'integer'}}},
    {'required': ['client'], 'properties': {'client': {'type': 'integer'}}},
]})
AutoDevisResponse = _ser('DevisAutoResponse', {
    'id': s.IntegerField(),
    'reference': s.CharField(),
    'statut': s.CharField(),
    'kwc': s.FloatField(allow_null=True),
    'nb_lignes': s.IntegerField(),
    'proposal_token': s.CharField(),
    'proposal_path': s.CharField(),
    'alertes': s.ListField(child=s.JSONField()),
})

FromLayoutRequest = _ser('DevisFromLayoutRequest', {
    'layout': s.DictField(),
    'lead': s.IntegerField(required=False, allow_null=True),
    'client': s.IntegerField(required=False, allow_null=True),
    'taux_tva': s.FloatField(required=False, allow_null=True),
    'remise_globale': s.FloatField(required=False, allow_null=True),
    'structure_produit_id': s.IntegerField(required=False, allow_null=True),
    'structure_type': s.CharField(required=False, allow_blank=True,
                                  allow_null=True),
    'calepinage': s.IntegerField(required=False, allow_null=True),
})
FromLayoutResponse = _ser('DevisFromLayoutResponse', {
    'id': s.IntegerField(),
    'reference': s.CharField(),
    'statut': s.CharField(),
    'proposal_token': s.CharField(),
    'proposal_path': s.CharField(),
    'avertissements': s.ListField(child=s.CharField()),
    'marques_manquantes': s.ListField(child=s.CharField()),
    'deduplicated': s.BooleanField(required=False),
})
ErreurFromLayout = _ser('DevisErreurFromLayout', {
    'detail': s.CharField(required=False),
    'errors': s.ListField(child=s.CharField(), required=False),
    'champ': s.CharField(required=False),
})

#: ``roof_layout`` : document de conception 3D (AreaRecord[] + result +
#: renderPlan) — objet libre à clés non préfixées ``_`` (cf.
#: ``resynchronisation._sans_cles_privees``).
LayoutRequest = {'application/json': {'type': 'object',
                                      'additionalProperties': True}}
LayoutResponse = _ser('DevisLayoutResponse', {
    'roof_layout': s.JSONField(allow_null=True),
})
SyncLayoutResponse = _ser('DevisSyncLayoutResponse', {
    'inchange': s.BooleanField(required=False),
    'panneaux': s.IntegerField(required=False),
    'kwc': s.FloatField(required=False),
    'scenario': s.CharField(required=False),
    'batterie': s.BooleanField(required=False),
    'lignes_modifiees': s.IntegerField(required=False),
    'lignes_ajoutees': s.IntegerField(required=False),
    'avertissements': s.ListField(child=s.CharField(), required=False),
    'electrique': s.DictField(required=False, allow_null=True),
})
ErreurSyncLayout = _ser('DevisErreurSyncLayout', {
    'detail': s.CharField(required=False),
    'revision_possible': s.BooleanField(required=False),
})

DesignContextResponse = _ser('DevisDesignContext', {
    'devis': s.DictField(),
    'geometrie': s.DictField(),
    'cible': s.DictField(),
    'cible_avec': s.DictField(required=False, allow_null=True),
    'carte': s.DictField(),
    'modifiable': s.BooleanField(),
    'raison_lecture_seule': s.CharField(allow_blank=True, allow_null=True),
    'avertissements': s.ListField(child=s.CharField()),
    'zones_types': s.DictField(required=False),
    'degagements': s.DictField(required=False),
})

RoofImageRequest = {
    'multipart/form-data': {
        'type': 'object',
        'properties': {'image': {'type': 'string', 'format': 'binary'}},
        'required': ['image'],
    },
}
#: PV47 — réponse de ``ajouter-boq-electrique`` (``domain/bordereau``) :
#: ``{creees, lignes, manques, deja_presentes}``, clés toujours présentes.
AjouterBoqResponse = _ser('DevisAjouterBoqResponse', {
    'creees': s.IntegerField(),
    'lignes': s.ListField(child=_ser('DevisBoqLigneCreee', {
        'designation': s.CharField(),
        'produit': s.IntegerField(allow_null=True),
        'quantite': s.FloatField(allow_null=True),
        'type_ligne': s.CharField(),
        'a_chiffrer': s.BooleanField(),
    })),
    'manques': s.ListField(child=_ser('DevisBoqManque', {
        'designation': s.CharField(),
        'quantite': s.FloatField(),
        'spec': s.JSONField(),
    })),
    'deja_presentes': s.ListField(child=s.CharField()),
})
RoofImageResponse = _ser('DevisRoofImageResponse', {
    'roof_image': s.CharField(),
    'url': s.CharField(),
})

SimulerRequest = _ser('DevisSimulerRequest', {
    'force_refresh': s.BooleanField(required=False),
})
SimulerResponse = _ser('DevisSimulerResponse', {
    'detail': s.CharField(),
    'job_id': s.CharField(),
    'status': s.CharField(),
    'zones': s.IntegerField(),
    'status_url': s.CharField(),
})

# ------------------------------------------------------------ atomic / lignes


class DevisAtomic(DevisWriteSerializer):
    """Corps de ``POST /devis/atomic/`` : les champs d'en-tête du devis (comme
    ``POST /devis/``) + ``lignes`` (au moins une) + ``etude_params`` (écrit
    par l'écrivain unique d'étude, pas par le sérialiseur d'en-tête)."""
    lignes = s.ListField(child=s.DictField(), min_length=1)
    etude_params = s.DictField(required=False, allow_null=True)

    class Meta(DevisWriteSerializer.Meta):
        fields = list(DevisWriteSerializer.Meta.fields) + ['lignes']


ReplaceLinesRequest = _ser('DevisReplaceLinesRequest', {
    'lignes': s.ListField(child=s.DictField(), min_length=1),
    'entete': s.DictField(required=False, allow_null=True),
    'etude_params': s.DictField(required=False, allow_null=True),
    'expected_updated_at': _JETON,
})

# --------------------------------------------------------------- cycle de vie
DeriveResponse = _ser('DevisDeriveResponse', {
    'devis': DevisSerializer(),
    'champs_repris': s.ListField(child=s.CharField()),
    'corrige_apres_envoi': s.BooleanField(),
    'avertissements': s.ListField(child=s.CharField()),
})

AccepterRequest = _ser('DevisAccepterRequest', {
    'nom': ChaineStricte(required=False, allow_blank=True),
    'date': ChaineStricte(required=False, allow_blank=True),
    'option': ChaineStricte(required=False, allow_blank=True),
    'entreprise': s.DictField(required=False, allow_null=True),
    'override_credit': BooleenStrict(required=False),
    'override_avertissement': BooleenStrict(required=False),
})
RefuserRequest = _ser('DevisRefuserRequest', {
    'motif': ChaineStricte(required=False, allow_blank=True),
    'note': ChaineStricte(required=False, allow_blank=True),
    'date': ChaineStricte(required=False, allow_blank=True),
    'marquer_lead_perdu': BooleenStrict(required=False),
})
#: Au moins un caractère non blanc (le serveur ``strip()`` puis refuse le vide).
_NON_BLANC = r'\S'
NoterRequest = _ser('DevisNoterRequest', {
    'body': s.RegexField(_NON_BLANC),
})
SavePresetRequest = _ser('DevisSavePresetRequest', {
    'nom': ChaineStricte(max_length=150),
    'description': ChaineStricte(required=False, allow_blank=True),
})

LotCreationRequest = _ser('DevisLotCreationRequest', {
    'nom_lot': s.CharField(),
    'adresse_site': s.CharField(required=False, allow_blank=True),
    'ordre': s.IntegerField(required=False),
    'lignes': s.ListField(child=s.IntegerField(), required=False),
})
LotsResponse = _ser('DevisLotsResponse', {
    'lots': s.ListField(child=s.DictField()),
    'hors_lot': s.JSONField(allow_null=True),
    'total_consolide': s.JSONField(allow_null=True),
})

HistoriqueConfigurationResponse = _ser('DevisHistoriqueConfiguration', {
    'snapshots': _ser('DevisConfigSnapshot', {
        'id': s.IntegerField(),
        'date': s.CharField(),
        'auteur': s.CharField(allow_null=True),
        'nb_lignes': s.IntegerField(),
        'contenu': s.DictField(),
    }, many=True),
    'diff': s.DictField(required=False),
})

# ------------------------------------------------------------ études / lecture
OverridesPatchRequest = {
    'application/json': {
        'type': 'object',
        'description': (
            'Carte `{chemin: valeur}` ou `{chemin: {valeur, origine?}}` '
            'fusionnée dans le registre. Liste blanche fermée (D12).'),
        'minProperties': 1,
        'additionalProperties': False,
        'properties': {
            chemin: {} for chemin in (
                'taille.nb_panneaux', 'taille.panel_watt', 'taille.kwc',
                'scenario', 'recommended_option', 'etude.jour_reference')
        },
    },
}
OverridesResponse = _ser('DevisOverridesResponse', {
    'overrides': s.DictField(),
    'effectif': s.DictField(),
    'lignes': s.DictField(),
    'updated_at': s.CharField(required=False, allow_null=True),
})
EtudeParamsGetResponse = _ser('DevisEtudeParamsResponse', {
    'etude_params': s.DictField(),
    'updated_at': s.CharField(required=False, allow_null=True),
})
EtudeParamsPatchRequest = {
    'application/json': {
        'type': 'object',
        'description': (
            "Clés d'étude à fusionner (une valeur `null` retire la clé) ; "
            '`expected_updated_at` : jeton optimiste optionnel.'),
        'minProperties': 1,
        'additionalProperties': True,
    },
}
OffresTaillesResponse = _ser('DevisOffresTailles', {
    'offres_tailles': s.DictField(allow_null=True),
    'editable': s.BooleanField(),
    'raison_non_editable': s.CharField(required=False),
    'applique': s.DictField(required=False),
    'updated_at': s.CharField(required=False, allow_null=True),
})
LectureClientResponse = _ser('DevisLectureClient', {
    'sections': s.DictField(),
    'friction': s.JSONField(allow_null=True),
})
SuperiorContactStatusResponse = _ser('DevisSuperiorContactStatus', {
    'requested': s.BooleanField(),
    'seen': s.BooleanField(required=False),
    'seen_by': s.ListField(child=s.CharField(), required=False),
    'requested_at': s.DateTimeField(required=False),
})
EtatPdfResponse = _ser('DevisEtatPdf', {
    'devis': s.IntegerField(),
    'statut': s.ChoiceField(choices=['pret', 'en_cours', 'echec']),
    'fichier_pdf': s.BooleanField(),
    'erreur': s.CharField(allow_null=True),
    'date': s.JSONField(allow_null=True),
})

EconomieResponse = _ser('DevisEconomie', {
    'horizon_ans': s.IntegerField(allow_null=True),
    'flux': s.ListField(child=s.DictField()),
    'van_mad': s.FloatField(allow_null=True),
    'tri_pct': s.FloatField(allow_null=True),
    'lcoe_mad_kwh': s.FloatField(allow_null=True),
    'retour_ans': s.FloatField(allow_null=True),
    'retour_actualise_ans': s.FloatField(allow_null=True),
    'hypotheses': s.ListField(child=s.DictField()),
    'omissions': s.ListField(child=s.DictField()),
})
_BLOC = dict(required=False, allow_null=True)
EconomieCiResponse = _ser('DevisEconomieCi', {
    'statut': s.CharField(),
    'motifs_omission': s.ListField(child=s.CharField()),
    'base': s.CharField(**_BLOC),
    'motif_base': s.CharField(**_BLOC),
    'tarif': s.DictField(**_BLOC),
    'economie_annee1': s.DictField(**_BLOC),
    'facture_avant': s.DictField(**_BLOC),
    'facture_apres': s.DictField(**_BLOC),
    'revente': s.DictField(**_BLOC),
    'flux_ht': s.DictField(**_BLOC),
    'flux_ttc': s.DictField(**_BLOC),
    'jalons': s.ListField(child=s.DictField(), **_BLOC),
    'jalons_ttc': s.ListField(child=s.DictField(), **_BLOC),
    'indicateurs': s.DictField(**_BLOC),
    'remplacements': s.ListField(child=s.DictField(), **_BLOC),
    'om': s.DictField(**_BLOC),
    'sensibilites': s.ListField(child=s.DictField(), **_BLOC),
    'financement': s.DictField(**_BLOC),
    'hypotheses': s.ListField(child=s.DictField(), **_BLOC),
    'omissions': s.ListField(child=s.DictField(), **_BLOC),
    'alertes_internes': s.ListField(child=s.DictField(), **_BLOC),
    'vue_interne': s.DictField(**_BLOC),
})
EconomiePompageResponse = _ser('DevisEconomiePompage', {
    'statut': s.CharField(),
    'publiable_client': s.BooleanField(),
    'motifs_non_publiable': s.ListField(child=s.CharField()),
    'cas': s.CharField(**_BLOC),
    'entrees_declarees': s.ListField(child=s.DictField(), **_BLOC),
    'depense_actuelle': s.DictField(**_BLOC),
    'charges_solaires': s.DictField(**_BLOC),
    'remplacements': s.ListField(child=s.DictField(), **_BLOC),
    'economie': s.DictField(**_BLOC),
    'couverture': s.DictField(**_BLOC),
    'mad_par_m3': s.DictField(**_BLOC),
    'sensibilite_carburant': s.ListField(child=s.DictField(), **_BLOC),
    'seuil_rentabilite_carburant': s.DictField(**_BLOC),
    'financement': s.DictField(**_BLOC),
    'coherence': s.ListField(child=s.DictField(), **_BLOC),
    'reperes_affiches': s.ListField(child=s.DictField(), **_BLOC),
    'omissions': s.ListField(child=s.DictField(), **_BLOC),
    'vue_interne': s.DictField(**_BLOC),
})
ErreurEconomie = _ser('DevisErreurEconomie', {
    'detail': s.CharField(),
    'champ': s.CharField(required=False, allow_null=True),
})

# --------------------------------------------------------------- facturation
#: CI #997 fuzz — un paiement DÉJÀ reçu (« Facturer », 0 à 5) publié tel que
#: ``domain/facturation_ops.valider_paiements_saisis`` le lit : montant
#: décimal-chaîne > 0 à 2 décimales au plus (10 chiffres entiers, colonne
#: 12,2), date ``AAAA-MM-JJ``, mode connu, référence de 120 signes au plus.
#: Une date FUTURE est un refus d'état (dépend du jour) : 409.
MOTIF_MONTANT_SAISI = (
    r'^(?:[1-9][0-9]{0,9}(?:\.[0-9]{0,2})?|0?\.(?:0[1-9]|[1-9][0-9]?))$')
PaiementDejaRecu = _ser('DevisFacturerCompletPaiementSaisi', {
    'montant': ChaineStricte(trim_whitespace=False, validators=[_MotifEntier(
        MOTIF_MONTANT_SAISI, message='Montant invalide.')]),
    'date_paiement': DateStricte(),
    'mode_paiement': s.ChoiceField(choices=[
        'especes', 'virement', 'cheque', 'carte', 'prelevement', 'autre']),
    'reference': ChaineStricte(required=False, allow_blank=True,
                               allow_null=True, max_length=120),
})
FacturerCompletRequest = _ser('DevisFacturerCompletRequest', {
    'paiements': s.ListField(child=PaiementDejaRecu, required=False,
                             max_length=5),
    'override_credit': BooleenStrict(required=False),
    'override_avertissement': BooleenStrict(required=False),
})
FacturerCompletResponse = _ser('DevisFacturerCompletResponse', {
    'facture_id': s.IntegerField(),
    'facture_reference': s.CharField(),
    'statut': s.CharField(),
    'total_ttc': s.CharField(),
    'montant_paye': s.CharField(),
    'montant_du': s.CharField(),
    'paiements': _ser('DevisFacturerCompletPaiement', {
        'id': s.IntegerField(),
        'montant': s.CharField(),
        'date_paiement': s.CharField(),
        'mode_paiement': s.CharField(),
        'reference': s.CharField(allow_blank=True),
    }, many=True),
})
# VNT31 — « Facturer la vente » (contrat ``devis_facturer.json``) : montants
# en TEXTE décimal, natures = ``Facture.TypeFacture``.
FacturerVenteRequest = _ser('DevisFacturerVenteRequest', {
    # acompte | intermediaire | solde | complete (validée par le service).
    'nature': ChaineStricte(),
    'montant_ttc': ChaineStricte(required=False, allow_null=True,
                                 allow_blank=True),
    'pourcentage': ChaineStricte(required=False, allow_null=True,
                                 allow_blank=True),
    'cle_attendue': ChaineStricte(required=False, allow_null=True,
                                  allow_blank=True),
    'libelle': ChaineStricte(required=False, allow_null=True,
                             allow_blank=True),
    'emettre': BooleenStrict(required=False),
    'paiements': s.ListField(child=s.DictField(), required=False,
                             max_length=5),
    'remplacer_brouillons': BooleenStrict(required=False),
    'utiliser_avances': BooleenStrict(required=False),
    'override_avertissement': BooleenStrict(required=False),
    # XFAC28 — responsable/admin : passe outre le blocage crédit à
    # l'émission (comme ``generer-facture``), journalisé.
    'override_credit': BooleenStrict(required=False),
})
FacturerVenteMontants = _ser('DevisFacturerVenteMontants', {
    cle: s.CharField() for cle in (
        'prix_convenu_ttc', 'emis_ttc', 'brouillons_ttc', 'paye_ttc',
        'reste_a_facturer_ttc', 'reste_a_payer_ttc')})
FacturerVenteResponse = _ser('DevisFacturerVenteResponse', {
    'facture': _ser('DevisFacturerVenteFacture', {
        'id': s.IntegerField(), 'reference': s.CharField(),
        'statut': s.CharField(), 'total_ttc': s.CharField(),
        'nature': s.CharField()}),
    'vente': FacturerVenteMontants,
})
FacturerVenteApercu = _ser('DevisFacturerVenteApercu', {
    'plan': _ser('DevisFacturerVentePlanLigne', {
        cle: s.CharField() for cle in (
            'cle', 'libelle', 'unite', 'valeur', 'montant_ttc', 'statut')},
        many=True),
    'prochaine': _ser('DevisFacturerVenteProchaine', {
        cle: s.CharField() for cle in ('cle', 'libelle', 'montant_ttc')},
        allow_null=True),
    'acompte_propose': s.CharField(),
    'vente': FacturerVenteMontants,
})
ErreurFacturerVente = _ser('DevisFacturerVenteErreur', {
    'detail': s.CharField(),
    'code': s.CharField(required=False),
})
GenererFactureRequest = _ser('DevisGenererFactureRequest', {
    # CI #997 fuzz — booléens STRICTS (``0`` était lu « faux » et accepté).
    'override_credit': BooleenStrict(required=False),
    'override_avertissement': BooleenStrict(required=False),
})


# ========================================================= ENF11 — facturation
# Bons de commande, factures, paiements, avoirs : corps et réponses RÉELS.
LigneLivraison = _ser('BonCommandeLigneLivraison', {
    'ligne_devis': s.IntegerField(),
    'quantite': s.DecimalField(max_digits=12, decimal_places=2,
                               min_value=Decimal('0.01')),
})
LivrerPartielRequest = _ser('BonCommandeLivrerPartielRequest', {
    'lignes': s.ListField(child=LigneLivraison, min_length=1),
    'date_livraison': s.DateField(required=False, allow_null=True),
    'note': s.CharField(required=False, allow_blank=True, max_length=255),
})
MarquerLivreJson = _ser('BonCommandeMarquerLivreJson', {
    'signataire': s.CharField(required=False, allow_blank=True),
    'note_pv': s.CharField(required=False, allow_blank=True),
})
MarquerLivreRequest = {
    'application/json': MarquerLivreJson,
    'multipart/form-data': {
        'type': 'object',
        'properties': {
            'signataire': {'type': 'string'},
            'note_pv': {'type': 'string'},
            'pv': {'type': 'string', 'format': 'binary'},
        },
    },
}

_MOTIFS_ABANDON = ['irrecouvrable', 'geste_commercial', 'ecart_reglement',
                   'liquidation', 'arrondi_caisse']


# CI #997 (5) — réponses d'ACTION : `FactureSerializer.to_representation` retire
# `situation_vente` / `prochaines_echeances` hors du détail (`_vente_pdf` → None) ;
# le schéma publié part donc de la forme LISTE (sans ces deux clés), jamais du détail.
class FactureAbandonnee(FactureListeSerializer):
    """Réponse de ``abandonner-solde`` : la facture + le montant soldé."""
    montant_abandonne = s.FloatField()


class FactureAbandonRepris(FactureListeSerializer):
    """Réponse de ``reprendre-abandon`` : la facture + l'abandon repris."""
    abandon_repris = s.IntegerField()
    montant_repris = s.CharField()


class FactureRelancee(FactureListeSerializer):
    """Réponse de ``relancer`` : la facture + l'e-mail éventuellement parti."""
    email_log_id = s.IntegerField(allow_null=True)


class FactureEmise(FactureListeSerializer):
    """Réponse de ``emettre`` : la facture + les anomalies légales éventuelles."""
    anomalies = s.ListField(child=s.CharField(), required=False)


class FactureCreeeDepuisBc(FactureListeSerializer):
    """Réponse de ``creer-facture`` : la facture + l'avertissement doux."""
    warnings = s.ListField(child=s.CharField(), required=False)


class FactureAnnulee(FactureListeSerializer):
    """Réponse de ``annuler`` (VNT4, ``facture_annulation.json``) : la
    facture + l'avoir de contre-passation (``null`` pour un brouillon)."""
    avoir = _ser('FactureAnnulationAvoir', {
        'id': s.IntegerField(), 'reference': s.CharField(),
        'montant': s.CharField()}, allow_null=True)


#: VNT14 — DELETE d'une facture refusé (409, ENF11 ConflitEtat) : pas un brouillon, ou
#: ``code: reference_legale`` (numéro légal remis en brouillon).
ErreurSuppressionFacture = _ser('FactureErreurSuppression', {
    'detail': s.CharField(), 'code': s.CharField(required=False)})


MarquerPayeeRequest = _ser('FactureMarquerPayeeRequest', {
    'motif': s.RegexField(_NON_BLANC),
})
AbandonnerSoldeRequest = _ser('FactureAbandonnerSoldeRequest', {
    'motif': s.ChoiceField(choices=_MOTIFS_ABANDON),
})
ReprendreAbandonRequest = _ser('FactureReprendreAbandonRequest', {
    'motif': s.RegexField(_NON_BLANC),
    'abandon': s.IntegerField(required=False, allow_null=True, min_value=1,
                              max_value=2 ** 31 - 1),
})
LibererRetenueRequest = _ser('FactureLibererRetenueRequest', {
    'date': s.DateField(),
})
ErreurRetenue = _ser('FactureErreurChamp', {
    'detail': s.CharField(),
    'champ': s.CharField(required=False),
    'code': s.CharField(required=False),
    'action_attendue': s.CharField(required=False),
})
EnvoyerEmailFactureRequest = _ser('FactureEnvoyerEmailRequest', {
    'to_email': ChaineStricte(required=False, allow_blank=True),
    'sujet': ChaineStricte(required=False, allow_blank=True),
    'corps': ChaineStricte(required=False, allow_blank=True),
    'attach_pdf': BooleenStrict(required=False),
})
EnvoyerEmailFactureResponse = _ser('FactureEnvoyerEmailResponse', {
    'detail': s.CharField(),
    'email_log_id': s.IntegerField(),
    'to_email': s.CharField(allow_blank=True, allow_null=True),
})
#: 400 de l'envoi : échec d'envoi (``detail`` + ``email_log_id``) OU corps
#: invalide (erreurs par champ de l'enveloppe commune) — d'où des clés toutes
#: facultatives, les autres clés (champs, ``error``) restant admises.
ErreurEnvoiEmail = _ser('FactureErreurEnvoiEmail', {
    'detail': s.CharField(required=False),
    'email_log_id': s.IntegerField(required=False),
})

# Tour 3 M1 — bornes = celles de ``_montants_ligne_corrective`` (vue
# facture), publiées DANS le motif du décimal-chaîne (drf-spectacular n'émet
# ni minimum ni maximum pour une chaîne) : un corps conforme au schéma n'est
# plus refusé en 400, un corps hors bornes l'est par le sérialiseur.
_MONTANT_LIGNE_MAX = Decimal('99999999.99')
_MOTIF_STRICT_POSITIF = r'^0*(?:[1-9]\d{0,7}(?:\.\d{0,2})?|\.(?:[1-9]\d?|0[1-9]))$'
_MOTIF_POSITIF = r'^(?:\d{1,8}(?:\.\d{0,2})?|\.\d{1,2})$'
_MOTIF_POURCENT = r'^(?:100(?:\.0{0,2})?|\d{1,2}(?:\.\d{0,2})?|\.\d{1,2})$'


def _decimal_publie(motif):
    """Classe ``DecimalField`` dont le schéma publié est ``motif``."""
    return extend_schema_field(
        {'type': 'string', 'format': 'decimal', 'pattern': motif})(
        type('DecimalBorne', (s.DecimalField,), {}))


_QuantiteLigne = _decimal_publie(_MOTIF_STRICT_POSITIF)
#: ENF11 — une ligne de facture saisie porte une quantité et un prix ≥ 0
#: (« La quantité ne peut pas être négative. », garde ``domain/bornes``) :
#: publiés sur les écritures de ``factures-lignes`` (le composant de la
#: réponse, partagé, ne change pas).
CORPS_LIGNE_FACTURE_POSITIVE = corps_resserre({'properties': {
    **{champ: {'type': 'string', 'pattern': _MOTIF_POSITIF}
       for champ in ('quantite', 'prix_unitaire')},
    # « La remise doit être comprise entre 0 et 100 %. »
    'remise': {'type': 'string', 'pattern': _MOTIF_POURCENT}}})
_MontantLigne = _decimal_publie(_MOTIF_POSITIF)
_PourcentLigne = _decimal_publie(_MOTIF_POURCENT)

#: ENF11 — règles d'ÉCRITURE d'une ligne de devis
#: (``LigneDevisSerializer.validate`` + garde ``domain/bornes``) publiées sur
#: ``devis-lignes`` : quantité / prix >= 0, remise 0-100, et un taux de TVA à
#: 0 % porte sa base légale (AGR217).
_ZERO_DECIMAL = r'^0*(?:\.0*)?$'
_REGLES_LIGNE_DEVIS = {
    'properties': {
        'quantite': {'type': 'string', 'pattern': _MOTIF_POSITIF},
        'prix_unitaire': {'type': 'string', 'pattern': _MOTIF_POSITIF},
        'remise': {'type': 'string', 'pattern': _MOTIF_POURCENT}},
    'anyOf': [
        {'properties': {'taux_tva': {'not': {'pattern': _ZERO_DECIMAL}}}},
        {'required': ['tva_base_legale'],
         'properties': {'tva_base_legale': {'type': 'string',
                                            'pattern': r'\S'}}},
    ],
}
CORPS_LIGNE_DEVIS_MODIF = corps_resserre(_REGLES_LIGNE_DEVIS)
#: Création / PUT : une ligne PRODUIT (type par défaut) référence un produit ;
#: une section ou une note porte un intitulé.
CORPS_LIGNE_DEVIS_ECRITURE = corps_resserre({'allOf': [
    _REGLES_LIGNE_DEVIS,
    {'anyOf': [
        {'required': ['type_ligne', 'designation'],
         'properties': {'type_ligne': {'enum': ['section', 'note']},
                        'designation': {'type': 'string', 'pattern': r'\S'}}},
        {'required': ['produit'],
         'properties': {'type_ligne': {'enum': ['produit']},
                        'produit': {'type': 'integer'}}},
    ]},
]})


def _ligne_corrective(nom):
    """Une ligne saisie d'avoir / de note de débit — instance NEUVE à chaque
    appel (un sérialiseur n'est l'enfant que d'un seul ``ListField``), sous
    un nom de composant propre (deux composants homonymes = avertissement)."""
    return _ser(nom, {
        'produit': EntierStrict(),
        'designation': ChaineStricte(),
        'quantite': _QuantiteLigne(max_digits=12, decimal_places=2,
                                   min_value=Decimal('0.01'),
                                   max_value=_MONTANT_LIGNE_MAX),
        'prix_unitaire': _MontantLigne(max_digits=12, decimal_places=2,
                                       min_value=Decimal('0'),
                                       max_value=_MONTANT_LIGNE_MAX),
        'remise': _PourcentLigne(max_digits=5, decimal_places=2,
                                 min_value=Decimal('0'),
                                 max_value=Decimal('100'), required=False),
        'taux_tva': _PourcentLigne(max_digits=5, decimal_places=2,
                                   min_value=Decimal('0'),
                                   max_value=Decimal('100'),
                                   required=False, allow_null=True),
    })


LigneAvoirCorrective = _ligne_corrective('FactureLigneAvoirCorrective')
CreerAvoirRequest = _ser('FactureCreerAvoirRequest', {
    'mode': s.ChoiceField(choices=['correction', 'contre_passation'],
                          required=False),
    'motif': ChaineStricte(required=False, allow_blank=True),
    'type': s.ChoiceField(
        choices=['correction', 'geste_commercial', 'retour'],
        required=False),
    'lignes': s.ListField(child=LigneAvoirCorrective, required=False,
                          allow_null=True),
})
CreerNoteDebitRequest = _ser('FactureCreerNoteDebitRequest', {
    # CI #1000 — textes STRICTS comme pour l'avoir : ``taux_tva: null`` (ou un
    # nombre) était « hors schéma » et pourtant accepté (201).
    'motif': ChaineStricte(required=False, allow_blank=True),
    # ENF11 — une ligne de note de débit est validée par
    # ``_montants_ligne_corrective`` comme une ligne d'avoir (désignation,
    # produit, bornes) : même forme publiée.
    'lignes': s.ListField(child=_ligne_corrective('FactureLigneNoteDebit'),
                          required=False),
    # AFAC32 — sans ``lignes`` : un montant HT + un taux (défaut : celui de
    # la facture). Publiés pour que la règle « lignes OU montant » le soit.
    'montant': ChaineStricte(required=False),
    'taux_tva': ChaineStricte(required=False, allow_blank=True),
})
LigneRetour = _ser('FactureLigneRetour', {
    # CI #997 fuzz — un id de produit (≥ 1, entier JSON) : ``0`` était
    # conforme puis refusé « produit requis ».
    'produit': EntierStrict(min_value=1),
    # ENF11 — « Ligne 1 : quantité > 0 requise. » : publiée > 0.
    'quantite': _QuantiteLigne(max_digits=12, decimal_places=2,
                               min_value=Decimal('0.01'),
                               max_value=_MONTANT_LIGNE_MAX),
})
RetourClientRequest = _ser('FactureRetourClientRequest', {
    # CI #997 fuzz — texte et booléen STRICTS (``"motif": 0``,
    # ``"restocker": 0`` étaient convertis) ; « non blanc » publié au sens
    # de DRF (``ChaineStricte``), plus le ``\S`` que la regex du schéma lit
    # autrement que ``str.strip``.
    'motif': ChaineStricte(),
    'lignes': s.ListField(child=LigneRetour, min_length=1),
    'restocker': BooleenStrict(required=False),
})

RelanceApercuResponse = _ser('FactureRelanceApercu', {
    'facture_id': s.IntegerField(),
    'facture_reference': s.CharField(),
    'montant_du': s.CharField(),
    'jours_retard': s.IntegerField(),
    'niveaux': s.ListField(child=s.DictField()),
    'niveau_suivant': s.DictField(allow_null=True),
    'deja_tous_envoyes': s.BooleanField(),
    'relances_envoyees': s.IntegerField(),
    'email_client': s.CharField(allow_blank=True, allow_null=True),
    'peut_envoyer_email': s.BooleanField(),
    'sujet': s.CharField(allow_blank=True),
    'message': s.CharField(allow_blank=True),
})
ArrondiCaisseResponse = _ser('FactureArrondiCaisse', {
    'applicable': s.BooleanField(),
    'montant_du': s.CharField(),
    'montant_arrondi': s.CharField(),
    'ecart': s.CharField(),
    'pas': s.CharField(),
})
ConsoliderRequest = _ser('FactureConsoliderRequest', {
    # CI #997 fuzz — ids entiers JSON (``"5"`` était relu par ``int()``).
    'devis_ids': s.ListField(child=EntierStrict(min_value=1),
                             min_length=2),
})
#: ENF11 — ``[5, 5]`` consolidait deux fois le même devis : ids DISTINCTS.
CORPS_DEVIS_IDS_UNIQUES = corps_resserre({
    'properties': {'devis_ids': {'type': 'array', 'uniqueItems': True}}})
#: CI #997 fuzz — montant encaissé tel que la vue l'ARRONDIT (au centime,
#: moitié vers le haut, ``quantize_mad``) : décimal-chaîne strictement
#: positif APRÈS arrondi (``0.005`` → 0,01 ; ``0.0049`` → 0 refusé), 9
#: chiffres entiers avec décimales libres (le total pré-rempli par l'écran
#: porte du bruit flottant) ou 10 chiffres et 2 décimales au plus (colonne
#: 12,2). Validé par ce MÊME motif, en entier et sans rognage.
MOTIF_MONTANT_ENCAISSE = (
    r'^(?:[1-9][0-9]{0,8}(?:\.[0-9]*)?|[1-9][0-9]{9}(?:\.[0-9]{0,2})?'
    r'|0?\.(?:0[1-9]|[1-9])[0-9]*|0?\.00[5-9][0-9]*)$')


EncaissementGroupeRequest = _ser('FactureEncaissementGroupeRequest', {
    # CI #997 fuzz — la vue lit ce corps VALIDÉ (elle le relisait à la main,
    # plus souplement que publié) : entiers, texte, date et décimaux STRICTS.
    'client': EntierStrict(min_value=1),
    'montant': ChaineStricte(trim_whitespace=False, validators=[_MotifEntier(
        MOTIF_MONTANT_ENCAISSE, message='Montant invalide.')]),
    'factures': s.ListField(child=EntierStrict(min_value=1), min_length=1),
    'mode': s.ChoiceField(
        choices=['especes', 'virement', 'cheque', 'carte', 'prelevement',
                 'autre'], required=False),
    'date': DateStricte(required=False),
    'reference': ChaineStricte(required=False, allow_blank=True,
                               max_length=120),
    # Clé = id d'une facture du lot (sinon 409), part en décimal-chaîne ;
    # une part ≤ 0 est ignorée.
    'repartition': s.DictField(child=DecimalStricte(
        max_digits=12, decimal_places=2), required=False, allow_null=True),
})
BulkRequest = _ser('FactureBulkRequest', {
    'action': s.ChoiceField(
        choices=['emettre', 'envoyer-email', 'generer-pdf', 'relancer']),
    # ENF11 — « La liste `ids` est requise et doit être non vide. »
    'ids': s.ListField(child=s.IntegerField(), min_length=1),
})
BulkResponse = {
    200: {
        'type': 'object',
        'description': 'Résultat par id de facture : `{id: {ok, detail}}`.',
        'additionalProperties': {
            'type': 'object',
            'properties': {
                'ok': {'type': 'boolean'},
                'detail': {'type': 'string'},
                'reference': {'type': 'string'},
                'task_id': {'type': 'string'},
            },
            'required': ['ok', 'detail'],
        },
    },
}
UblXml = {(200, 'application/xml'): OpenApiTypes.BINARY}
PdfBinaire = {(200, 'application/pdf'): OpenApiTypes.BINARY}
DgiConformiteResponse = _ser('FactureDgiConformite', {
    'conforme': s.BooleanField(),
    'problemes': s.ListField(child=s.JSONField()),
})
DgiTransmissionResponse = _ser('FactureDgiTransmission', {
    'dgi_statut': s.CharField(allow_blank=True, allow_null=True),
    'dgi_reference': s.CharField(allow_blank=True, allow_null=True),
    'dgi_motif_rejet': s.CharField(allow_blank=True, allow_null=True),
})


# ---------------------------------------------------------------- paiements
PaiementAvecRetenueResponse = _ser('PaiementAvecRetenueResponse', {
    'paiement': PaiementSerializer(),
    'retenue': RetenueSubieSerializer(),
    'facture': FactureSerializer(),
})
AttestationRecueRequest = _ser('PaiementAttestationRecueRequest', {
    'attestation_date': s.DateField(required=False),
    'attestation_fichier': s.CharField(required=False, allow_blank=True,
                                       max_length=500),
})
EnvoyerRecuRequest = _ser('PaiementEnvoyerRecuRequest', {
    'to_email': s.CharField(required=False, allow_blank=True,
                            allow_null=True),
})
EnvoyerRecuResponse = _ser('PaiementEnvoyerRecuResponse', {
    'statut': s.CharField(),
    'to_email': s.CharField(allow_blank=True, allow_null=True),
    'erreur': s.CharField(allow_blank=True, allow_null=True),
})
# CI #997 (2) — corps VALIDÉS par la vue (``corps_valide``) : texte, date et
# entier STRICTS (``motif: [null]`` → 500, ``date_rejet: ""`` → aujourd'hui).
RejeterPaiementRequest = _ser('PaiementRejeterRequest', {
    'motif': ChaineStricte(),
    'frais': DecimalSouple(max_digits=10, decimal_places=2, required=False,
                           allow_null=True),
    'date_rejet': DateStricte(required=False, allow_null=True),
})
AnnulerSaisieRequest = _ser('PaiementAnnulerSaisieRequest', {
    'motif': ChaineStricte(),
})
ReaffecterRequest = _ser('PaiementReaffecterRequest', {
    'facture_cible': EntierStrict(min_value=1),
})
_FACTURE_RESUME = _ser('PaiementReaffecterFacture', {
    'id': s.IntegerField(),
    'reference': s.CharField(),
    'montant_du': s.CharField(),
    'statut': s.CharField(),
})
ReaffecterResponse = _ser('PaiementReaffecterResponse', {
    'paiement': PaiementSerializer(),
    'facture_source': _FACTURE_RESUME,
    'facture_cible': _FACTURE_RESUME,
})
ErreurCode = _ser('PaiementErreurCode', {
    'detail': s.CharField(),
    'code': s.CharField(required=False),
})
NoteDebitAnnuleeResponse = _ser('NoteDebitAnnulationResponse', {
    'note_debit': NoteDebitSerializer(),
    'avoir': AvoirSerializer(),
    'cree': s.BooleanField(),
})

# --------------------------------------------------------- offres de tailles
OffreTailleCleRequest = _ser('DevisOffreTailleCleRequest', {
    'cle': s.ChoiceField(choices=['eco', 'recommande', 'max']),
    'expected_updated_at': _JETON,
})
#: CI #997 fuzz — ``offres-tailles/appliquer`` : SEULE « Recommandé »
#: s'applique au devis (Éco et Max étaient « conformes » puis TOUJOURS
#: refusées) ; jeton en texte STRICT (``0`` était relu « 0 »). Validé par la
#: vue avant toute autre garde.
OffreTailleAppliquerRequest = _ser('DevisOffreTailleAppliquerRequest', {
    'cle': ChoixDocumente(choices=['recommande'], error_messages={
        'invalid_choice': 'Seule la taille « Recommandé » s\'applique au '
                          'devis : « {input} » est une taille d\'exploration, '
                          'montrée au client à côté de l\'offre officielle.'}),
    'expected_updated_at': ChaineStricte(required=False, allow_blank=True,
                                         allow_null=True),
})
OffreTailleConfigRequest = {
    'application/json': {
        'type': 'object',
        'required': ['cle', 'config'],
        'properties': {
            'cle': {'type': 'string', 'enum': ['eco', 'recommande', 'max']},
            # ENTRÉES seulement : tout nombre dérivé ou clé inconnue = 400.
            'config': {
                'type': 'object',
                'minProperties': 1,
                'additionalProperties': False,
                'properties': {
                    'nb_panneaux': {'type': 'integer', 'minimum': 1,
                                    'maximum': 500},
                    'batterie_nb_modules': {'type': 'integer', 'minimum': 0,
                                            'maximum': 100},
                    'equipements': {'type': 'object',
                                    'additionalProperties': {
                                        'type': 'integer'}},
                },
            },
        },
    },
}

# ---------------------------------------------------------- plafond de crédit
CreditWarningResponse = _ser('ClientCreditWarning', {
    'plafond': s.CharField(allow_null=True),
    'encours': s.CharField(),
    'encours_avec_nouveau': s.CharField(allow_null=True),
    'depasse': s.BooleanField(),
    'depassera': s.BooleanField(allow_null=True),
    'message': s.CharField(allow_blank=True, allow_null=True),
    'recouvrement': _ser('ClientCreditWarningRecouvrement', {
        'a_jour': s.BooleanField(),
        'retard_max_jours': s.IntegerField(),
        'niveau_relance': s.DictField(allow_null=True),
        'encours_echu': s.CharField(),
    }),
})
