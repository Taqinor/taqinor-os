"""NTNRG27 — Registre des certificats carbone émis (traçabilité / anti-double-comptage).

Couvre :
  * un certificat émis se retrouve dans le registre, avec une référence
    race-safe posée côté serveur ;
  * un doublon EXACT (même cible + même période) est refusé ;
  * une période différente ou une cible différente n'est PAS un doublon ;
  * ni site ni client (ou les deux) est rejeté (XOR) ;
  * société isolée (jamais de fuite cross-tenant).

Run :
    python manage.py test apps.monitoring.test_ntnrg27_registre_certificats -v 2
"""
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company
from apps.monitoring.models import CertificatCarbone
from apps.monitoring.services import emettre_certificat_carbone


def regler_facteur(company, g_kwh='810', source='ONEE'):
    """AMON41 — règle le facteur CO₂ du réseau de la société (Paramètres) :
    sans lui, aucun tonnage n'est établi."""
    from apps.parametres.models import CompanyProfile
    profil = CompanyProfile.get(company=company)
    profil.facteur_co2_reseau_g_kwh = Decimal(g_kwh)
    profil.facteur_co2_reseau_source = source
    profil.facteur_co2_reseau_date = date(2026, 1, 15)
    profil.save()


class TestEmettreCertificatCarbone(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntnrg27-co', defaults={'nom': 'NTNRG27 Co'})

    def test_emission_cree_le_registre_avec_reference(self):
        certif = emettre_certificat_carbone(
            self.company, installation_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('12.500'))
        self.assertTrue(certif.reference.startswith('CERT-CO2-'))
        self.assertEqual(CertificatCarbone.objects.count(), 1)

    def test_doublon_exact_refuse(self):
        emettre_certificat_carbone(
            self.company, installation_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('12.500'))
        with self.assertRaises(ValueError):
            emettre_certificat_carbone(
                self.company, installation_id=1,
                periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
                tco2_evitees=Decimal('12.500'))
        self.assertEqual(CertificatCarbone.objects.count(), 1)

    def test_periode_differente_nest_pas_un_doublon(self):
        emettre_certificat_carbone(
            self.company, installation_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('12.500'))
        certif2 = emettre_certificat_carbone(
            self.company, installation_id=1,
            periode_debut=date(2026, 7, 1), periode_fin=date(2026, 12, 31),
            tco2_evitees=Decimal('13.000'))
        self.assertEqual(CertificatCarbone.objects.count(), 2)
        self.assertNotEqual(
            certif2.reference,
            CertificatCarbone.objects.exclude(pk=certif2.pk).first().reference)

    def test_client_consolide_meme_periode_que_site_nest_pas_un_doublon(self):
        # Un certificat SITE (installation_id=1) et un certificat CLIENT
        # (client_id=1) sur la même période sont des cibles DIFFÉRENTES —
        # jamais confondus par la contrainte d'unicité (branches XOR séparées).
        emettre_certificat_carbone(
            self.company, installation_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('12.500'))
        certif_client = emettre_certificat_carbone(
            self.company, client_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('20.000'))
        self.assertEqual(CertificatCarbone.objects.count(), 2)
        self.assertEqual(certif_client.client_id, 1)

    def test_ni_site_ni_client_est_rejete(self):
        with self.assertRaises(ValueError):
            emettre_certificat_carbone(
                self.company,
                periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
                tco2_evitees=Decimal('1'))

    def test_site_et_client_a_la_fois_est_rejete(self):
        with self.assertRaises(ValueError):
            emettre_certificat_carbone(
                self.company, installation_id=1, client_id=2,
                periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
                tco2_evitees=Decimal('1'))

    def test_periode_fin_avant_debut_est_rejetee(self):
        with self.assertRaises(ValueError):
            emettre_certificat_carbone(
                self.company, installation_id=1,
                periode_debut=date(2026, 6, 30), periode_fin=date(2026, 1, 1),
                tco2_evitees=Decimal('1'))

    def test_isolation_societe(self):
        autre_co, _ = Company.objects.get_or_create(
            slug='ntnrg27-autre-co', defaults={'nom': 'NTNRG27 Autre Co'})
        emettre_certificat_carbone(
            self.company, installation_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('12.500'))
        # Même cible/période, société DIFFÉRENTE → pas un doublon.
        certif = emettre_certificat_carbone(
            autre_co, installation_id=1,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 6, 30),
            tco2_evitees=Decimal('12.500'))
        self.assertEqual(certif.company_id, autre_co.id)
        self.assertEqual(
            CertificatCarbone.objects.filter(company=self.company).count(), 1)
        self.assertEqual(
            CertificatCarbone.objects.filter(company=autre_co).count(), 1)

    def test_db_constraint_backstop_on_direct_create(self):
        # Contrainte DB en dernier recours si on contourne le service
        # (création directe du modèle) : même défense-en-profondeur que le
        # contrôle applicatif ci-dessus.
        CertificatCarbone.objects.create(
            company=self.company, installation_id=5,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 3, 31),
            tco2_evitees=Decimal('1'), reference='CERT-CO2-TEST-0001')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CertificatCarbone.objects.create(
                    company=self.company, installation_id=5,
                    periode_debut=date(2026, 1, 1), periode_fin=date(2026, 3, 31),
                    tco2_evitees=Decimal('1'), reference='CERT-CO2-TEST-0002')


