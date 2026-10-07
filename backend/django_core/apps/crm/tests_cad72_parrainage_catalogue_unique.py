"""CAD72 — `parrainage` promettait un lien qui n'existe pas — et ce n'était
même pas ce texte qui partait.

Avant CAD72, le flux vivant passait par un SECOND catalogue :
`apps.crm.services._PARRAINAGE_TEMPLATE_DEFAULTS` +
`get_or_create_parrainage_template`, seedant une SECONDE ligne
`crm.MessageTemplate` — texte FR promettant une récompense FERME, darija en
ARABIZI LATIN (« Salam {prenom}, choukran 3la ti9a dyalek… »), alors que
tout le catalogue darija validé (`parametres.MESSAGE_TEMPLATE_DEFAULTS_DARIJA`)
est écrit en arabe, relu par un natif le 04/09/2026. Leur seul appelant
vivait dans `apps/compta/services.py` (flux NPS), retiré quand `compta` a
été mis en coquille par le drain SOLMVP — plus aucun appelant.

Fix : suppression du second catalogue. Un seul catalogue pour les messages
client — `parametres.MessageTemplate` (clé `parrainage`, déjà validée dans
`docs/crm/messages_meryem.md`), rendu par `message_pour_etape` comme
n'importe quelle autre touche.
"""
import datetime
import pathlib
import re

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.crm import horaires
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import message_pour_etape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_messages import MESSAGE_TEMPLATE_DEFAULTS

User = get_user_model()

LUNDI = datetime.datetime(2026, 9, 7, 9, 0, tzinfo=horaires.CASABLANCA)

#: Marqueurs indiscutables de l'arabizi latin retiré par CAD72 — aucun n'a
#: la moindre raison légitime d'apparaître dans une chaîne applicative ou un
#: texte client (le catalogue darija validé est en écriture arabe).
_MARQUEURS_ARABIZI = ('choukran', 'dyalek', "l'parrainage", 'mokafaa',
                      'lmostachar')

_FICHIERS_A_VERIFIER = (
    pathlib.Path(__file__).resolve().parent / 'services.py',
    pathlib.Path(__file__).resolve().parent / 'models.py',
)


class CatalogueUniqueSourceTests(SimpleTestCase):
    """LE Done : `grep _PARRAINAGE_TEMPLATE_DEFAULTS` = 0, et aucun texte
    darija en arabizi ne subsiste."""

    def setUp(self):
        self.source_services = (
            pathlib.Path(__file__).resolve().parent / 'services.py'
        ).read_text(encoding='utf-8')

    def test_le_second_catalogue_nexiste_plus(self):
        motif = '_PARRAINAGE' + '_TEMPLATE_DEFAULTS'
        self.assertNotIn(motif, self.source_services)

    def test_le_generateur_du_second_catalogue_nexiste_plus(self):
        motif = 'get_or_create_parrainage_template'
        self.assertNotIn(motif, self.source_services)

    def test_aucun_texte_darija_en_arabizi_ne_subsiste(self):
        for fichier in _FICHIERS_A_VERIFIER:
            with self.subTest(fichier=fichier.name):
                texte = fichier.read_text(encoding='utf-8').lower()
                for marqueur in _MARQUEURS_ARABIZI:
                    self.assertNotIn(
                        marqueur, texte,
                        f'{fichier.name} contient encore un marqueur '
                        f'arabizi ({marqueur!r}).')

    def test_aucun_appelant_du_second_catalogue_dans_le_backend(self):
        """Anti-régression : si un futur commit réintroduit un appel à
        l'ancien générateur, ce test le détecte — même sans base."""
        racine = pathlib.Path(__file__).resolve().parents[1]  # backend/django_core
        motif = re.compile(r'get_or_create_parrainage_template')
        offenders = []
        for chemin in racine.rglob('*.py'):
            if '__pycache__' in chemin.parts or 'migrations' in chemin.parts:
                continue
            if chemin.name.startswith('tests_cad72'):
                continue
            if motif.search(chemin.read_text(encoding='utf-8')):
                offenders.append(str(chemin))
        self.assertEqual(offenders, [])


class MessageParrainageRenduTests(TestCase):
    """LE Done : « le message de parrainage rend le texte validé » — via
    `message_pour_etape`, le SEUL chemin qui reste (`parametres` catalog)."""

    def _lead_et_touche(self, slug):
        company, _ = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})
        CompanyProfile.objects.get_or_create(company=company)
        acteur = User.objects.create_user(
            username=f'{slug}-u', password='x',
            role_legacy='responsable', company=company, first_name='Conseiller')
        lead = Lead.objects.create(
            company=company, nom='Benali', prenom='Aziz',
            ville='Casablanca', telephone='+212651971400', owner=acteur)
        etape = RelanceEtape.objects.create(
            company=company, lead=lead, ordre=1, canal='whatsapp',
            due_date=LUNDI.date(), due_at=LUNDI, cadence='generique',
            template_cle='parrainage')
        return acteur, etape

    def test_le_rendu_est_le_texte_valide_du_catalogue_parametres(self):
        """Le texte servi vient du catalogue `parametres`, et de lui seul.

        L'attendu passe par le MÊME moteur de rendu que le message réel
        (`ventes.utils.whatsapp.render_message_template`) : il substitue les
        placeholders puis nettoie la ponctuation — il retire notamment
        l'espace français avant « ; », que le catalogue écrit. Comparer au
        texte BRUT épinglerait cette typographie, pas la source ; le contrat
        de CAD72 est qu'il n'existe plus qu'UN catalogue.
        """
        acteur, etape = self._lead_et_touche('cad72-rendu')
        rendu = message_pour_etape(etape, user=acteur)
        from apps.ventes.utils.whatsapp import render_message_template
        attendu = render_message_template(
            MESSAGE_TEMPLATE_DEFAULTS['parrainage'], {'prenom': 'Aziz'})
        self.assertEqual(rendu['message'], attendu)
        # Et le texte reste bien CELUI du catalogue, pas un autre.
        self.assertIn('lien de parrainage', rendu['message'])

    def test_le_rendu_ne_contient_aucun_marqueur_arabizi(self):
        acteur, etape = self._lead_et_touche('cad72-rendu-fr')
        rendu = message_pour_etape(etape, user=acteur)
        texte = rendu['message'].lower()
        for marqueur in _MARQUEURS_ARABIZI:
            self.assertNotIn(marqueur, texte)

    def test_le_rendu_darija_ne_contient_aucun_marqueur_arabizi(self):
        acteur, etape = self._lead_et_touche('cad72-rendu-darija')
        etape.lead.langue_preferee = 'darija'
        etape.lead.save(update_fields=['langue_preferee'])
        rendu = message_pour_etape(etape, user=acteur)
        texte = rendu['message'].lower()
        for marqueur in _MARQUEURS_ARABIZI:
            self.assertNotIn(marqueur, texte)
