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

#: La FIN DU SUIVI de ce devis-là : la DERNIÈRE touche de la partition
#: `apres_devis`, mardi 22/09/2026. Ce n'est pas « ENVOI + 14 jours » et ce
#: n'est plus censé l'être : la touche J+13 tombe le dimanche 20/09, glisse
#: au lundi 21/09 dans le créneau des messages (CAD19 ancre ouvrable, CAD25
#: créneaux par type de touche), et la règle « jamais plus d'un message par
#: jour » (CAD20) pousse alors la touche J+14 au mardi 22/09. Le protocole
#: n'a ni gagné ni perdu de touche : seule la DATE de la dernière a bougé.
#: VALID1 pose la validité sur cette date — la fin du suivi, pas un J+N.
FIN_DU_SUIVI = datetime.date(2026, 9, 22)


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
        """Comportement VALID1 inchangé — la DERNIÈRE touche du suivi.

        L'attente était écrite « ENVOI + 14 jours », un raccourci qui a cessé
        d'être vrai le jour même : voir ``FIN_DU_SUIVI``. Ce qui est vérifié
        reste exactement la règle CAD57 — un dossier NON financé garde la fin
        du suivi, jamais la validité allongée du réglage société.
        """
        devis = self._envoyer()
        self.assertIsNotNone(devis.date_validite)
        self.assertEqual(devis.date_validite, FIN_DU_SUIVI)
        self.assertNotEqual(
            devis.date_validite,
            ENVOI.date() + datetime.timedelta(
                days=jours_validite_societe(self.company)))

    def test_le_lead_comptant_n_est_pas_un_dossier_finance(self):
        self.assertFalse(lead_finance_a_credit(self.lead))


class IndecisTests(_Base):
    slug = 'cad57-indecis'
    financement = 'indecis'

    def test_pas_encore_decide_ne_declenche_RIEN(self):
        """On n'allonge pas une validité sur une supposition.

        Même correction d'attente que ci-dessus : la fin du suivi
        (``FIN_DU_SUIVI``), pas le raccourci « ENVOI + 14 jours ».
        """
        devis = self._envoyer()
        self.assertEqual(devis.date_validite, FIN_DU_SUIVI)
        self.assertNotEqual(
            devis.date_validite,
            ENVOI.date() + datetime.timedelta(
                days=jours_validite_societe(self.company)))
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


class _SubventionBase(_Base):
    """AGR523 — un dossier de subvention DÉPOSÉ (en instruction) reçoit la
    validité du réglage société, comme le crédit — aucun nombre propre à la
    FDA."""
    financement = 'cash'
    dossier = None

    def setUp(self):
        super().setUp()
        if self.dossier:
            self.lead.dossier_subvention = self.dossier
            self.lead.dossier_subvention_le = datetime.date(2026, 9, 1)
            self.lead.save(update_fields=['dossier_subvention',
                                          'dossier_subvention_le'])


class SubventionDeposeeTests(_SubventionBase):
    slug = 'agr523-depose'
    dossier = 'depose'

    def test_depose_et_reglage_30j_donne_le_plus_lointain(self):
        self.profil.quote_validity_days = 30
        self.profil.save(update_fields=['quote_validity_days'])
        devis = self._envoyer('DEV-AGR523-0030')
        attendu = max(FIN_DU_SUIVI, ENVOI.date() + datetime.timedelta(days=30))
        self.assertEqual(devis.date_validite, attendu)
        from apps.crm.models import LeadActivity
        from apps.crm.services import MOTIF_VALIDITE_SUBVENTION
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, body__contains=MOTIF_VALIDITE_SUBVENTION).exists())

    def test_le_message_J9_et_le_devis_disent_la_meme_date(self):
        from apps.crm.services import message_pour_etape

        self.profil.quote_validity_days = 30
        self.profil.save(update_fields=['quote_validity_days'])
        devis = self._envoyer('DEV-AGR523-J9')
        etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=7, due_at=ENVOI + datetime.timedelta(days=9),
            due_date=(ENVOI + datetime.timedelta(days=9)).date(),
            canal='whatsapp', libelle='Validité de la proposition',
            template_cle='j9_validite', devis=devis)
        rendu = message_pour_etape(etape, user=self.acteur)
        self.assertIn(devis.date_validite.strftime('%d/%m/%Y'),
                      rendu['message'])


class SubventionADeposerTests(_SubventionBase):
    slug = 'agr523-a-deposer'
    dossier = 'a_deposer'

    def test_a_deposer_garde_la_fin_du_plan(self):
        self.profil.quote_validity_days = 30
        self.profil.save(update_fields=['quote_validity_days'])
        devis = self._envoyer('DEV-AGR523-ADEP')
        self.assertEqual(devis.date_validite, FIN_DU_SUIVI)


class SubventionVideTests(_SubventionBase):
    slug = 'agr523-vide'
    dossier = None

    def test_sans_dossier_garde_la_fin_du_plan(self):
        self.profil.quote_validity_days = 30
        self.profil.save(update_fields=['quote_validity_days'])
        devis = self._envoyer('DEV-AGR523-VIDE')
        self.assertEqual(devis.date_validite, FIN_DU_SUIVI)


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


# ── CIQ510 — validité d'un dossier PRO : financement déclaré / attente ─────

