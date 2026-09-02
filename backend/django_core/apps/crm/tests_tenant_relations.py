"""CRX13 — les 13 relations nues d'``apps/crm`` sont scopées société.

Un test cross-tenant **création + PATCH** par relation. Les assertions portent
sur le CHAMP concerné (``field in serializer.errors`` / ``not in``) plutôt que
sur la validité globale du payload : le reste du corps n'est pas le sujet, et
une exigence sans rapport (garde funnel, champ personnalisé…) ne doit pas
transformer ce test en test de bout en bout fragile. Quand la relation est
refusée, on vérifie EN PLUS le code d'erreur ``does_not_exist`` — c'est la
preuve qu'aucun oracle d'existence ne subsiste (le message est identique à
celui d'un id qui n'existe nulle part).

Les relations couvertes (13) :
``ForecastEntry.lead`` (+ validateur d'unicité scopé), ``PlanCompte.client``,
``RevueCompte.plan``, ``DealEnregistre.lead``/``apporteur``,
``SalleVente.lead``/``client``, ``EquipeCommerciale.responsable``/``membres``,
``ObjectifCommercial.owner``, ``Client.liste_prix``/``tiers``,
``LeadSerializer.deleted_by``.
"""
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from authentication.models import Company
from core.serializers import CompanyScopedPrimaryKeyRelatedField

from .models import (
    Apporteur, Client, DealEnregistre, EquipeCommerciale, ForecastEntry, Lead,
    ObjectifCommercial, PlanCompte, RevueCompte, SalleVente,
)
from .serializers import (
    ClientSerializer, DealEnregistreSerializer, EquipeCommercialeSerializer,
    ForecastEntrySerializer, LeadSerializer, ObjectifCommercialSerializer,
    PlanCompteSerializer, RevueCompteSerializer, SalleVenteSerializer,
    _CompanyScopedUniqueValidator,
)

User = get_user_model()


def _liste_prix(company, nom):
    return django_apps.get_model('ventes', 'ListePrix').objects.create(
        company=company, nom=nom)


def _tiers(company, nom):
    return django_apps.get_model('tiers', 'Tiers').objects.create(
        company=company, nom=nom)


class ScopedRelationsBase(TestCase):
    """Deux sociétés complètes : A (le demandeur) et B (la voisine)."""

    def setUp(self):
        self.a = Company.objects.create(nom='CRX13 A', slug='crx13-a')
        self.b = Company.objects.create(nom='CRX13 B', slug='crx13-b')
        self.user_a = User.objects.create_user(
            username='crx13-user-a', password='x', company=self.a)
        self.user_b = User.objects.create_user(
            username='crx13-user-b', password='x', company=self.b)
        self.factory = APIRequestFactory()

    # ── helpers ─────────────────────────────────────────────────────────────

    def ctx(self):
        request = self.factory.post('/')
        request.user = self.user_a
        return {'request': request}

    def _errors(self, serializer_class, data, instance=None):
        kwargs = {'data': data, 'context': self.ctx()}
        if instance is not None:
            kwargs['partial'] = True
            serializer = serializer_class(instance, **kwargs)
        else:
            serializer = serializer_class(**kwargs)
        serializer.is_valid()
        return serializer.errors

    def assert_relation_scoped(self, serializer_class, field, foreign_pk,
                               own_pk, create_data, instance, many=False):
        """CREATE + PATCH cross-tenant refusés, valeur de la société acceptée."""
        wrap = (lambda pk: [pk]) if many else (lambda pk: pk)

        # 1. CRÉATION avec l'id de la société VOISINE → refusée.
        errors = self._errors(
            serializer_class, {**create_data, field: wrap(foreign_pk)})
        self.assertIn(
            field, errors,
            f'{serializer_class.__name__}.{field} accepte encore un id '
            'appartenant à une autre société (création).')
        self.assertEqual(
            _codes(errors[field]), {'does_not_exist'},
            f'{serializer_class.__name__}.{field} : le refus doit être le '
            '« objet inexistant » standard, jamais un message qui révèle '
            "l'existence de la ligne voisine.")

        # 2. CRÉATION avec l'id de SA société → la relation passe.
        errors = self._errors(
            serializer_class, {**create_data, field: wrap(own_pk)})
        self.assertNotIn(
            field, errors,
            f'{serializer_class.__name__}.{field} refuse un id LÉGITIME de sa '
            f'propre société : {errors.get(field)}')

        # 3. PATCH avec l'id de la société VOISINE → refusé lui aussi.
        errors = self._errors(
            serializer_class, {field: wrap(foreign_pk)}, instance=instance)
        self.assertIn(
            field, errors,
            f'{serializer_class.__name__}.{field} accepte encore un id '
            'appartenant à une autre société (PATCH).')
        self.assertEqual(_codes(errors[field]), {'does_not_exist'})


def _codes(detail):
    """Codes d'erreur d'un champ, à plat (listes imbriquées des M2M incluses)."""
    codes = set()
    items = detail if isinstance(detail, (list, tuple)) else [detail]
    for item in items:
        if isinstance(item, (list, tuple)):
            codes |= _codes(item)
        elif isinstance(item, dict):
            for value in item.values():
                codes |= _codes(value)
        else:
            codes.add(getattr(item, 'code', None))
    return codes


