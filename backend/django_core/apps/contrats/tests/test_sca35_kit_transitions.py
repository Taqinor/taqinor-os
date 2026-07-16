"""SCA35 — Pilote « Contrat » du kit ``core.documents`` : non-régression.

``Contrat`` n'hérite pas de ``core.documents.DocumentMetier`` (voir la note
SCA35 dans ``models.py``/``services.py``/``views.py``) : le kit ne serait
qu'un socle plus pauvre pour un modèle déjà riche (chatter ARC8 déjà vivant,
PDF déjà délégué à ``core.pdf``, garde métier « ≥2 parties » absente du
socle générique). L'ADOPTION porte sur le CONTRAT de lecture du graphe :
``Contrat.TRANSITIONS`` / ``transitions_permises`` / ``transition_permise``
exposent, au format et avec la même API que
``core.documents.DocumentMetier``, EXACTEMENT le graphe de la machine
d'états EXISTANTE (``machine_etats._transitions()``, CONTRAT12).

Ce module prouve :
1. ``Contrat.TRANSITIONS`` (propriété d'instance, format kit) ==
   ``machine_etats._transitions()`` (source de vérité), statut par statut,
   pour TOUS les statuts déclarés — aucune transition ajoutée, aucune perdue.
2. ``transitions_permises()`` / ``transition_permise()`` (API du kit,
   ``core.documents.DocumentMetier``) donnent EXACTEMENT le même résultat que
   ``machine_etats.statuts_suivants()`` / ``machine_etats.transition_permise()``
   pour chaque statut de départ.
3. Le cycle de vie fonctionnel n'a pas changé : ``services.changer_statut``
   (le SEUL point d'écriture) reste gardé identiquement (transitions permises/
   refusées + garde « ≥2 parties »), confirmant que l'ADOPTION du kit est
   purement une lecture supplémentaire, jamais une réécriture du graphe.
"""
from django.test import TestCase

from authentication.models import Company

from apps.contrats import machine_etats, services
from apps.contrats.machine_etats import TransitionInterdite
from apps.contrats.models import Contrat, PartieContrat

S = Contrat.Statut


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_contrat(company, statut=S.BROUILLON, parties=2):
    contrat = Contrat.objects.create(company=company, objet="Contrat", statut=statut)
    roles = [
        PartieContrat.TypePartie.CLIENT,
        PartieContrat.TypePartie.PRESTATAIRE,
        PartieContrat.TypePartie.TEMOIN,
    ]
    for i in range(parties):
        PartieContrat.objects.create(
            company=company, contrat=contrat,
            type_partie=roles[i % len(roles)], nom=f"Partie {i}", ordre=i,
        )
    return contrat


class TransitionsGrapheIdentiqueTests(TestCase):
    """``Contrat.TRANSITIONS`` (format kit) == ``machine_etats._transitions()``."""

    def setUp(self):
        self.co = make_company("sca35-graphe", "Graphe")

    def test_transitions_property_egale_machine_etats(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        attendu = machine_etats._transitions()
        obtenu = contrat.TRANSITIONS
        self.assertEqual(set(obtenu.keys()), set(attendu.keys()))
        for statut, cibles in attendu.items():
            self.assertEqual(
                set(obtenu[statut]), set(cibles),
                msg=f"Divergence pour le statut « {statut} »",
            )

    def test_tous_les_statuts_couverts(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        self.assertEqual(set(contrat.TRANSITIONS.keys()), set(S.values))


class TransitionsPermisesMatriceTests(TestCase):
    """``transitions_permises``/``transition_permise`` (API kit) vs machine_etats."""

    def setUp(self):
        self.co = make_company("sca35-matrice", "Matrice")

    def test_matrice_complete_statut_par_statut(self):
        """Pour CHAQUE statut source, l'ensemble des cibles permises via l'API
        du kit est identique à celui de la machine d'états CONTRAT12."""
        for statut_source in S.values:
            with self.subTest(statut_source=statut_source):
                contrat = make_contrat(self.co, statut=statut_source, parties=2)
                attendu = set(machine_etats.statuts_suivants(contrat))
                obtenu = contrat.transitions_permises()
                self.assertEqual(
                    obtenu, attendu,
                    msg=f"Divergence transitions_permises() pour « {statut_source} »",
                )

    def test_transition_permise_matrice_croisee(self):
        """``transition_permise(cible)`` (kit) == ``machine_etats.transition_permise``
        (source de vérité) pour TOUT couple (source, cible) — y compris les
        transitions REFUSÉES (pas seulement les permises)."""
        for statut_source in S.values:
            contrat = make_contrat(self.co, statut=statut_source, parties=2)
            for statut_cible in S.values:
                with self.subTest(source=statut_source, cible=statut_cible):
                    attendu = machine_etats.transition_permise(
                        statut_source, statut_cible)
                    obtenu = contrat.transition_permise(statut_cible)
                    self.assertEqual(
                        obtenu, attendu,
                        msg=(
                            f"Divergence transition_permise() : "
                            f"« {statut_source} » → « {statut_cible} »"
                        ),
                    )

    def test_etats_terminaux_aucune_transition_permise(self):
        for statut_terminal in (S.RESILIE, S.EXPIRE):
            contrat = make_contrat(self.co, statut=statut_terminal, parties=2)
            self.assertEqual(contrat.transitions_permises(), set())


class CycleVieInchangeTests(TestCase):
    """Le SEUL point d'écriture (``services.changer_statut``) reste inchangé :
    l'adoption du kit est une lecture supplémentaire, jamais une réécriture."""

    def setUp(self):
        self.co = make_company("sca35-cycle", "Cycle")

    def test_changer_statut_toujours_le_seul_point_ecriture(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        services.changer_statut(contrat, S.EN_APPROBATION)
        services.changer_statut(contrat, S.SIGNE)
        services.changer_statut(contrat, S.ACTIF)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, S.ACTIF)

    def test_transition_hors_graphe_toujours_refusee(self):
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=2)
        with self.assertRaises(TransitionInterdite):
            services.changer_statut(contrat, S.ACTIF)

    def test_garde_parties_toujours_active_hors_du_kit(self):
        """La garde « ≥2 parties » n'est PAS un contrat du kit générique — elle
        doit rester active après adoption (le kit ne la connaît pas)."""
        contrat = make_contrat(self.co, statut=S.BROUILLON, parties=1)
        # Le kit dirait la transition « permise » (elle est dans le graphe) ;
        # seule la machine d'états EXISTANTE applique la garde métier.
        self.assertTrue(contrat.transition_permise(S.EN_APPROBATION))
        with self.assertRaises(TransitionInterdite):
            services.changer_statut(contrat, S.EN_APPROBATION)

    def test_reference_reste_un_champ_libre_non_numerote(self):
        """SCA35 : aucune numérotation ``core.numbering`` n'est câblée sur
        ``Contrat`` — le champ ``reference`` reste tel que saisi (comportement
        inchangé, pas de régression introduite par le pilote)."""
        contrat = Contrat.objects.create(
            company=self.co, objet="Réf libre", reference="MA-REF-CUSTOM-42")
        contrat.refresh_from_db()
        self.assertEqual(contrat.reference, "MA-REF-CUSTOM-42")
