"""TCH70 — Étapes nocturnes du rythme et révélations à leur événement.

Base requise (`TestCase`) : joué par la CI. La nuit est appelée avec son `jour` (jamais d'horloge
vivante) ; chaque test relit l'état STOCKÉ et rejoue la même nuit : rien de plus ne doit changer
(rejeu déterministe, contrainte unique des cartes).
"""
import datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.taches import nocturne
from apps.taches.choix import (
    CanalIncitation, ModeRythme, SourceObjectif, StatutJour, StatutTache, TypeIncitationEcran,
)
from apps.taches.models.journee import PlanJour
from apps.taches.models.rythme import IncitationCoach, ReglagesRythme
from apps.taches.services import revelations, rythme
from apps.taches.tests import fabriques

J = datetime.date(2026, 11, 18)  # la nuit du 18 clôt le 17
J7 = J + datetime.timedelta(days=7)


def jours(compte, comptes, *, avant=J, statut=StatutJour.EVALUE):
    """Un `PlanJour` clos par compte, les jours qui précèdent `avant` (le dernier = veille)."""
    for rang, faites in enumerate(reversed(comptes), start=1):
        fabriques.plan(compte, avant - datetime.timedelta(days=rang), statut_jour=statut, compte_rythme=faites)


def cartes(compte, **filtres):
    return list(IncitationCoach.objects.filter(proprietaire=compte, **filtres).order_by('pk'))


def instantane():
    return (list(IncitationCoach.objects.order_by('pk').values_list('pk', 'type', 'cle', 'reponse', 'donnees')),
            list(ReglagesRythme.objects.order_by('pk').values_list(
                'palier', 'bloc_debut', 'refus_montee', 'blocs_a_sauter', 'tenir_reference', 'tenir_fixee_le',
                'tenir_silence_jusquau', 'pauses_sollicitations')))


class NuitRythmeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.ailleurs = fabriques.compte(cls.b, nom='u1')

    def nuit(self):
        rythme.etapes_nocturnes(self.a.pk, J)

    def rejouer_sans_effet(self):
        avant = instantane()
        self.nuit()
        self.assertEqual(instantane(), avant)

    def test_demarrage_a_froid_propose_sans_imposer(self):
        reglages = fabriques.reglages(self.u1)
        jours(self.u1, [9, 10, 9, 1, 2, 1, 2, 9, 10, 9])  # regles.md §6.10 n° 11 : journée type 6
        self.nuit()
        reglages.refresh_from_db()
        self.assertEqual((reglages.palier, reglages.bloc_debut), (None, J))
        [carte] = cartes(self.u1, type=TypeIncitationEcran.PROPOSITION_PALIER)
        self.assertEqual((carte.cle, carte.donnees, carte.jour, carte.expire_le), ('premier', {'type': 6}, J, J7))
        self.rejouer_sans_effet()

    def test_objectif_dit_carte_journee_type(self):
        fabriques.reglages(self.u1, palier=5, palier_source=SourceObjectif.DIT)
        jours(self.u1, [3, 3, 2, 4, 3, 3, 2, 3, 4, 3])  # n° 12 : (5, 3, journee_type)
        self.nuit()
        [carte] = cartes(self.u1, type=TypeIncitationEcran.PROPOSITION_PALIER)
        self.assertEqual((carte.cle, carte.donnees), ('journee_type', {'type': 3, 'dit': 5}))

    def test_bloc_tenu_propose_monter_et_repart(self):
        reglages = fabriques.reglages(self.u1, palier=5, palier_source=SourceObjectif.ACCEPTE,
                                      bloc_debut=J - datetime.timedelta(days=10))
        jours(self.u1, [5, 6, 5, 4, 7, 5, 3, 6, 5, 4])  # n° 13 : 7/10 → monter
        self.nuit()
        reglages.refresh_from_db()
        self.assertEqual((reglages.palier, reglages.bloc_debut, reglages.meilleur_tenu), (5, J, 5))
        [carte] = cartes(self.u1, type=TypeIncitationEcran.PROPOSITION_PALIER)
        self.assertEqual((carte.cle, carte.donnees, carte.expire_le),
                         ('monter', {'N': 5, 'N1': 6, 'tenus': 7, 'refus': 1}, J7))
        self.rejouer_sans_effet()

    def test_bloc_faible_propose_baisser_jamais_impose(self):
        reglages = fabriques.reglages(self.u1, palier=6, palier_source=SourceObjectif.ACCEPTE,
                                      bloc_debut=J - datetime.timedelta(days=10))
        jours(self.u1, [5, 4, 6, 5, 3, 5, 6, 4, 5, 4])  # n° 14 : 2/10 → baisser
        self.nuit()
        reglages.refresh_from_db()
        self.assertEqual(reglages.palier, 6)
        [carte] = cartes(self.u1, type=TypeIncitationEcran.PROPOSITION_PALIER)
        self.assertEqual((carte.cle, carte.donnees), ('baisser', {'N': 6, 'N_1': 5, 'tenus': 2}))

    def test_bloc_incomplet_rien(self):
        fabriques.reglages(self.u1, palier=5, bloc_debut=J - datetime.timedelta(days=9))
        jours(self.u1, [5] * 9)
        self.nuit()
        self.assertEqual(cartes(self.u1), [])

    def test_derive_sous_puis_silence_28_jours(self):
        fixee = J - datetime.timedelta(days=14)
        reglages = fabriques.reglages(self.u1, mode=ModeRythme.TENIR, tenir_reference=5, tenir_fixee_le=fixee)
        jours(self.u1, [3] * 11 + [4] * 3)  # n° 27 : moyenne 3,21 → sous
        self.nuit()
        reglages.refresh_from_db()
        self.assertEqual(reglages.tenir_silence_jusquau, J + datetime.timedelta(days=28))
        [carte] = cartes(self.u1, type=TypeIncitationEcran.DERIVE_TENIR)
        self.assertEqual(carte.cle, 'sous')
        self.assertEqual((carte.donnees['m'], carte.donnees['R'], carte.donnees['bas'], carte.donnees['haut']),
                         (3, 5.0, 4.0, 6.0))
        self.assertAlmostEqual(carte.donnees['moyenne'], 3.2143, places=4)
        self.rejouer_sans_effet()

    def test_derive_jamais_vers_zero_ni_borne_negative(self):
        """Revue F2 tour 2 #9 : `m` plancher 1, bas de zone plancher 0, `R` montré comme l'objectif."""
        fixee = J - datetime.timedelta(days=14)
        reglages = fabriques.reglages(self.u1, mode=ModeRythme.TENIR, tenir_reference=3, tenir_fixee_le=fixee)
        jours(self.u1, [0] * 13 + [1])  # moyenne 0,07 → sous, arrondie 0
        self.nuit()
        [carte] = cartes(self.u1, type=TypeIncitationEcran.DERIVE_TENIR)
        self.assertEqual((carte.donnees['m'], carte.donnees['R'], carte.donnees['bas']), (1, 3, 2.0))
        IncitationCoach.objects.all().delete()
        reglages.tenir_reference, reglages.tenir_silence_jusquau = 0.29, None
        reglages.save(update_fields=['tenir_reference', 'tenir_silence_jusquau'])
        PlanJour.objects.filter(proprietaire=self.u1).update(compte_rythme=2)  # moyenne 2 → au-dessus de 1,29
        self.nuit()
        [carte] = cartes(self.u1, type=TypeIncitationEcran.DERIVE_TENIR)
        self.assertEqual((carte.cle, carte.donnees['m'], carte.donnees['R'], carte.donnees['bas']),
                         ('au_dessus', 2, 1, 0))

    def test_derive_sans_carte_quand_rien_a_proposer(self):
        """#9 : R 1,4 (objectif 1) et 0,1 tâche par jour : « Garder 1, ou descendre à 1 » ne propose rien —
        pas de carte, pas de silence (aucune carte dont le bouton ne fait rien)."""
        fixee = J - datetime.timedelta(days=14)
        reglages = fabriques.reglages(self.u1, mode=ModeRythme.TENIR, tenir_reference=1.4, tenir_fixee_le=fixee)
        jours(self.u1, [0] * 12 + [1, 1])
        self.nuit()
        self.assertEqual(cartes(self.u1, type=TypeIncitationEcran.DERIVE_TENIR), [])
        reglages.refresh_from_db()
        self.assertIsNone(reglages.tenir_silence_jusquau)

    def test_tenir_provisoire_fixee_apres_14_jours(self):
        reglages = fabriques.reglages(self.u1, mode=ModeRythme.TENIR, tenir_reference=5)
        jours(self.u1, [5] * 13 + [8])  # n° 37 : R 5,21
        self.nuit()
        reglages.refresh_from_db()
        self.assertEqual((float(reglages.tenir_reference), reglages.tenir_fixee_le), (5.21, J))

    def test_constat_c7_et_coupe_rien(self):
        reglages = fabriques.reglages(self.u1)
        fabriques.tache(self.u1, jour_prevu=J, reports=3)
        self.nuit()
        [carte] = cartes(self.u1, type=TypeIncitationEcran.CONSTAT)
        self.assertEqual((carte.cle, carte.donnees, carte.expire_le), ('C7', {'n': 1}, J7))
        self.rejouer_sans_effet()
        IncitationCoach.objects.all().delete()
        reglages.comprendre_mon_rythme = False
        reglages.save(update_fields=['comprendre_mon_rythme'])
        self.nuit()
        self.assertEqual(cartes(self.u1, type=TypeIncitationEcran.CONSTAT), [])

    def test_constats_hors_premiere_livraison_jamais_crees(self):
        """Revue F2 tour 2 #7 : C4 et C8 (leur « Oui » ne change rien) et C1, C2 (leurs lignes ne sont
        écrites par rien) ne naissent pas, même quand leurs données y sont."""
        fabriques.reglages(self.u1)
        for d in range(1, 11):  # 10 plans à 5 gardées dont 2 faites : C4 serait vrai
            fabriques.plan(self.u1, J - datetime.timedelta(days=d), statut_jour=StatutJour.EVALUE, compte_rythme=2,
                           plan_prevues=5, plan_faites=2)
        projet = fabriques.projet(self.u1)
        with mock.patch.object(rythme, '_projet_neglige', return_value=projet.pk):
            self.nuit()
        self.assertEqual([c.cle for c in cartes(self.u1, type=TypeIncitationEcran.CONSTAT)
                          if c.cle in ('C1', 'C2', 'C4', 'C8')], [])

    def test_c7_compte_les_lignes_d_a_revoir(self):
        """#7 : C7 compte les lignes « Reportée 3 fois » d'À revoir, que son bouton ouvre — jamais une
        tâche déjà tranchée ni une tâche de la réserve."""
        from apps.taches.services.journee import aujourdhui
        fabriques.reglages(self.u1)
        fabriques.tache(self.u1, reports=3, reports_tranches=3, jour_prevu=J + datetime.timedelta(days=2))
        fabriques.tache(self.u1, reports=4, reports_tranches=4, quelque_jour=True)
        self.nuit()
        self.assertEqual(cartes(self.u1, type=TypeIncitationEcran.CONSTAT, cle='C7'), [])
        fabriques.tache(self.u1, reports=3, jour_prevu=J - datetime.timedelta(days=1))
        fabriques.tache(self.u1, reports=5, reports_tranches=2, jour_prevu=J)
        IncitationCoach.objects.all().delete()
        self.nuit()
        [carte] = cartes(self.u1, type=TypeIncitationEcran.CONSTAT, cle='C7')
        maintenant = timezone.make_aware(datetime.datetime(2026, 11, 18, 9, 0))
        a_revoir = aujourdhui(self.u1, J, maintenant)['a_decider']
        self.assertEqual((carte.donnees, len(a_revoir)), ({'n': 2}, 2))

    def test_constat_c3_les_autres_jours(self):
        fabriques.reglages(self.u1)
        vendredis = {J - datetime.timedelta(days=d) for d in range(1, 57)
                     if (J - datetime.timedelta(days=d)).weekday() == 4}
        for d in range(1, 57):
            jour = J - datetime.timedelta(days=d)
            if jour.weekday() < 5:
                fabriques.plan(self.u1, jour, statut_jour=StatutJour.EVALUE,
                               compte_rythme=3 if jour in vendredis else 6)
        self.nuit()
        [carte] = cartes(self.u1, type=TypeIncitationEcran.CONSTAT, cle='C3')
        self.assertEqual(carte.donnees, {'jour': 4, 'm1': 3.0, 'm2': 6.0})

    def test_expirees_et_ignorees(self):
        fabriques.reglages(self.u1)
        vieille = IncitationCoach.objects.create(
            company=self.a, proprietaire=self.u1, type=TypeIncitationEcran.CONSTAT, cle='C5',
            canal=CanalIncitation.ECRAN, jour=J - datetime.timedelta(days=8), expire_le=J - datetime.timedelta(days=1))
        envoye = timezone.make_aware(datetime.datetime(2026, 11, 17, 18, 0))
        push = IncitationCoach.objects.create(company=self.a, proprietaire=self.u1, type='bilan_soir',
                                              canal=CanalIncitation.PUSH, jour=J - datetime.timedelta(days=1),
                                              montre_le=envoye)
        ouvert = IncitationCoach.objects.create(company=self.a, proprietaire=self.u1, type='plan_matin',
                                                canal=CanalIncitation.PUSH, jour=J - datetime.timedelta(days=1),
                                                montre_le=envoye, ouvert_le=envoye)
        self.nuit()
        for carte, attendu in ((vieille, 'expiree'), (push, 'ignoree'), (ouvert, '')):
            carte.refresh_from_db()
            self.assertEqual(carte.reponse, attendu)

    def test_pause_apres_14_ignorees(self):
        reglages = fabriques.reglages(self.u1)
        for d in range(1, 15):
            IncitationCoach.objects.create(
                company=self.a, proprietaire=self.u1, type='relance', canal=CanalIncitation.PUSH,
                jour=J - datetime.timedelta(days=d), reponse='ignoree',
                montre_le=timezone.make_aware(datetime.datetime(2026, 11, 1, 15, 0)))
        self.nuit()
        reglages.refresh_from_db()
        self.assertEqual(reglages.pauses_sollicitations, [{'type': 'relance', 'ignorees': 14}])
        [carte] = cartes(self.u1, type=TypeIncitationEcran.PAUSE)
        self.assertEqual((carte.cle, carte.donnees), ('relance', {'type_pause': 'relance', 'ignorees': 14,
                                                                  'heure': '15:00'}))
        self.rejouer_sans_effet()

    def test_revelation_revue_apres_la_premiere_semaine(self):
        reglages = fabriques.reglages(self.u1)
        self.nuit()
        self.assertEqual(cartes(self.u1, type=TypeIncitationEcran.REVELATION), [])
        ReglagesRythme.objects.filter(pk=reglages.pk).update(
            created_at=timezone.make_aware(datetime.datetime(2026, 11, 10, 9, 0)))
        self.nuit()
        [carte] = cartes(self.u1, type=TypeIncitationEcran.REVELATION)
        self.assertEqual((carte.cle, carte.jour, carte.expire_le), ('revue', J, J7))
        self.rejouer_sans_effet()

    def test_une_autre_societe_n_est_pas_touchee(self):
        etrangere = fabriques.reglages(self.ailleurs, palier=5, bloc_debut=J - datetime.timedelta(days=10))
        jours(self.ailleurs, [6] * 10)
        self.nuit()
        etrangere.refresh_from_db()
        self.assertEqual(etrangere.bloc_debut, J - datetime.timedelta(days=10))
        self.assertEqual(cartes(self.ailleurs), [])

    def test_par_la_nuit_orchestree(self):
        fabriques.reglages(self.u1, palier=5, bloc_debut=J - datetime.timedelta(days=10))
        jours(self.u1, [5, 6, 5, 4, 7, 5, 3, 6, 5, 4])
        # La nuit clôt la veille : son compte est RECALCULÉ des tâches faites (4), pas lu du plan posé.
        for _ in range(4):
            fabriques.tache(self.u1, statut=StatutTache.FAIT, estimation_minutes=30,
                            fait_le=timezone.make_aware(datetime.datetime(2026, 11, 17, 12, 0)))
        self.assertTrue(nocturne.executer(self.a.pk, J)['etapes_nocturnes'])
        self.assertEqual(len(cartes(self.u1, type=TypeIncitationEcran.PROPOSITION_PALIER)), 1)


