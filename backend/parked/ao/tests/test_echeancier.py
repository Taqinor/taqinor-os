"""AOF15 — échéancier DÉRIVÉ du projet + du CPS, rappels, automatisation.

Un dossier d'appel d'offres se perd sur une DATE, jamais sur la technique. Ce
test verrouille les quatre promesses :

  1. la génération est IDEMPOTENTE — rejouer ne duplique rien ;
  2. une PROROGATION écrite DÉCALE l'échéance existante (et donc son rappel)
     au lieu d'en créer une seconde ; sans cela un dossier prorogé deux fois
     afficherait trois dates de validité concurrentes ;
  3. le rappel se déclenche exactement à J-``rappel_jours`` ;
  4. AUCUN envoi réseau dans le service (sélection = calcul pur).

Bonus vérifié ici : la surface ``automation_state_fields`` déclarée dans
``apps/ao/platform.py`` est RÉELLEMENT câblée (règle d'honnêteté ARC41).

Run :
    python manage.py test apps.ao.tests.test_echeancier -v2
"""
import datetime

from django.test import SimpleTestCase, TestCase

from apps.ao import services
from apps.ao.models import AppelOffre, EcheanceAO, ExigenceCPS
from authentication.models import Company


class TestManifestePlateforme(SimpleTestCase):
    def test_statut_declare_automatisable(self):
        from apps.ao.platform import PLATFORM
        self.assertIn(
            {'model': 'ao.appeloffre', 'field': 'statut'},
            PLATFORM['automation_state_fields'])

    def test_la_surface_est_reellement_cablee(self):
        """ARC41 — une surface annoncée doit exister dans le code."""
        self.assertTrue(
            callable(services.emettre_changement_statut_automation))


class TestGenerationEcheancier(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF15 Co', slug='aof15-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-15-1', objet='Échéancier',
            date_limite=datetime.date(2026, 3, 2),
            date_ouverture_plis=datetime.date(2026, 3, 10))

    def test_genere_les_trois_echeances_derivees(self):
        resume = services.generer_echeancier_ao(self.ao)
        self.assertEqual(resume['creees'], 3)
        types = set(self.ao.echeances.values_list('type_echeance', flat=True))
        self.assertEqual(types, {'remise_plis', 'ouverture', 'validite'})

    def test_generation_idempotente(self):
        services.generer_echeancier_ao(self.ao)
        resume = services.generer_echeancier_ao(self.ao)
        self.assertEqual(resume, {'creees': 0, 'mises_a_jour': 0,
                                  'inchangees': 3})
        self.assertEqual(self.ao.echeances.count(), 3)

    def test_aucune_date_inventee(self):
        """Sans date au projet, aucune échéance n'est fabriquée."""
        nu = AppelOffre.objects.create(
            company=self.company, reference='AO-15-NU', objet='Sans dates')
        resume = services.generer_echeancier_ao(nu)
        self.assertEqual(resume['creees'], 0)
        self.assertEqual(nu.echeances.count(), 0)

    def test_validite_derivee_de_l_ouverture(self):
        services.generer_echeancier_ao(self.ao)
        validite = self.ao.echeances.get(type_echeance='validite')
        self.assertEqual(validite.date_echeance, datetime.date(2026, 5, 24))

    def test_clause_cps_prime_sur_le_champ_du_projet(self):
        ExigenceCPS.objects.create(
            company=self.company, appel_offre=self.ao, code='VALIDITE_OFFRE',
            libelle="Validité de l'offre",
            type_exigence=ExigenceCPS.TypeExigence.VALIDITE_OFFRE,
            valeur_num='90', unite='jours')
        self.assertEqual(services.jours_validite_effectifs(self.ao), 90)
        services.generer_echeancier_ao(self.ao)
        validite = self.ao.echeances.get(type_echeance='validite')
        self.assertEqual(validite.date_echeance, datetime.date(2026, 6, 8))


