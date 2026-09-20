"""CAL30 — la reprise des ``roof_layout`` d'affaire vers le module Calepinage.

Ce que ce module VERROUILLE :

  1. **Une affaire qui porte un layout ressort avec un calepinage de SA
     société**, rattaché par ``appel_offre_id``, et l'affaire pointe son
     identifiant.
  2. **Zéro affaire sans layout n'en crée un** — ``NULL``, ``{}`` et ``[]``
     veulent tous dire « aucune session 3D ».
  3. **Le rejeu ne duplique rien** : la reprise est idempotente.
  4. **La marche arrière ne détruit rien** : les calepinages créés restent
     (orphelins ASSUMÉS — les détruire effacerait des versions et variantes
     créées après la bascule).
  5. **Une affaire sans lead n'est PAS migrée** : la base refuse un calepinage
     sans lead ni client (contrainte ``calepinage_lead_ou_client``, CAL7) et
     ``AppelOffre`` ne porte aucun client. Son ``roof_layout`` reste intact.
  6. **``roof_layout`` est CONSERVÉ** par cette tâche : rien n'est effacé.

Les deux fonctions de reprise sont appelées DIRECTEMENT avec la signature que
Django leur passe (``apps``, ``schema_editor``) : cela teste la LOGIQUE de
reprise sans rejouer les ~850 migrations du projet dans chaque test. Le modèle
``Calepinage`` est lu par le REGISTRE (``apps.get_model``), jamais importé —
le même interdit que la migration elle-même respecte.

Run :
    python manage.py test apps.ao.tests.test_migration_calepinage -v2
"""
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps as registre
from django.db import connection
from django.test import TestCase

from apps.ao.models import AppelOffre
from authentication.models import Company

#: Le nom du module commence par un chiffre : seul ``import_module`` sait le
#: charger (``import apps.ao.migrations.0027…`` est une erreur de syntaxe).
MIGRATION = import_module('apps.ao.migrations.0027_cal30_calepinage_id')

LAYOUT = {'version': 2, 'roofs': [{'id': 'A', 'vertices': [[-7.59, 33.57]]}]}


def _calepinages():
    return registre.get_model('calepinage', 'Calepinage').objects


def _reprendre():
    """Rejoue la reprise comme Django le ferait, sur le registre réel."""
    MIGRATION.reprendre_les_layouts(
        registre, SimpleNamespace(connection=connection))


def _revenir():
    """Rejoue la marche arrière de la reprise (la colonne, elle, est effacée
    par l'inverse d'``AddField`` — hors de portée de ce test)."""
    MIGRATION.laisser_les_calepinages(
        registre, SimpleNamespace(connection=connection))


