"""FG24 — export/import de la CONFIGURATION entre sociétés.

Distinct d'``ExportSauvegarde`` (données métier) : on n'exporte QUE de la
configuration reproductible — profil (réglages, jamais les secrets/clés/logo),
rôles personnalisés, modèles de message, règles d'automatisation (sans état
d'exécution), surcharges de statut, textes de documents. JAMAIS de données
métier (clients, devis, stock…), JAMAIS de secrets (RIB, providers OCR, etc.).

Import ADDITIF, admin uniquement, company-scopé (la cible est TOUJOURS la
société de l'appelant, jamais lue du corps). Deux modes :

* ``merge`` (défaut) — crée ce qui manque, NE touche PAS l'existant ;
* ``overwrite`` — crée le manquant ET met à jour l'existant (par clé naturelle).

Les types d'intervention / étapes de checklist (app ``installations``) sont
HORS périmètre de cet outil : ils ont leur propre amorçage et ne sont pas
touchés ici (on ne franchit pas la frontière d'une autre app pour les écrire).
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAdminRole

from .models import CompanyProfile, MessageTemplate
from .models_statuses import StatutConfig
from .models_documents import DocumentTemplates

# Champs de profil EXPORTABLES — réglages métier reproductibles uniquement.
# Volontairement SANS : identité légale (ice/rc/cnss…), coordonnées, secrets
# (rib/banque/providers), clés d'objets (logo/signature), responsables par
# défaut (FK propres à la société source).
PROFILE_CONFIG_FIELDS = [
    'couleur_principale', 'payment_terms', 'quote_validity_days',
    'agricole_pump_hours', 'doc_prefixes', 'doc_numbering',
    'tva_standard', 'tva_panneaux', 'onee_tarif_kwh', 'productible_kwh_kwc',
    'rendement_global', 'panneaux_par_900mad', 'prix_cible_kwc_defaut',
    'remise_max_pct', 'discount_approval_threshold',
    'seuil_regime_declaration_kwc', 'seuil_regime_anre_kwc',
    'devise_defaut', 'lead_sla_hours', 'overage_seuil_pct',
    # FG22 — politique de sécurité (réglages, pas de secret).
    'password_min_length', 'password_require_complexity',
    'lockout_max_attempts', 'lockout_duration_minutes', 'password_expiry_days',
]

DOCUMENT_TEMPLATE_FIELDS = [
    'validite_badge_p1', 'validite_onepage', 'cgv_titre', 'cgv_bullets',
    'garantie_titre', 'garantie_detail', 'garantie_perf_label',
    'bpa_titre',
]

CONFIG_VERSION = 1


def _serialize_profile(profile):
    if profile is None:
        return {}
    return {f: _jsonable(getattr(profile, f, None))
            for f in PROFILE_CONFIG_FIELDS}


def _serialize_document_templates(company):
    row = DocumentTemplates.objects.filter(company=company).first()
    if row is None:
        return {}
    return {f: _jsonable(getattr(row, f, None))
            for f in DOCUMENT_TEMPLATE_FIELDS}


def _jsonable(value):
    from decimal import Decimal
    if isinstance(value, Decimal):
        return str(value)
    return value


def _serialize_roles(company):
    from apps.roles.models import Role
    out = []
    for r in Role.objects.filter(company=company):
        out.append({
            'nom': r.nom,
            'permissions': list(r.permissions or []),
            'est_systeme': r.est_systeme,
        })
    return out


def _serialize_message_templates(company):
    return [
        {'cle': m.cle, 'corps_fr': m.corps_fr, 'corps_darija': m.corps_darija}
        for m in MessageTemplate.objects.filter(company=company)
    ]


def _serialize_automation_rules(company):
    from apps.automation.models import AutomationRule
    out = []
    for r in AutomationRule.objects.filter(company=company):
        out.append({
            'nom': r.nom,
            'enabled': r.enabled,
            'trigger_type': r.trigger_type,
            'trigger_config': r.trigger_config,
            'action_type': r.action_type,
            'action_config': r.action_config,
            'requires_approval': r.requires_approval,
            'approval_threshold': _jsonable(r.approval_threshold),
            'ordre': r.ordre,
        })
    return out


def _serialize_statuts(company):
    return [
        {'domaine': s.domaine, 'cle': s.cle, 'libelle': s.libelle,
         'ordre': s.ordre, 'actif': s.actif}
        for s in StatutConfig.objects.filter(company=company)
    ]


@api_view(['GET'])
@permission_classes([IsAdminOrResponsableTier])
def config_export(request):
    """Exporte la configuration de la société de l'appelant (JSON)."""
    company = request.user.company if request.user.company_id else None
    if company is None:
        return Response({'detail': 'Aucune société.'}, status=400)
    profile = CompanyProfile.objects.filter(company=company).first()
    bundle = {
        'version': CONFIG_VERSION,
        'profile': _serialize_profile(profile),
        'document_templates': _serialize_document_templates(company),
        'roles': _serialize_roles(company),
        'message_templates': _serialize_message_templates(company),
        'automation_rules': _serialize_automation_rules(company),
        'statuts': _serialize_statuts(company),
    }
    return Response(bundle)


def _import_profile(company, data, overwrite):
    profile = CompanyProfile.get(company)
    changed = []
    for f in PROFILE_CONFIG_FIELDS:
        if f not in data:
            continue
        # En merge, on ne touche que les champs encore au défaut ? Trop fragile.
        # Politique simple : merge n'écrase JAMAIS un profil existant déjà créé ;
        # overwrite applique. Comme un profil existe toujours (get_or_create),
        # on n'applique le profil qu'en mode overwrite.
        if not overwrite:
            continue
        setattr(profile, f, data[f])
        changed.append(f)
    if changed:
        profile.save()
    return len(changed)