class ClientRelationsTests(ScopedRelationsBase):
    def setUp(self):
        super().setUp()
        self.client_a = Client.objects.create(company=self.a, nom='Client A')

    def test_liste_prix_scoped(self):
        self.assert_relation_scoped(
            ClientSerializer, 'liste_prix',
            foreign_pk=_liste_prix(self.b, 'Tarif voisin').pk,
            own_pk=_liste_prix(self.a, 'Tarif maison').pk,
            create_data={'nom': 'Nouveau client'},
            instance=self.client_a)

    def test_tiers_scoped(self):
        self.assert_relation_scoped(
            ClientSerializer, 'tiers',
            foreign_pk=_tiers(self.b, 'Tiers voisin').pk,
            own_pk=_tiers(self.a, 'Tiers maison').pk,
            create_data={'nom': 'Nouveau client 2'},
            instance=self.client_a)


class LeadRelationsTests(ScopedRelationsBase):
    def test_deleted_by_scoped(self):
        lead_a = Lead.objects.create(company=self.a, nom='Lead A')
        self.assert_relation_scoped(
            LeadSerializer, 'deleted_by',
            foreign_pk=self.user_b.pk,
            own_pk=self.user_a.pk,
            create_data={'nom': 'Lead créé'},
            instance=lead_a)


class ObjectifRelationsTests(ScopedRelationsBase):
    def test_owner_scoped(self):
        objectif_a = ObjectifCommercial.objects.create(
            company=self.a, metric=ObjectifCommercial.Metric.NB_LEADS,
            period_type=ObjectifCommercial.PeriodType.YEAR,
            period_year=2026, cible=10, owner=self.user_a)
        self.assert_relation_scoped(
            ObjectifCommercialSerializer, 'owner',
            foreign_pk=self.user_b.pk,
            own_pk=self.user_a.pk,
            create_data={
                'metric': ObjectifCommercial.Metric.NB_LEADS,
                'period_type': ObjectifCommercial.PeriodType.YEAR,
                'period_year': 2027, 'cible': '20',
            },
            instance=objectif_a)


class EquipeRelationsTests(ScopedRelationsBase):
    def setUp(self):
        super().setUp()
        self.equipe_a = EquipeCommerciale.objects.create(
            company=self.a, nom='Équipe A')

    def test_responsable_scoped(self):
        self.assert_relation_scoped(
            EquipeCommercialeSerializer, 'responsable',
            foreign_pk=self.user_b.pk,
            own_pk=self.user_a.pk,
            create_data={'nom': 'Nouvelle équipe'},
            instance=self.equipe_a)

    def test_membres_scoped(self):
        self.assert_relation_scoped(
            EquipeCommercialeSerializer, 'membres',
            foreign_pk=self.user_b.pk,
            own_pk=self.user_a.pk,
            create_data={'nom': 'Équipe membres'},
            instance=self.equipe_a, many=True)


class ForecastRelationsTests(ScopedRelationsBase):
    def setUp(self):
        super().setUp()
        self.lead_a = Lead.objects.create(company=self.a, nom='Lead forecast A')
        self.lead_a_libre = Lead.objects.create(
            company=self.a, nom='Lead forecast libre')
        self.lead_b = Lead.objects.create(company=self.b, nom='Lead voisin')
        self.entry_a = ForecastEntry.objects.create(
            company=self.a, lead=self.lead_a)

    def test_lead_scoped(self):
        self.assert_relation_scoped(
            ForecastEntrySerializer, 'lead',
            foreign_pk=self.lead_b.pk,
            own_pk=self.lead_a_libre.pk,
            create_data={'categorie': ForecastEntry.Categorie.COMMIT},
            instance=self.entry_a)

    def test_unique_validator_is_company_scoped(self):
        """Le validateur d'unicité auto-généré (OneToOne) est remplacé par sa
        version scopée — il ne peut plus interroger les autres sociétés."""
        field = ForecastEntrySerializer(context=self.ctx()).fields['lead']
        unique = [v for v in field.validators
                  if isinstance(v, _CompanyScopedUniqueValidator)]
        self.assertTrue(
            unique,
            "Le UniqueValidator de ForecastEntry.lead n'est pas scopé société.")

    def test_unique_within_company_still_enforced(self):
        """Non-régression : deux entrées pour le MÊME lead restent refusées."""
        errors = self._errors(
            ForecastEntrySerializer,
            {'lead': self.lead_a.pk,
             'categorie': ForecastEntry.Categorie.COMMIT})
        self.assertIn('lead', errors)
        self.assertEqual(_codes(errors['lead']), {'unique'})


