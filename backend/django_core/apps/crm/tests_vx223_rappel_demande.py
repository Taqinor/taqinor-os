"""VX223 — « Rappels demandés » : le signal le plus chaud du pipeline
(``contact_preference=='phone_ok'``) n'alimentait jusqu'ici aucune file — un
badge passif sur ``LeadCard.jsx``, jamais actionnable. Couvre :
  - ``leads_rappel_demande`` : filtre exact (phone_ok, hors perdu/archivé,
    company-scopé) ;
  - ``ma_file_commercial_items`` : la 4e famille apparaît avec
    ``kind='rappel'``/``urgency='high'``, aux côtés des trois familles VX83
    existantes (relance/lead_chaud/devis_expire), sans les perturber.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Lead
from apps.crm.selectors import leads_rappel_demande, ma_file_commercial_items
from apps.roles.models import Role

User = get_user_model()


class LeadsRappelDemandeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor VX223', slug='taqinor-vx223')
        self.role = Role.objects.create(
            company=self.company, nom='Admin VX223', permissions=['crm_creer', 'crm_voir'])
        self.user = User.objects.create_user(
            username='vx223_admin', password='x', company=self.company,
            role=self.role, role_legacy='admin')

    def test_seuls_les_leads_phone_ok_reviennent(self):
        rappel = Lead.objects.create(
            company=self.company, nom='Rappel', contact_preference='phone_ok')
        Lead.objects.create(
            company=self.company, nom='WhatsApp seul', contact_preference='whatsapp_only')
        Lead.objects.create(company=self.company, nom='Sans préférence')
        result = list(leads_rappel_demande(self.company, self.user))
        self.assertEqual(result, [rappel])

    def test_exclut_perdu_et_archive(self):
        Lead.objects.create(
            company=self.company, nom='Perdu', contact_preference='phone_ok',
            perdu=True, motif_perte='Prix')
        Lead.objects.create(
            company=self.company, nom='Archivé', contact_preference='phone_ok',
            is_archived=True)
        self.assertEqual(list(leads_rappel_demande(self.company, self.user)), [])

    def test_scope_societe(self):
        other = Company.objects.create(nom='Autre VX223', slug='vx223-autre')
        Lead.objects.create(company=other, nom='Ailleurs', contact_preference='phone_ok')
        self.assertEqual(list(leads_rappel_demande(self.company, self.user)), [])

    def test_liste_vide_jamais_une_exception(self):
        self.assertEqual(list(leads_rappel_demande(self.company, self.user)), [])


class MaFileCommercialItemsRappelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor VX223 File', slug='taqinor-vx223-file')
        self.role = Role.objects.create(
            company=self.company, nom='Admin VX223 File', permissions=['crm_creer'])
        self.user = User.objects.create_user(
            username='vx223_file_admin', password='x', company=self.company,
            role=self.role, role_legacy='admin')

    def test_item_rappel_bien_forme(self):
        lead = Lead.objects.create(
            company=self.company, nom='Alami', prenom='Yasmine',
            contact_preference='phone_ok')
        items = ma_file_commercial_items(self.company, self.user)
        rappel_items = [it for it in items if it['kind'] == 'rappel']
        self.assertEqual(len(rappel_items), 1)
        item = rappel_items[0]
        self.assertEqual(item['urgency'], 'high')
        self.assertEqual(item['link'], f'/crm/leads?lead={lead.id}')
        self.assertIn('Alami', item['title'])
        self.assertIsNone(item['due'])

    def test_absent_quand_aucun_rappel_demande(self):
        Lead.objects.create(company=self.company, nom='Sans préférence')
        items = ma_file_commercial_items(self.company, self.user)
        self.assertEqual([it for it in items if it['kind'] == 'rappel'], [])

    def test_coexiste_avec_les_familles_vx83_existantes(self):
        # Un lead qui alimente la famille « lead chaud » (score élevé, jamais
        # contacté) EN MÊME TEMPS qu'un lead « rappel demandé » distinct :
        # les deux familles doivent apparaître, sans collision.
        Lead.objects.create(
            company=self.company, nom='Chaud', score=90, first_contacted_at=None)
        Lead.objects.create(
            company=self.company, nom='Rappel', contact_preference='phone_ok')
        items = ma_file_commercial_items(self.company, self.user)
        kinds = {it['kind'] for it in items}
        self.assertIn('rappel', kinds)
        self.assertIn('lead_chaud', kinds)