class RevelationsCreationTests(TestCase):
    """Révélations à leur événement : `planifier_projet` (1er projet), `ranger_copilote` (À trier ≥ 5)."""

    @classmethod
    def setUpTestData(cls):
        cls.a = fabriques.societe('a')
        cls.u1 = fabriques.compte(cls.a, nom='u1')

    def setUp(self):
        horloge = mock.patch('django.utils.timezone.localdate', return_value=J)
        horloge.start()
        self.addCleanup(horloge.stop)

    def test_ranger_copilote_a_5_a_trier(self):
        taches = [fabriques.tache(self.u1) for _ in range(4)]
        self.assertIsNone(revelations.apres_creation(self.u1, taches, [], porte='ecran'))
        taches.append(fabriques.tache(self.u1))
        carte = revelations.apres_creation(self.u1, taches[-1:], [], porte='ecran')
        self.assertEqual((carte.type, carte.cle, carte.donnees, carte.jour, carte.expire_le),
                         ('revelation', 'ranger_copilote', {'n': 5}, J, J7))
        self.assertIsNone(revelations.apres_creation(self.u1, taches[-1:], [], porte='ecran'))  # une fois

    def test_ranger_copilote_dit_le_compte_courant(self):
        """Revue F2 tour 2 #10 : « N tâches à trier » rendu À LA LECTURE, le même nombre que le compteur
        À trier (`a_trier.boite_reception`) ; sous 5, la carte se tait."""
        from apps.taches.models.taches import Tache
        from apps.taches.serializers.rythme import forme_proposition
        from apps.taches.services.journee import a_trier
        taches = [fabriques.tache(self.u1) for _ in range(6)]
        carte = revelations.apres_creation(self.u1, taches[-1:], [], porte='saisie')
        self.assertEqual(carte.donnees, {'n': 6})
        Tache.objects.filter(pk=taches[0].pk).update(projet=fabriques.projet(self.u1), triee_le=timezone.now())
        forme = forme_proposition(carte)
        self.assertEqual(a_trier(self.u1, J)['boite_reception'], 5)
        self.assertEqual((forme['donnees'], forme['texte']),
                         ({'n': 5}, '5 tâches à trier : le Copilote peut les ranger dans tes projets.'))
        Tache.objects.filter(pk=taches[1].pk).update(triee_le=timezone.now())
        self.assertIsNone(forme_proposition(carte))  # 4 à trier : sous le seuil, la carte se tait
        carte.reponse = 'ok'
        self.assertEqual(forme_proposition(carte)['boutons'], [])  # répondue : rendue, sans boutons

    def test_planifier_le_premier_projet_seulement(self):
        premier = fabriques.projet(self.u1)
        tache = fabriques.tache(self.u1, projet=premier)
        carte = revelations.apres_creation(self.u1, [tache], [premier], porte='saisie')
        self.assertEqual((carte.cle, carte.donnees), ('planifier_projet', {'projet_id': premier.pk}))
        IncitationCoach.objects.all().delete()
        second = fabriques.projet(self.u1)
        self.assertIsNone(revelations.apres_creation(self.u1, [], [second], porte='saisie'))

    def test_mon_iphone_au_premier_creer_de_la_saisie_3_jours_seulement(self):
        tache = fabriques.tache(self.u1)
        self.assertIsNone(revelations.apres_creation(self.u1, [tache], [], porte='ecran'))
        carte = revelations.apres_creation(self.u1, [tache], [], porte='saisie')
        self.assertEqual((carte.type, carte.cle, carte.donnees, carte.jour, carte.expire_le),
                         ('revelation', 'mon_iphone', {}, J, J + datetime.timedelta(days=3)))
        self.assertIsNone(revelations.apres_creation(self.u1, [tache], [], porte='saisie'))  # une fois

    def test_mon_iphone_passe_apres_les_autres_revelations(self):
        premier = fabriques.projet(self.u1)
        tache = fabriques.tache(self.u1, projet=premier)
        carte = revelations.apres_creation(self.u1, [tache], [premier], porte='saisie')
        self.assertEqual(carte.cle, 'planifier_projet')
        self.assertIsNone(revelations.apres_creation(self.u1, [tache], [], porte='saisie'))  # une par jour

    def test_une_revelation_par_jour(self):
        premier = fabriques.projet(self.u1)
        taches = [fabriques.tache(self.u1) for _ in range(5)]
        revelations.apres_creation(self.u1, taches, [premier], porte='saisie')
        self.assertEqual(list(IncitationCoach.objects.values_list('cle', flat=True)), ['planifier_projet'])

    def test_par_creer_taches(self):
        from apps.taches.services.creation import creer_taches
        lignes = [{'titre': f'Idée {n}'} for n in range(5)]
        creer_taches(self.u1, lignes, source='rapide', porte='ecran')
        self.assertEqual(list(IncitationCoach.objects.filter(proprietaire=self.u1).values_list('cle', flat=True)),
                         ['ranger_copilote'])
