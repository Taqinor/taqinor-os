# -*- coding: utf-8 -*-
"""AGR123 — le rafraîchisseur d'étude pompage : l'étude suit la pompe
FACTURÉE, à chaque écriture de ligne et à chaque copie.

Sonde C1-03 : un CV 6 saisi donnait une ligne « Pompe 7,5 CV » mais l'étude
gardait ``pompe_cv=6``, ``pompe_kw=4,41`` et un champ 1,16× la pompe réelle.

Réseau : PVGIS et TMY simulés (``profils_horaires_site`` /
``temperatures_du_site`` patchés) — aucun test ne touche le réseau.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_agr123_rafraichir_pompage"
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.parametres.models import CompanyProfile
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.domain import etude_schema, pompage
from apps.ventes.domain.etudes import rafraichir_etudes_du_devis
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.tests._quote_engine_common import make_client
from authentication.models import Company

User = get_user_model()

_JOUR = ([0] * 6 + [100, 300, 500, 700, 850, 950, 1000, 950, 850, 700, 500,
                    300, 100] + [0] * 5)
PROFILS = [[g * (0.7 + 0.05 * i) for g in _JOUR] for i in range(12)]
COURBE = {'debits_m3h': [0, 12, 24, 30, 36, 39],
          'hmt_m': [91, 85, 70, 60, 43, 34]}

ENTREES = {
    'mode_pompe': 'neuve', 'type_pompe': 'immergee', 'alim': 'tri',
    'besoin': {'mode': 'volume_declare', 'volume_m3_jour': 135},
    'hmt_entrees': {'saisie_m': 60},
    'localisation': {'ville': 'Taroudant', 'lat': 30.47, 'lon': -8.88},
}
#: L'étude PÉRIMÉE de la sonde C1-03 (pompe 6 CV saisie à l'écran).
PERIMEE = {'pompe_cv': 6, 'pompe_kw': 4.41, 'champ_kwc': 6.39}


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='agr123-co', defaults={'nom': 'AGR123 Co'})[0]
        profil, _ = CompanyProfile.objects.get_or_create(company=cls.co)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            agricole_pump_hours=Decimal('7'))
        cls.pompe = cls._produit(
            'Pompe immergée OSP 30/8 7,5 CV 380V', role_pompage='pompe',
            type_pompe='immergee', alimentation='tri',
            pompe_kw=Decimal('5.5'), pompe_cv=Decimal('7.5'), tension_v=380,
            courbe_pompe=COURBE)
        cls.variateur = cls._produit(
            'VARIATEUR VEICHI SI23 5.5KW 380V',
            role_pompage='variateur_pompage', alimentation='tri',
            pompe_kw=Decimal('5.5'), tension_v=380)
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.variateur,
            type_fiche='variateur_pompage', ond_mppt_v_min=Decimal('250'),
            ond_mppt_v_max=Decimal('750'), ond_v_max_abs=Decimal('800'),
            ond_i_max_mppt_a=Decimal('20'), ond_phases=3,
            var_v_sortie_v=Decimal('380'))
        cls.panneau = cls._produit('Panneau 710W')
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        cls.client_obj = make_client(cls.co)

    @classmethod
    def _produit(cls, nom, **kw):
        kw.setdefault('prix_vente', Decimal('1000'))
        kw.setdefault('prix_achat', Decimal('600'))
        return Produit.objects.create(company=cls.co, nom=nom, **kw)

    def setUp(self):
        self.user = User.objects.create_user(
            username='agr123_user', password='x', role_legacy='responsable',
            company=self.co)
        for cible, valeur in (('profils_horaires_site', PROFILS),
                              ('temperatures_du_site', None)):
            patcher = mock.patch.object(pompage, cible, return_value=valeur)
            patcher.start()
            self.addCleanup(patcher.stop)

    def devis(self, *, mode='agricole', etude=None, panneaux=10,
              reference='DEV-AGR123-0010'):
        devis = Devis.objects.create(
            company=self.co, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            mode_installation=mode,
            etude_params=dict(ENTREES, **PERIMEE) if etude is None else etude)
        for ordre, (produit, qte) in enumerate((
                (self.pompe, 1), (self.variateur, 1),
                (self.panneau, panneaux))):
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal(qte), prix_unitaire=Decimal('1000'),
                remise=Decimal('0'), ordre=ordre)
        return devis


class EtudeSuitLaPompeFactureeTests(_Base):

    def test_la_pompe_facturee_remplace_l_etude_perimee(self):
        """ROUGE AVANT : l'étude gardait 6 CV / 4,41 kW / 6,39 kWc."""
        devis = self.devis()
        pompage.rafraichir_etude_pompage_devis(devis)
        devis.refresh_from_db()
        etude = devis.etude_params
        self.assertEqual(etude['pompe_kw'], 5.5)
        self.assertEqual(etude['pompe_cv'], 7.5)
        self.assertEqual(etude['champ_kwc'], 7.1)
        self.assertEqual(etude['champ']['nb_panneaux'], 10)
        self.assertEqual(etude['champ']['ratio'], round(7.1 / 5.5, 2))
        self.assertEqual(etude['hmt_m'], 60)
        self.assertEqual(etude['debit_hmt_m3h'], 30.0)
        # Les ENTRÉES ne sont jamais réécrites.
        for cle, valeur in ENTREES.items():
            self.assertEqual(etude[cle], valeur)

    def test_c_est_la_cinquieme_etude_de_l_orchestrateur(self):
        devis = self.devis()
        resultat = rafraichir_etudes_du_devis(devis)
        self.assertIn('etude_pompage', resultat)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['pompe_kw'], 5.5)

    def test_second_appel_sans_changement_zero_ecriture(self):
        devis = self.devis()
        pompage.rafraichir_etude_pompage_devis(devis)
        devis.refresh_from_db()
        avant = (dict(devis.etude_params), devis.updated_at)
        with mock.patch.object(etude_schema, 'ecrire') as ecrire, \
                mock.patch.object(pompage, 'etudier_pompage') as moteur:
            pompage.rafraichir_etude_pompage_devis(devis)
        ecrire.assert_not_called()
        moteur.assert_not_called()
        devis.refresh_from_db()
        self.assertEqual((devis.etude_params, devis.updated_at), avant)

    def test_ligne_pompe_supprimee_derivees_omises(self):
        devis = self.devis()
        pompage.rafraichir_etude_pompage_devis(devis)
        devis.lignes.filter(produit=self.pompe).delete()
        devis.refresh_from_db()
        pompage.rafraichir_etude_pompage_devis(devis)
        devis.refresh_from_db()
        etude = devis.etude_params
        for cle in ('pompe_kw', 'pompe_cv', 'debit_hmt_m3h', 'm3_jour',
                    'heures_pompage', 'champ_kwc', 'production'):
            with self.subTest(cle=cle):
                self.assertNotIn(cle, etude)

    def test_statut_et_lignes_intouches(self):
        devis = self.devis()
        lignes = list(devis.lignes.values_list('id', 'quantite',
                                               'prix_unitaire'))
        pompage.rafraichir_etude_pompage_devis(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'brouillon')
        self.assertEqual(list(devis.lignes.values_list(
            'id', 'quantite', 'prix_unitaire')), lignes)


class LigneDevisViewSetTests(_Base):

    def test_modifier_une_ligne_fait_suivre_l_etude(self):
        devis = self.devis()
        pompage.rafraichir_etude_pompage_devis(devis)
        api = APIClient()
        api.force_authenticate(user=self.user)
        ligne = devis.lignes.get(produit=self.panneau)
        rep = api.patch('/api/django/ventes/devis-lignes/%s/' % ligne.id,
                        {'quantite': '12'}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content[:400])
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['champ_kwc'], 8.52)
        self.assertEqual(devis.etude_params['champ']['nb_panneaux'], 12)


class AutreMarcheInchangeTests(_Base):

    def test_devis_residentiel_strictement_inchange(self):
        etude = {'scenario': 'Sans batterie', 'pompe_kw': 4.41}
        devis = self.devis(mode='residentiel', etude=dict(etude),
                           reference='DEV-AGR123-0020')
        avant = devis.updated_at
        with mock.patch.object(pompage, 'etudier_pompage') as moteur:
            self.assertIsNone(pompage.rafraichir_etude_pompage_devis(devis))
        moteur.assert_not_called()
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params, etude)
        self.assertEqual(devis.updated_at, avant)