class TestProrogation(TestCase):
    """Une prorogation DÉCALE — elle n'ajoute jamais une seconde échéance."""

    def setUp(self):
        self.company = Company.objects.create(nom='AOF15 Pro', slug='aof15-pro')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-15-P', objet='Prorogation',
            date_ouverture_plis=datetime.date(2026, 3, 10))
        services.generer_echeancier_ao(self.ao)

    def test_prorogation_decale_au_lieu_de_dupliquer(self):
        avant = self.ao.echeances.get(type_echeance='validite')
        self.assertEqual(avant.date_echeance, datetime.date(2026, 5, 24))
        ExigenceCPS.objects.create(
            company=self.company, appel_offre=self.ao, code='VALIDITE_OFFRE',
            libelle='Prorogation écrite',
            type_exigence=ExigenceCPS.TypeExigence.VALIDITE_OFFRE,
            valeur_num='105', unite='jours')
        resume = services.generer_echeancier_ao(self.ao)
        self.assertEqual(resume['mises_a_jour'], 1)
        self.assertEqual(
            self.ao.echeances.filter(type_echeance='validite').count(), 1)
        apres = self.ao.echeances.get(type_echeance='validite')
        self.assertEqual(apres.pk, avant.pk)
        self.assertEqual(apres.date_echeance, datetime.date(2026, 6, 23))

    def test_prorogation_rouvre_l_echeance_traitee(self):
        validite = self.ao.echeances.get(type_echeance='validite')
        validite.traitee = True
        validite.save(update_fields=['traitee'])
        ExigenceCPS.objects.create(
            company=self.company, appel_offre=self.ao, code='VALIDITE_OFFRE',
            libelle='Prorogation écrite',
            type_exigence=ExigenceCPS.TypeExigence.VALIDITE_OFFRE,
            valeur_num='105', unite='jours')
        services.generer_echeancier_ao(self.ao)
        validite.refresh_from_db()
        self.assertFalse(validite.traitee)


class TestRappels(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF15 Rap', slug='aof15-rap')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-15-R', objet='Rappels')

    def _echeance(self, date_echeance, rappel_jours):
        return EcheanceAO.objects.create(
            company=self.company, appel_offre=self.ao,
            type_echeance=EcheanceAO.TypeEcheance.REMISE_PLIS,
            libelle='Remise des plis', date_echeance=date_echeance,
            rappel_jours=rappel_jours)

    def test_rappel_exactement_a_j_moins_rappel_jours(self):
        echeance = self._echeance(datetime.date(2026, 3, 10), 7)
        veille = services.echeances_ao_dues(
            self.company, a_la_date=datetime.date(2026, 3, 2))
        self.assertEqual(veille, [])
        jour_j = services.echeances_ao_dues(
            self.company, a_la_date=datetime.date(2026, 3, 3))
        self.assertEqual([e.pk for e in jour_j], [echeance.pk])

    def test_echeance_traitee_ne_revient_pas(self):
        echeance = self._echeance(datetime.date(2026, 3, 10), 7)
        echeance.traitee = True
        echeance.save(update_fields=['traitee'])
        dues = services.echeances_ao_dues(
            self.company, a_la_date=datetime.date(2026, 3, 9))
        self.assertEqual(dues, [])

    def test_service_sans_aucun_envoi_reseau(self):
        """Le module de services ne connaît AUCUN client réseau.

        L'échéancier CALCULE et ÉCRIT ; la diffusion (courriel, notification)
        appartient aux apps dédiées, jamais à ``ao``.
        """
        import inspect

        source = inspect.getsource(services)
        for interdit in ('requests', 'urllib', 'smtplib', 'send_mail',
                         'http.client', 'httpx'):
            self.assertNotIn(interdit, source, interdit)

    def test_beat_pose_une_note_et_marque_traitee(self):
        from apps.ao.scheduled import rappeler_echeances
        from apps.records.services import chatter_qs

        echeance = self._echeance(datetime.date.today(), 7)
        resultat = rappeler_echeances()
        self.assertGreaterEqual(resultat['rappels'], 1)
        echeance.refresh_from_db()
        self.assertTrue(echeance.traitee)
        notes = list(chatter_qs(self.ao, company=self.company))
        self.assertEqual(len(notes), 1)
        self.assertIn('Rappel', notes[0].body)


class TestTacheGeneration(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF15 Tac', slug='aof15-tac')

    def test_tache_idempotente_et_tolerante_a_l_absence(self):
        from apps.ao.tasks import generer_echeancier

        ao = AppelOffre.objects.create(
            company=self.company, reference='AO-15-T', objet='Tâche',
            date_limite=datetime.date(2026, 4, 1))
        premier = generer_echeancier(ao.id)
        second = generer_echeancier(ao.id)
        # Une date de remise implique DEUX échéances, pas une : la remise des
        # plis, et la fin de validité de l'offre — DÉRIVÉE de la durée portée
        # par le projet (75 j par défaut au Maroc) à partir de cette même
        # date réelle. Rien n'est inventé, et compter « 1 » ici revenait à
        # ignorer une date sur laquelle un dossier se perd.
        types = set(EcheanceAO.objects.filter(appel_offre=ao).values_list(
            'type_echeance', flat=True))
        self.assertEqual(types, {EcheanceAO.TypeEcheance.REMISE_PLIS,
                                 EcheanceAO.TypeEcheance.VALIDITE})
        self.assertEqual(premier['creees'], len(types))
        # Le vrai sujet du test : rejouer ne duplique RIEN.
        self.assertEqual(second['creees'], 0)
        self.assertEqual(second['inchangees'], len(types))
        self.assertEqual(generer_echeancier(999999),
                         {'creees': 0, 'mises_a_jour': 0, 'inchangees': 0})
