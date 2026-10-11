"""ACRM62 (C-ACRM-028, D-ACRM-5 (2)=(a)) — l'opposition survit à l'effacement.

Sonde V_VB LSVC5-3 : un lead « ne plus contacter » effacé (DSR) puis recréé
repartait vierge — drapeau faux, cadence posée. Désormais l'effacement
(chemin unique ``dsr_provider.anonymiser_lead``) laisse une EMPREINTE hachée
seule de l'e-mail et du téléphone, et tout lead qui naît avec l'une d'elles
naît « ne plus contacter ».

Nouveau fichier car : aucun module existant ne couvre l'opposition après
effacement. Aucun mock : effacement, création et cadence réels.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import dsr_provider
from apps.crm.cadence_reponses import creer_lead_proprietaire
from apps.crm.leads_doublons import normalize_email, normalize_phone
from apps.crm.models import EmpreinteOpposition, Lead, RelanceEtape

User = get_user_model()

EMAIL = 'Sara.Opposee@Example.com'
TELEPHONE = '+212661626262'
TELEPHONE_LOCAL = '0661 62 62 62'


class EmpreinteOppositionTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM62 Solaire', slug='acrm62-opposition')
        self.autre = Company.objects.create(
            nom='ACRM62 Autre', slug='acrm62-autre')
        self.user = User.objects.create_user(
            username='acrm62-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.oppose = Lead.objects.create(
            company=self.company, nom='Sara', email=EMAIL,
            telephone=TELEPHONE, ne_plus_contacter=True, owner=self.user)
        self.locataire = Lead.objects.create(
            company=self.company, nom='Locataire', telephone='+212700000062',
            owner=self.user)

    def _effacer(self):
        dsr_provider.erase_crm(self.company, EMAIL)

    def test_lead_recree_nait_oppose(self):
        self._effacer()
        proprietaire, cree = creer_lead_proprietaire(
            self.locataire, self.user,
            {'nom': 'Sara', 'telephone': TELEPHONE_LOCAL})
        self.assertTrue(cree)
        proprietaire = Lead.objects.get(pk=proprietaire.pk)
        self.assertTrue(proprietaire.ne_plus_contacter)
        self.assertFalse(
            RelanceEtape.objects.filter(lead=proprietaire).exists())
        # Même personne par une autre porte, e-mail en casse différente.
        par_email = Lead.objects.create(
            company=self.company, nom='Sara', email='  SARA.opposee@example.COM')
        self.assertTrue(Lead.objects.get(pk=par_email.pk).ne_plus_contacter)

    def test_aucune_valeur_en_clair(self):
        self._effacer()
        empreintes = list(EmpreinteOpposition.objects.filter(
            company=self.company).values_list('nature', 'empreinte'))
        self.assertEqual(sorted(n for n, _ in empreintes),
                         ['email', 'telephone'])
        clairs = {EMAIL, EMAIL.lower(), TELEPHONE, normalize_email(EMAIL),
                  normalize_phone(TELEPHONE)}
        for _nature, empreinte in empreintes:
            self.assertRegex(empreinte, r'^[0-9a-f]{64}$')
            for clair in clairs:
                self.assertNotIn(clair, empreinte)
        # Un second effacement de la même personne ne duplique rien.
        self._effacer()
        self.assertEqual(EmpreinteOpposition.objects.filter(
            company=self.company).count(), 2)

    def test_non_oppose_sans_empreinte(self):
        Lead.objects.filter(pk=self.oppose.pk).update(ne_plus_contacter=False)
        self._effacer()
        self.assertFalse(EmpreinteOpposition.objects.exists())
        recree = Lead.objects.create(
            company=self.company, nom='Sara', email=EMAIL, telephone=TELEPHONE)
        self.assertFalse(Lead.objects.get(pk=recree.pk).ne_plus_contacter)

    def test_autre_societe_intacte(self):
        self._effacer()
        ailleurs = Lead.objects.create(
            company=self.autre, nom='Sara', email=EMAIL, telephone=TELEPHONE)
        self.assertFalse(Lead.objects.get(pk=ailleurs.pk).ne_plus_contacter)
        self.assertFalse(
            EmpreinteOpposition.objects.filter(company=self.autre).exists())