def _import_document_templates(company, data, overwrite):
    if not data or not overwrite:
        return 0
    row, _ = DocumentTemplates.objects.get_or_create(company=company)
    changed = []
    for f in DOCUMENT_TEMPLATE_FIELDS:
        if f in data:
            setattr(row, f, data[f])
            changed.append(f)
    if changed:
        row.save()
    return len(changed)


def _import_roles(company, rows, overwrite):
    from apps.roles.models import Role
    created = updated = 0
    for r in rows or []:
        nom = (r.get('nom') or '').strip()
        if not nom:
            continue
        # On ne réécrit JAMAIS les rôles système (perms canoniques gérées par
        # init_roles) — on n'importe que des rôles personnalisés.
        if r.get('est_systeme'):
            continue
        existing = Role.objects.filter(company=company, nom=nom).first()
        if existing is None:
            Role.objects.create(
                company=company, nom=nom,
                permissions=list(r.get('permissions') or []),
                est_systeme=False)
            created += 1
        elif overwrite and not existing.est_systeme:
            existing.permissions = list(r.get('permissions') or [])
            existing.save(update_fields=['permissions'])
            updated += 1
    return created, updated


def _import_message_templates(company, rows, overwrite):
    valid = {c.value for c in MessageTemplate.Cle}
    created = updated = 0
    for r in rows or []:
        cle = r.get('cle')
        if cle not in valid:
            continue
        existing = MessageTemplate.objects.filter(
            company=company, cle=cle).first()
        if existing is None:
            MessageTemplate.objects.create(
                company=company, cle=cle,
                corps_fr=r.get('corps_fr', '') or '',
                corps_darija=r.get('corps_darija', '') or '')
            created += 1
        elif overwrite:
            existing.corps_fr = r.get('corps_fr', '') or ''
            existing.corps_darija = r.get('corps_darija', '') or ''
            existing.save(update_fields=['corps_fr', 'corps_darija'])
            updated += 1
    return created, updated


def _import_automation_rules(company, rows, overwrite):
    from apps.automation.models import AutomationRule, ActionType, TriggerType
    valid_trig = {c.value for c in TriggerType}
    valid_act = {c.value for c in ActionType}
    created = updated = 0
    for r in rows or []:
        nom = (r.get('nom') or '').strip()
        trig = r.get('trigger_type')
        act = r.get('action_type')
        if not nom or trig not in valid_trig or act not in valid_act:
            continue
        existing = AutomationRule.objects.filter(
            company=company, nom=nom).first()
        payload = dict(
            enabled=bool(r.get('enabled', True)),
            trigger_type=trig,
            trigger_config=r.get('trigger_config') or {},
            action_type=act,
            action_config=r.get('action_config') or {},
            requires_approval=bool(r.get('requires_approval', False)),
            approval_threshold=r.get('approval_threshold'),
            ordre=r.get('ordre') or 0,
        )
        if existing is None:
            AutomationRule.objects.create(company=company, nom=nom, **payload)
            created += 1
        elif overwrite:
            for k, v in payload.items():
                setattr(existing, k, v)
            existing.save()
            updated += 1
    return created, updated


def _import_statuts(company, rows, overwrite):
    from .statuses_defaults import VALID_DOMAINES, default_keys
    created = updated = 0
    for r in rows or []:
        domaine = r.get('domaine')
        cle = r.get('cle')
        if domaine not in VALID_DOMAINES or cle not in default_keys(domaine):
            continue
        existing = StatutConfig.objects.filter(
            company=company, domaine=domaine, cle=cle).first()
        if existing is None:
            StatutConfig.objects.create(
                company=company, domaine=domaine, cle=cle,
                libelle=r.get('libelle', '') or '',
                ordre=r.get('ordre') or 0, actif=bool(r.get('actif', True)))
            created += 1
        elif overwrite:
            existing.libelle = r.get('libelle', '') or ''
            existing.ordre = r.get('ordre') or 0
            existing.actif = bool(r.get('actif', True))
            existing.save(update_fields=['libelle', 'ordre', 'actif'])
            updated += 1
    return created, updated


@api_view(['POST'])
@permission_classes([IsAdminRole])
def config_import(request):
    """Importe une configuration dans la société de l'appelant (additif).

    Corps : le bundle exporté. ``?mode=merge`` (défaut) ou ``?mode=overwrite``.
    La société cible est TOUJOURS celle de l'appelant (jamais lue du corps)."""
    company = request.user.company if request.user.company_id else None
    if company is None:
        return Response({'detail': 'Aucune société.'}, status=400)
    data = request.data if isinstance(request.data, dict) else {}
    overwrite = request.query_params.get('mode') == 'overwrite'

    roles_c, roles_u = _import_roles(company, data.get('roles'), overwrite)
    msg_c, msg_u = _import_message_templates(
        company, data.get('message_templates'), overwrite)
    rule_c, rule_u = _import_automation_rules(
        company, data.get('automation_rules'), overwrite)
    stat_c, stat_u = _import_statuts(company, data.get('statuts'), overwrite)
    profile_changed = _import_profile(
        company, data.get('profile') or {}, overwrite)
    doc_changed = _import_document_templates(
        company, data.get('document_templates') or {}, overwrite)

    return Response({
        'mode': 'overwrite' if overwrite else 'merge',
        'roles': {'created': roles_c, 'updated': roles_u},
        'message_templates': {'created': msg_c, 'updated': msg_u},
        'automation_rules': {'created': rule_c, 'updated': rule_u},
        'statuts': {'created': stat_c, 'updated': stat_u},
        'profile_fields_changed': profile_changed,
        'document_template_fields_changed': doc_changed,
    })
