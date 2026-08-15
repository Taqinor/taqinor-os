from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsAdminRole
from apps.parametres.models import SettingsAuditLog
from .audit_plateforme import AuditPlateformeMixin
from .models import CustomFieldDef, CustomObjectDef, CustomRecord
from .serializers import (
    CustomFieldDefSerializer, CustomObjectDefSerializer, CustomRecordSerializer,
    _module_model,
)

# NTEXT2 — largeur/formatage suggérés par type de champ pour la vue LISTE
# auto-générée (purement indicatif, le front reste libre de les ajuster).
_COLONNE_LARGEUR_PAR_TYPE = {
    'text': 200, 'number': 110, 'date': 130, 'boolean': 90,
    'choice': 160, 'relation': 200, 'fichier': 160, 'ia': 220,
}
_COLONNE_FORMAT_PAR_TYPE = {
    'text': 'texte', 'number': 'nombre', 'date': 'date', 'boolean': 'oui_non',
    'choice': 'badge', 'relation': 'lien', 'fichier': 'fichier', 'ia': 'texte',
}


# NTEXT38 — champs dont la modification revient à « renommer » une définition
# verrouillée (la structure), par opposition aux réglages d'affichage (ordre,
# visible_liste…) qui restent librement ajustables même verrouillés.
_CHAMPS_STRUCTURE_CHAMP = ('code', 'libelle', 'module', 'type')
_CHAMPS_STRUCTURE_OBJET = ('code', 'libelle')


def _refus_verrouille(quoi, geste):
    """403 en français — jamais un 500 ni un silence."""
    return PermissionDenied(
        f'{quoi} est verrouillé : impossible de le {geste} tant qu\'il n\'est '
        f'pas déverrouillé (action « déverrouiller », réservée à '
        f'l\'administration).')


def _colonne_liste(field_def):
    """NTEXT2 — schéma d'une colonne de liste pour un CustomFieldDef donné."""
    return {
        'code': field_def.code,
        'libelle': field_def.libelle,
        'type': field_def.type,
        'largeur': _COLONNE_LARGEUR_PAR_TYPE.get(field_def.type, 150),
        'formatage': _COLONNE_FORMAT_PAR_TYPE.get(field_def.type, 'texte'),
    }


def _champ_formulaire(field_def):
    """NTEXT3 — schéma d'un champ de formulaire pour un CustomFieldDef donné.

    Les conditions XPLT15 (visible_si/requis_si/lecture_seule_si) sont
    renvoyées TELLES QUELLES (arbres core.rules) pour évaluation front ;
    requis_si reste de toute façon RE-VALIDÉ côté serveur par
    ``serializers.validate_custom_data`` — le front ne fait jamais foi seul."""
    conditions = field_def.conditions or {}
    return {
        'code': field_def.code,
        'libelle': field_def.libelle,
        'type': field_def.type,
        'obligatoire': field_def.obligatoire,
        'options': field_def.options or [],
        # XPLT14 — module cible d'un champ RELATION (ignoré sinon).
        'module_cible': field_def.relation_module
        if field_def.type == 'relation' else None,
        'visible_si': conditions.get('visible_si'),
        'requis_si': conditions.get('requis_si'),
        'lecture_seule_si': conditions.get('lecture_seule_si'),
    }


