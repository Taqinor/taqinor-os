"""Touche J4 « chantier comparable » — la preuve est RÉELLE ou n'est pas.

Ordre fondateur du 08/09/2026. Avant : « posée en [mois] à [ville] », deux
crochets à remplir à la main et aucun lien — la touche promettait une preuve
qu'elle n'apportait jamais. Après : le serveur choisit dans le catalogue
`parametres.Realisation` l'installation de la MÊME ville que le lead (sinon la
plus proche, sinon — repli fondateur — la dernière de la société, avec SA vraie
ville), et remplit mois, ville, puissance et lien de sa page publique.

La garde qui compte : SANS réalisation, la phrase entière est OMISE (MRY13) et
`placeholders_manquants` le dit. Jamais un crochet, jamais un blanc, jamais un
chantier inventé.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import horaires
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import message_pour_etape
from apps.parametres.models_messages import MESSAGE_TEMPLATE_DEFAULTS
from apps.parametres.models_realisations import Realisation

User = get_user_model()

LUNDI = datetime.datetime(2026, 9, 7, 9, 0, tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'j4-preuve'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company,
            first_name='Nadia')
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', prenom='Aziz',
            ville='Casablanca', telephone='+212651971400',
            owner=self.acteur)

    def _touche(self):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=4, canal='whatsapp',
            due_date=LUNDI.date(), due_at=LUNDI, cadence='apres_devis',
            template_cle='j4_preuve')

    def _rendu(self):
        return message_pour_etape(self._touche(), user=self.acteur)


class AvecRealisationTests(_Base):
    slug = 'j4-preuve-avec'

    def setUp(self):
        super().setUp()
        self.realisation = Realisation.objects.create(
            company=self.company, titre='Villa à Casablanca',
            ville='Casablanca',
            mise_en_service=datetime.date(2026, 7, 1),
            puissance_kwc=Decimal('11.44'),
            url_page='https://taqinor.ma/realisations/villa-casablanca/')

    def test_le_mois_la_ville_et_le_lien_sont_remplis(self):
        rendu = self._rendu()
        self.assertIn('juillet 2026', rendu['message'])
        self.assertIn('Casablanca', rendu['message'])
        self.assertIn('https://taqinor.ma/realisations/villa-casablanca/',
                      rendu['message'])
        self.assertEqual(rendu['placeholders_manquants'], [])

    def test_aucun_placeholder_ne_reste_visible(self):
        message = self._rendu()['message']
        for jeton in ('{mois_preuve}', '{ville_preuve}', '{lien_preuve}',
                      '{puissance_preuve}', '[mois]', '[ville]'):
            self.assertNotIn(jeton, message)

    def test_la_phrase_de_suivi_reste(self):
        self.assertIn('Le suivi de production est en temps réel',
                      self._rendu()['message'])

    def test_la_puissance_est_dite_et_omise_seule_si_inconnue(self):
        """« comparable » parle de la TAILLE : la puissance réelle est dite
        (« 11,44 kWc ») ; inconnue, SA phrase tombe seule — la preuve reste."""
        self.assertIn('11,44 kWc', self._rendu()['message'])
        self.realisation.puissance_kwc = None
        self.realisation.save(update_fields=['puissance_kwc'])
        message = self._rendu()['message']
        self.assertNotIn('Puissance installée', message)
        self.assertIn('installation comparable', message)

    def test_une_realisation_d_une_ville_voisine_sert_aussi(self):
        """Mohammedia est à 24 km de Casablanca : dans le rayon."""
        self.realisation.delete()
        Realisation.objects.create(
            company=self.company, titre='Villa à Mohammedia',
            ville='Mohammedia',
            mise_en_service=datetime.date(2026, 3, 1),
            url_page='https://taqinor.ma/realisations/villa-mohammedia/')
        message = self._rendu()['message']
        self.assertIn('mars 2026', message)
        self.assertIn('Mohammedia', message)


class SansRealisationTests(_Base):
    slug = 'j4-preuve-sans'

    def test_la_phrase_de_preuve_est_OMISE(self):
        """Le catalogue est vide : plutôt que d'annoncer un chantier qui
        n'existe pas, la phrase disparaît — la touche reste honnête."""
        rendu = self._rendu()
        self.assertNotIn('installation comparable', rendu['message'])
        self.assertNotIn('{', rendu['message'])
        self.assertNotIn('[', rendu['message'])
        self.assertIn('Le suivi de production est en temps réel',
                      rendu['message'])

    def test_les_placeholders_manquants_sont_nommes(self):
        manquants = self._rendu()['placeholders_manquants']
        self.assertEqual(
            sorted(manquants),
            ['lien_preuve', 'mois_preuve', 'puissance_preuve', 'ville_preuve'])

    def test_une_realisation_lointaine_sert_en_repli(self):
        """Agadir est à 400 km de Casablanca : repli fondateur (08/09/2026) —
        plutôt qu'aucune preuve, la dernière installation, avec SA vraie
        ville (« comparable » parle de la taille, jamais du lieu)."""
        Realisation.objects.create(
            company=self.company, titre='Villa à Agadir', ville='Agadir',
            mise_en_service=datetime.date(2026, 5, 1),
            url_page='https://taqinor.ma/realisations/villa-agadir/')
        rendu = self._rendu()
        self.assertIn('Agadir', rendu['message'])
        self.assertIn('installation comparable', rendu['message'])

    def test_une_realisation_sans_mois_fait_tomber_la_phrase_entiere(self):
        """Zéro chiffre inventé : sans mois de mise en service, on n'écrit pas
        « posée en  à Casablanca » — la phrase part en entier, le lien avec."""
        Realisation.objects.create(
            company=self.company, titre='Villa à Casablanca',
            ville='Casablanca',
            url_page='https://taqinor.ma/realisations/villa-sans-mois/')
        rendu = self._rendu()
        self.assertNotIn('installation comparable', rendu['message'])
        self.assertIn('mois_preuve', rendu['placeholders_manquants'])


class TexteSourceTests(TestCase):
    """Le défaut lui-même : trois placeholders, plus aucun crochet."""

    def test_le_defaut_porte_les_quatre_placeholders(self):
        texte = MESSAGE_TEMPLATE_DEFAULTS['j4_preuve']
        for jeton in ('{mois_preuve}', '{ville_preuve}', '{lien_preuve}',
                      '{puissance_preuve}'):
            self.assertIn(jeton, texte)

    def test_le_defaut_ne_porte_plus_aucun_crochet(self):
        texte = MESSAGE_TEMPLATE_DEFAULTS['j4_preuve']
        self.assertNotIn('[mois]', texte)
        self.assertNotIn('[ville]', texte)
