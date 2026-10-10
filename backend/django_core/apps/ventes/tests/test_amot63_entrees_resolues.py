"""AMOT63 (C-AMOT-055) — le moteur pompage persiste les valeurs RÉSOLUES qu'il
a utilisées (``etude_params['entrees_pompage']`` : cultures, région, niveaux,
profondeur, bassin, distance, plaque) et le schéma comme la comparaison
besoin/livré les impriment ; forme figée dans
``contract_samples/etude_pompage_preview.json``.

Chemin RÉEL : ``POST /ventes/devis/auto/`` (``creation_auto`` → moteur
pompage → dérivées) puis ``build_quote_data`` → ``synthese_agricole``. Rejoue
VC agr2/agr3 (schéma ``{'profondeur_m': None, 'niveau_m': None, …}`` alors
que le moteur avait résolu la profondeur et le niveau du lead).

Test-du-test : retirer ``entrees_pompage`` de ``derivees_de_l_etude`` ⇒
``test_schema_porte_les_valeurs_resolues`` rougit.
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Lead
from apps.parametres.models import CompanyProfile
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.domain import pompage
from apps.ventes.domain.pompage import (
    CLES_ENTREES_POMPAGE, rafraichir_etude_pompage_devis)
from apps.ventes.models import Devis
from apps.ventes.quote_engine.agricole.synthese import synthese_agricole
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.tests.test_agr124_devis_auto_agricole import COURBE, PROFILS
from authentication.models import Company

User = get_user_model()

CONTRAT = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'etude_pompage_preview.json')


class EntreesResoluesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='amot63-co', defaults={'nom': 'AMOT63 Co'})[0]
        profil, _ = CompanyProfile.objects.get_or_create(company=cls.co)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            agricole_pump_hours=Decimal('7'))
        variateur = cls._produit(
            'VARIATEUR VEICHI SI23 5.5KW 380V', '6000',
            role_pompage='variateur_pompage', alimentation='tri',
            pompe_kw=Decimal('5.5'), tension_v=380)
        FicheTechnique.objects.create(
            company=cls.co, produit=variateur,
            type_fiche='variateur_pompage', ond_mppt_v_min=Decimal('250'),
            ond_mppt_v_max=Decimal('750'), ond_v_max_abs=Decimal('800'),
            ond_i_max_mppt_a=Decimal('20'), ond_phases=3,
            var_v_sortie_v=Decimal('380'))
        panneau = cls._produit('Panneau 710W', '1100')
        FicheTechnique.objects.create(
            company=cls.co, produit=panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        cls._produit(
            'Pompe immergée OSP 30/8 7,5 CV 380V', '15000',
            role_pompage='pompe', type_pompe='immergee', alimentation='tri',
            pompe_kw=Decimal('5.5'), pompe_cv=Decimal('7.5'), tension_v=380,
            courbe_pompe=COURBE)

    @classmethod
    def _produit(cls, nom, prix, **kw):
        return Produit.objects.create(
            company=cls.co, nom=nom, prix_vente=Decimal(prix),
            prix_achat=Decimal('1'), **kw)

    def setUp(self):
        self.user = User.objects.create_user(
            username='amot63_user', password='x', role_legacy='responsable',
            company=self.co)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        for cible, valeur in (('profils_horaires_site', PROFILS),
                              ('temperatures_du_site', None)):
            patcher = mock.patch.object(pompage, cible, return_value=valeur)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _devis_auto(self):
        lead = Lead.objects.create(
            company=self.co, nom='Ferme', prenom='AMOT63',
            email='amot63@example.com', type_installation='agricole',
            raccordement='triphase', ville='Taroudant',
            gps_lat=Decimal('30.47'), gps_lng=Decimal('-8.88'),
            pompe_hmt_m=Decimal('60'), besoin_eau_m3j=Decimal('135'),
            niveau_statique_m=Decimal('30'), debit_forage_m3h=Decimal('50'),
            profondeur_forage_m=Decimal('80'))
        rep = self.api.post('/api/django/ventes/devis/auto/',
                            {'lead': lead.id}, format='json')
        self.assertEqual(rep.status_code, 201, rep.data)
        return Devis.objects.get(pk=rep.data['id'])

    def test_entrees_resolues_persistees(self):
        devis = self._devis_auto()
        entrees = devis.etude_params.get('entrees_pompage') or {}
        self.assertEqual(float(entrees['niveau_statique_m']), 30.0)
        self.assertEqual(float(entrees['profondeur_forage_m']), 80.0)
        self.assertTrue(set(entrees) <= set(CLES_ENTREES_POMPAGE))
        # CLAUSE PERSISTANCE — rafraîchir deux fois → dérivées identiques.
        rafraichir_etude_pompage_devis(devis, force=True)
        devis.refresh_from_db()
        premier = dict(devis.etude_params)
        rafraichir_etude_pompage_devis(devis, force=True)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['entrees_pompage'],
                         premier['entrees_pompage'])
        self.assertEqual(devis.etude_params['provenance_pompage'],
                         premier['provenance_pompage'])

    def test_schema_porte_les_valeurs_resolues(self):
        devis = self._devis_auto()
        s = synthese_agricole(build_quote_data(devis, {}))
        self.assertEqual(s['schema']['profondeur_m'], 80.0)

    def test_saisie_du_devis_prioritaire(self):
        """Une valeur saisie au devis (``source``) garde la priorité."""
        devis = self._devis_auto()
        etude = dict(devis.etude_params)
        etude['source'] = dict(etude.get('source') or {},
                               profondeur_forage_m=95)
        Devis.objects.filter(pk=devis.pk).update(etude_params=etude)
        devis.refresh_from_db()
        s = synthese_agricole(build_quote_data(devis, {}))
        self.assertEqual(s['schema']['profondeur_m'], 95.0)

    def test_forme_figee_au_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        forme = contrat['cles_etude_params_v2'][
            'forme_derivees_lues_par_le_rendu']
        self.assertEqual(set(forme['entrees_pompage']),
                         set(CLES_ENTREES_POMPAGE))
        self.assertEqual(set(forme['provenance_pompage']),
                         {'entrees', '_empreinte'})
        derivees = {i['cle'] for i in
                    contrat['cles_etude_params_v2']['derivees']}
        self.assertIn('entrees_pompage', derivees)