class _ProBase(_Base):
    """CIQ510 — un PROFESSIONNEL n'est pas visé par la loi 31-08 ; la règle
    « financé » (le réglage société, jamais plus court que le plan) vaut pour
    un financement pro DÉCLARÉ (contrat CIQ1) et pour une attente d'accord
    déclarée (CIQ508). CAD57 tient : aucun nombre nouveau."""
    segment = 'commercial'
    tags = ''

    def setUp(self):
        super().setUp()
        self.lead.type_installation = self.segment
        self.lead.tags = self.tags
        self.lead.save(update_fields=['type_installation', 'tags'])
        self.profil.quote_validity_days = 30
        self.profil.save(update_fields=['quote_validity_days'])


class ProFinancementDeclareTests(_ProBase):
    slug = 'ciq510-pro-fin'
    financement = 'credit_bail'

    def test_a_financement_pro_declare_reglage_30j(self):
        devis = self._envoyer('DEV-CIQ510-0010')
        self.assertEqual(
            devis.date_validite,
            max(FIN_DU_SUIVI, ENVOI.date() + datetime.timedelta(days=30)))


class ProEtiquetteAttenteAuDemarrageTests(_ProBase):
    slug = 'ciq510-pro-tag'
    financement = 'indecis'
    tags = 'Attend la direction / le comité'

    def test_etiquette_attente_au_demarrage_du_plan(self):
        from apps.crm.models import LeadActivity
        from apps.crm.services import MOTIF_VALIDITE_ATTENTE
        devis = self._envoyer('DEV-CIQ510-0020')
        self.assertEqual(
            devis.date_validite,
            max(FIN_DU_SUIVI, ENVOI.date() + datetime.timedelta(days=30)))
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, body__contains=MOTIF_VALIDITE_ATTENTE).exists())


class ResidentielComptantInchangeTests(_ProBase):
    slug = 'ciq510-resid'
    segment = 'residentiel'
    financement = 'cash'

    def test_f_residentiel_comptant_inchange(self):
        devis = self._envoyer('DEV-CIQ510-0030')
        self.assertEqual(devis.date_validite, FIN_DU_SUIVI)


class AttenteApresEnvoiTests(_ProBase):
    """(b)-(e) — l'attente déclarée à J+3 sur un devis ENVOYÉ valable
    jusqu'à la fin du plan."""
    slug = 'ciq510-attente'
    financement = 'indecis'

    def _repondre_attente(self):
        from testkit.time import frozen
        from apps.crm.services import repondre_attente_accord
        j3 = ENVOI + datetime.timedelta(days=3)
        with frozen(j3):
            etape = (self.lead.relance_etapes
                     .filter(statut=RelanceEtape.Statut.A_FAIRE)
                     .order_by('due_at').first())
            repondre_attente_accord(
                etape, self.acteur, ENVOI + datetime.timedelta(days=60),
                raison='direction')

    def test_b_attente_a_j3_porte_a_envoi_plus_reglage(self):
        from apps.crm.models import LeadActivity
        devis = self._envoyer('DEV-CIQ510-0040')
        self.assertEqual(devis.date_validite, FIN_DU_SUIVI)
        self._repondre_attente()
        devis.refresh_from_db()
        attendu = ENVOI.date() + datetime.timedelta(days=30)
        self.assertEqual(devis.date_validite, attendu)
        self.assertEqual(devis.statut, 'envoye')
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead,
            body=(f'Validité prolongée au {attendu:%d/%m} — en attente '
                  "d'un accord (réglage société).")).exists())

    def test_c_reglage_10j_validite_inchangee(self):
        self.profil.quote_validity_days = 10
        self.profil.save(update_fields=['quote_validity_days'])
        devis = self._envoyer('DEV-CIQ510-0050')
        avant = devis.date_validite
        self._repondre_attente()
        devis.refresh_from_db()
        self.assertEqual(devis.date_validite, avant)

    def test_d_devis_accepte_intouche(self):
        from apps.ventes.services import prolonger_validite_devis
        devis = self._envoyer('DEV-CIQ510-0060')
        avant = devis.date_validite
        Devis.objects.filter(pk=devis.pk).update(statut='accepte')
        self._repondre_attente()
        devis.refresh_from_db()
        self.assertEqual(devis.date_validite, avant)
        self.assertIsNone(prolonger_validite_devis(
            devis, avant + datetime.timedelta(days=90)))

    def test_jamais_plus_courte(self):
        from apps.ventes.services import prolonger_validite_devis
        devis = self._envoyer('DEV-CIQ510-0070')
        self.assertIsNone(prolonger_validite_devis(
            devis, devis.date_validite - datetime.timedelta(days=1)))

    def test_e_message_j9_et_pdf_meme_date(self):
        from apps.crm.services import message_pour_etape
        from apps.ventes.selectors import date_validite_effective
        devis = self._envoyer('DEV-CIQ510-0080')
        self._repondre_attente()
        devis.refresh_from_db()
        etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=7, due_at=ENVOI + datetime.timedelta(days=9),
            due_date=(ENVOI + datetime.timedelta(days=9)).date(),
            canal='whatsapp', libelle='Validité de la proposition',
            template_cle='j9_validite', devis=devis)
        rendu = message_pour_etape(etape, user=self.acteur)
        self.assertEqual(date_validite_effective(devis), devis.date_validite)
        self.assertIn(devis.date_validite.strftime('%d/%m/%Y'),
                      rendu['message'])
