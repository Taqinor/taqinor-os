"""
XFSM6 — Rappel client J-1 automatique avec lien de confirmation.

Couvre :
  * le sweep cible EXACTEMENT les interventions J+1 non confirmées ;
  * idempotent (aucun champ muté sur l'intervention par le sweep) ;
  * template éditable (clé `rappel_rdv`, FR + darija via
    `parametres.MessageTemplate`) ;
  * no-op propre sans email client (pas de crash), compte correct.

Run :
    python manage.py test apps.installations.tests_xfsm6_rappel_rdv -v2
"""
import itertools
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.core import mail

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import Intervention
from apps.installations.services import create_installation_from_devis
from apps.installations.tasks import rappel_rdv_j1, casablanca_today
from apps.parametres.models import MessageTemplate

User = get_user_model()
_seq = itertools.count(1)
# AMSG56 — une clé factice + ``locmem`` = l'envoi est opérationnel.
AVEC_CLE = override_settings(
    ANYMAIL={'SENDGRID_API_KEY': 'sg-test-key'},
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm6-co-{n}', defaults={'nom': nom or f'XFSM6 Co {n}'})
    return company


def make_user(company, role='responsable', username=None, phone=None):
    return User.objects.create_user(
        username=username or f'xfsm6-{next(_seq)}', password='x',
        role_legacy=role, company=company,
        phone_number=phone or '0612345678')


def make_chantier(company, user, client_email='client@example.invalid'):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client', email=client_email,
        telephone='0612345678')  # APAR62 — le brouillon WhatsApp vise le client
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-XFSM6-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, user, company)
    inst.technicien_responsable = user
    inst.save(update_fields=['technicien_responsable'])
    return inst


