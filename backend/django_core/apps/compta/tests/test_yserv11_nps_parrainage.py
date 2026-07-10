"""Tests YSERV11 — NPS promoteur → demande de parrainage à l'enchantement.

Couvre : réponse 9-10 + toggle ``referral_enabled`` ON → notification au
commercial du client (« Client promoteur — proposer le parrainage ») avec
brouillon WhatsApp wa.me construit sur le MessageTemplate « parrainage »
(clé posée additivement, FR + darija éditables) + lien de création de
Parrainage (parrain pré-rempli) — UNE seule fois (idempotent par enquête) ;
réponse 0-6 → activité de rappel « Client détracteur — rappeler » assignée
au responsable ; toggle OFF (défaut) → rien ; passif (7-8) → rien.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.compta import services
from apps.compta.models import EnqueteNPS
from apps.crm.models import Client, Lead, MessageTemplate
from apps.notifications.models import EventType, Notification
from apps.parametres.models_company import CompanyProfile
from apps.records.models import Activity

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class _Base(TestCase):
    referral = True

    def setUp(self):
        self.company = make_company(
            f'yserv11-{self.__class__.__name__.lower()}',
            'YSERV11 Co')
        CompanyProfile.objects.create(
            company=self.company, referral_enabled=self.referral)
        self.commercial = User.objects.create_user(
            username=f'yserv11-com-{self.__class__.__name__.lower()}',
            password='x', company=self.company, role_legacy='commercial')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Yasmine',
            email='yasmine@example.com', telephone='+212600000051')
        # Le commercial du client = owner du lead le plus récent lié.
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Yasmine',
            client=self.client_obj, owner=self.commercial)
        self.enquete = EnqueteNPS.objects.create(
            company=self.company, client_id=self.client_obj.id,
            chantier_id=901)


class TestPromoteurDeclencheParrainage(_Base):
    def test_score_9_notifie_le_commercial_avec_brouillon(self):
        services.repondre_enquete_nps(self.enquete, score=9)
        notes = Notification.objects.filter(
            company=self.company, recipient=self.commercial,
            event_type=EventType.NPS_PROMOTEUR)
        self.assertEqual(notes.count(), 1)
        note = notes.first()
        self.assertIn('proposer le parrainage', note.title)
        # Brouillon construit sur le MessageTemplate (prenom substitué).
        self.assertIn('Yasmine', note.body)
        self.assertIn('Brouillon :', note.body)
        # Lien wa.me (le client a un téléphone).
        self.assertIn('wa.me', note.body)
        # Lien frontend de création de Parrainage, parrain pré-rempli.
        self.assertEqual(
            note.link, f'/crm/parrainage?parrain={self.client_obj.id}')

    def test_template_parrainage_cree_additivement_et_editable(self):
        services.repondre_enquete_nps(self.enquete, score=10)
        template = MessageTemplate.objects.get(
            company=self.company, nom='parrainage')
        self.assertEqual(template.langue, MessageTemplate.Langue.FR)
        self.assertIn('{prenom}', template.corps)

    def test_langue_darija_prend_le_gabarit_darija(self):
        self.lead.langue_preferee = 'darija'
        self.lead.save(update_fields=['langue_preferee'])
        services.repondre_enquete_nps(self.enquete, score=9)
        self.assertTrue(
            MessageTemplate.objects.filter(
                company=self.company, nom='parrainage_darija',
                langue=MessageTemplate.Langue.DARIJA).exists())

    def test_idempotent_une_seule_notification(self):
        services.repondre_enquete_nps(self.enquete, score=9)
        # Ré-appel (déjà répondue) → aucun second déclenchement.
        services.repondre_enquete_nps(self.enquete, score=9)
        self.assertEqual(
            Notification.objects.filter(
                company=self.company,
                event_type=EventType.NPS_PROMOTEUR).count(),
            1)

    def test_passif_7_8_ne_declenche_rien(self):
        services.repondre_enquete_nps(self.enquete, score=7)
        # Filtre event_type : la fixture (Lead avec owner) emet deja un
        # lead_assigned legitime qui n'a rien a voir avec le flux NPS.
        self.assertEqual(Notification.objects.filter(
            company=self.company,
            event_type=EventType.NPS_PROMOTEUR).count(), 0)
        self.assertEqual(Activity.objects.filter(
            company=self.company).count(), 0)


class TestDetracteurOuvreRappel(_Base):
    def test_score_3_ouvre_activite_de_rappel(self):
        services.repondre_enquete_nps(self.enquete, score=3)
        activites = Activity.objects.filter(
            company=self.company, assigned_to=self.commercial)
        self.assertEqual(activites.count(), 1)
        act = activites.first()
        self.assertEqual(act.summary, 'Client détracteur — rappeler')
        self.assertEqual(act.object_id, self.client_obj.id)
        self.assertIn(f'[nps:{self.enquete.id}]', act.note)
        # Aucune notification promoteur sur ce chemin.
        self.assertEqual(
            Notification.objects.filter(
                company=self.company,
                event_type=EventType.NPS_PROMOTEUR).count(),
            0)

    def test_idempotent_une_seule_activite(self):
        services.repondre_enquete_nps(self.enquete, score=2)
        services.repondre_enquete_nps(self.enquete, score=2)
        self.assertEqual(
            Activity.objects.filter(company=self.company).count(), 1)


class TestToggleOff(_Base):
    referral = False

    def test_toggle_off_promoteur_rien(self):
        services.repondre_enquete_nps(self.enquete, score=10)
        self.assertEqual(
            Notification.objects.filter(
                company=self.company,
                event_type=EventType.NPS_PROMOTEUR).count(), 0)
        self.assertFalse(
            MessageTemplate.objects.filter(
                company=self.company, nom='parrainage').exists())

    def test_toggle_off_detracteur_rien(self):
        services.repondre_enquete_nps(self.enquete, score=1)
        self.assertEqual(
            Activity.objects.filter(company=self.company).count(), 0)

    def test_reponse_toujours_enregistree(self):
        services.repondre_enquete_nps(self.enquete, score=10)
        self.enquete.refresh_from_db()
        self.assertEqual(self.enquete.score, 10)
        self.assertEqual(self.enquete.statut, EnqueteNPS.Statut.REPONDUE)


class TestMultiTenant(TestCase):
    def test_suivi_reste_dans_sa_societe(self):
        co_a = make_company('yserv11-mt-a', 'YSERV11 MT A')
        co_b = make_company('yserv11-mt-b', 'YSERV11 MT B')
        CompanyProfile.objects.create(company=co_a, referral_enabled=True)
        CompanyProfile.objects.create(company=co_b, referral_enabled=True)
        com_a = User.objects.create_user(
            username='yserv11-mt-com-a', password='x', company=co_a,
            role_legacy='commercial')
        client_a = Client.objects.create(
            company=co_a, nom='ClientA', telephone='+212600000052')
        Lead.objects.create(
            company=co_a, nom='ClientA', client=client_a, owner=com_a)
        enquete_a = EnqueteNPS.objects.create(
            company=co_a, client_id=client_a.id)
        services.repondre_enquete_nps(enquete_a, score=9)
        self.assertEqual(
            Notification.objects.filter(
                company=co_a, event_type=EventType.NPS_PROMOTEUR).count(), 1)
        self.assertEqual(
            Notification.objects.filter(company=co_b).count(), 0)
        self.assertFalse(
            MessageTemplate.objects.filter(company=co_b).exists())