class PlanCompteRelationsTests(ScopedRelationsBase):
    def setUp(self):
        super().setUp()
        self.client_a = Client.objects.create(company=self.a, nom='Compte A')
        self.client_b = Client.objects.create(company=self.b, nom='Compte B')
        self.plan_a = PlanCompte.objects.create(
            company=self.a, client=self.client_a)
        self.plan_b = PlanCompte.objects.create(
            company=self.b, client=self.client_b)

    def test_client_scoped(self):
        self.assert_relation_scoped(
            PlanCompteSerializer, 'client',
            foreign_pk=self.client_b.pk,
            own_pk=self.client_a.pk,
            create_data={'statut': 'brouillon'},
            instance=self.plan_a)

    def test_plan_de_revue_scoped(self):
        """``RevueCompte.plan`` est la SEULE frontière société du modèle."""
        revue_a = RevueCompte.objects.create(
            plan=self.plan_a, date_revue='2026-07-15')
        self.assert_relation_scoped(
            RevueCompteSerializer, 'plan',
            foreign_pk=self.plan_b.pk,
            own_pk=self.plan_a.pk,
            create_data={'date_revue': '2026-08-15'},
            instance=revue_a)

    def test_creation_complete_reste_valide(self):
        """Contrôle positif complet : un plan de compte légitime passe."""
        serializer = PlanCompteSerializer(
            data={'client': self.client_a.pk, 'statut': 'brouillon'},
            context=self.ctx())
        self.assertTrue(serializer.is_valid(), serializer.errors)


class SalleVenteRelationsTests(ScopedRelationsBase):
    def setUp(self):
        super().setUp()
        self.lead_a = Lead.objects.create(company=self.a, nom='Lead salle A')
        self.lead_b = Lead.objects.create(company=self.b, nom='Lead salle B')
        self.client_a = Client.objects.create(company=self.a, nom='Client SV A')
        self.client_b = Client.objects.create(company=self.b, nom='Client SV B')
        self.salle_a = SalleVente.objects.create(
            company=self.a, titre='Salle A', lead=self.lead_a)

    def test_lead_scoped(self):
        self.assert_relation_scoped(
            SalleVenteSerializer, 'lead',
            foreign_pk=self.lead_b.pk,
            own_pk=self.lead_a.pk,
            create_data={'titre': 'Salle lead'},
            instance=self.salle_a)

    def test_client_scoped(self):
        self.assert_relation_scoped(
            SalleVenteSerializer, 'client',
            foreign_pk=self.client_b.pk,
            own_pk=self.client_a.pk,
            create_data={'titre': 'Salle client'},
            instance=self.salle_a)


class DealEnregistreRelationsTests(ScopedRelationsBase):
    def setUp(self):
        super().setUp()
        self.apporteur_a = Apporteur.objects.create(company=self.a, nom='App A')
        self.apporteur_b = Apporteur.objects.create(company=self.b, nom='App B')
        self.lead_a = Lead.objects.create(
            company=self.a, nom='Lead deal A', email='deal-a@ex.com')
        self.lead_a_libre = Lead.objects.create(
            company=self.a, nom='Lead deal libre', email='deal-libre@ex.com')
        self.lead_b = Lead.objects.create(
            company=self.b, nom='Lead deal B', email='deal-b@ex.com')
        self.deal_a = DealEnregistre.objects.create(
            company=self.a, apporteur=self.apporteur_a, lead=self.lead_a)

    def test_apporteur_scoped(self):
        self.assert_relation_scoped(
            DealEnregistreSerializer, 'apporteur',
            foreign_pk=self.apporteur_b.pk,
            own_pk=self.apporteur_a.pk,
            create_data={'lead': self.lead_a_libre.pk},
            instance=self.deal_a)

    def test_lead_scoped(self):
        self.assert_relation_scoped(
            DealEnregistreSerializer, 'lead',
            foreign_pk=self.lead_b.pk,
            own_pk=self.lead_a_libre.pk,
            create_data={'apporteur': self.apporteur_a.pk},
            instance=self.deal_a)


class ThirteenRelationsCoverageTests(ScopedRelationsBase):
    """Garde structurelle : les 13 relations listées par CRX13 sont bien des
    champs scopés — un futur refactor qui en re-déclarerait une NUE échoue ici.
    """

    EXPECTED = (
        (ClientSerializer, ('liste_prix', 'tiers')),
        (LeadSerializer, ('deleted_by',)),
        (ObjectifCommercialSerializer, ('owner',)),
        (EquipeCommercialeSerializer, ('responsable', 'membres')),
        (ForecastEntrySerializer, ('lead',)),
        (RevueCompteSerializer, ('plan',)),
        (PlanCompteSerializer, ('client',)),
        (SalleVenteSerializer, ('lead', 'client')),
        (DealEnregistreSerializer, ('apporteur', 'lead')),
    )

    def test_all_thirteen_relations_are_company_scoped(self):
        total = 0
        for serializer_class, names in self.EXPECTED:
            fields = serializer_class(context=self.ctx()).fields
            for name in names:
                self.assertIn(name, fields,
                              f'{serializer_class.__name__}.{name} a disparu.')
                field = fields[name]
                target = getattr(field, 'child_relation', field)
                self.assertIsInstance(
                    target, CompanyScopedPrimaryKeyRelatedField,
                    f'{serializer_class.__name__}.{name} est redevenue une '
                    'relation NUE (non scopée société).')
                total += 1
        self.assertEqual(total, 13, 'CRX13 couvre exactement 13 relations.')