class CustomFieldDefViewSet(TenantMixin, viewsets.ModelViewSet):
    """Définitions de champs personnalisés (Paramètres). Lecture tout rôle
    (les formulaires en ont besoin), écriture admin. Filtre ?module=lead.
    Création/suppression d'une définition est journalisée au Journal d'audit
    des paramètres (section='champs')."""
    queryset = CustomFieldDef.objects.all()
    serializer_class = CustomFieldDefSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        module = self.request.query_params.get('module')
        if module:
            qs = qs.filter(module=module)
        return qs

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsAdminRole()]

    def _audit(self, label, instance, old=None, new=None):
        """Écrit une ligne d'audit company-scopée (section='champs')."""
        user = self.request.user
        SettingsAuditLog.log_change(
            company=getattr(user, 'company', None), user=user,
            section='champs', field=f'{instance.module}.{instance.code}',
            field_label=label, old=old, new=new,
        )

    def perform_create(self, serializer):
        # L818 — TenantMixin force la société côté serveur (jamais du corps).
        instance = serializer.save(company=self.request.user.company)
        self._audit('Champ personnalisé créé', instance,
                    old=None, new=instance.libelle)

    def perform_update(self, serializer):
        # NTEXT38 — un champ VERROUILLÉ ne se renomme pas : seules les
        # retouches d'affichage (ordre, visible_liste, actif…) passent.
        instance = serializer.instance
        if instance.verrouille:
            for champ in _CHAMPS_STRUCTURE_CHAMP:
                if champ in serializer.validated_data and \
                        serializer.validated_data[champ] != getattr(
                            instance, champ):
                    raise _refus_verrouille('Ce champ personnalisé', 'renommer')
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        # NTEXT38 — un champ VERROUILLÉ ne se supprime pas.
        if instance.verrouille:
            raise _refus_verrouille('Ce champ personnalisé', 'supprimer')
        # L818 — journaliser avant suppression (le custom_data des
        # enregistrements n'est pas touché : approche additive).
        self._audit('Champ personnalisé supprimé', instance,
                    old=instance.libelle, new=None)
        instance.delete()

    @action(detail=True, methods=['post'])
    def verrouiller(self, request, pk=None):
        """NTEXT38 — pose le verrou anti-casse (admin), et l'audite."""
        return self._basculer_verrou(True)

    @action(detail=True, methods=['post'])
    def deverrouiller(self, request, pk=None):
        """NTEXT38 — retire le verrou anti-casse (admin), et l'audite."""
        return self._basculer_verrou(False)

    def _basculer_verrou(self, verrouille):
        field_def = self.get_object()
        avant = field_def.verrouille
        if avant != verrouille:
            field_def.verrouille = verrouille
            field_def.save(update_fields=['verrouille'])
        self._audit(
            'Champ verrouillé' if verrouille else 'Champ déverrouillé',
            field_def,
            old='verrouillé' if avant else 'déverrouillé',
            new='verrouillé' if verrouille else 'déverrouillé')
        return Response(self.get_serializer(field_def).data)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """L813 — réordonne les définitions d'un module. Corps : une liste
        d'ids dans l'ordre voulu ({"ids": [3, 1, 2]}). `ordre` est posé selon
        la position ; seules les définitions de la société courante sont
        affectées."""
        ids = request.data.get('ids') or []
        if not isinstance(ids, list):
            return Response({'detail': 'Liste d’ids attendue.'}, status=400)
        defs = {d.id: d for d in self.get_queryset().filter(id__in=ids)}
        for position, def_id in enumerate(ids):
            d = defs.get(def_id)
            if d is not None and d.ordre != position:
                d.ordre = position
                d.save(update_fields=['ordre'])
        return Response({'ok': True, 'count': len(defs)})

    @action(detail=True, methods=['post'])
    def generer(self, request, pk=None):
        """XPLT17 — génère (bouton « Générer ») la valeur d'un champ IA pour
        UN enregistrement précis, à la demande UNIQUEMENT (jamais de
        génération de masse — pas de boucle sur un queryset ici).

        Corps : ``{"record_id": <id>}``. Le contexte de prompt est le
        ``custom_data``/``data`` ACTUEL de l'enregistrement (jamais les
        champs natifs sensibles — cohérent avec la garde `ia_prompt`).
        Écrit le résultat dans le champ (même clé que les autres types) et
        journalise le changement. NO-OP-safe : sans clé LLM, renvoie 200 avec
        ``configured=False`` et un message dégradé, n'écrit rien."""
        field_def = self.get_object()
        if field_def.type != 'ia':
            return Response(
                {'detail': "Ce champ n'est pas de type IA."}, status=400)
        record_id = request.data.get('record_id')
        if not record_id:
            return Response(
                {'detail': 'record_id requis.'}, status=400)

        from .services import generate_ia_value
        company = request.user.company

        if field_def.module.startswith('custom:'):
            object_code = field_def.module.split(':', 1)[1]
            record = get_object_or_404(
                CustomRecord, company=company, objet__code=object_code,
                pk=record_id)
            context = dict(record.data or {})
            result = generate_ia_value(field_def=field_def, context=context)
            if not result.available:
                return Response({'configured': result.configured,
                                 'ok': result.ok, 'error': result.error})
            old = (record.data or {}).get(field_def.code)
            record.data = {**(record.data or {}), field_def.code: result.text}
            record.save(update_fields=['data', 'date_modification'])
        else:
            model = _module_model(field_def.module)
            if model is None:
                return Response(
                    {'detail': 'Module cible introuvable.'}, status=400)
            record = get_object_or_404(model, company=company, pk=record_id)
            context = dict(getattr(record, 'custom_data', None) or {})
            result = generate_ia_value(field_def=field_def, context=context)
            if not result.available:
                return Response({'configured': result.configured,
                                 'ok': result.ok, 'error': result.error})
            old = (record.custom_data or {}).get(field_def.code)
            record.custom_data = {**(record.custom_data or {}),
                                  field_def.code: result.text}
            record.save(update_fields=['custom_data'])

        self._audit(f'Champ IA généré ({field_def.libelle})', field_def,
                    old=old, new=result.text)
        return Response({'configured': True, 'ok': True, 'value': result.text,
                         'source': result.source})


