"""CRX12 — primitive ``CompanyScopedPrimaryKeyRelatedField`` (fondation core).

Prouve les quatre propriétés attendues de la primitive :

1. **Isolation** — un id appartenant à une AUTRE société est refusé.
2. **Aucun oracle d'existence** — le refus porte EXACTEMENT le même code/gabarit
   d'erreur qu'un id qui n'existe nulle part : impossible de distinguer « existe
   chez le voisin » de « n'existe pas ».
3. **Non-régression** — sans requête dans le contexte (rendu serveur/interne),
   pour un anonyme, pour un superuser plateforme SANS société, ou quand le
   modèle cible n'a pas de ``company``, le queryset est renvoyé INCHANGÉ.
4. **Composition** — ``many=True`` et la base-serializer optionnelle
   (auto-construction + promotion des champs déclarés) donnent la même garantie.

Modèles JETABLES (``isolate_apps('core')`` + ``schema_editor``) : ils vivent
dans un registre d'apps TEMPORAIRE, jamais dans le registre global — sinon un
autre test du même shard qui supprime une ``Company`` verrait le collecteur de
suppression suivre la FK inverse vers une table qui n'existe qu'ici.
"""
from django.contrib.auth.models import AnonymousUser
from django.db import connection, models
from django.test import SimpleTestCase, TestCase
from django.test.utils import isolate_apps
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from authentication.models import Company, CustomUser
from core.serializers import (
    CompanyScopedModelSerializer,
    CompanyScopedPrimaryKeyRelatedField,
    CompanyScopedRelationsMixin,
    model_is_company_scoped,
    request_company_id,
    scope_related_field,
)

# La FK ``company`` est redéclarée avec la CLASSE ``Company`` (la référence
# paresseuse 'authentication.Company' ne se résout pas dans un registre isolé)
# et ``related_name='+'`` (aucun accesseur inverse posé sur le vrai Company).
with isolate_apps('core'):
    class CrxScopedTarget(models.Model):
        """Cible SCOPÉE société (le cas normal d'un modèle métier)."""

        company = models.ForeignKey(
            Company, on_delete=models.CASCADE, related_name='+',
            verbose_name='Société')
        nom = models.CharField(max_length=120, blank=True, default='')

        class Meta:
            app_label = 'core'

    class CrxGlobalTarget(models.Model):
        """Cible SANS ``company`` (référentiel global) — jamais filtrée."""

        nom = models.CharField(max_length=120, blank=True, default='')

        class Meta:
            app_label = 'core'

    class CrxHolder(models.Model):
        """Porteur : une FK scopée + une FK globale (auto-construction)."""

        company = models.ForeignKey(
            Company, on_delete=models.CASCADE, related_name='+',
            verbose_name='Société')
        cible = models.ForeignKey(
            CrxScopedTarget, on_delete=models.CASCADE, related_name='+')
        referentiel = models.ForeignKey(
            CrxGlobalTarget, on_delete=models.CASCADE, related_name='+',
            null=True, blank=True)

        class Meta:
            app_label = 'core'


class _TablesMixin:
    """Crée/supprime les tables des modèles jetables (cf. docstring module)."""

    MODELS = (CrxScopedTarget, CrxGlobalTarget)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as schema:
            for model in cls.MODELS:
                schema.create_model(model)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as schema:
            for model in reversed(cls.MODELS):
                schema.delete_model(model)
        super().tearDownClass()


# ── Sérialiseurs d'essai ─────────────────────────────────────────────────────

class _ScopedFieldSerializer(serializers.Serializer):
    """Champ scopé déclaré explicitement (usage « champ par champ »)."""

    cible = CompanyScopedPrimaryKeyRelatedField(
        queryset=CrxScopedTarget.objects.all())


class _ScopedManySerializer(serializers.Serializer):
    """Même primitive en ``many=True`` (ManyRelatedField → child_relation)."""

    cibles = CompanyScopedPrimaryKeyRelatedField(
        queryset=CrxScopedTarget.objects.all(), many=True)


class _NakedFieldSerializer(serializers.Serializer):
    """Témoin NU (le trou que CRX12 ferme) — sert de référence d'oracle."""

    cible = serializers.PrimaryKeyRelatedField(
        queryset=CrxScopedTarget.objects.all())


class _GlobalFieldSerializer(serializers.Serializer):
    """Cible SANS ``company`` : la primitive ne doit RIEN filtrer."""

    referentiel = CompanyScopedPrimaryKeyRelatedField(
        queryset=CrxGlobalTarget.objects.all())


class _HolderSerializer(CompanyScopedModelSerializer):
    """Base optionnelle : relations AUTO-CONSTRUITES depuis ``Meta.fields``."""

    class Meta:
        model = CrxHolder
        fields = ['id', 'cible', 'referentiel']


class _DeclaredRelationSerializer(CompanyScopedRelationsMixin,
                                  serializers.Serializer):
    """Le mixin promeut aussi une relation DÉCLARÉE à la main."""

    cible = serializers.PrimaryKeyRelatedField(
        queryset=CrxScopedTarget.objects.all())


