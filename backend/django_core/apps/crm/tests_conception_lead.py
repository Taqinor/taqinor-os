"""ALEA68 / ALEA69 (D-ACAL-97, « un seul moteur ») — le CRM émet
``lead_entrees_modifiees`` quand une ENTRÉE du moteur change, et écrit au
chatter la phrase d'une ``conception_recalculee``.

Aucun mock du chemin testé : ``Lead.save`` réel, signaux réels capturés par un
récepteur de test, callbacks ``on_commit`` exécutés par
``captureOnCommitCallbacks``."""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Lead
from authentication.models import Company
from core.events import lead_entrees_modifiees


class _Capture:
    """Récepteur de test : garde les appels reçus."""

    def __init__(self):
        self.appels = []

    def __call__(self, sender, **kwargs):
        self.appels.append(kwargs)


class EmissionEntreesModifieesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ALEA68', slug='taqinor-alea68')
        self.lead = Lead.objects.create(
            company=self.company, nom='Alea', prenom='Soixante-huit',
            telephone='+212661680001', ville='Casablanca',
            facture_hiver=Decimal('900'))
        self.capture = _Capture()
        lead_entrees_modifiees.connect(
            self.capture, dispatch_uid='test_alea68', weak=False)
        self.addCleanup(lead_entrees_modifiees.disconnect,
                        dispatch_uid='test_alea68')

    def _enregistrer(self, **valeurs):
        self.lead.refresh_from_db()
        for cle, valeur in valeurs.items():
            setattr(self.lead, cle, valeur)
        with self.captureOnCommitCallbacks(execute=True):
            self.lead.save()

    def test_facture_hiver_modifiee_emet_un_evenement(self):
        self._enregistrer(facture_hiver=Decimal('1200'))
        self.assertEqual(len(self.capture.appels), 1)
        appel = self.capture.appels[0]
        self.assertEqual(appel['company_id'], self.company.pk)
        self.assertEqual(appel['lead_id'], self.lead.pk)
        self.assertEqual(
            appel['champs'],
            [{'champ': 'facture_hiver', 'avant': 900.0, 'apres': 1200.0}])

    def test_nom_telephone_etape_n_emettent_rien(self):
        self._enregistrer(nom='Autre nom', telephone='+212661680002',
                          note='une note', stage='CONTACTED')
        self.assertEqual(self.capture.appels, [])

    def test_aucun_changement_n_emet_rien(self):
        self._enregistrer()
        self.assertEqual(self.capture.appels, [])

    def test_plusieurs_entrees_un_seul_evenement(self):
        self._enregistrer(facture_hiver=Decimal('1500'), ville='Rabat',
                          nom='Autre nom')
        self.assertEqual(len(self.capture.appels), 1)
        noms = {c['champ'] for c in self.capture.appels[0]['champs']}
        self.assertEqual(noms, {'facture_hiver', 'ville'})

    def test_emission_apres_le_commit_seulement(self):
        self.lead.refresh_from_db()
        self.lead.facture_hiver = Decimal('1300')
        with self.captureOnCommitCallbacks(execute=False) as rappels:
            self.lead.save()
        self.assertEqual(self.capture.appels, [])
        for rappel in rappels:
            rappel()
        self.assertEqual(len(self.capture.appels), 1)

    def test_update_fields_ne_regarde_que_les_colonnes_sauvees(self):
        self.lead.refresh_from_db()
        self.lead.facture_hiver = Decimal('1400')
        self.lead.nom = 'Nom seul'
        with self.captureOnCommitCallbacks(execute=True):
            self.lead.save(update_fields=['nom'])
        self.assertEqual(self.capture.appels, [])

    def test_creation_n_emet_rien(self):
        with self.captureOnCommitCallbacks(execute=True):
            Lead.objects.create(
                company=self.company, nom='Neuf', prenom='Lead',
                telephone='+212661680003', facture_hiver=Decimal('500'))
        self.assertEqual(self.capture.appels, [])

    def test_abonne_en_echec_ne_casse_pas_l_ecriture(self):
        def _casse(sender, **kwargs):
            raise RuntimeError('abonné en échec')
        lead_entrees_modifiees.connect(
            _casse, dispatch_uid='test_alea68_casse', weak=False)
        self.addCleanup(lead_entrees_modifiees.disconnect,
                        dispatch_uid='test_alea68_casse')
        with self.assertLogs('apps.crm.receivers', level='WARNING'):
            self._enregistrer(facture_hiver=Decimal('1600'))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.facture_hiver, Decimal('1600'))
        self.assertEqual(len(self.capture.appels), 1)

    def test_champ_hors_marche_n_emet_rien(self):
        """Une colonne de pompage sur un lead résidentiel : pas une entrée."""
        self._enregistrer(pompe_hmt_m=Decimal('40'))
        self.assertEqual(self.capture.appels, [])