def _object_permission_code(object_code, action_kind):
    """XPLT16 — code de permission dynamique par objet, branché sur la grille
    roles existante (``Role.permissions`` reste un JSON de codes ; aucune
    migration côté ``apps.roles`` n'est nécessaire — un admin ajoute le code
    au rôle voulu). ``action_kind`` ∈ 'voir' | 'gerer'."""
    return f'custom_object.{object_code}.{action_kind}'


class CustomObjectDefViewSet(AuditPlateformeMixin, TenantMixin,
                             viewsets.ModelViewSet):
    """Objets personnalisés no-code (Paramètres). Lecture tout rôle, écriture
    admin — comme les définitions de champs dont ils réutilisent le
    mécanisme.

    NTEXT36 — toute création/modification/suppression laisse une ligne dans le
    Journal d'audit des paramètres (section='plateforme')."""
    queryset = CustomObjectDef.objects.all()
    serializer_class = CustomObjectDefSerializer
    audit_plateforme_cible = 'objet'
    audit_plateforme_nom = 'Objet personnalisé'

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'objets_catalogue'):
            return [IsAnyRole()]
        return [IsAdminRole()]

    # ── NTEXT38 — verrou anti-casse ────────────────────────────────────────

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.verrouille:
            for champ in _CHAMPS_STRUCTURE_OBJET:
                if champ in serializer.validated_data and \
                        serializer.validated_data[champ] != getattr(
                            instance, champ):
                    raise _refus_verrouille('Cet objet personnalisé',
                                            'renommer')
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        if instance.verrouille:
            raise _refus_verrouille('Cet objet personnalisé', 'supprimer')
        super().perform_destroy(instance)

    @action(detail=True, methods=['post'])
    def verrouiller(self, request, pk=None):
        """NTEXT38 — pose le verrou anti-casse (admin), et l'audite."""
        return self._basculer_verrou(True)

    @action(detail=True, methods=['post'])
    def deverrouiller(self, request, pk=None):
        """NTEXT38 — retire le verrou anti-casse (admin), et l'audite."""
        return self._basculer_verrou(False)

    def _basculer_verrou(self, verrouille):
        objet = self.get_object()
        avant = objet.verrouille
        if avant != verrouille:
            objet.verrouille = verrouille
            objet.save(update_fields=['verrouille'])
        self._journaliser_plateforme(
            objet,
            'Objet personnalisé verrouillé' if verrouille
            else 'Objet personnalisé déverrouillé',
            old='verrouillé' if avant else 'déverrouillé',
            new='verrouillé' if verrouille else 'déverrouillé')
        return Response(self.get_serializer(objet).data)

    # Exposées par des routes DÉDIÉES (``urls.py``) et non par le routeur :
    # le catalogue vit à ``customfields/objets-catalogue/``, pas sous
    # ``objects/`` (il ne décrit pas un objet existant de la société).
    def objets_catalogue(self, request):
        """NTEXT34 — modèles d'objets prêts à l'emploi + état d'installation.

        ``deja_installe`` dit si la société possède déjà un objet portant ce
        code : l'écran peut proposer « Installer » ou « Déjà installé » sans
        second appel.
        """
        from .catalogue import CATALOGUE

        company = request.user.company
        installes = set(
            CustomObjectDef.objects.filter(company=company)
            .values_list('code', flat=True))
        return Response({'modeles': [
            {
                'code': modele['code'],
                'libelle': modele['libelle'],
                'icone': modele.get('icone', ''),
                'description': modele.get('description', ''),
                'champs': [
                    {'code': champ['code'], 'libelle': champ['libelle'],
                     'type': champ.get('type', 'text'),
                     'obligatoire': champ.get('obligatoire', False)}
                    for champ in modele.get('champs') or []
                ],
                'deja_installe': modele['code'] in installes,
            }
            for modele in CATALOGUE
        ]})

    def installer_modele_catalogue(self, request, code=None):
        """NTEXT34 — installe un modèle du catalogue pour la société (admin).

        Idempotent : ré-installer ne duplique rien et n'écrase aucune
        personnalisation locale (ni les enregistrements saisis).
        """
        from .catalogue import installer_modele, modele_par_code

        modele = modele_par_code(code)
        if modele is None:
            return Response(
                {'detail': f'Modèle « {code} » inconnu du catalogue.'},
                status=404)
        objet, cree, champs_crees = installer_modele(
            request.user.company, modele, created_by=request.user)
        return Response({
            'objet': CustomObjectDefSerializer(objet).data,
            'cree': cree,
            'champs_crees': champs_crees,
        }, status=201 if cree else 200)


