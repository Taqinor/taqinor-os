"""CAD103 — un lead créé déjà « Contacté » n'entrait dans aucun protocole, et
rien ne le disait.

La garde refuse la cadence dès que l'étape n'est pas « Nouveau » ou qu'une
date de premier contact est posée — et ce refus était volontairement MUET
(`_GARDES_CADENCE_TRACEES` ne contenait que `sans_numero` et `doublon`).

C'est pourtant le cas le PLUS COURANT : la commerciale reçoit un appel, crée
la fiche, la passe en « Contacté » parce que c'est la vérité, et le dossier
n'entre dans AUCUN plan sans une ligne pour le signaler. Même silence pour
l'API publique partenaire, qui accepte une étape dans sa requête puis appelle
la cadence.

Ce qui change : le refus est TRACÉ comme les deux autres, et il PROPOSE la
suite — démarrer le protocole à la touche 3, le rappel du jour même, ce que
fait exactement un commercial après un premier échange. Le placement à
barreau intermédiaire existe déjà (MRY30, « Placer les anciens leads » : il
pose le plan depuis une ancre rétrodatée et annule les touches déjà passées).

GARDE-FOU : la garde elle-même ne change pas d'avis — aucune cadence ne
démarre toute seule sur un lead déjà contacté ; le nombre et l'ordre des
touches du protocole ne bougent pas ; la note reste une note SYSTÈME
(`user=None`), sinon le récepteur QJ7 la prendrait pour un premier contact
manuel.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm import services, stages
from apps.crm.models import Lead, LeadActivity
from apps.crm.services import demarrer_cadence_contact
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

MOBILE = '+212661000002'


class _Base(TestCase):
    slug = 'cad103'

    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD103 Solaire', slug=f'{self.slug}-a')
        CompanyProfile.objects.get_or_create(company=self.company)
        CadenceRelanceEtape.seed_defaults(self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, **kw):
        champs = {'company': self.company, 'nom': 'Benali',
                  'prenom': 'Aziz', 'ville': 'Bouskoura',
                  'owner': self.acteur, 'telephone': MOBILE,
                  'stage': stages.NEW}
        champs.update(kw)
        return Lead.objects.create(**champs)

    def _notes(self, lead):
        return list(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE))


class LeRefusEstTraceTests(_Base):
    """Le « Done = » : une ligne de refus tracée."""

    slug = 'cad103-trace'

    def test_un_lead_cree_en_CONTACTED_laisse_une_ligne(self):
        lead = self._lead(stage=stages.CONTACTED)
        self.assertEqual(demarrer_cadence_contact(lead, user=self.acteur), [])
        notes = self._notes(lead)
        self.assertEqual(len(notes), 1, [n.body for n in notes])
        self.assertIn('Cadence de relance non initialisée', notes[0].body)

    def test_un_lead_avec_un_premier_contact_horodate_aussi(self):
        lead = self._lead(first_contacted_at=timezone.now())
        demarrer_cadence_contact(lead, user=self.acteur)
        self.assertEqual(len(self._notes(lead)), 1)

    def test_la_note_est_une_note_SYSTEME(self):
        """`user=None` : posée au nom de l'utilisateur, le récepteur QJ7 la
        prendrait pour un premier contact manuel et stamperait le SLA."""
        lead = self._lead(stage=stages.CONTACTED)
        demarrer_cadence_contact(lead, user=self.acteur)
        self.assertIsNone(self._notes(lead)[0].user)

    def test_la_note_nest_ecrite_QUUNE_fois_par_tentative(self):
        lead = self._lead(stage=stages.CONTACTED)
        demarrer_cadence_contact(lead, user=self.acteur)
        self.assertEqual(len(self._notes(lead)), 1)


class LeRefusPROPOSELaSuiteTests(_Base):
    """Une ligne qui constate sans proposer ne sert à rien."""

    slug = 'cad103-suite'

    def test_la_note_propose_le_demarrage_a_la_touche_3(self):
        lead = self._lead(stage=stages.CONTACTED)
        demarrer_cadence_contact(lead, user=self.acteur)
        corps = self._notes(lead)[0].body
        self.assertIn('touche 3', corps)
        self.assertIn('rappel du jour même', corps)

    def test_elle_nomme_lecran_qui_sait_le_faire(self):
        lead = self._lead(stage=stages.CONTACTED)
        demarrer_cadence_contact(lead, user=self.acteur)
        self.assertIn('Placer les anciens leads',
                      self._notes(lead)[0].body)

    def test_le_motif_de_la_garde_PURE_porte_deja_la_proposition(self):
        """La garde reste PURE (aucune écriture) mais son motif dit la
        suite : c'est lui que le dry-run de la reprise affiche."""
        lead = self._lead(stage=stages.CONTACTED)
        code, motif = services._garde_cadence_contact(lead)
        self.assertEqual(code, 'deja_contacte')
        self.assertIn(services.SUITE_DEJA_CONTACTE, motif)
        self.assertFalse(self._notes(lead))

    def test_la_touche_3_du_protocole_existe_bien(self):
        """Zéro proposition en l'air : le barreau 3 du gabarit est bien un
        geste du JOUR MÊME."""
        barreaux = CadenceRelanceEtape.cadence_pour(self.company, 'contact')
        troisieme = next(b for b in barreaux if b.ordre == 3)
        self.assertEqual(troisieme.delai_jours, 0)


class LaGardeNeChangePasDavisTests(_Base):
    """Tracer n'est pas autoriser."""

    slug = 'cad103-garde'

    def test_aucune_cadence_ne_demarre_toute_seule(self):
        lead = self._lead(stage=stages.CONTACTED)
        self.assertEqual(demarrer_cadence_contact(lead, user=self.acteur), [])
        self.assertEqual(
            lead.relance_etapes.filter(cadence='contact').count(), 0)

    def test_un_lead_NEUF_demarre_toujours_sans_note_de_refus(self):
        lead = self._lead()
        self.assertTrue(demarrer_cadence_contact(lead, user=self.acteur))
        self.assertFalse(
            [n for n in self._notes(lead)
             if 'non initialisée' in (n.body or '')])

    def test_un_lead_quon_ne_relance_plus_reste_MUET(self):
        """Garde négative : seuls les refus RATTRAPABLES sont écrits."""
        lead = self._lead(ne_plus_contacter=True)
        demarrer_cadence_contact(lead, user=self.acteur)
        self.assertFalse(self._notes(lead))
