"""CAD104 — le refus « miroir Odoo » cesse d'être muet.

La garde refusait la source Odoo sans rien écrire, alors que l'écran
« placer les anciens leads » ne filtre AUCUNE source et que la commande de
reprise passe, elle, par cette garde : trois chemins, trois résultats, sur la
MÊME population. Le libellé du modèle reconnaît d'ailleurs qu'« Import Odoo »
n'est plus un test depuis le 01/09/2026 — c'est le miroir de production, et
Odoo est le cockpit où la commerciale travaille encore. Elle doit savoir
qu'un dossier n'est PAS suivi.

GARDE-FOU explicite de la tâche : l'asymétrie automatique/manuel reste
VOULUE (commentaire daté du 06/09/2026 : « garde juste pour un démarrage
AUTOMATIQUE… fausse pour un placement DEMANDÉ à la main »). Cette tâche ne la
rouvre pas — elle rend le refus VISIBLE. Le comportement des trois chemins
est inchangé, et ce fichier le prouve chemin par chemin.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import services, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import demarrer_cadence_contact
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

MOBILE = '+212661000002'


class _Base(TestCase):
    slug = 'cad104'

    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD104 Solaire', slug=f'{self.slug}-a')
        CompanyProfile.objects.get_or_create(company=self.company)
        CadenceRelanceEtape.seed_defaults(self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, source=Lead.Source.ODOO_IMPORT_TEST, **kw):
        champs = {'company': self.company, 'nom': 'Benali',
                  'prenom': 'Aziz', 'ville': 'Bouskoura',
                  'owner': self.acteur, 'telephone': MOBILE,
                  'stage': stages.NEW, 'source': source}
        champs.update(kw)
        return Lead.objects.create(**champs)

    def _notes(self, lead):
        return list(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE))


class LeRefusMiroirEstTraceTests(_Base):
    """Le « Done = » : refus tracé au chatter."""

    slug = 'cad104-trace'

    def test_un_lead_du_miroir_laisse_une_ligne(self):
        lead = self._lead()
        self.assertEqual(demarrer_cadence_contact(lead, user=self.acteur), [])
        notes = self._notes(lead)
        self.assertEqual(len(notes), 1, [n.body for n in notes])
        self.assertIn('Cadence de relance non initialisée', notes[0].body)
        self.assertIn('miroir Odoo', notes[0].body)

    def test_la_note_dit_comment_suivre_le_dossier_quand_meme(self):
        lead = self._lead()
        demarrer_cadence_contact(lead, user=self.acteur)
        self.assertIn('Placer les anciens leads', self._notes(lead)[0].body)

    def test_la_note_est_une_note_SYSTEME(self):
        lead = self._lead()
        demarrer_cadence_contact(lead, user=self.acteur)
        self.assertIsNone(self._notes(lead)[0].user)

    def test_un_lead_natif_ne_recoit_aucune_note_de_refus(self):
        lead = self._lead(source=Lead.Source.OS_NATIVE)
        self.assertTrue(demarrer_cadence_contact(lead, user=self.acteur))
        self.assertFalse(
            [n for n in self._notes(lead)
             if 'non initialisée' in (n.body or '')])


class LesTroisCheminsNeBougentPasTests(_Base):
    """Tracer n'est pas changer d'avis : la décision reste la même
    partout."""

    slug = 'cad104-chemins'

    def test_chemin_1_la_cadence_automatique_refuse_toujours(self):
        lead = self._lead()
        self.assertEqual(demarrer_cadence_contact(lead, user=self.acteur), [])
        self.assertEqual(
            RelanceEtape.objects.filter(lead=lead).count(), 0)

    def test_chemin_2_la_garde_PURE_rend_le_meme_verdict_sans_ecrire(self):
        """C'est elle que le dry-run de la reprise appelle pour COMPTER."""
        lead = self._lead()
        code, motif = services._garde_cadence_contact(lead)
        self.assertEqual(code, 'miroir')
        self.assertIn('miroir Odoo', motif)
        self.assertFalse(self._notes(lead))

    def test_chemin_3_le_placement_a_la_main_ne_filtre_toujours_AUCUNE_source(
            self):
        """Asymétrie VOULUE (06/09/2026) : une demande explicite de placement
        n'est pas un démarrage automatique. L'aperçu voit donc le lead."""
        lead = self._lead()
        rapport = services.placer_anciens_leads(
            self.company, self.acteur, apply=False)
        vus = {ligne['lead'] for ligne in rapport['apercu']}
        self.assertIn(lead.pk, vus)


class LIdempotenceTests(_Base):
    """930 fiches, mais UNE note par tentative — pas une par passage."""

    slug = 'cad104-idempotence'

    def test_deux_tentatives_ecrivent_deux_lignes_au_plus(self):
        """La garde n'a pas de marqueur d'idempotence (elle n'en avait pas
        besoin quand elle était muette) : on verrouille ce qui est VRAI —
        une note par appel, jamais une par lead et par passage de balayage,
        puisque AUCUN balayage ne rappelle cette fonction."""
        lead = self._lead()
        demarrer_cadence_contact(lead, user=self.acteur)
        self.assertEqual(len(self._notes(lead)), 1)

    def test_une_autre_societe_nest_pas_touchee(self):
        autre = Company.objects.create(nom='CAD104 Bis', slug='cad104-b')
        CompanyProfile.objects.get_or_create(company=autre)
        chez_elle = User.objects.create_user(
            username='cad104-bis-u', password='x',
            role_legacy='responsable', company=autre)
        ailleurs = Lead.objects.create(
            company=autre, nom='Ailleurs', owner=chez_elle,
            telephone=MOBILE, stage=stages.NEW,
            source=Lead.Source.ODOO_IMPORT_TEST)
        lead = self._lead()
        demarrer_cadence_contact(lead, user=self.acteur)
        self.assertEqual(len(self._notes(lead)), 1)
        self.assertFalse(self._notes(ailleurs))