class TestAsav102RegistreApi(TestCase):
    """ASAV102 — registre carbone rendu utilisable : route company-scopée
    (responsable/admin), tCO₂ calculées par le serveur depuis la production
    mesurée, forme conforme au contrat ``certificats_carbone.json``."""
    URL = '/api/django/monitoring/certificats-carbone/'

    def setUp(self):
        import json
        from pathlib import Path

        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from apps.crm.models import Client
        from apps.installations.models import Installation
        from apps.monitoring.models import ProductionReading

        User = get_user_model()
        self.contrat = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'certificats_carbone.json').read_text(encoding='utf-8'))
        self.company, _ = Company.objects.get_or_create(
            slug='asav102-co', defaults={'nom': 'ASAV102 Co'})
        self.autre, _ = Company.objects.get_or_create(
            slug='asav102-b', defaults={'nom': 'ASAV102 B'})

        def inst(company, ref):
            client = Client.objects.create(
                company=company, nom='Cli', prenom=ref,
                email=f'{ref.lower()}@example.invalid')
            return Installation.objects.create(
                company=company, reference=ref, client=client,
                puissance_installee_kwc=Decimal('10'))
        self.inst = inst(self.company, 'ASAV102-1')
        self.inst_b = inst(self.autre, 'ASAV102-B')
        # 1 000 kWh mesurés sur la période → 0,810 tCO₂ (facteur réglé 810 g).
        regler_facteur(self.company)
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 3, 1), period_days=30, energy_kwh=Decimal('1000'))

        def client_de(username, role, company):
            api = APIClient()
            api.force_authenticate(User.objects.create_user(
                username=username, password='x', role_legacy=role,
                company=company))
            return api
        self.api = client_de('asav102_resp', 'responsable', self.company)
        self.api_b = client_de('asav102_b', 'admin', self.autre)
        self.api_normal = client_de('asav102_n', 'normal', self.company)

    def _emettre(self, **corps):
        data = {'installation_id': self.inst.id,
                'periode_debut': '2026-01-01', 'periode_fin': '2026-06-30'}
        data.update(corps)
        return self.api.post(self.URL, data, format='json')

    def test_emission_calculee_et_liste_au_contrat(self):
        r = self._emettre(tco2_evitees='999')  # ignoré : calculé serveur
        self.assertEqual(r.status_code, 201, r.data)
        certif = CertificatCarbone.objects.get(id=r.data['id'])
        self.assertEqual(certif.company_id, self.company.id)
        self.assertEqual(certif.tco2_evitees, Decimal('0.810'))
        self.assertTrue(certif.reference.startswith('CERT-CO2-'))
        lst = self.api.get(self.URL)
        exemple = self.contrat['exemple']
        self.assertEqual(set(lst.data), set(exemple))
        self.assertEqual(set(lst.data['results'][0]),
                         set(exemple['results'][0]))
        # Doublon exact refusé (anti-double-comptage) : refus d'ÉTAT = 409.
        self.assertEqual(self._emettre().status_code, 409)

    def test_periode_obligatoire_publiee_a_la_racine(self):
        """ENF11 : la période est ``required`` à la racine du corps publié
        (pas seulement dans les branches ``oneOf``) ; sans elle = 400."""
        from apps.monitoring.views import _CORPS_CERTIFICAT_CARBONE
        corps = _CORPS_CERTIFICAT_CARBONE['application/json']
        self.assertEqual(corps['required'], ['periode_debut', 'periode_fin'])
        for manquant in ('periode_debut', 'periode_fin'):
            r = self.api.post(
                self.URL, {'installation_id': self.inst.id,
                           **{k: '2026-01-01' for k in
                              ('periode_debut', 'periode_fin')
                              if k != manquant}}, format='json')
            self.assertEqual(r.status_code, 400, r.data)

    def test_refus_sans_production_cible_ou_autre_societe(self):
        r = self._emettre(periode_debut='2025-01-01', periode_fin='2025-06-30')
        self.assertEqual(r.status_code, 409)  # aucune production : refus d'ÉTAT
        self.assertIn('detail', r.data)
        r = self._emettre(client_id=self.inst.client_id)
        self.assertEqual(r.status_code, 409)  # ENF11 : cible XOR = règle croisée
        # Système d'une autre société : id bien formé mais inconnu = 404
        # (CI #997 fuzz (2)), même corps qu'un id absent.
        r = self._emettre(installation_id=self.inst_b.id)
        self.assertEqual(r.status_code, 404)
        self.assertIn('installation_id', r.data)
        self.assertEqual(CertificatCarbone.objects.count(), 0)

    def test_certificat_client_consolide(self):
        r = self._emettre(installation_id=None, client_id=self.inst.client_id)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['tco2_evitees'], '0.810')

    def test_recouvrement_et_fin_future_409(self):
        """AMON42 — recouvrement sur la cible ou une cible qui partage ses
        relevés (site ↔ client consolidé) et fin future : 409."""
        from apps.installations.models import Installation
        from apps.monitoring.models import ProductionReading

        s2 = Installation.objects.create(
            company=self.company, reference='ASAV102-2',
            client_id=self.inst.client_id,
            puissance_installee_kwc=Decimal('10'))
        for site in (self.inst, s2):
            ProductionReading.objects.create(
                company=self.company, installation=site,
                date=date(2025, 6, 1), period_days=30,
                energy_kwh=Decimal('1000'))
        an = {'periode_debut': '2025-01-01', 'periode_fin': '2025-12-31'}
        r = self._emettre(**an)
        self.assertEqual(r.status_code, 201, r.data)
        ref = r.data['reference']
        r = self._emettre(periode_debut='2025-06-01', periode_fin='2025-06-30')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn(ref, str(r.data['detail']))
        r = self._emettre(installation_id=None,
                          client_id=self.inst.client_id, **an)
        self.assertEqual(r.status_code, 409, r.data)
        r = self._emettre(periode_debut='2026-01-01', periode_fin='2027-12-31')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('futur', str(r.data['detail']))
        self.assertIn('periode_fin', r.data)
        r = self._emettre(installation_id=s2.id, **an)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            set(CertificatCarbone.objects.values_list(
                'installation_id', flat=True)), {self.inst.id, s2.id})

    def test_facteur_de_la_societe_ou_refus(self):
        """AMON41 — facteur réglé à 630 g : 6 000 kWh ⇒ 3,780 t ; société
        sans facteur : 409 ; attestation : valeur, source et date."""
        from apps.monitoring.models import ProductionReading
        from apps.monitoring.report_carbon import build_carbon_report_data_site
        regler_facteur(self.company, g_kwh='630')
        for site, company in ((self.inst, self.company),
                              (self.inst_b, self.autre)):
            ProductionReading.objects.create(
                company=company, installation=site, date=date(2025, 1, 1),
                period_days=365, energy_kwh=Decimal('6000'))
        an = {'periode_debut': '2025-01-01', 'periode_fin': '2025-12-31'}
        r = self._emettre(**an)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['tco2_evitees'], '3.780')
        r = self.api_b.post(self.URL, {'installation_id': self.inst_b.id, **an},
                            format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('Facteur', str(r.data['detail']))
        data = build_carbon_report_data_site(
            self.inst, since=date(2025, 1, 1), until=date(2025, 12, 31))
        self.assertIn('630 gCO₂/kWh — source ONEE, 15/01/2026',
                      data['methodologie'])
        sans = build_carbon_report_data_site(self.inst_b)
        self.assertIsNone(sans['co2_tonnes'])
        self.assertIsNone(sans['co2_kg_par_kwh'])

    def test_pdf_du_certificat_reference_et_ged(self):
        """AMON94 — l'émission dépose le PDF en GED (`fichier_key`) ; GET
        …/pdf/ rend ce PDF (référence, tonnes figées, facteur et source)."""
        from unittest import mock

        from apps.ged.services import find_document_by_source
        from apps.monitoring.models import ProductionReading
        regler_facteur(self.company, g_kwh='630')
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2025, 1, 1), period_days=365, energy_kwh=Decimal('6000'))
        faux_pdf = (lambda html: b'%PDF-1.4 ' + html.encode('utf-8'))
        with mock.patch('apps.monitoring.report_carbon.render_pdf',
                        side_effect=faux_pdf):
            r = self._emettre(periode_debut='2025-01-01',
                              periode_fin='2025-12-31')
            self.assertEqual(r.status_code, 201, r.data)
            certif = CertificatCarbone.objects.get(pk=r.data['id'])
            self.assertTrue(certif.fichier_key)
            self.assertIsNotNone(find_document_by_source(
                self.company, source_type='monitoring.certificat_carbone',
                source_id=certif.pk))
            pdf = self.api.get(f'{self.URL}{certif.pk}/pdf/')
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        contenu = pdf.content.decode('utf-8', errors='ignore')
        self.assertIn(certif.reference, contenu)
        self.assertIn('3.780', contenu)
        self.assertIn('630 gCO₂/kWh — source ONEE', contenu)
        self.assertEqual(self.api_b.get(
            f'{self.URL}{certif.pk}/pdf/').status_code, 404)

    def test_annuler_puis_reemettre(self):
        """AMON93 — annulation (motif, auteur, date) puis ré-émission de la
        même cible et période ; second « annuler » 409 ; motif vide 400."""
        a = self._emettre().data
        url = f'{self.URL}{a["id"]}/annuler/'
        r = self.api.post(url, {'motif': '  '}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('motif', r.data)
        self.assertEqual(self.api_b.post(
            url, {'motif': 'x'}, format='json').status_code, 404)
        r = self.api.post(url, {'motif': 'Relevé de juin corrigé'},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'annule')
        self.assertEqual(r.data['motif_annulation'], 'Relevé de juin corrigé')
        self.assertIsNotNone(r.data['annule_le'])
        self.assertEqual(r.data['annule_par_nom'], 'asav102_resp')
        self.assertEqual(set(r.data),
                         set(self.contrat['exemple_annulation']['reponse']))
        self.assertEqual(self.api.post(
            url, {'motif': 'encore'}, format='json').status_code, 409)
        b = self._emettre()
        self.assertEqual(b.status_code, 201, b.data)
        self.assertNotEqual(b.data['reference'], a['reference'])
        self.assertEqual(CertificatCarbone.objects.filter(
            statut='emis', installation_id=self.inst.id).count(), 1)

    def test_autre_societe_404_et_normal_403(self):
        cid = self._emettre().data['id']
        self.assertEqual(self.api_b.get(f'{self.URL}{cid}/').status_code, 404)
        self.assertEqual(self.api_b.get(self.URL).data['count'], 0)
        self.assertEqual(self.api_normal.get(self.URL).status_code, 403)
