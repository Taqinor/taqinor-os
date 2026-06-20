"""Vues du profil entreprise (lecture + mise à jour, avec audit N55).

Domaine « Société & identité / Devis & logique métier ». Extrait de l'ancien
``views.py`` sans aucun changement d'endpoint, de permission ni de
comportement."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole
from .models import SettingsAuditLog
from .serializers import CompanyProfileSerializer
from .views_common import _audit_company, _profile


# Champs du profil entreprise suivis par l'audit (N55) : libellé FR par champ.
_PROFILE_AUDIT_FIELDS = {
    'nom': 'Nom',
    'adresse': 'Adresse',
    'email': 'Email',
    'telephone': 'Téléphone',
    'siret': 'SIRET',
    'tva_intra': 'TVA intra',
    'ice': 'ICE',
    'identifiant_fiscal': 'Identifiant fiscal',
    'rc': 'Registre de commerce',
    'patente': 'Patente',
    'cnss': 'CNSS',
    'rib': 'RIB',
    'banque': 'Banque',
    'instructions_paiement': 'Instructions de paiement',
    'conditions_generales': 'Conditions générales',
    'couleur_principale': 'Couleur principale',
    'responsable_defaut_leads': 'Responsable par défaut des leads',
    'default_installer': 'Installateur par défaut',
    'payment_terms': 'Échéancier de paiement',
    'quote_validity_days': 'Validité du devis (jours)',
    'agricole_pump_hours': 'Heures de pompage par défaut',
    'doc_prefixes': 'Préfixes de numérotation',
    'doc_numbering': 'Numérotation (largeur / réinitialisation)',
    'tva_standard': 'TVA standard',
    'tva_panneaux': 'TVA panneaux',
    'onee_tarif_kwh': 'Tarif ONEE (kWh)',
    'productible_kwh_kwc': 'Productible (kWh/kWc)',
    'discount_approval_threshold': "Seuil d'approbation de remise",
    'rendement_global': 'Rendement global',
    'panneaux_par_900mad': 'Panneaux par tranche de 900 MAD',
    'prix_cible_kwc_defaut': 'Prix cible /kWc par défaut',
    'remise_max_pct': 'Limite de remise (%)',
    'commission_mode': 'Commission — mode',
    'commission_valeur': 'Commission — valeur',
    'referral_enabled': 'Parrainage activé',
    'referral_reward': 'Parrainage — récompense par défaut',
    # Module d'exécution terrain (F9–F20) — interfaces swappables + seuil F12.
    'ocr_serie_provider': 'Fournisseur OCR n° de série (F9)',
    'transcription_provider': 'Fournisseur de transcription (F14)',
    'photo_qa_provider': 'Fournisseur QA photo IA (F20)',
    'overage_seuil_pct': 'Seuil de dépassement consommation (%) (F12)',
}


def _audit_profile_changes(request, profile, before):
    """Écrit une ligne SettingsAuditLog par champ de profil modifié.

    `before` est un dict {field: valeur} capturé AVANT save ; on compare aux
    valeurs APRÈS save et on journalise chaque écart (ancien→nouveau)."""
    company = _audit_company(request)
    for field, label in _PROFILE_AUDIT_FIELDS.items():
        old = before.get(field)
        new = getattr(profile, field, None)
        if old == new:
            continue
        SettingsAuditLog.log_change(
            company=company, user=request.user, section='profil',
            field=field, field_label=label, old=old, new=new,
        )


@api_view(['GET'])
@permission_classes([IsAnyRole])
def get_profile(request):
    profile = _profile(request)
    return Response(CompanyProfileSerializer(profile).data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminOrResponsableTier])
def update_profile(request):
    profile = _profile(request)
    partial = request.method == 'PATCH'
    # Capture l'état AVANT save pour l'audit (N55).
    before = {f: getattr(profile, f, None) for f in _PROFILE_AUDIT_FIELDS}
    serializer = CompanyProfileSerializer(
        profile, data=request.data, partial=partial,
        context={'request': request},
    )
    serializer.is_valid(raise_exception=True)
    updated = serializer.save()
    _audit_profile_changes(request, updated, before)
    return Response(CompanyProfileSerializer(updated).data)
