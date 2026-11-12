"""FG274 — tests du protocole d'essais de mise en service IEC 62446.

Couvre : calcul pur du résultat global, création (company forcée), résultat
dérivé serveur (jamais du corps), isolation société, filtre, ne change aucun
statut de devis.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fg274_commissioning -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from rest_framework.test import APIClient

from apps.ventes.models import Devis, CommissioningTest
from apps.ventes.commissioning import compute_commissioning_result
from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_devis(company, user, ref='DEV-FG274-1'):
    client = Client.objects.create(
        company=company, nom='Berrada', prenom='Salma',
        email=f's_{ref}@example.com', telephone='+212666666666')
    return Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='accepte', created_by=user)


class ComputeResultTest(SimpleTestCase):
    def test_any_false_is_non_conforme(self):
        self.assertEqual(
            compute_commissioning_result(
                isolement_ok=True, polarite_ok=False),
            'non_conforme')

    def test_all_true_no_defect_is_conforme(self):
        self.assertEqual(
            compute_commissioning_result(
                isolement_ok=True, polarite_ok=True,
                continuite_terre_ok=True, controle_onduleur_ok=True),
            'conforme')

    def test_defective_iv_forces_non_conforme(self):
        self.assertEqual(
            compute_commissioning_result(
                isolement_ok=True, polarite_ok=True,
                continuite_terre_ok=True, controle_onduleur_ok=True,
                has_defective_iv=True),
            'non_conforme')

    def test_partial_is_en_cours(self):
        self.assertEqual(
            compute_commissioning_result(isolement_ok=True),
            'en_cours')


class CommissioningApiTest(TestCase):
    def setUp(self):
        self.company = make_company('mes-acme')
        self.other = make_company('mes-other')
        self.user = make_user(self.company, 'mes_user')
        self.devis = make_devis(self.company, self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/recettes-mes/'

    def test_lectures_dossier_recette_fiche_bornees(self):
        """APFS109 (D-APFS-4) — Admin RH : 403 sur les dossiers et la
        recette ; Technicien (octroi ``installation_voir``) : la recette et le
        dossier de SON chantier, rien d'un autre ; un rôle Ventes : 200."""
        from apps.installations.models import Installation
        from apps.roles import permissions_registre as registre
        from apps.roles.models import Role
        from apps.ventes.models import RegulatoryDossier

        def compte(nom, codes):
            role = Role.objects.create(company=self.company, nom=nom,
                                       permissions=list(codes))
            return User.objects.create_user(
                username='apfs109_' + nom.replace(' ', '_'), password='x',
                role=role, company=self.company)

        rh = compte('Admin RH', registre.ADMIN_RH_PERMISSIONS)
        tech = compte('Technicien', registre.TECHNICIEN_PERMISSIONS)
        commercial = compte('Commercial', registre.COMMERCIAL_PERMISSIONS)
        d2 = make_devis(self.company, self.user, ref='DEV-FG274-2')
        k1 = Installation.objects.create(
            company=self.company, reference='CH-APFS109-1',
            client=self.devis.client, devis=self.devis,
            technicien_responsable=tech)
        k2 = Installation.objects.create(
            company=self.company, reference='CH-APFS109-2',
            client=d2.client, devis=d2)
        r1 = CommissioningTest.objects.create(
            company=self.company, devis=self.devis, chantier=k1)
        CommissioningTest.objects.create(company=self.company, devis=d2,
                                         chantier=k2)
        dossier1 = RegulatoryDossier.objects.create(
            company=self.company, devis=self.devis, chantier=k1)
        RegulatoryDossier.objects.create(company=self.company, devis=d2,
                                         chantier=k2)
        dossiers = '/api/django/ventes/dossiers-reglementaires/'

        def lire(user, url):
            api = APIClient()
            api.force_authenticate(user)
            return api.get(url)

        def ids(reponse):
            corps = reponse.data
            rangs = corps.get('results', corps) if isinstance(corps, dict) \
                else corps
            return {ligne['id'] for ligne in rangs}

        for url in (self.url, dossiers):
            with self.subTest(url=url):
                self.assertEqual(lire(rh, url).status_code, 403)
                self.assertEqual(lire(commercial, url).status_code, 200)
        r = lire(tech, self.url)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ids(r), {r1.pk})
        r = lire(tech, dossiers)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ids(r), {dossier1.pk})

    def test_suppression_dossier_exige_ventes_supprimer(self):
        """ADRG6 (C-ADRG-013) — supprimer un dossier réglementaire, une pièce,
        un échange, une subvention ou une régularisation 82-21 exige
        `ventes_supprimer` : Commercial livré 403 (rien supprimé), Commercial
        responsable 204."""
        from datetime import date
        from django.core.management import call_command
        from apps.roles.models import Role
        from apps.ventes.models_regulatory import (
            DossierChecklistItem, DossierExchange, Regularisation8221,
            RegulatoryDossier, SubventionDossier)
        call_command('init_roles', verbosity=0)
        dossier = RegulatoryDossier.objects.create(
            company=self.company, devis=self.devis)
        objets = [
            ('dossiers-checklist', DossierChecklistItem.objects.create(
                company=self.company, dossier=dossier, code='cin', libelle='CIN')),
            ('dossiers-echanges', DossierExchange.objects.create(
                company=self.company, dossier=dossier, date_echange=date.today())),
            ('subventions', SubventionDossier.objects.create(
                company=self.company, devis=self.devis)),
            ('regularisations-8221', Regularisation8221.objects.create(
                company=self.company, devis=self.devis)),
            ('dossiers-reglementaires', dossier),
        ]

        def api_role(nom):
            api = APIClient()
            api.force_authenticate(User.objects.create_user(
                username='adrg6_' + nom.replace(' ', '_'), password='x',
                company=self.company,
                role=Role.objects.get(company=self.company, nom=nom)))
            return api
        commercial = api_role('Commercial')
        responsable = api_role('Commercial responsable')
        for route, obj in objets:
            url = f'/api/django/ventes/{route}/{obj.pk}/'
            with self.subTest(route=route):
                r = commercial.delete(url)
                self.assertEqual(r.status_code, 403, r.data)
                self.assertIn('ventes_supprimer', str(r.data))
                self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())
                self.assertEqual(responsable.delete(url).status_code, 204)
                self.assertFalse(type(obj).objects.filter(pk=obj.pk).exists())

    def test_result_derived_server_side(self):
        # ENF11 — texte strict : ``observations: 0`` n'est plus converti.
        refus = self.api.post(self.url, {
            'devis': self.devis.id, 'observations': 0}, format='json')
        self.assertEqual(refus.status_code, 400, refus.content)
        # Le corps tente d'imposer resultat=conforme ; serveur l'ignore et
        # dérive non_conforme car polarite_ok=False.
        resp = self.api.post(self.url, {
            'devis': self.devis.id, 'isolement_ok': True,
            'polarite_ok': False, 'continuite_terre_ok': True,
            'controle_onduleur_ok': True, 'isolement_mohm': '5.50',
            'resultat': 'conforme',  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        rec = CommissioningTest.objects.get(id=resp.data['id'])
        self.assertEqual(rec.resultat, 'non_conforme')
        self.assertEqual(rec.company_id, self.company.id)
        # Le statut du devis ne change pas (RULE #4).
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'accepte')

    def test_all_pass_is_conforme(self):
        resp = self.api.post(self.url, {
            'devis': self.devis.id, 'isolement_ok': True,
            'polarite_ok': True, 'continuite_terre_ok': True,
            'controle_onduleur_ok': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['resultat'], 'conforme')

    def test_devis_of_other_company_refused(self):
        other_user = make_user(self.other, 'mes_o')
        other_devis = make_devis(self.other, other_user, ref='DEV-OTHER-MES')
        resp = self.api.post(self.url, {
            'devis': other_devis.id, 'isolement_ok': True,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        # ENF17 — même réponse qu'un devis absent (aucun oracle).
        self.assertEqual(resp.data['devis'][0].code, 'does_not_exist')

    def test_enf17_fk_mise_en_service_bornees_societe(self):
        """ENF17 — chantier / devis / recette d'une autre société = id absent
        (400 « objet inexistant ») sur les six sérialiseurs ; ceux de la
        société passent."""
        from types import SimpleNamespace

        from apps.installations.models import Installation
        from apps.ventes import serializers_commissioning as sc
        other_user = make_user(self.other, 'mes_enf17_o')
        devis_b = make_devis(self.other, other_user, ref='DEV-ENF17-MES-B')
        objets = {
            'devis': (self.devis, devis_b),
            'chantier': tuple(
                Installation.objects.create(
                    company=d.company, reference=f'CH-ENF17-{d.pk}',
                    client=d.client)
                for d in (self.devis, devis_b)),
            'recette': tuple(
                CommissioningTest.objects.create(company=d.company, devis=d)
                for d in (self.devis, devis_b)),
        }
        ctx = {'request': SimpleNamespace(user=self.user)}
        for cls in (sc.IVCurveCaptureSerializer, sc.CommissioningTestSerializer,
                    sc.AsBuiltPackSerializer, sc.AttestationConformiteSerializer,
                    sc.TestPerformanceReceptionSerializer,
                    sc.AttestationRESerializer):
            for champ in cls.same_company_fields:
                propre, etranger = objets[champ]
                with self.subTest(serializer=cls.__name__, champ=champ):
                    ser = cls(data={champ: etranger.pk}, partial=True,
                              context=ctx)
                    self.assertFalse(ser.is_valid())
                    self.assertEqual(ser.errors[champ][0].code,
                                     'does_not_exist')
                    champ_lie = cls(context=ctx).fields[champ]
                    self.assertEqual(champ_lie.to_internal_value(propre.pk),
                                     propre)

    def test_filtres_stricts_resultat_et_entiers(self):
        # CI #997 fuzz (24/10) : une valeur hors liste (dont le caractère nul,
        # 500 avant) ou un entier vide / illisible = 400 nommé.
        for params in ({'resultat': 'zzz'}, {'resultat': 'a\x00'},
                       {'chantier': ''}, {'devis': 'abc'}):
            with self.subTest(params=params):
                resp = self.api.get(self.url, params)
                self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(
            self.api.get(self.url, {'chantier': '0'}).status_code, 200)
        for ressource, cle in (('attestations-conformite', 'statut'),
                               ('tests-pr-reception', 'verdict'),
                               ('attestations-re', 'statut')):
            with self.subTest(ressource=ressource):
                url = f'/api/django/ventes/{ressource}/'
                self.assertEqual(
                    self.api.get(url, {cle: 'x\x00'}).status_code, 400)
                self.assertEqual(self.api.get(url).status_code, 200)

    def test_list_scoped_and_filter_resultat(self):
        CommissioningTest.objects.create(
            company=self.company, devis=self.devis, resultat='conforme')
        CommissioningTest.objects.create(
            company=self.company, devis=self.devis, resultat='non_conforme')
        resp = self.api.get(self.url, {'resultat': 'conforme'})
        rows = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['resultat'], 'conforme')
