"""CAD57 — validité J+30 pour un dossier financé, J+14 sinon.

[TRANCHÉ 21/09/2026] La validité était posée sur la DERNIÈRE touche de la
cadence, c'est-à-dire J+14 : le devis expirait le jour exact où le suivi
s'arrête. Or la loi 31-08 impose, une fois l'offre de crédit émise, 10 jours
de réflexion PUIS 7 jours de rétractation avant déblocage — un client qui
finance ne peut pas, légalement, boucler dans cette fenêtre.

Garde-fou vérifié ici : la DURÉE vient d'un réglage société
(``CompanyProfile.quote_validity_days``), jamais d'un nombre écrit dans le
code du message ; et le message J9 cite la MÊME date que le devis (CAD59).

Le temps est GELÉ : « J+30 » est exactement ce qu'une horloge vivante rend
instable.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from core.events import devis_sent

from apps.crm import horaires
from apps.crm.models import Client, Lead, RelanceEtape
from apps.crm.services import lead_finance_a_credit
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis
from apps.ventes.services import jours_validite_societe

User = get_user_model()

#: Lundi 7 septembre 2026, 10 h — l'envoi du devis.
ENVOI = datetime.datetime(2026, 9, 7, 10, 0, tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'cad57'
    financement = None

    def setUp(self):
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        self.profil = CompanyProfile.objects.create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur,
            telephone='+212661112233', financing_intent=self.financement)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client',
            email=f'{self.slug}@example.com')

    def _envoyer(self, reference='DEV-CAD57-0001'):
        devis = Devis.objects.create(
            company=self.company, reference=reference,
            client=self.client_obj, lead=self.lead, statut='envoye',
            taux_tva=Decimal('20.00'), date_envoi=ENVOI)
        devis_sent.send(sender='test', devis=devis, user=self.acteur,
                        ancien_statut='brouillon')
        devis.refresh_from_db()
        return devis

    def _fin_du_suivi(self):
        """La dernière échéance du plan après-devis matérialisé/prévu."""
        derniere = (self.lead.relance_etapes
                    .filter(cadence='apres_devis', due_at__isnull=False)
                    .order_by('-due_at').first())
        return (derniere.due_at.astimezone(horaires.CASABLANCA).date()
                if derniere else None)


class ComptantTests(_Base):
    slug = 'cad57-comptant'
    financement = 'cash'

    def test_un_devis_comptant_expire_a_la_FIN_DU_SUIVI(self):
        """Comportement VALID1 inchangé — J+14, la dernière touche."""
        devis = self._envoyer()
        self.assertIsNotNone(devis.date_validite)
        self.assertEqual(
            devis.date_validite, ENVOI.date() + datetime.timedelta(days=14))

    def test_le_lead_comptant_n_est_pas_un_dossier_finance(self):
        self.assertFalse(lead_finance_a_credit(self.lead))


class IndecisTests(_Base):
    slug = 'cad57-indecis'
    financement = 'indecis'

    def test_pas_encore_decide_ne_declenche_RIEN(self):
        """On n'allonge pas une validité sur une supposition."""
        devis = self._envoyer()
        self.assertEqual(
            devis.date_validite, ENVOI.date() + datetime.timedelta(days=14))
        self.assertFalse(lead_finance_a_credit(self.lead))


class CreditTests(_Base):
    slug = 'cad57-credit'
    financement = 'credit'

    def test_un_devis_finance_porte_la_validite_du_REGLAGE_SOCIETE(self):
        devis = self._envoyer()
        jours = jours_validite_societe(self.company)
        self.assertEqual(jours, self.profil.quote_validity_days)
        self.assertEqual(
            devis.date_validite,
            ENVOI.date() + datetime.timedelta(days=jours))

    def test_elle_est_PLUS_LOINTAINE_que_la_fin_du_suivi(self):
        devis = self._envoyer()
        self.assertGreater(devis.date_validite, self._fin_du_suivi())

    def test_la_duree_suit_le_reglage_societe_et_non_un_nombre_ecrit(self):
        """Zéro chiffre inventé : changer le réglage change la date."""
        self.profil.quote_validity_days = 45
        self.profil.save(update_fields=['quote_validity_days'])
        devis = self._envoyer('DEV-CAD57-0045')
        self.assertEqual(
            devis.date_validite, ENVOI.date() + datetime.timedelta(days=45))

    def test_un_reglage_plus_COURT_que_le_suivi_ne_raccourcit_rien(self):
        """Une société qui règle 10 jours ne se retrouve pas avec un devis
        financé qui expire AVANT la fin de son propre suivi."""
        self.profil.quote_validity_days = 10
        self.profil.save(update_fields=['quote_validity_days'])
        devis = self._envoyer('DEV-CAD57-0010')
        self.assertEqual(devis.date_validite, self._fin_du_suivi())

    def test_une_validite_deja_SAISIE_a_la_main_n_est_jamais_ecrasee(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-CAD57-MAIN',
            client=self.client_obj, lead=self.lead, statut='envoye',
            taux_tva=Decimal('20.00'), date_envoi=ENVOI,
            date_validite=datetime.date(2026, 10, 31))
        devis_sent.send(sender='test', devis=devis, user=self.acteur,
                        ancien_statut='brouillon')
        devis.refresh_from_db()
        self.assertEqual(devis.date_validite, datetime.date(2026, 10, 31))


class MessageJ9Tests(_Base):
    slug = 'cad57-message'
    financement = 'credit'

    def test_le_message_J9_cite_la_MEME_date_que_le_devis(self):
        from apps.crm.services import message_pour_etape

        devis = self._envoyer()
        etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=7, due_at=ENVOI + datetime.timedelta(days=9),
            due_date=(ENVOI + datetime.timedelta(days=9)).date(),
            canal='whatsapp', libelle='Validité de la proposition',
            template_cle='j9_validite', devis=devis)

        rendu = message_pour_etape(etape, user=self.acteur)

        self.assertIn(devis.date_validite.strftime('%d/%m/%Y'),
                      rendu['message'])
