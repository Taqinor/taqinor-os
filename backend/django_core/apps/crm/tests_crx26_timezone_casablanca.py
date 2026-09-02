"""CRX26 — la date « aujourd'hui » du CRM est celle de Casablanca, pas d'UTC.

``settings.TIME_ZONE`` vaut ``'UTC'`` : ``timezone.localdate()`` rendait donc
la date UTC. Africa/Casablanca étant à UTC+1 la majeure partie de l'année,
**entre 23 h et minuit UTC il est déjà demain au Maroc** — et pendant cette
heure-là, chaque décision de date du CRM était fausse d'un jour entier :
relance « du jour », étape « en retard », signal d'intérêt « déjà noté
aujourd'hui », départ d'une cadence de relance, certification échue.

Ce module vérifie le helper ``core.dates.aujourd_hui_local``, deux sites
métier de bout en bout, et pose la GARDE qui empêche un nouveau
``timezone.localdate()`` nu de rentrer dans ``apps/crm``.
"""
import datetime as dt
import re
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from apps.crm.models import Partenaire, RelanceEtape
from apps.crm.serializers import RelanceEtapeSerializer
from authentication.models import Company
from core.dates import FUSEAU_METIER, aujourd_hui_local, maintenant_local

UTC = dt.timezone.utc

#: 1ᵉʳ mai 2026, 23 h 30 UTC — hors Ramadan, donc Casablanca est à UTC+1 :
#: il est déjà le 2 mai sur le terrain. C'est LA fenêtre du défaut.
FIN_DE_SOIREE_UTC = dt.datetime(2026, 5, 1, 23, 30, tzinfo=UTC)
#: Le même jour à midi : aucune ambiguïté, les deux dates coïncident.
MIDI_UTC = dt.datetime(2026, 5, 1, 12, 0, tzinfo=UTC)


class AujourdHuiLocalTests(TestCase):
    def test_fuseau_metier_est_casablanca(self):
        self.assertEqual(FUSEAU_METIER, 'Africa/Casablanca')

    def test_avant_minuit_utc_on_est_deja_demain_au_maroc(self):
        self.assertEqual(
            aujourd_hui_local(FIN_DE_SOIREE_UTC), dt.date(2026, 5, 2))
        # Et c'est bien DIFFÉRENT de la date UTC — le défaut, en une ligne.
        self.assertNotEqual(
            aujourd_hui_local(FIN_DE_SOIREE_UTC), FIN_DE_SOIREE_UTC.date())

    def test_en_journee_les_deux_dates_coincident(self):
        self.assertEqual(aujourd_hui_local(MIDI_UTC), MIDI_UTC.date())

    def test_sans_argument_lit_l_horloge(self):
        with patch('core.dates.timezone.now', return_value=FIN_DE_SOIREE_UTC):
            self.assertEqual(aujourd_hui_local(), dt.date(2026, 5, 2))

    def test_maintenant_local_est_aware_et_decale(self):
        local = maintenant_local(FIN_DE_SOIREE_UTC)
        self.assertIsNotNone(local.tzinfo)
        self.assertEqual(local.hour, 0)   # 23 h 30 UTC = 00 h 30 à Casablanca
        self.assertEqual(local.minute, 30)

    def test_datetime_naif_est_rendu_aware_avant_conversion(self):
        naif = dt.datetime(2026, 5, 1, 23, 30)
        self.assertEqual(aujourd_hui_local(naif), dt.date(2026, 5, 2))


