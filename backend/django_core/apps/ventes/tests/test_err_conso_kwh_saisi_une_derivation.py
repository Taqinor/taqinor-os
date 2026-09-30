"""ERR-QAC-CONSO-KWH-SAISI-DEUX-DERIVATIONS — UNE résolution de la
consommation pour le bloc horaire, le dimensionnement ET l'empreinte.

``etude_horaire._etude_horaire_pour_devis`` passait le kWh mensuel DÉCLARÉ du
lead (CAD166) et le barème société à ``profil_depuis_factures`` ;
``domain.entrees.entrees_depuis_devis`` — qui nourrit le dimensionnement et
l'empreinte ``_empreinte_entrees`` des blocs — ne passait ni l'un ni l'autre.
DEV-202609-0082 : bloc chiffré sur 46 kWh/mois (économie ÷600), dimensionnement
sur 109 880 kWh/an de factures, et l'empreinte ne voyait jamais le kWh : un
kWh effacé ne périmait aucun bloc.

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_err_conso_kwh_saisi_une_derivation -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.ventes.domain import entrees as E
from apps.ventes.domain.entrees import (
    empreinte_entrees, entrees_depuis_devis, entrees_depuis_lead,
)
from apps.ventes.etude_horaire import profil_conso_du_devis
from apps.ventes.models import Devis

User = get_user_model()

FACTURES_12 = [15000] * 12   # 180 000 MAD/an, comme DEV-202609-0082


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
