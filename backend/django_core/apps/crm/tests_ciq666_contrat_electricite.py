"""CIQ666 — contrat d'électricité DÉCLARÉ sur le lead pro (décision fondateur
08/10/2026), lu par ``entrees_ci_du_lead`` comme ``tarif_declare``.

Contrat partagé : ``apps/crm/contract_samples/lead_pro.json`` (``colonnes_pro``
+ ``entrees_ci.cibles``). Jamais un contrat supposé : « ne sait pas » et vide
n'émettent aucune entrée.

Run :
    python manage.py test apps.crm.tests_ciq666_contrat_electricite -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.crm.selectors import entrees_ci_du_lead
from apps.parametres.tarifs_officiels import CONTRATS
from authentication.models import Company

User = get_user_model()


def _entree_contrat(bloc):
    return next((e for e in bloc['entrees']
                 if e['colonne'] == 'contrat_electricite'), None)


class EntreeContrat(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ciq666-co', defaults={'nom': 'CIQ666 Co'})

    def _lead(self, **kw):
        kw.setdefault('type_installation', 'commercial')
        kw.setdefault('tension_raccordement', 'bt')
        return Lead.objects.create(company=self.company, nom='Pro', **kw)

    def test_les_choix_sont_le_vocabulaire_du_tarif_declare(self):
        valeurs = [v for v, _ in
                   Lead._meta.get_field('contrat_electricite').choices]
        self.assertEqual(valeurs, list(CONTRATS) + ['ne_sait_pas'])

    def test_contrat_declare_devient_tarif_declare(self):
        bloc = entrees_ci_du_lead(self._lead(contrat_electricite='bt_patente'))
        entree = _entree_contrat(bloc)
        self.assertEqual(entree['valeur'], {'contrat': 'bt_patente'})
        self.assertEqual(entree['cle_etude'], 'tarif_declare')
        self.assertEqual(entree['chemin'], 'tarif_declare')
        self.assertEqual(entree['provenance']['origine'], 'lead')
        self.assertNotIn('contrat_electricite', bloc['manquants'])

    def test_vide_ou_ne_sait_pas_aucune_entree_et_manquant(self):
        for valeur in (None, 'ne_sait_pas'):
            bloc = entrees_ci_du_lead(self._lead(contrat_electricite=valeur))
            self.assertIsNone(_entree_contrat(bloc), valeur)
            self.assertIn('contrat_electricite', bloc['manquants'], valeur)

    def test_mt_sans_contrat_n_en_manque_pas(self):
        bloc = entrees_ci_du_lead(self._lead(tension_raccordement='mt'))
        self.assertIsNone(_entree_contrat(bloc))
        self.assertNotIn('contrat_electricite', bloc['manquants'])

    def test_bi_horaire_seulement_pour_la_force_motrice(self):
        fm = entrees_ci_du_lead(self._lead(
            contrat_electricite='bt_force_motrice',
            option_tarifaire_bt='bi_horaire'))
        self.assertEqual(_entree_contrat(fm)['valeur'],
                         {'contrat': 'bt_force_motrice',
                          'option_bi_horaire': True})
        normale = entrees_ci_du_lead(self._lead(
            contrat_electricite='bt_force_motrice',
            option_tarifaire_bt='normale'))
        self.assertEqual(_entree_contrat(normale)['valeur'],
                         {'contrat': 'bt_force_motrice',
                          'option_bi_horaire': False})
        # Une option restée en base sur un autre contrat n'est jamais
        # transmise (la grille patenté n'a pas de bi-horaire).
        lead = self._lead(contrat_electricite='bt_patente')
        Lead.objects.filter(pk=lead.pk).update(option_tarifaire_bt='bi_horaire')
        lead.refresh_from_db()
        self.assertEqual(_entree_contrat(entrees_ci_du_lead(lead))['valeur'],
                         {'contrat': 'bt_patente'})


class SaisieParLApi(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ciq666-api', defaults={'nom': 'CIQ666 API'})
        self.user = User.objects.create_user(
            username='ciq666_user', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Commerce CIQ666',
            type_installation='commercial')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.url = f'/api/django/crm/leads/{self.lead.id}/'

    def test_patch_puis_get_et_entree_servie(self):
        resp = self.api.patch(self.url, {
            'contrat_electricite': 'bt_force_motrice',
            'option_tarifaire_bt': 'bi_horaire'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lu = self.api.get(self.url).data
        self.assertEqual(lu['contrat_electricite'], 'bt_force_motrice')
        self.assertEqual(lu['option_tarifaire_bt'], 'bi_horaire')
        entree = _entree_contrat(lu['entrees_ci'])
        self.assertEqual(entree['valeur'], {'contrat': 'bt_force_motrice',
                                            'option_bi_horaire': True})

    def test_bi_horaire_hors_force_motrice_400_nomme_le_champ(self):
        resp = self.api.patch(self.url, {
            'contrat_electricite': 'bt_patente',
            'option_tarifaire_bt': 'bi_horaire'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('option_tarifaire_bt', resp.data)

    def test_contrat_inconnu_refuse(self):
        resp = self.api.patch(self.url, {'contrat_electricite': 'plat_1_20'},
                              format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('contrat_electricite', resp.data)
