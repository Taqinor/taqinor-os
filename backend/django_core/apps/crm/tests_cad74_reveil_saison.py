"""CAD74 — le réveil saisonnier `reveil_b` (« la saison des factures d'été »).

Constat de l'audit L3 du 21/09/2026 : le texte et la clé `reveil_b` existent
et sont validés, mais la clé n'est dans AUCUN gabarit — aucun câblage dans le
dépôt, et après le réveil J60 plus rien ne repart.

Le Done de la tâche, verrouillé ici :
  * un dormant HORS fenêtre reçoit `reveil_b` une seule fois dans la fenêtre
    juin-septembre ;
  * aucun dormant n'en reçoit deux (plafond : une par an et par dormant).

Plus les garde-fous qui rendent ce plafond vrai : hors saison rien n'est
posé, un dormant dont le réveil est DÉJÀ tombé en saison n'en reçoit pas un
second (la « vague trimestrielle » écartée par l'audit), et le protocole
garde ses DEUX réveils — `reveil_b` n'est pas un barreau du gabarit.

Le temps est GELÉ : la fenêtre saisonnière est exactement la question qu'une
horloge vivante rend instable.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.cadence_reveil_saison import (
    REVEIL_SAISON_CLE, REVEIL_SAISON_ORDRE, dans_la_fenetre_saison,
    motif_de_refus,
)
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import poser_reveil_saisonnier, poser_reveils_saisonniers
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import (
    CADENCE_REVEIL_DEFAUT, CanalRelance,
)

User = get_user_model()

#: Mercredi 15 juillet 2026, 10 h à Casablanca — en pleine fenêtre.
EN_SAISON = datetime.datetime(2026, 7, 15, 10, 0, tzinfo=horaires.CASABLANCA)
#: Jeudi 15 janvier 2026, 10 h — hors fenêtre, plein hiver.
HORS_SAISON = datetime.datetime(2026, 1, 15, 10, 0,
                                tzinfo=horaires.CASABLANCA)


class FenetreSaisonTests(SimpleTestCase):
    """La fenêtre elle-même, sans base : juin → septembre, bornes incluses."""

    def test_les_quatre_mois_de_la_saison_sont_dedans(self):
        for mois in (6, 7, 8, 9):
            self.assertTrue(
                dans_la_fenetre_saison(datetime.date(2026, mois, 15)),
                f'mois {mois}')

    def test_mai_et_octobre_sont_dehors(self):
        for mois in (1, 5, 10, 12):
            self.assertFalse(
                dans_la_fenetre_saison(datetime.date(2026, mois, 15)),
                f'mois {mois}')

    def test_une_date_absente_n_est_jamais_dans_la_fenetre(self):
        self.assertFalse(dans_la_fenetre_saison(None))


class GabaritDeReveilTests(SimpleTestCase):
    """Le protocole garde ses DEUX réveils — `reveil_b` n'en est pas un."""

    def test_le_gabarit_de_reveil_garde_ses_deux_barreaux_J30_J60(self):
        self.assertEqual([b['delai_jours'] for b in CADENCE_REVEIL_DEFAUT],
                         [30, 60])

    def test_le_reveil_J30_est_un_APPEL_et_le_J60_un_WhatsApp(self):
        """Décision fondateur du 21/09/2026 (Q20)."""
        self.assertEqual(CADENCE_REVEIL_DEFAUT[0]['canal'],
                         CanalRelance.APPEL)
        self.assertEqual(CADENCE_REVEIL_DEFAUT[1]['canal'],
                         CanalRelance.WHATSAPP)

    def test_reveil_b_n_est_dans_aucun_barreau_du_gabarit(self):
        self.assertNotIn(
            REVEIL_SAISON_CLE,
            [b.get('template_cle') for b in CADENCE_REVEIL_DEFAUT])


class _Base(TestCase):
    slug = 'cad74'
    maintenant = EN_SAISON

    def setUp(self):
        # Import LOCAL : les classes ``SimpleTestCase`` de ce module doivent
        # rester exécutables sur un poste sans `freezegun`.
        from testkit.time import frozen

        gel = frozen(self.maintenant)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        CompanyProfile.objects.create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)

    def _dormant(self, nom='Dormant', **kw):
        kw.setdefault('stage', stages.COLD)
        return Lead.objects.create(
            company=self.company, nom=nom, prenom='Benali',
            ville='Bouskoura', owner=self.acteur, **kw)

    def _reveil_pose_le(self, lead, jour, *, ordre=2,
                        statut=RelanceEtape.Statut.FAIT):
        """Un réveil du gabarit (J30/J60) déjà traité, à une date donnée."""
        quand = datetime.datetime.combine(
            jour, datetime.time(10, 0), tzinfo=horaires.CASABLANCA)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='reveil', ordre=ordre,
            due_at=quand, due_date=jour, canal=CanalRelance.WHATSAPP,
            libelle='Réveil J60', template_cle='reveil_a3', statut=statut)


