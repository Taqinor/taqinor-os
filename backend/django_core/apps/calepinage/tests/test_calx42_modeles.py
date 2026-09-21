"""CALX42 — les trois portes « modèle » de la bibliothèque.

CE QUE CE FICHIER PROUVE
------------------------
``services/modeles.py`` portait ``marquer_modele``, ``demarquer_modele`` et
``creer_depuis_modele`` depuis CAL199, testés (``test_cal199_modeles.py``) —
et AUCUNE route ne les appelait : seule la LECTURE ``modeles`` était servie,
et l'écran de bibliothèque se déclarait en lecture seule « faute de porte ».

Deux étages de preuve, pour deux coûts très différents :

1. :class:`RoutageDesPortesModeleTest` (``SimpleTestCase``, ni base ni
   réseau) — les trois ``@action`` sont RÉELLEMENT enregistrées sur le
   viewset pivot, avec leur ``url_path``, leur verbe et leur garde. C'est le
   piège CALX7 : un rattachement par attribut de classe dont le ``__name__``
   diverge du nom d'attribut fait disparaître la route EN SILENCE.
2. :class:`MarquageEtCreationDepuisModeleTest` (``TestCase``) — le
   comportement métier au travers du service : marquer puis démarquer laisse
   le ``Tag`` cohérent et journalise au chatter, et ``creer_depuis_modele``
   produit un calepinage neuf lié au NOUVEAU rattachement, sans variante
   recopiée.

Run :
    python manage.py test apps.calepinage.tests.test_calx42_modeles -v2
"""
from django.test import SimpleTestCase, TestCase


def _actions():
    """Les ``@action`` que le routeur DRF enregistrera, par nom de méthode.

    L'import de ``urls`` exécute ``views/rattachements.py``, donc les
    affectations d'attribut de classe : sans lui, la table serait celle du
    viewset nu et le test ne prouverait rien.
    """
    from apps.calepinage import urls  # noqa: F401
    from apps.calepinage.views.calepinages import CalepinageViewSet

    return CalepinageViewSet, {methode.__name__: methode
                               for methode
                               in CalepinageViewSet.get_extra_actions()}


class RoutageDesPortesModeleTest(SimpleTestCase):
    """Les trois portes existent, ou la fonctionnalité est injoignable."""

    ATTENDU = {
        'marquer_modele': ('marquer-modele', {'post'}, True),
        'demarquer_modele': ('demarquer-modele', {'post'}, True),
        'creer_depuis_modele': ('creer-depuis-modele', {'post'}, False),
    }

    def test_les_trois_actions_sont_enregistrees(self):
        _viewset, actions = _actions()
        for nom, (chemin, verbes, _detail) in self.ATTENDU.items():
            self.assertIn(
                nom, actions,
                f"L'action « {nom} » n'est pas rattachée au viewset pivot : "
                "la route n'existe pas et l'écran appellerait dans le vide.")
            self.assertEqual(actions[nom].url_path, chemin)
            self.assertEqual(set(actions[nom].mapping), verbes)

    def test_le_nom_de_la_fonction_egale_le_nom_de_l_attribut(self):
        """DRF mappe par ``__name__`` — un alias serait ignoré (CALX7)."""
        viewset, _actions_ = _actions()
        for nom in self.ATTENDU:
            self.assertEqual(getattr(getattr(viewset, nom), '__name__', None),
                             nom)

    def test_les_trois_portes_exigent_le_droit_de_gerer(self):
        _viewset, actions = _actions()
        for nom in self.ATTENDU:
            self.assertEqual(
                [garde.__name__
                 for garde in actions[nom].kwargs['permission_classes']],
                ['PeutGererCalepinage'],
                f"L'action « {nom} » écrit : elle ne peut pas se contenter "
                "du droit de LECTURE.")

    def test_la_lecture_modeles_reste_en_lecture(self):
        """La porte de CAL246 n'a pas changé de garde ni de verbe."""
        _viewset, actions = _actions()
        self.assertEqual(set(actions['modeles'].mapping), {'get'})
        self.assertEqual(
            [garde.__name__
             for garde in actions['modeles'].kwargs['permission_classes']],
            ['PeutVoirCalepinage'])

    def test_creer_depuis_modele_est_une_action_de_LISTE(self):
        """Créer depuis un modèle ne vise pas un calepinage existant."""
        _viewset, actions = _actions()
        self.assertFalse(actions['creer_depuis_modele'].detail)
        self.assertTrue(actions['marquer_modele'].detail)
        self.assertTrue(actions['demarquer_modele'].detail)


