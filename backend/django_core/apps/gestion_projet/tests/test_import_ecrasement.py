"""Garde-fou anti-écrasement — audit import du plan de tâches (XPRJ24).

``services.importer_taches`` est AUDITÉ ici pour confirmer qu'il est
CRÉATION SEULE : il ne fait jamais ``get_or_create``/``update_or_create`` ni
aucun rapprochement par ``code_wbs`` sur une tâche déjà existante — chaque
ligne du fichier importé produit un ``Tache.objects.create(...)``
inconditionnel. Réimporter un fichier périmé sur un projet qui contient déjà
des tâches saisies à la main ne peut donc JAMAIS remplacer une valeur réelle
existante : au pire il crée des DOUBLONS (même ``code_wbs``, ``pk``
différent), jamais un écrasement silencieux.

Si un jour ``importer_taches`` gagne un mode de MISE À JOUR d'une tâche déjà
existante, ces tests doivent être remplacés par la suite complète (aperçu /
remplissage-seul / écrasement opt-in / journal) construite sur la primitive
plateforme ``apps.dataimport.services.appliquer_maj_import`` — jamais un
garde-fou maison.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.gestion_projet.models import Projet, Tache
from apps.gestion_projet.services import importer_taches


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ImporterTachesJamaisDecrasementTests(TestCase):
    """``importer_taches`` ne touche jamais une tâche déjà existante."""

    def setUp(self):
        self.co = make_company('gp-import-ecr', 'S')
        self.autre_co = make_company('gp-import-ecr-autre', 'Autre')
        self.projet = Projet.objects.create(
            company=self.co, code='P-ECR', nom='Projet écrasement')
        self.tache_existante = Tache.objects.create(
            company=self.co, projet=self.projet, code_wbs='1',
            libelle='Libellé réel saisi à la main',
            charge_estimee=Decimal('12'),
            statut=Tache.Statut.EN_COURS,
        )

    def test_reimport_meme_code_wbs_ne_modifie_pas_la_tache_existante(self):
        """Une ligne réimportée sur un ``code_wbs`` déjà utilisé laisse la
        tâche existante STRICTEMENT intacte (aucun champ modifié)."""
        libelle_avant = self.tache_existante.libelle
        charge_avant = self.tache_existante.charge_estimee
        statut_avant = self.tache_existante.statut
        pk_avant = self.tache_existante.pk

        lignes = [{
            'code_wbs': '1',
            'libelle': 'Libellé PÉRIMÉ du fichier réimporté',
            'charge_estimee': '999',
            'statut': Tache.Statut.TERMINE,
        }]
        resultat = importer_taches(self.projet, lignes, confirm=True)
        self.assertEqual(resultat['erreurs'], [])

        self.tache_existante.refresh_from_db()
        self.assertEqual(self.tache_existante.pk, pk_avant)
        self.assertEqual(self.tache_existante.libelle, libelle_avant)
        self.assertEqual(self.tache_existante.charge_estimee, charge_avant)
        self.assertEqual(self.tache_existante.statut, statut_avant)

    def test_reimport_meme_code_wbs_cree_un_doublon_plutot_qu_un_ecrasement(self):
        """La ligne réimportée produit une NOUVELLE tâche (pk différent), pas
        une mise à jour de la tâche existante — le risque réel est la
        duplication, jamais l'écrasement."""
        lignes = [{
            'code_wbs': '1',
            'libelle': 'Libellé du fichier réimporté',
        }]
        resultat = importer_taches(self.projet, lignes, confirm=True)
        self.assertEqual(resultat['erreurs'], [])
        self.assertEqual(resultat['nb_creees'], 1)

        taches = list(Tache.objects.filter(projet=self.projet, code_wbs='1'))
        self.assertEqual(len(taches), 2)
        pks = {t.pk for t in taches}
        self.assertIn(self.tache_existante.pk, pks)
        libelles = {t.libelle for t in taches}
        self.assertEqual(
            libelles,
            {'Libellé réel saisi à la main', 'Libellé du fichier réimporté'})

    def test_cellule_vide_ne_vide_jamais_un_champ_de_la_tache_existante(self):
        """Une ligne réimportée avec des champs vides ne peut, de toute
        façon, jamais atteindre la tâche existante (création seule) — la
        tâche existante garde sa charge/son statut d'origine."""
        lignes = [{'code_wbs': '1', 'libelle': 'Nouvelle ligne', 'statut': ''}]
        importer_taches(self.projet, lignes, confirm=True)

        self.tache_existante.refresh_from_db()
        self.assertEqual(self.tache_existante.charge_estimee, Decimal('12'))
        self.assertEqual(self.tache_existante.statut, Tache.Statut.EN_COURS)

    def test_import_ne_traverse_jamais_les_societes(self):
        """Un import sur le projet de ``self.co`` ne peut ni lire ni modifier
        une tâche d'une AUTRE société, même avec un ``code_wbs`` identique —
        ``importer_taches`` ne fait aucun rapprochement, donc aucune requête
        ne croise jamais la frontière société."""
        projet_autre = Projet.objects.create(
            company=self.autre_co, code='P-ECR-AUTRE', nom='Projet autre société')
        tache_autre = Tache.objects.create(
            company=self.autre_co, projet=projet_autre, code_wbs='1',
            libelle='Tâche autre société', charge_estimee=Decimal('7'))

        lignes = [{'code_wbs': '1', 'libelle': 'Import société A'}]
        importer_taches(self.projet, lignes, confirm=True)

        tache_autre.refresh_from_db()
        self.assertEqual(tache_autre.libelle, 'Tâche autre société')
        self.assertEqual(tache_autre.charge_estimee, Decimal('7'))
        self.assertEqual(
            Tache.objects.filter(projet=projet_autre).count(), 1)