class _ExemptedRelationSerializer(CompanyScopedRelationsMixin,
                                  serializers.Serializer):
    """Exemption nommée : le champ listé n'est PAS promu."""

    company_scoped_relations_exclude = ('cible',)

    cible = serializers.PrimaryKeyRelatedField(
        queryset=CrxScopedTarget.objects.all())


class _CustomRelatedField(serializers.PrimaryKeyRelatedField):
    """Sous-classe métier : jamais promue (comportement écrit à la main)."""


# ── Helpers purs (sans DB) ───────────────────────────────────────────────────

class ModelIsCompanyScopedTests(SimpleTestCase):
    def test_true_for_model_with_company_relation(self):
        self.assertTrue(model_is_company_scoped(CrxScopedTarget))

    def test_false_for_model_without_company(self):
        self.assertFalse(model_is_company_scoped(CrxGlobalTarget))

    def test_false_for_none(self):
        self.assertFalse(model_is_company_scoped(None))


class RequestCompanyIdTests(SimpleTestCase):
    def test_none_without_request(self):
        self.assertIsNone(request_company_id({}))
        self.assertIsNone(request_company_id(None))

    def test_none_for_anonymous_user(self):
        request = APIRequestFactory().get('/')
        request.user = AnonymousUser()
        self.assertIsNone(request_company_id({'request': request}))


class ScopeRelatedFieldPromotionTests(SimpleTestCase):
    """La promotion sur place est PRUDENTE : type exact, jamais une sous-classe."""

    def test_promotes_exact_primary_key_related_field(self):
        field = serializers.PrimaryKeyRelatedField(
            queryset=CrxScopedTarget.objects.all())
        self.assertTrue(scope_related_field(field))
        self.assertIsInstance(field, CompanyScopedPrimaryKeyRelatedField)

    def test_promotes_child_of_many_related_field(self):
        field = serializers.PrimaryKeyRelatedField(
            queryset=CrxScopedTarget.objects.all(), many=True)
        self.assertTrue(scope_related_field(field))
        self.assertIsInstance(field.child_relation,
                              CompanyScopedPrimaryKeyRelatedField)

    def test_leaves_subclass_untouched(self):
        field = _CustomRelatedField(queryset=CrxScopedTarget.objects.all())
        self.assertFalse(scope_related_field(field))
        self.assertIs(type(field), _CustomRelatedField)

    def test_leaves_read_only_untouched(self):
        field = serializers.PrimaryKeyRelatedField(read_only=True)
        self.assertFalse(scope_related_field(field))
        self.assertIs(type(field), serializers.PrimaryKeyRelatedField)

    def test_leaves_unscoped_target_untouched(self):
        field = serializers.PrimaryKeyRelatedField(
            queryset=CrxGlobalTarget.objects.all())
        self.assertFalse(scope_related_field(field))
        self.assertIs(type(field), serializers.PrimaryKeyRelatedField)

    def test_writable_field_requires_queryset(self):
        with self.assertRaises(AssertionError):
            CompanyScopedPrimaryKeyRelatedField()


class SerializerCompositionTests(SimpleTestCase):
    """La base optionnelle scope l'AUTO-CONSTRUIT et promeut le DÉCLARÉ."""

    def test_auto_built_relation_is_scoped(self):
        fields = _HolderSerializer().fields
        self.assertIsInstance(fields['cible'],
                              CompanyScopedPrimaryKeyRelatedField)

    def test_auto_built_relation_on_unscoped_target_is_still_usable(self):
        # La classe scopée est posée partout par ``serializer_related_field`` ;
        # elle ne filtre RIEN si la cible n'a pas de ``company`` (cf. test DB).
        fields = _HolderSerializer().fields
        self.assertIsInstance(fields['referentiel'],
                              CompanyScopedPrimaryKeyRelatedField)

    def test_declared_relation_is_promoted(self):
        fields = _DeclaredRelationSerializer().fields
        self.assertIsInstance(fields['cible'],
                              CompanyScopedPrimaryKeyRelatedField)

    def test_named_exemption_is_respected(self):
        fields = _ExemptedRelationSerializer().fields
        self.assertIs(type(fields['cible']),
                      serializers.PrimaryKeyRelatedField)


# ── Comportement réel de validation (DB) ─────────────────────────────────────