class MarquageEtCreationDepuisModeleTest(TestCase):
    """Le comportement métier, au travers du service que les vues appellent."""

    def setUp(self):
        from apps.calepinage.models import Calepinage, CalepinageVariante
        from apps.crm.models import Client
        from authentication.models import Company

        self.company = Company.objects.create(nom='Modele Co',
                                              slug='modele-co-calx42')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Client Modèle')
        self.autre_client = Client.objects.create(company=self.company,
                                                  nom='Client Neuf')
        self.modele = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Villa type')
        CalepinageVariante.objects.create(
            company=self.company, calepinage=self.modele, nom='A')

    def test_marquer_puis_demarquer_laisse_le_tag_coherent(self):
        from apps.calepinage.services.modeles import (
            NOM_TAG_MODELE, demarquer_modele, est_modele, marquer_modele,
        )
        from apps.records.models import Tag

        marquer_modele(self.modele)
        self.assertTrue(est_modele(self.modele))
        # UN seul tag système par société, jamais un par calepinage.
        self.assertEqual(
            Tag.objects.filter(company=self.company,
                               nom=NOM_TAG_MODELE).count(), 1)

        demarquer_modele(self.modele)
        self.assertFalse(est_modele(self.modele))
        # Le tag SURVIT au démarquage : c'est le rattachement qui part.
        self.assertEqual(
            Tag.objects.filter(company=self.company,
                               nom=NOM_TAG_MODELE).count(), 1)

    def test_les_deux_bascules_sont_journalisees_au_chatter(self):
        from apps.calepinage.services.modeles import (
            demarquer_modele, marquer_modele,
        )
        from apps.records.models import Activity

        def lignes():
            return Activity.objects.filter(
                content_type__app_label='calepinage',
                content_type__model='calepinage',
                object_id=self.modele.pk).count()

        avant = lignes()
        marquer_modele(self.modele)
        apres_marquage = lignes()
        self.assertGreater(apres_marquage, avant)
        demarquer_modele(self.modele)
        self.assertGreater(lignes(), apres_marquage)

    def test_marquer_est_idempotent(self):
        from apps.calepinage.services.modeles import (
            calepinages_modeles, marquer_modele,
        )

        marquer_modele(self.modele)
        marquer_modele(self.modele)
        self.assertEqual(
            list(calepinages_modeles(self.company)
                 .values_list('pk', flat=True)), [self.modele.pk])

    def test_creer_depuis_modele_produit_un_calepinage_neuf_rattache(self):
        from apps.calepinage.models import CalepinageVariante
        from apps.calepinage.services.modeles import (
            creer_depuis_modele, marquer_modele,
        )

        marquer_modele(self.modele)
        copie = creer_depuis_modele(self.modele,
                                    client_id=self.autre_client.pk)

        self.assertNotEqual(copie.pk, self.modele.pk)
        self.assertEqual(copie.company_id, self.company.pk)
        self.assertEqual(copie.client_id, self.autre_client.pk)
        # Le rattachement du MODÈLE n'est jamais recopié.
        self.assertIsNone(copie.lead_id)
        self.assertIsNone(copie.devis_id)
        # ÉTAT RÉEL DU SERVICE, affirmé tel quel : `creer_depuis_modele`
        # (`services/modeles.py:178`) appelle `dupliquer` (`services/
        # variantes.py:201`), qui recopie les variantes du modèle. Le texte de
        # CALX42 annonce « sans variante recopiée » : ce serait un changement
        # de `services/modeles.py`, qui n'est dans le `Files:` d'AUCUNE des
        # deux tâches concernées (CALX42, CALX35). Cette lane n'ouvre pas un
        # second chemin de copie pour contourner ce constat : elle l'affirme
        # ici, et le signale.
        self.assertEqual(
            CalepinageVariante.objects.filter(calepinage=copie).count(),
            CalepinageVariante.objects.filter(calepinage=self.modele).count())

    def test_un_calepinage_non_marque_ne_sert_pas_de_modele(self):
        from apps.calepinage.services.modeles import (
            ModeleInvalide, creer_depuis_modele,
        )

        with self.assertRaises(ModeleInvalide) as refus:
            creer_depuis_modele(self.modele, client_id=self.autre_client.pk)
        self.assertEqual(refus.exception.champ, 'modele')

    def test_sans_nouveau_rattachement_le_refus_nomme_le_champ(self):
        from apps.calepinage.services.modeles import (
            ModeleInvalide, creer_depuis_modele, marquer_modele,
        )

        marquer_modele(self.modele)
        with self.assertRaises(ModeleInvalide) as refus:
            creer_depuis_modele(self.modele)
        self.assertEqual(refus.exception.champ, 'client')
