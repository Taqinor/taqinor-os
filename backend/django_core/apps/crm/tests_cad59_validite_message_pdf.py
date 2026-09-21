"""CAD59 — le message J9 et le PDF calculent la validité de la MÊME façon.

Constat de l'audit L3 du 21/09/2026 : le moteur de devis a un repli documenté
(``date_validite``, sinon date de création + le réglage société
``quote_validity_days``) alors que ``message_pour_etape`` ne lisait QUE
``devis.date_validite``. Vide, MRY13 supprimait la phrase entière et le
message enchaînait sur « Après, je dois revalider les prix… » pendant que le
PDF affichait « valable jusqu'au X » — deux voix contradictoires sur le même
dossier.

Garde-fou : règle #4 — le moteur de rendu n'est PAS touché ; le message lit la
MÊME règle (``apps.ventes.selectors.date_validite_effective``, qui appelle
``utils/expiry.date_expiration``, celle que le PDF applique déjà).

Le chemin ``devis=None`` (TREADMILL-1538) reste couvert par CAD55 : il n'est
pas retesté ici.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import horaires
from apps.crm.models import Client, Lead, RelanceEtape
from apps.crm.services import message_pour_etape
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis
from apps.ventes.selectors import date_validite_effective
from apps.ventes.utils.expiry import date_expiration

User = get_user_model()

#: Lundi 7 septembre 2026, 10 h.
ENVOI = datetime.datetime(2026, 9, 7, 10, 0, tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'cad59'

    def setUp(self):
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        self.profil = CompanyProfile.objects.create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur,
            telephone='+212661112233')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client',
            email=f'{self.slug}@example.com')

    def _devis(self, *, date_validite=None, reference='DEV-CAD59-0001'):
        return Devis.objects.create(
            company=self.company, reference=reference,
            client=self.client_obj, lead=self.lead, statut='envoye',
            taux_tva=Decimal('20.00'), date_envoi=ENVOI,
            date_validite=date_validite)

    def _message_j9(self, devis):
        etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=7, due_at=ENVOI + datetime.timedelta(days=9),
            due_date=(ENVOI + datetime.timedelta(days=9)).date(),
            canal='whatsapp', libelle='Validité de la proposition',
            template_cle='j9_validite', devis=devis)
        return message_pour_etape(etape, user=self.acteur)


class LaMemeRegleTests(_Base):
    slug = 'cad59-regle'

    def test_le_selecteur_rend_EXACTEMENT_ce_que_le_PDF_calcule(self):
        """Anti-divergence : une seule règle, deux lecteurs."""
        pose = self._devis(date_validite=datetime.date(2026, 10, 15))
        vide = self._devis(reference='DEV-CAD59-VIDE')
        for devis in (pose, vide):
            with self.subTest(reference=devis.reference):
                self.assertEqual(date_validite_effective(devis),
                                 date_expiration(devis))

    def test_sans_devis_aucune_date_n_est_inventee(self):
        self.assertIsNone(date_validite_effective(None))

    def test_le_repli_suit_le_reglage_societe(self):
        self.profil.quote_validity_days = 45
        self.profil.save(update_fields=['quote_validity_days'])
        devis = self._devis(reference='DEV-CAD59-45')
        self.assertEqual(
            date_validite_effective(devis),
            devis.date_creation.date() + datetime.timedelta(days=45))


class LeMessageJ9Tests(_Base):
    slug = 'cad59-message'

    def test_sans_date_validite_le_message_affiche_QUAND_MEME_la_date(self):
        """Le cœur du Done : la phrase de validité ne disparaît plus."""
        devis = self._devis(date_validite=None)
        attendue = date_expiration(devis)
        self.assertIsNotNone(attendue)

        rendu = self._message_j9(devis)

        self.assertIn(attendue.strftime('%d/%m/%Y'), rendu['message'])
        self.assertNotIn('date_validite', rendu['placeholders_manquants'])

    def test_avec_une_date_saisie_c_est_ELLE_qui_part(self):
        saisie = datetime.date(2026, 10, 15)
        devis = self._devis(date_validite=saisie,
                            reference='DEV-CAD59-SAISIE')
        rendu = self._message_j9(devis)
        self.assertIn(saisie.strftime('%d/%m/%Y'), rendu['message'])

    def test_le_message_et_le_PDF_citent_la_MEME_date(self):
        devis = self._devis(date_validite=None, reference='DEV-CAD59-PAIR')
        rendu = self._message_j9(devis)
        self.assertIn(date_expiration(devis).strftime('%d/%m/%Y'),
                      rendu['message'])