class CustomRecordViewSet(TenantMixin, viewsets.ModelViewSet):
    """Enregistrements d'un objet personnalisé — CRUD dynamique scopé par
    ``object_code`` (segment d'URL), jamais par le corps. Un rôle sans la
    permission ``custom_object.<code>.voir``/``gerer`` ne voit/n'écrit rien
    (compat : un compte hérité sans rôle fin — ``role`` NULL — passe comme les
    autres écrans de l'ERP, cf. ``IsAnyRole``/``IsAdminRole`` ; la permission
    par objet est un raffinement OPT-IN posé par l'admin sur les rôles fins)."""
    serializer_class = CustomRecordSerializer

    def _objet(self):
        company = self.request.user.company
        return get_object_or_404(
            CustomObjectDef, company=company,
            code=self.kwargs['object_code'], actif=True)

    def _check_object_permission(self, action_kind):
        user = self.request.user
        role = getattr(user, 'role', None)
        if user.is_superuser or role is None:
            return  # compat : superuser ou compte hérité sans rôle fin.
        code = _object_permission_code(self.kwargs['object_code'], action_kind)
        if not user.has_erp_permission(code):
            raise PermissionDenied(
                "Vous n'avez pas accès à cet objet personnalisé.")

    def get_queryset(self):
        objet = self._objet()
        self._check_object_permission('voir')
        return CustomRecord.objects.filter(
            company=self.request.user.company, objet=objet)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['objet'] = self._objet()
        return ctx

    def perform_create(self, serializer):
        self._check_object_permission('gerer')
        serializer.save(company=self.request.user.company,
                        objet=self._objet(), created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_object_permission('gerer')
        serializer.save(company=self.request.user.company)

    def perform_destroy(self, instance):
        self._check_object_permission('gerer')
        instance.delete()

    def vue_liste(self, request, *args, **kwargs):
        """NTEXT2 — schéma de liste auto-générée (colonnes ``visible_liste``)
        + les données paginées de l'objet. Multi-tenant strict : la société
        vient de ``request.user`` (via ``_objet``/``get_queryset``), jamais du
        corps ni de l'URL au-delà du ``object_code``."""
        objet = self._objet()
        self._check_object_permission('voir')
        champs = CustomFieldDef.objects.filter(
            company=request.user.company, module=objet.field_module,
            actif=True, visible_liste=True).order_by('ordre', 'libelle')
        colonnes = [_colonne_liste(c) for c in champs]

        queryset = CustomRecord.objects.filter(
            company=request.user.company, objet=objet)
        page = self.paginate_queryset(queryset)
        objects = page if page is not None else list(queryset)
        serializer = CustomRecordSerializer(objects, many=True)
        if page is not None:
            paginated = self.get_paginated_response(serializer.data)
            data = dict(paginated.data)
        else:
            data = {'count': len(objects), 'next': None,
                    'previous': None, 'results': serializer.data}
        data['colonnes'] = colonnes
        return Response(data)

    def vue_formulaire(self, request, *args, **kwargs):
        """NTEXT3 — schéma de formulaire auto-généré (tous les champs actifs
        de l'objet, ordonnés) pour un rendu no-code du formulaire de saisie."""
        objet = self._objet()
        self._check_object_permission('voir')
        champs = CustomFieldDef.objects.filter(
            company=request.user.company, module=objet.field_module,
            actif=True).order_by('ordre', 'libelle')
        return Response({'champs': [_champ_formulaire(c) for c in champs]})