class BaseCal30(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CAL30 Co', slug='cal30-co')
        self.autre = Company.objects.create(nom='CAL30 Bis', slug='cal30-bis')

    def _affaire(self, reference, *, layout=None, lead_id=77, company=None):
        return AppelOffre.objects.create(
            company=company or self.company, reference=reference,
            objet='Reprise CAL30', lead_id=lead_id, roof_layout=layout)


class ChaqueAffaireAvecLayoutEstReprise(BaseCal30):
    def test_un_calepinage_de_sa_societe_est_cree_et_pointe(self):
        affaire = self._affaire('AO-CAL30-1', layout=LAYOUT)

        _reprendre()

        affaire.refresh_from_db()
        self.assertIsNotNone(affaire.calepinage_id)
        calepinage = _calepinages().get(pk=affaire.calepinage_id)
        self.assertEqual(calepinage.company_id, self.company.pk)
        self.assertEqual(calepinage.appel_offre_id, affaire.pk)
        self.assertEqual(calepinage.lead_id, 77)
        self.assertEqual(calepinage.roof_layout, LAYOUT)
        self.assertEqual(calepinage.titre, 'Calepinage AO-CAL30-1')

    def test_chaque_societe_garde_le_sien(self):
        """Deux affaires de deux sociétés : deux calepinages, jamais croisés."""
        ici = self._affaire('AO-CAL30-A', layout=LAYOUT)
        ailleurs = self._affaire('AO-CAL30-B', layout=LAYOUT,
                                 company=self.autre)

        _reprendre()

        ici.refresh_from_db()
        ailleurs.refresh_from_db()
        self.assertNotEqual(ici.calepinage_id, ailleurs.calepinage_id)
        self.assertEqual(
            _calepinages().get(pk=ici.calepinage_id).company_id,
            self.company.pk)
        self.assertEqual(
            _calepinages().get(pk=ailleurs.calepinage_id).company_id,
            self.autre.pk)

    def test_le_roof_layout_de_l_affaire_est_conserve(self):
        """CAL30 ne supprime RIEN : la colonne reste, et son contenu aussi."""
        affaire = self._affaire('AO-CAL30-C', layout=LAYOUT)

        _reprendre()

        affaire.refresh_from_db()
        self.assertEqual(affaire.roof_layout, LAYOUT)


class AucuneAffaireSansLayoutNEnCree(BaseCal30):
    def test_null_vide_et_liste_vide_ne_produisent_rien(self):
        sans = self._affaire('AO-CAL30-N', layout=None)
        vide = self._affaire('AO-CAL30-V', layout={})
        liste = self._affaire('AO-CAL30-L', layout=[])

        _reprendre()

        self.assertEqual(_calepinages().count(), 0)
        for affaire in (sans, vide, liste):
            affaire.refresh_from_db()
            self.assertIsNone(affaire.calepinage_id)


class UneAffaireSansLeadNEstPasMigree(BaseCal30):
    """La base refuse un calepinage sans lead ni client (CAL7) — et
    ``AppelOffre`` ne porte aucun client : lui en inventer un serait faux."""

    def test_elle_est_sautee_sans_erreur_et_garde_son_layout(self):
        affaire = self._affaire('AO-CAL30-S', layout=LAYOUT, lead_id=None)

        _reprendre()  # ne doit PAS lever

        affaire.refresh_from_db()
        self.assertIsNone(affaire.calepinage_id)
        self.assertEqual(affaire.roof_layout, LAYOUT)
        self.assertEqual(_calepinages().count(), 0)

    def test_elle_n_empeche_pas_ses_voisines_d_etre_migrees(self):
        sans_lead = self._affaire('AO-CAL30-S2', layout=LAYOUT, lead_id=None)
        avec_lead = self._affaire('AO-CAL30-S3', layout=LAYOUT)

        _reprendre()

        sans_lead.refresh_from_db()
        avec_lead.refresh_from_db()
        self.assertIsNone(sans_lead.calepinage_id)
        self.assertIsNotNone(avec_lead.calepinage_id)


class LeRejeuNeDupliqueRien(BaseCal30):
    def test_deux_passes_donnent_un_seul_calepinage(self):
        affaire = self._affaire('AO-CAL30-I', layout=LAYOUT)

        _reprendre()
        premier = AppelOffre.objects.get(pk=affaire.pk).calepinage_id
        _reprendre()

        self.assertEqual(_calepinages().count(), 1)
        self.assertEqual(
            AppelOffre.objects.get(pk=affaire.pk).calepinage_id, premier)

    def test_un_calepinage_deja_rattache_est_reutilise_jamais_double(self):
        """Lien posé par un autre chemin (CAL32) : la reprise s'y raccroche."""
        affaire = self._affaire('AO-CAL30-R', layout=LAYOUT)
        deja = _calepinages().create(
            company_id=self.company.pk, lead_id=77,
            appel_offre_id=affaire.pk, titre='Posé avant la migration')

        _reprendre()

        affaire.refresh_from_db()
        self.assertEqual(affaire.calepinage_id, deja.pk)
        self.assertEqual(_calepinages().count(), 1)


class LaMarcheArriereNeDetruitRien(BaseCal30):
    def test_les_calepinages_crees_survivent_au_retour_en_arriere(self):
        affaire = self._affaire('AO-CAL30-Z', layout=LAYOUT)
        _reprendre()
        affaire.refresh_from_db()
        cree = affaire.calepinage_id

        _revenir()

        self.assertEqual(_calepinages().filter(pk=cree).count(), 1)
        self.assertEqual(
            _calepinages().get(pk=cree).appel_offre_id, affaire.pk)

    def test_l_aller_retour_aller_ne_perd_ni_ne_duplique(self):
        """``migrate`` → ``migrate <précédente>`` → ``migrate`` : un seul
        document, et l'affaire le repointe."""
        affaire = self._affaire('AO-CAL30-Y', layout=LAYOUT)

        _reprendre()
        _revenir()
        # La marche arrière efface la COLONNE : on le simule ici, puisque le
        # test appelle les fonctions de données, pas le schéma.
        AppelOffre.objects.filter(pk=affaire.pk).update(calepinage_id=None)
        _reprendre()

        affaire.refresh_from_db()
        self.assertEqual(_calepinages().count(), 1)
        self.assertEqual(affaire.calepinage_id, _calepinages().first().pk)


class LaMigrationDeclareSesDependances(TestCase):
    """Sans la dépendance au module, ``get_model('calepinage', …)`` tomberait
    sur une table inexistante au déploiement."""

    def test_elle_depend_du_module_calepinage_et_de_la_precedente_ao(self):
        dependances = set(MIGRATION.Migration.dependencies)
        self.assertIn(('calepinage', '0001_initial'), dependances)
        self.assertIn(('ao', '0026_piecesoumission_fichier_filename_and_more'),
                      dependances)

    def test_la_reprise_est_reversible(self):
        """Une ``RunPython`` sans inverse rendrait la migration irréversible."""
        runpython = [op for op in MIGRATION.Migration.operations
                     if op.__class__.__name__ == 'RunPython']
        self.assertEqual(len(runpython), 1)
        self.assertTrue(runpython[0].reversible)
