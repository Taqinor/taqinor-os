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
from django.test import TestCase
from django.core import mail

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import Intervention
from apps.installations.services import create_installation_from_devis
from apps.installations.tasks import rappel_rdv_j1, casablanca_today
from apps.parametres.models import MessageTemplate

User = get_user_model()
_seq = itertools.count(1)


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
        company=company, nom='Site', prenom='Client', email=client_email)
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

    def test_email_client_envoye_backend_test(self):
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            date_prevue=self.demain, rdv_confirme=False)
        result = rappel_rdv_j1()
        self.assertEqual(result['emails_envoyes'], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('demain', mail.outbox[0].subject.lower())

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

    def test_wa_draft_genere_avec_responsable(self):
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