class TestRappelRdvJ1(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.inst = make_chantier(self.company, self.user)
        self.demain = casablanca_today() + timedelta(days=1)

    def test_cible_exactement_j1_non_confirmees(self):
        cible = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            date_prevue=self.demain, rdv_confirme=False)
        # confirmée : hors cible.
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', created_by=self.user,
            date_prevue=self.demain, rdv_confirme=True)
        # aujourd'hui : hors cible.
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='depannage', created_by=self.user,
            date_prevue=casablanca_today(), rdv_confirme=False)
        # J+2 : hors cible.
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='depannage', created_by=self.user,
            date_prevue=self.demain + timedelta(days=1), rdv_confirme=False)

        result = rappel_rdv_j1()
        self.assertEqual(result['cibles'], 1)
        self.assertEqual(result['jour_cible'], str(self.demain))
        cible.refresh_from_db()
        self.assertFalse(cible.rdv_confirme)  # sweep ne mute rien.

    def test_ne_mute_aucun_champ_intervention(self):
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            date_prevue=self.demain, rdv_confirme=False)
        avant = (interv.statut, interv.date_prevue, interv.rdv_confirme,
                 interv.rdv_reschedule_count)
        rappel_rdv_j1()
        interv.refresh_from_db()
        apres = (interv.statut, interv.date_prevue, interv.rdv_confirme,
                 interv.rdv_reschedule_count)
        self.assertEqual(avant, apres)

    @AVEC_CLE
    def test_email_client_envoye_backend_test(self):
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            date_prevue=self.demain, rdv_confirme=False)
        result = rappel_rdv_j1()
        self.assertEqual(result['emails_envoyes'], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('demain', mail.outbox[0].subject.lower())
        from apps.records.models import Activity
        self.assertFalse(Activity.objects.filter(  # AMSG56 — e-mail parti
            summary='Envoyer ce WhatsApp').exists())

    @AVEC_CLE
    def test_sujet_suit_la_langue_du_client(self):
        """AMSG66 — sujet du rappel lu du modèle d'e-mail ``rappel_rdv`` de
        la société, dans la langue du client ; sans langue : sujet d'avant."""
        from apps.parametres.models_email import EmailTemplate
        EmailTemplate.objects.create(
            company=self.company, cle='rappel_rdv',
            sujet_ar='تذكير بموعد الغد {reference}')
        arabe = make_chantier(self.company, self.user,
                              client_email='ar@example.invalid')
        arabe.client.langue_document = 'ar'
        arabe.client.save(update_fields=['langue_document'])
        for inst in (self.inst, arabe):
            Intervention.objects.create(
                company=self.company, installation=inst,
                type_intervention='pose', created_by=self.user,
                date_prevue=self.demain, rdv_confirme=False)
        rappel_rdv_j1()
        sujets = {m.to[0]: m.subject for m in mail.outbox}
        self.assertEqual(sujets['ar@example.invalid'],
                         f'تذكير بموعد الغد {arabe.reference}')
        self.assertEqual(sujets['client@example.invalid'],
                         'Rappel de rendez-vous — demain')

    @AVEC_CLE
    def test_balayage_rejoue_n_envoie_pas_deux_fois(self):
        """AMSG76 — un balayage rejoué le même jour (worker tué) ne renvoie
        pas le rappel : le marqueur est posé une fois après l'envoi ; un
        marqueur d'un jour passé (RDV replanifié) ne bloque pas."""
        from django.utils import timezone
        premiere = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            date_prevue=self.demain, rdv_confirme=False)
        rappel_rdv_j1()
        premiere.refresh_from_db()
        marque = premiere.rappel_j1_traite_le
        self.assertIsNotNone(marque)
        autre = make_chantier(self.company, self.user,
                              client_email='autre@example.invalid')
        Intervention.objects.create(
            company=self.company, installation=autre,
            type_intervention='pose', created_by=self.user,
            date_prevue=self.demain, rdv_confirme=False,
            rappel_j1_traite_le=timezone.now() - timedelta(days=3))
        rappel_rdv_j1()
        destinataires = sorted(m.to[0] for m in mail.outbox)
        self.assertEqual(destinataires, ['autre@example.invalid',
                                         'client@example.invalid'])
        premiere.refresh_from_db()
        self.assertEqual(premiere.rappel_j1_traite_le, marque)

    def test_sans_email_configure_rien_n_est_compte_et_brouillon_remis(self):
        """AMSG56 — état de la prod (``locmem`` sans clé) : aucun e-mail
        compté, le brouillon WhatsApp devient une tâche sur l'intervention."""
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Activity
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            date_prevue=self.demain, rdv_confirme=False)
        result = rappel_rdv_j1()
        self.assertEqual(result['emails_envoyes'], 0)
        self.assertEqual(len(mail.outbox), 0)
        taches = Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Intervention),
            object_id=interv.pk, summary='Envoyer ce WhatsApp')
        self.assertEqual(taches.count(), 1)
        self.assertIn('wa.me/', taches.get().note)
        self.assertIn(self.inst.reference, taches.get().note)

    def test_brouillon_remis_assigne_au_responsable(self):
        """AMSG96 — la tâche « Envoyer ce WhatsApp » du rappel J-1 (créée sans
        auteur) va au technicien responsable du chantier : visible dans
        « Mes activités »."""
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Activity
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            date_prevue=self.demain, rdv_confirme=False)
        rappel_rdv_j1()
        tache = Activity.objects.get(
            content_type=ContentType.objects.get_for_model(Intervention),
            object_id=interv.pk, summary='Envoyer ce WhatsApp')
        self.assertEqual(tache.assigned_to_id, self.user.id)
        self.assertIsNone(tache.created_by_id)

    def test_no_op_propre_sans_email_client(self):
        inst_sans_email = make_chantier(
            self.company, self.user, client_email='')
        Intervention.objects.create(
            company=self.company, installation=inst_sans_email,
            type_intervention='pose', created_by=self.user,
            date_prevue=self.demain, rdv_confirme=False)
        result = rappel_rdv_j1()  # ne doit jamais lever.
        self.assertEqual(result['cibles'], 1)
        self.assertEqual(result['emails_envoyes'], 0)

    @AVEC_CLE
    def test_template_editable_rappel_rdv(self):
        MessageTemplate.objects.create(
            company=self.company, cle='rappel_rdv',
            corps_fr='Salut {nom}, RDV demain pour {reference} !')
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            date_prevue=self.demain, rdv_confirme=False)
        rappel_rdv_j1()
        self.assertIn('Salut', mail.outbox[-1].body)

    def test_wa_draft_genere_pour_le_client(self):
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            date_prevue=self.demain, rdv_confirme=False)
        result = rappel_rdv_j1()
        self.assertEqual(result['wa_generes'], 1)

    def test_aucune_intervention_j1_compte_zero(self):
        result = rappel_rdv_j1()
        self.assertEqual(result['cibles'], 0)
        self.assertEqual(result['wa_generes'], 0)
        self.assertEqual(result['emails_envoyes'], 0)
