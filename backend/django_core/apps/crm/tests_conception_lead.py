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

    def test_creation_avec_une_entree_emet_son_premier_calcul(self):
        """Relecture E5 B1(b) — un lead CRÉÉ avec au moins une entrée du moteur
        part en calcul comme une modification (``avant`` nul) ; créé sans
        aucune entrée, rien n'est émis."""
        with self.captureOnCommitCallbacks(execute=True):
            neuf = Lead.objects.create(
                company=self.company, nom='Neuf', prenom='Lead',
                telephone='+212661680003', facture_hiver=Decimal('500'))
        self.assertEqual(len(self.capture.appels), 1)  # mutant « création muette » : 0
        appel = self.capture.appels[0]
        self.assertEqual((appel['company_id'], appel['lead_id']), (self.company.pk, neuf.pk))
        self.assertEqual(appel['champs'], [{'champ': 'facture_hiver', 'avant': None, 'apres': 500.0}])
        with self.captureOnCommitCallbacks(execute=True):
            Lead.objects.create(company=self.company, nom='Vide', prenom='Lead',
                                telephone='+212661680004')
        self.assertEqual(len(self.capture.appels), 1)

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

    def test_valeurs_egales_apres_normalisation_n_emettent_rien(self):
        """Relecture m2 — ``Decimal('900.00')`` relu en base et ``900.0``
        posé par un formulaire, ``''`` et ``None`` : la même valeur."""
        self._enregistrer(facture_hiver=900.0)
        self._enregistrer(occupation_jour='')
        self.assertEqual(self.capture.appels, [])
        self._enregistrer(facture_hiver=Decimal('1200'))
        self.assertEqual(len(self.capture.appels), 1)
        self.assertEqual(self.capture.appels[0]['champs'],
                         [{'champ': 'facture_hiver', 'avant': 900.0, 'apres': 1200.0}])

    def test_champ_hors_marche_n_emet_rien(self):
        """Une colonne de pompage sur un lead résidentiel : pas une entrée."""
        self._enregistrer(pompe_hmt_m=Decimal('40'))
        self.assertEqual(self.capture.appels, [])


DECLENCHEUR = {
    'raison': "Conception recalculée : facture d'hiver 900 → 1 200 MAD",
    'champs': [{'champ': 'facture_hiver', 'avant': 900, 'apres': 1200}],
    'origine': 'lead_entrees_modifiees',
}


class NoteConceptionRecalculeeTests(TestCase):
    """ALEA69 — une conception recalculée écrit UNE ligne système au chatter."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ALEA69', slug='taqinor-alea69')
        self.autre = Company.objects.create(
            nom='Autre ALEA69', slug='autre-alea69')
        self.lead = Lead.objects.create(
            company=self.company, nom='Alea', prenom='Soixante-neuf',
            telephone='+212661690001', facture_hiver=Decimal('1200'))

    def _envoyer(self, version=4, company_id=None, declencheur=DECLENCHEUR):
        from core.events import conception_recalculee
        conception_recalculee.send(
            sender='ventes.ConceptionLead',
            company_id=company_id or self.company.pk,
            lead_id=self.lead.pk, calepinage_id=None,
            version=version, declencheur=declencheur)

    def _lignes(self):
        from apps.crm.models import LeadActivity
        return list(LeadActivity.objects.filter(
            lead=self.lead, field='conception_version'))

    def test_une_ligne_systeme_avec_la_phrase(self):
        self._envoyer()
        lignes = self._lignes()
        self.assertEqual(len(lignes), 1)
        self.assertIsNone(lignes[0].user)
        self.assertEqual(lignes[0].company_id, self.company.pk)
        self.assertEqual(
            lignes[0].body,
            "Conception recalculée : facture d'hiver 900 → 1 200 MAD")

    def test_evenement_rejoue_meme_version_une_seule_ligne(self):
        self._envoyer(version=4)
        self._envoyer(version=4)
        self.assertEqual(len(self._lignes()), 1)
        self._envoyer(version=5)
        self.assertEqual(len(self._lignes()), 2)

    def test_lead_d_une_autre_societe_n_ecrit_rien(self):
        self._envoyer(company_id=self.autre.pk)
        self.assertEqual(self._lignes(), [])

    def test_calepinage_sans_lead_n_ecrit_rien(self):
        from core.events import conception_recalculee
        conception_recalculee.send(
            sender='ventes.ConceptionLead', company_id=self.company.pk,
            lead_id=None, calepinage_id=7, version=1,
            declencheur=DECLENCHEUR)
        self.assertEqual(self._lignes(), [])

    def test_lead_efface_apres_la_lecture_rien_n_est_ecrit(self):
        """Relecture E4 M5 — le scrub (loi 09-08) valide ENTRE la lecture du
        lead et le verrou : relu sous verrou, aucune ligne (sa phrase porte les
        valeurs effacées)."""
        from unittest import mock

        from apps.crm import selectors
        from apps.crm.dsr_provider import LEAD_NOM_ANONYMISE

        Lead.objects.filter(pk=self.lead.pk).update(nom=LEAD_NOM_ANONYMISE)
        with mock.patch.object(selectors, 'lead_efface', return_value=False):  # lu avant le scrub
            self._envoyer()
        self.assertEqual(self._lignes(), [])  # mutant « sans relecture sous verrou » : 1 ligne

    def test_raison_sans_prefixe_est_prefixee(self):
        self._envoyer(declencheur={**DECLENCHEUR, 'raison': 'pose modifiée'})
        self.assertEqual(self._lignes()[0].body,
                         'Conception recalculée : pose modifiée')
