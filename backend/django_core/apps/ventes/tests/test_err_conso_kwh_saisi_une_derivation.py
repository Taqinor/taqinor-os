"""ERR-QAC-CONSO-KWH-SAISI-DEUX-DERIVATIONS — UNE résolution de la
consommation pour le bloc horaire, le dimensionnement ET l'empreinte.

``etude_horaire._etude_horaire_pour_devis`` passait le kWh mensuel DÉCLARÉ du
lead (CAD166) et le barème société à ``profil_depuis_factures`` ;
``domain.entrees.entrees_depuis_devis`` — qui nourrit le dimensionnement et
l'empreinte ``_empreinte_entrees`` des blocs — ne passait ni l'un ni l'autre.
DEV-202609-0082 : bloc chiffré sur 46 kWh/mois (économie ÷600), dimensionnement
sur 109 880 kWh/an de factures, et l'empreinte ne voyait jamais le kWh : un
kWh effacé ne périmait aucun bloc.

AGNR6 (C-AGNR-001, D-AGNR-1 option (a)) — les DEUX factures tapées à l'écran
(``factures_hiver_ete``, contrat AGNR5 ``factures_client.json``) entrent par
cette même résolution, prioritaires sur celles du lead : marches, jamais une
rampe « réelle ».

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_err_conso_kwh_saisi_une_derivation -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.domain import entrees as E
from apps.ventes.domain import etude_schema as S
from apps.ventes.domain.entrees import (
    empreinte_entrees, entrees_depuis_devis, entrees_depuis_lead,
)
from apps.ventes.etude_horaire import (
    controle_kwh_declare_du_devis, profil_conso_du_devis,
)
from apps.ventes.models import Devis

from .test_cj2b_economies_publiques import _CJ2bBase

User = get_user_model()

FACTURES_12 = [15000] * 12   # 180 000 MAD/an, comme DEV-202609-0082

#: AGNR6 — corps et sorties du contrat partagé AGNR5, jamais recopiés.
CONTRAT_FACTURES = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'factures_client.json').read_text(encoding='utf-8'))
DEUX_FACTURES = CONTRAT_FACTURES['corps_deux_factures']
SORTIE_DEUX = CONTRAT_FACTURES['sorties_moteur']['facture_hiver_ete']


class UneSeuleDerivationTests(TestCase):

    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.create(nom='ERR conso', slug='err-conso-kwh')
        User.objects.create(username='err-conso-user', password='x',
                            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client conso')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='kWh',
            telephone='+212600000001', ville='Casablanca',
            facture_hiver=15000, ete_differente=False,
            conso_mensuelle_kwh=Decimal('46'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ERR-CONSO-01',
            client=self.client_obj, lead=self.lead, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel',
            etude_params={'factures_mensuelles_reelles': FACTURES_12})

    def test_entrees_et_bloc_lisent_la_meme_conso(self):
        tranches, charges = E._reglages_tarifaires_de(self.company)
        conso_bloc, source_bloc, _d = profil_conso_du_devis(
            self.devis, tranches=tranches, charges_fixes_mad=charges)
        entrees = entrees_depuis_devis(self.devis)
        self.assertEqual(source_bloc, 'kwh_mensuel_saisi')
        self.assertEqual(entrees.source_conso, source_bloc)
        self.assertEqual(list(entrees.conso_kwh_mensuelles), list(conso_bloc))
        self.assertEqual(list(entrees.conso_kwh_mensuelles), [46.0] * 12)

    def test_le_chemin_de_garde_lit_la_meme_conso(self):
        garde = entrees_depuis_devis(self.devis, contexte=False)
        self.assertEqual(garde.source_conso, 'kwh_mensuel_saisi')

    def test_kwh_efface_perime_l_empreinte(self):
        avant = empreinte_entrees(entrees_depuis_devis(self.devis))
        Lead.objects.filter(pk=self.lead.pk).update(conso_mensuelle_kwh=None)
        devis = Devis.objects.get(pk=self.devis.pk)
        apres_entrees = entrees_depuis_devis(devis)
        self.assertEqual(apres_entrees.source_conso,
                         'factures_mensuelles_reelles')
        self.assertNotEqual(avant, empreinte_entrees(apres_entrees))

    def test_le_lead_et_son_devis_se_dimensionnent_sur_la_meme_conso(self):
        depuis_lead = entrees_depuis_lead(self.lead, self.company)
        self.assertEqual(depuis_lead.source_conso, 'kwh_mensuel_saisi')
        self.assertEqual(list(depuis_lead.conso_kwh_mensuelles), [46.0] * 12)

    def test_version_moteur_bumpee_perime_les_anciens_blocs(self):
        self.assertNotEqual(E.VERSION_MOTEUR_ENTREES, 'qjr43-1')


class FacturesHiverEteEcranTests(_CJ2bBase):
    """AGNR6 — ``PATCH etude-params {factures_hiver_ete}`` (corps du contrat
    AGNR5) : le moteur calcule sur les MARCHES hiver/été, source
    ``facture_hiver_ete`` ; la taille et l'étude lisent la même série.

    Test-du-test : ne plus lire ``factures_hiver_ete`` dans
    ``profil_conso_du_devis`` ⇒ le devis sans lead retombe sans conso
    (``absente``) et ``test_devis_sans_lead_calcule_sur_les_marches`` échoue ;
    sans la déclaration au schéma, le PATCH répond 400 (clé inconnue)."""

    def _patch(self, devis, corps):
        from authentication.models import CustomUser
        from testkit.factories import UserFactory
        user = UserFactory(company=devis.company,
                           role_legacy=CustomUser.ROLE_RESPONSABLE)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.patch(f'/api/django/ventes/devis/{devis.id}/etude-params/',
                         corps, format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        devis.refresh_from_db()

    def assertMarches(self, serie):
        self.assertEqual([round(v) for v in serie],
                         SORTIE_DEUX['serie_kwh_mensuelle'])
        self.assertEqual(round(sum(serie)), SORTIE_DEUX['conso_annuelle_kwh'])

    def test_la_cle_est_une_entree_ecran_du_moteur(self):
        regle = S.SCHEMA['factures_hiver_ete']
        self.assertEqual((regle['proprietaire'], regle['nature']),
                         (S.ECRAN, S.ENTREE))
        self.assertIn('factures_hiver_ete', S.entrees_du_moteur())
        self.assertEqual(S.valider(CONTRAT_FACTURES['exemple']['etude_params']),
                         [])

    def test_devis_sans_lead_calcule_sur_les_marches(self):
        devis, _lien = self._devis('agnr6-sans-lead', scenario='Sans batterie',
                                   avec_batterie=False, avec_lead=False)
        self._patch(devis, DEUX_FACTURES)
        self.assertEqual(devis.etude_params['factures_hiver_ete'],
                         DEUX_FACTURES['factures_hiver_ete'])
        self.assertNotIn('factures_mensuelles_reelles', devis.etude_params)
        conso, source, detail = profil_conso_du_devis(devis)
        self.assertEqual(source, SORTIE_DEUX['source'])
        self.assertEqual(detail.get('methode'), SORTIE_DEUX['methode'])
        self.assertMarches(conso)
        # La TAILLE lit la MÊME série que l'étude (V_VA p2).
        entrees = entrees_depuis_devis(devis)
        self.assertEqual(entrees.source_conso, SORTIE_DEUX['source'])
        self.assertEqual(list(entrees.conso_kwh_mensuelles), list(conso))

    def test_lead_ete_different_les_factures_tapees_priment(self):
        devis, lien = self._devis('agnr6-lead', scenario='Sans batterie',
                                  avec_batterie=False)
        Lead.objects.filter(pk=devis.lead_id).update(
            facture_ete=Decimal('2600'), ete_differente=True)
        self._patch(devis, DEUX_FACTURES)
        bloc = devis.etude_params.get('etude_horaire')
        self.assertIsNotNone(bloc, 'aucun bloc horaire persisté')
        self.assertEqual(bloc['source_consommation'], SORTIE_DEUX['source'])
        self.assertMarches([m['consommation_kwh'] for m in
                            sorted(bloc['mois'], key=lambda m: m['mois'])])
        # La page publique sert les mêmes marches, aucun second calcul, et
        # l'économie mensuelle porte le libellé client du contrat.
        payload = self._payload(lien)
        self.assertEqual(payload['monthly_consumption'],
                         SORTIE_DEUX['serie_kwh_mensuelle'])
        note = payload['economies_mensuelles']['note']
        self.assertTrue(note.startswith(SORTIE_DEUX['libelle_client']), note)
        self.assertNotIn('réelles', note)
        # Rouvrir puis ré-enregistrer sans toucher : rien ne bouge.
        avant = Devis.objects.get(pk=devis.pk).etude_params
        self._patch(devis, DEUX_FACTURES)
        self.assertEqual(Devis.objects.get(pk=devis.pk).etude_params, avant)

    def test_la_note_publique_nomme_les_deux_factures(self):
        from apps.ventes.public import payload_economie as PE
        libelle = SORTIE_DEUX['libelle_client']
        for note in (PE._note_economies_mensuelles('horaire', 'facture_hiver_ete',
                                                   True),
                     PE._note_economies_mensuelles_standard('facture_hiver_ete')):
            with self.subTest(note=note):
                self.assertTrue(note.startswith(libelle), note)
                self.assertNotIn('réelles', note)
                self.assertFalse(any(c.isdigit() for c in note))
        # Les autres sources gardent leur note.
        self.assertNotIn(libelle, PE._note_economies_mensuelles(
            'horaire', 'facture_hiver', True))
        self.assertEqual(PE._note_economies_mensuelles_standard('facture_hiver'),
                         PE._note_economies_mensuelles_standard())

    def test_douze_mois_tapes_restent_la_source(self):
        devis, _lien = self._devis('agnr6-douze', scenario='Sans batterie',
                                   avec_batterie=False, avec_lead=False)
        self._patch(devis, dict(DEUX_FACTURES,
                                **CONTRAT_FACTURES['corps_douze_mois_tapes']))
        _conso, source, _detail = profil_conso_du_devis(devis)
        self.assertEqual(source, 'factures_mensuelles_reelles')

    def test_la_garde_kwh_confronte_les_factures_tapees(self):
        devis, _lien = self._devis('agnr6-garde', scenario='Sans batterie',
                                   avec_batterie=False)
        Lead.objects.filter(pk=devis.lead_id).update(
            facture_hiver=None, conso_mensuelle_kwh=Decimal('46'))
        self._patch(devis, DEUX_FACTURES)
        garde = controle_kwh_declare_du_devis(devis)
        self.assertIsNotNone(garde)
        self.assertFalse(garde['coherent'])
