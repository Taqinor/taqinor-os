"""CIQ500 — le placeholder ``{societe}`` : un message B2B peut nommer
l'entreprise, sans jamais laisser un blanc.

``{societe}`` = la raison sociale du lead (``Lead.societe``, nettoyée — contrat
CIQ1 ``lead_pro.json``). Elle rejoint les DEUX contextes de rendu (touches
``message_pour_etape`` et visite ``message_visite_pour_lead``), la liste des
placeholders rendus et celle de l'éditeur (``PLACEHOLDERS_RELANCE``). Vide ⇒
la phrase qui la porte est OMISE (MRY13) et ``societe`` figure dans
``placeholders_manquants`` (contrat ``relance_etape_message.json``, bloc
``ajout_ciq10``). La salutation reste civilité + prénom (CAD65).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import horaires
from apps.crm.models import Lead, RelanceEtape
from apps.crm.cadence_messages import (
    _PLACEHOLDERS_RENDUS,
    message_pour_etape,
    message_visite_pour_lead,
)
from apps.parametres.models import CompanyProfile
from apps.parametres.models_messages import (
    PLACEHOLDERS_RELANCE, MessageTemplate)

User = get_user_model()

LUNDI = datetime.datetime(2026, 9, 7, 9, 0, tzinfo=horaires.CASABLANCA)
GABARIT = 'Étude pour {societe}. Bonjour {prenom}.'


class _Base(TestCase):
    slug = 'ciq500'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company,
            first_name='Meryem')
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', prenom='Aziz',
            ville='Casablanca', telephone='+212651971400',
            owner=self.acteur, type_installation='commercial',
            societe='  Hôtel   Exemple SARL ')

    def _touche(self):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=1, canal='whatsapp',
            due_date=LUNDI.date(), due_at=LUNDI, cadence='contact',
            template_cle='identite')

    def _sans_societe(self):
        self.lead.societe = ''
        self.lead.save(update_fields=['societe'])


class PlaceholderDeclareTests(TestCase):
    def test_societe_est_rendu_et_propose_a_l_editeur(self):
        self.assertIn('societe', _PLACEHOLDERS_RENDUS)
        self.assertIn('{societe}', PLACEHOLDERS_RELANCE)


class ToucheTests(_Base):
    slug = 'ciq500-touche'

    def setUp(self):
        super().setUp()
        MessageTemplate.objects.create(
            company=self.company, cle='identite', corps_fr=GABARIT)

    def test_a_la_societe_est_rendue_nettoyee(self):
        rendu = message_pour_etape(self._touche(), user=self.acteur)
        self.assertIn('Étude pour Hôtel Exemple SARL.', rendu['message'])
        self.assertIn('Bonjour Aziz', rendu['message'])
        self.assertNotIn('{societe}', rendu['message'])
        self.assertNotIn('societe', rendu['placeholders_manquants'])

    def test_b_sans_societe_seule_la_phrase_est_omise(self):
        self._sans_societe()
        rendu = message_pour_etape(self._touche(), user=self.acteur)
        self.assertNotIn('Étude pour', rendu['message'])
        self.assertNotIn('{societe}', rendu['message'])
        self.assertIn('Bonjour Aziz', rendu['message'])
        self.assertIn('societe', rendu['placeholders_manquants'])


class VisiteTests(_Base):
    slug = 'ciq500-visite'

    def setUp(self):
        super().setUp()
        MessageTemplate.objects.create(
            company=self.company, cle='visite_proposition', corps_fr=GABARIT)

    def test_c_message_visite_avec_societe(self):
        rendu = message_visite_pour_lead(
            self.lead, 'visite_proposition', user=self.acteur)
        self.assertIn('Étude pour Hôtel Exemple SARL.', rendu['corps_fr'])
        self.assertIn('Bonjour Aziz', rendu['corps_fr'])

    def test_c_message_visite_sans_societe_omet_la_phrase(self):
        self._sans_societe()
        rendu = message_visite_pour_lead(
            self.lead, 'visite_proposition', user=self.acteur)
        self.assertNotIn('Étude pour', rendu['corps_fr'])
        self.assertNotIn('{societe}', rendu['corps_fr'])
        self.assertIn('Bonjour Aziz', rendu['corps_fr'])