class ScopedRelationValidationTests(_TablesMixin, TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.mine = Company.objects.create(nom='CRX12 Mienne',
                                           slug='crx12-mienne')
        self.other = Company.objects.create(nom='CRX12 Autre',
                                            slug='crx12-autre')
        self.user = CustomUser.objects.create_user(
            username='crx12user', email='crx12user@ex.com', password='x',
            company=self.mine)
        self.mine_target = CrxScopedTarget.objects.create(
            company=self.mine, nom='à moi')
        self.other_target = CrxScopedTarget.objects.create(
            company=self.other, nom='au voisin')
        self.global_target = CrxGlobalTarget.objects.create(nom='référentiel')

    def _context(self, user):
        request = self.factory.post('/')
        request.user = user
        return {'request': request}

    # -- Isolation ----------------------------------------------------------

    def test_own_company_id_is_accepted(self):
        ser = _ScopedFieldSerializer(data={'cible': self.mine_target.pk},
                                     context=self._context(self.user))
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data['cible'], self.mine_target)

    def test_foreign_company_id_is_refused(self):
        ser = _ScopedFieldSerializer(data={'cible': self.other_target.pk},
                                     context=self._context(self.user))
        self.assertFalse(ser.is_valid())
        self.assertIn('cible', ser.errors)

    def test_naked_field_still_accepts_foreign_id(self):
        """Témoin : sans la primitive, la fuite est réelle (le trou CRX12)."""
        ser = _NakedFieldSerializer(data={'cible': self.other_target.pk},
                                    context=self._context(self.user))
        self.assertTrue(ser.is_valid(), ser.errors)

    # -- Aucun oracle d'existence -------------------------------------------

    def test_foreign_id_and_absent_id_are_indistinguishable(self):
        absent_pk = self.other_target.pk + 10_000
        self.assertFalse(
            CrxScopedTarget.objects.filter(pk=absent_pk).exists())

        def _error_for(pk):
            field = CompanyScopedPrimaryKeyRelatedField(
                queryset=CrxScopedTarget.objects.all())
            ser = _ScopedFieldSerializer(context=self._context(self.user))
            field.bind('cible', ser)
            try:
                field.to_internal_value(pk)
            except ValidationError as exc:
                return exc.detail
            return None

        foreign = _error_for(self.other_target.pk)
        absent = _error_for(absent_pk)
        self.assertIsNotNone(foreign)
        self.assertIsNotNone(absent)
        # Même code d'erreur ET même gabarit de message : seule la valeur d'id
        # citée diffère — aucune information sur l'existence chez le voisin.
        self.assertEqual([d.code for d in foreign],
                         [d.code for d in absent])
        self.assertEqual(
            [str(d).replace(str(self.other_target.pk), '<pk>')
             for d in foreign],
            [str(d).replace(str(absent_pk), '<pk>') for d in absent])

    # -- Non-régression -----------------------------------------------------

    def test_without_request_nothing_is_scoped(self):
        """Rendu serveur/interne (shell, tâche Celery) : comportement d'origine."""
        ser = _ScopedFieldSerializer(data={'cible': self.other_target.pk})
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_anonymous_user_is_not_scoped(self):
        ser = _ScopedFieldSerializer(
            data={'cible': self.other_target.pk},
            context=self._context(AnonymousUser()))
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_platform_superuser_without_company_sees_everything(self):
        platform = CustomUser.objects.create_superuser(
            username='crx12plat', email='crx12plat@ex.com', password='x')
        self.assertIsNone(platform.company_id)
        ser = _ScopedFieldSerializer(data={'cible': self.other_target.pk},
                                     context=self._context(platform))
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_superuser_with_company_is_scoped(self):
        """Parité TenantMixin : un superuser AVEC société reste scopé."""
        admin = CustomUser.objects.create_superuser(
            username='crx12admin', email='crx12admin@ex.com', password='x')
        admin.company = self.mine
        admin.save(update_fields=['company'])
        ser = _ScopedFieldSerializer(data={'cible': self.other_target.pk},
                                     context=self._context(admin))
        self.assertFalse(ser.is_valid())

    def test_unscoped_target_model_is_never_filtered(self):
        ser = _GlobalFieldSerializer(
            data={'referentiel': self.global_target.pk},
            context=self._context(self.user))
        self.assertTrue(ser.is_valid(), ser.errors)

    # -- Composition --------------------------------------------------------

    def test_many_true_refuses_a_foreign_id_in_the_list(self):
        ser = _ScopedManySerializer(
            data={'cibles': [self.mine_target.pk, self.other_target.pk]},
            context=self._context(self.user))
        self.assertFalse(ser.is_valid())
        self.assertIn('cibles', ser.errors)

    def test_many_true_accepts_own_ids(self):
        second = CrxScopedTarget.objects.create(company=self.mine, nom='moi 2')
        ser = _ScopedManySerializer(
            data={'cibles': [self.mine_target.pk, second.pk]},
            context=self._context(self.user))
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_promoted_declared_relation_refuses_foreign_id(self):
        ser = _DeclaredRelationSerializer(
            data={'cible': self.other_target.pk},
            context=self._context(self.user))
        self.assertFalse(ser.is_valid())

    def test_model_serializer_base_refuses_foreign_id(self):
        ser = _HolderSerializer(data={'cible': self.other_target.pk},
                                context=self._context(self.user))
        self.assertFalse(ser.is_valid())
        self.assertIn('cible', ser.errors)

    def test_model_serializer_base_accepts_own_id(self):
        ser = _HolderSerializer(
            data={'cible': self.mine_target.pk,
                  'referentiel': self.global_target.pk},
            context=self._context(self.user))
        self.assertTrue(ser.is_valid(), ser.errors)