class PoseDuReveilSaisonnierTests(_Base):
    slug = 'cad74-pose'

    def test_un_dormant_hors_fenetre_recoit_reveil_b_une_fois(self):
        """Le cœur du Done."""
        lead = self._dormant()
        self._reveil_pose_le(lead, datetime.date(2026, 3, 2))

        etape = poser_reveil_saisonnier(lead, self.acteur)

        self.assertIsNotNone(etape)
        self.assertEqual(etape.template_cle, REVEIL_SAISON_CLE)
        self.assertEqual(etape.canal, CanalRelance.WHATSAPP)
        self.assertEqual(etape.ordre, REVEIL_SAISON_ORDRE)
        self.assertEqual(etape.cadence, 'reveil')
        self.assertTrue(dans_la_fenetre_saison(etape.due_date))

    def test_aucun_dormant_n_en_recoit_deux(self):
        """Plafond : UNE touche par an et par dormant."""
        lead = self._dormant()
        self._reveil_pose_le(lead, datetime.date(2026, 3, 2))

        premier = poser_reveil_saisonnier(lead, self.acteur)
        premier.statut = RelanceEtape.Statut.FAIT
        premier.save(update_fields=['statut'])
        second = poser_reveil_saisonnier(lead, self.acteur)

        self.assertIsNotNone(premier)
        self.assertIsNone(second)
        self.assertEqual(
            RelanceEtape.objects.filter(
                lead=lead, template_cle=REVEIL_SAISON_CLE).count(), 1)

    def test_un_dormant_dont_le_reveil_est_tombe_EN_saison_est_ignore(self):
        """« les dormants qui retombent HORS de cette fenêtre » : celui dont
        le J60 est déjà tombé en juillet a eu son message au bon moment."""
        lead = self._dormant()
        self._reveil_pose_le(lead, datetime.date(2026, 7, 2))
        self.assertIsNone(poser_reveil_saisonnier(lead, self.acteur))

    def test_rien_ne_s_empile_sur_une_touche_encore_ouverte(self):
        lead = self._dormant()
        self._reveil_pose_le(lead, datetime.date(2026, 3, 2),
                             statut=RelanceEtape.Statut.A_FAIRE)
        self.assertIsNone(poser_reveil_saisonnier(lead, self.acteur))

    def test_un_lead_qui_n_est_pas_au_Froid_n_est_pas_un_dormant(self):
        lead = self._dormant(nom='Actif', stage=stages.FOLLOW_UP)
        self._reveil_pose_le(lead, datetime.date(2026, 3, 2))
        self.assertIsNone(poser_reveil_saisonnier(lead, self.acteur))
        self.assertIn('Froid', motif_de_refus(lead))

    def test_un_archive_ou_un_perdu_ne_recoit_rien(self):
        archive = self._dormant(nom='Archive', is_archived=True)
        self._reveil_pose_le(archive, datetime.date(2026, 3, 2))
        perdu = self._dormant(nom='Perdu', perdu=True)
        self._reveil_pose_le(perdu, datetime.date(2026, 3, 2))
        self.assertIsNone(poser_reveil_saisonnier(archive, self.acteur))
        self.assertIsNone(poser_reveil_saisonnier(perdu, self.acteur))

    def test_le_motif_de_refus_est_une_phrase_francaise(self):
        """Règle fondateur du 08/09 : jamais un refus muet."""
        lead = self._dormant(nom='Actif2', stage=stages.CONTACTED)
        motif = motif_de_refus(lead)
        self.assertIsInstance(motif, str)
        self.assertTrue(motif.strip())

    def test_le_balayage_de_societe_pose_une_touche_par_dormant(self):
        a = self._dormant(nom='A')
        self._reveil_pose_le(a, datetime.date(2026, 3, 2))
        b = self._dormant(nom='B')
        self._reveil_pose_le(b, datetime.date(2026, 2, 2))
        posees = poser_reveils_saisonniers(self.company, self.acteur)
        self.assertEqual({e.lead_id for e in posees}, {a.id, b.id})
        # Deuxième passage dans la même saison : rien de plus.
        self.assertEqual(
            poser_reveils_saisonniers(self.company, self.acteur), [])


class HorsSaisonTests(_Base):
    slug = 'cad74-hiver'
    maintenant = HORS_SAISON

    def test_en_janvier_aucun_reveil_saisonnier_n_est_pose(self):
        lead = self._dormant()
        self._reveil_pose_le(lead, datetime.date(2025, 11, 2))
        self.assertIsNone(poser_reveil_saisonnier(lead, self.acteur))
        self.assertEqual(
            poser_reveils_saisonniers(self.company, self.acteur), [])
        self.assertIn('Hors saison', motif_de_refus(lead))
