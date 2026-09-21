"""CAD108 — [TRANCHÉ 21/09/2026] l'étage 3 de la reprise exclut le miroir
Odoo, comme l'étage 2.

L'étage 2 de `demarrer_cadences_existantes` (leads neufs) filtre `OS_NATIVE`,
mais l'étage 3 « dormants → réveils » n'avait AUCUN filtre de source : les
fiches du miroir Odoo étaient donc éligibles aux réveils J30/J60 alors que la
cadence automatique les écarte. Même population, deux réponses selon l'étage.

Décision fondateur : l'étage 3 applique le même filtre que l'étage 2. Les
fiches du miroir historique n'entrent pas dans les réveils.

GARDE-FOU, et c'est la cohérence de la décision : seuls les leads Odoo NEUFS
entrent dans une cadence (CAD105), et par la SYNCHRONISATION — jamais par la
reprise de masse.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm import stages
from apps.crm.management.commands.demarrer_cadences_existantes import (
    demarrer_cadences_existantes)
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()


class _Base(TestCase):
    slug = 'cad108'

    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD108 Solaire', slug=f'{self.slug}-a')
        CompanyProfile.objects.get_or_create(company=self.company)
        CadenceRelanceEtape.seed_defaults(self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)

    def _dormant(self, nom, source, stage=stages.COLD):
        lead = Lead.objects.create(
            company=self.company, nom=nom, owner=self.acteur,
            ville='Bouskoura', stage=stage, source=source,
            telephone=f'+21266{abs(hash(nom)) % 10000000:07d}')
        # Un dossier VRAIMENT dormant : aucune activité humaine récente.
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=timezone.now() - datetime.timedelta(days=120))
        return Lead.objects.get(pk=lead.pk)

    def _reveils(self, lead):
        return RelanceEtape.objects.filter(lead=lead, cadence='reveil')


class LeMiroirNentrePasDansLesReveilsTests(_Base):
    """Le « Done = » : la reprise de masse ne pose aucune touche de réveil
    sur un lead du miroir Odoo."""

    slug = 'cad108-miroir'

    def test_aucune_touche_de_reveil_sur_un_lead_du_miroir(self):
        miroir = self._dormant('Miroir', Lead.Source.ODOO_IMPORT_TEST)
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertEqual(self._reveils(miroir).count(), 0)

    def test_le_dry_run_ne_lannonce_pas_non_plus(self):
        """Une simulation qui promet ce que `--apply` ne fera pas ne vaut
        rien : les deux étages lisent la MÊME requête."""
        self._dormant('Miroir', Lead.Source.ODOO_IMPORT_TEST)
        simulation = demarrer_cadences_existantes(self.company)
        self.assertEqual(simulation['reveil']['nb'], 0, simulation)

    def test_un_dormant_NATIF_recoit_toujours_ses_reveils(self):
        """Garde négative : on a fermé une porte, pas le portail."""
        natif = self._dormant('Natif', Lead.Source.OS_NATIVE)
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertGreater(self._reveils(natif).count(), 0)

    def test_un_dormant_du_SITE_WEB_aussi(self):
        site = self._dormant('Site', Lead.Source.SITE_WEB)
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertGreater(self._reveils(site).count(), 0)

    def test_les_deux_etages_filtrent_la_MEME_source(self):
        """L'étage 2 écartait déjà le miroir ; l'étage 3 le fait enfin
        aussi. Même population, même réponse."""
        miroir = self._dormant('Miroir', Lead.Source.ODOO_IMPORT_TEST,
                               stage=stages.QUOTE_SENT)
        demarrer_cadences_existantes(self.company, apply_changes=True)
        self.assertEqual(
            miroir.relance_etapes.filter(cadence='reveil').count(), 0)
        self.assertEqual(
            miroir.relance_etapes.filter(cadence='contact').count(), 0)

    def test_le_rapport_reste_coherent_entre_simulation_et_application(self):
        self._dormant('Miroir', Lead.Source.ODOO_IMPORT_TEST)
        self._dormant('Natif', Lead.Source.OS_NATIVE)
        simulation = demarrer_cadences_existantes(self.company)
        applique = demarrer_cadences_existantes(
            self.company, apply_changes=True)
        self.assertEqual(simulation['reveil']['nb'], applique['reveil']['nb'])