class SitesMetierTests(TestCase):
    """Deux sites réels, pris à la fenêtre 23 h-minuit UTC."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX26', slug='taqinor-crx26')

    def test_certification_expire_le_jour_marocain(self):
        """Certification échéant le 2 mai, horloge au 2 mai 23 h 30 UTC : il
        est le 3 mai au Maroc, la certification est ÉCHUE. En date UTC elle
        aurait encore été valide pendant une heure."""
        partenaire = Partenaire(
            company=self.company, nom='Installateur CRX26',
            token_acces='crx26-token',
            date_expiration_certification=dt.date(2026, 5, 2))
        soir = dt.datetime(2026, 5, 2, 23, 30, tzinfo=UTC)

        with patch('core.dates.timezone.now', return_value=soir):
            self.assertTrue(partenaire.certification_expiree)

        # Contrôle : à midi le même jour, elle est encore valide.
        midi = dt.datetime(2026, 5, 2, 12, 0, tzinfo=UTC)
        with patch('core.dates.timezone.now', return_value=midi):
            self.assertFalse(partenaire.certification_expiree)

    def test_etape_de_relance_en_retard_sur_le_jour_marocain(self):
        """Étape due le 2 mai, horloge au 2 mai 23 h 30 UTC : au Maroc on est
        le 3, l'étape est EN RETARD. La date UTC l'aurait dite à l'heure."""
        from apps.crm.models import Lead

        lead = Lead.objects.create(company=self.company, nom='Lead CRX26')
        etape = RelanceEtape.objects.create(
            company=self.company, lead=lead, ordre=1,
            due_date=dt.date(2026, 5, 2),
            canal=RelanceEtape.Canal.APPEL, libelle='Relancer')
        soir = dt.datetime(2026, 5, 2, 23, 30, tzinfo=UTC)

        with patch('core.dates.timezone.now', return_value=soir):
            self.assertTrue(RelanceEtapeSerializer(etape).data['overdue'])

        midi = dt.datetime(2026, 5, 2, 12, 0, tzinfo=UTC)
        with patch('core.dates.timezone.now', return_value=midi):
            self.assertFalse(RelanceEtapeSerializer(etape).data['overdue'])


# ── Garde : aucun nouveau `timezone.localdate()` nu dans apps/crm ────────────

_RACINE_CRM = Path(__file__).resolve().parent

#: Les deux formes qui rendent la date UTC au lieu de la date marocaine.
_FORMES_NUES = re.compile(
    r'timezone\.localdate\s*\(|timezone\.now\s*\(\s*\)\s*\.date\s*\(')


def _fichiers_de_production():
    """Modules de PRODUCTION d'``apps/crm`` (hors migrations et tests)."""
    for chemin in sorted(_RACINE_CRM.rglob('*.py')):
        parties = chemin.relative_to(_RACINE_CRM).parts
        if 'migrations' in parties:
            continue
        nom = chemin.name
        if (nom.startswith(('test_', 'tests_')) or nom == 'tests.py'
                or 'tests' in parties):
            continue
        yield chemin


def _lignes_de_code(texte):
    """Lignes NON commentées (une mention d'une forme interdite dans un
    commentaire explicatif ne doit pas faire rougir la garde)."""
    for numero, ligne in enumerate(texte.splitlines(), start=1):
        if ligne.lstrip().startswith('#'):
            continue
        yield numero, ligne


class GardeDateMetierTests(TestCase):
    def test_aucune_forme_nue_dans_apps_crm(self):
        fautes = []
        for chemin in _fichiers_de_production():
            texte = chemin.read_text(encoding='utf-8')
            for numero, ligne in _lignes_de_code(texte):
                if _FORMES_NUES.search(ligne):
                    fautes.append(
                        f'{chemin.relative_to(_RACINE_CRM)}:{numero}: '
                        f'{ligne.strip()}')
        self.assertEqual(
            fautes, [],
            "CRX26 — date UTC utilisée comme date métier dans apps/crm. "
            "settings.TIME_ZONE vaut 'UTC' : entre 23 h et minuit ces appels "
            "rendent la veille du jour marocain. Utiliser "
            "`from core.dates import aujourd_hui_local` puis "
            "`aujourd_hui_local()`.\n" + '\n'.join(fautes))

    def test_la_garde_sait_rougir(self):
        """Une garde qui ne peut plus rougir est inutilisable."""
        self.assertTrue(_FORMES_NUES.search('today = timezone.localdate()'))
        self.assertTrue(_FORMES_NUES.search('d = timezone.now().date()'))
        self.assertIsNone(_FORMES_NUES.search('d = aujourd_hui_local()'))
        # Un horodatage technique reste parfaitement légitime.
        self.assertIsNone(_FORMES_NUES.search('quand = timezone.now()'))

    def test_la_garde_ignore_les_commentaires(self):
        lignes = list(_lignes_de_code('# timezone.localdate() interdit\nx = 1'))
        self.assertEqual(lignes, [(2, 'x = 1')])

    def test_la_garde_couvre_les_quatre_modules_convertis(self):
        """Filet anti-régression du filtre : si ``_fichiers_de_production``
        cessait de voir ces modules, la garde deviendrait verte à vide."""
        vus = {c.name for c in _fichiers_de_production()}
        for attendu in ('selectors.py', 'services.py', 'models.py',
                        'serializers.py'):
            self.assertIn(attendu, vus)
