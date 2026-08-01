"""AOF29 — empreinte d'entrée + péremption AUTOMATIQUE en cascade.

Le défaut réel évité : la note de synthèse d'un dossier annonçait encore 264
modules quand la donnée en disait 314 — **la pièce la plus lue était la plus
fausse**.

Trois promesses testées :
  1. modifier un obstacle PÉRIME la variante retenue de sa toiture ;
  2. recalculer avec des entrées IDENTIQUES ne change rien (idempotence) ;
  3. la péremption est GRANULAIRE — une planche du bâtiment C ne périme PAS
     parce que le bâtiment A a changé. Sans cette borne, le bandeau rouge
     s'afficherait partout et l'utilisateur apprendrait à l'ignorer.

Run :
    python manage.py test apps.ao.tests.test_peremption -v2
"""
from decimal import Decimal

from django.test import TestCase

from apps.ao.hashing import empreinte_entree, entree_canonique
from apps.ao.models import (
    AppelOffre, BatimentAO, ObstacleAO, ToitureAO, VarianteCalepinage,
)
from apps.ao.receivers import perimer_variantes_divergentes
from authentication.models import Company

CARRE = [[0, 0], [20, 0], [20, 10], [0, 10]]


class BasePeremption(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF29 Co', slug='aof29-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-29-1', objet='Péremption')
        self.bat_a = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A')
        self.bat_c = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture_a = ToitureAO.objects.create(
            company=self.company, batiment=self.bat_a, code_document='05A',
            contour_local_m=CARRE)
        self.toiture_c = ToitureAO.objects.create(
            company=self.company, batiment=self.bat_c, code_document='05H',
            contour_local_m=CARRE)

    def _variante(self, toiture, **kwargs):
        variante = VarianteCalepinage(
            company=self.company, toiture=toiture, appel_offre=self.ao,
            nom=f'Retenue {toiture.code_document}',
            statut=VarianteCalepinage.Statut.CALCULEE, **kwargs)
        variante.entree_hash = empreinte_entree(toiture)
        variante.save()
        return variante


class TestEmpreinteDeterministe(BasePeremption):
    def test_deux_calculs_identiques_donnent_la_meme_empreinte(self):
        self.assertEqual(empreinte_entree(self.toiture_a),
                         empreinte_entree(self.toiture_a))

    def test_deux_toitures_identiques_ont_la_meme_empreinte(self):
        self.assertEqual(empreinte_entree(self.toiture_a),
                         empreinte_entree(self.toiture_c))

    def test_l_enveloppe_change_l_empreinte(self):
        avant = empreinte_entree(self.toiture_a)
        self.toiture_a.contour_local_m = [[0, 0], [30, 0], [30, 10], [0, 10]]
        self.assertNotEqual(empreinte_entree(self.toiture_a), avant)

    def test_un_obstacle_actif_change_l_empreinte(self):
        avant = empreinte_entree(self.toiture_a)
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture_a, repere='D',
            nature=ObstacleAO.Nature.SOUCHE)
        self.assertNotEqual(empreinte_entree(self.toiture_a), avant)

    def test_un_obstacle_ecarte_ne_compte_pas(self):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture_a, repere='D',
            nature=ObstacleAO.Nature.SOUCHE)
        avec = empreinte_entree(self.toiture_a)
        obstacle.actif = False
        obstacle.save(update_fields=['actif'])
        self.assertNotEqual(empreinte_entree(self.toiture_a), avec)

    def test_les_params_et_les_kits_entrent_dans_l_empreinte(self):
        base = empreinte_entree(self.toiture_a)
        self.assertNotEqual(
            empreinte_entree(self.toiture_a, params={'allee_min_m': 0.6}),
            base)
        self.assertNotEqual(
            empreinte_entree(self.toiture_a, kits=['AO-TABLE-PORTRAIT']),
            base)
        self.assertNotEqual(
            empreinte_entree(self.toiture_a, version_moteur='2.0'), base)

    def test_l_ordre_des_kits_n_a_pas_d_importance(self):
        self.assertEqual(
            empreinte_entree(self.toiture_a, kits=['B', 'A']),
            empreinte_entree(self.toiture_a, kits=['A', 'B']))

    def test_l_entree_canonique_est_debogable(self):
        canonique = entree_canonique(self.toiture_a)
        self.assertIn('enveloppe', canonique)
        self.assertIn('obstacles', canonique)
        self.assertIn('chaines', canonique)
        self.assertEqual(canonique['enveloppe']['contour_local_m'][1],
                         [20.0, 0.0])


class TestPeremptionEnCascade(BasePeremption):
    def test_modifier_un_obstacle_perime_la_variante(self):
        variante = self._variante(self.toiture_a, est_retenue=True)
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture_a, repere='D',
            nature=ObstacleAO.Nature.SOUCHE)
        variante.refresh_from_db()
        self.assertEqual(variante.statut, VarianteCalepinage.Statut.PERIME)

    def test_entrees_identiques_ne_periment_rien(self):
        variante = self._variante(self.toiture_a)
        # Une écriture qui ne change RIEN de l'entrée (le libellé du bâtiment).
        self.toiture_a.designation = 'Aile est'
        self.toiture_a.save(update_fields=['designation'])
        variante.refresh_from_db()
        self.assertEqual(variante.statut, VarianteCalepinage.Statut.CALCULEE)

    def test_peremption_granulaire_entre_batiments(self):
        """Le bâtiment C ne périme PAS parce que le bâtiment A a changé."""
        variante_a = self._variante(self.toiture_a)
        variante_c = self._variante(self.toiture_c)
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture_a, repere='D',
            nature=ObstacleAO.Nature.SOUCHE)
        variante_a.refresh_from_db()
        variante_c.refresh_from_db()
        self.assertEqual(variante_a.statut, VarianteCalepinage.Statut.PERIME)
        self.assertEqual(variante_c.statut, VarianteCalepinage.Statut.CALCULEE)

    def test_une_variante_sans_empreinte_n_est_pas_perimee(self):
        variante = VarianteCalepinage.objects.create(
            company=self.company, toiture=self.toiture_a, appel_offre=self.ao,
            nom='Sans empreinte',
            statut=VarianteCalepinage.Statut.CALCULEE)
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture_a, repere='D',
            nature=ObstacleAO.Nature.SOUCHE)
        variante.refresh_from_db()
        self.assertEqual(variante.statut, VarianteCalepinage.Statut.CALCULEE)

    def test_supprimer_un_obstacle_perime_aussi(self):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture_a, repere='D',
            nature=ObstacleAO.Nature.SOUCHE)
        variante = self._variante(self.toiture_a)
        obstacle.delete()
        variante.refresh_from_db()
        self.assertEqual(variante.statut, VarianteCalepinage.Statut.PERIME)

    def test_modifier_une_cote_perime(self):
        from apps.ao.models import ChaineCotes

        chaine = ChaineCotes.objects.create(
            company=self.company, toiture=self.toiture_a, libelle='Sud',
            segments=[{'libelle': 'A→B', 'valeur_m': 10.0,
                       'statut': 'MESURE'}],
            mesure_globale_m=Decimal('10.000'))
        variante = self._variante(self.toiture_a)
        chaine.segments = [{'libelle': 'A→B', 'valeur_m': 12.0,
                            'statut': 'MESURE'}]
        chaine.save(update_fields=['segments'])
        variante.refresh_from_db()
        self.assertEqual(variante.statut, VarianteCalepinage.Statut.PERIME)

    def test_une_variante_deja_perimee_reste_perimee(self):
        variante = self._variante(
            self.toiture_a, statut=VarianteCalepinage.Statut.PERIME)
        self.assertEqual(perimer_variantes_divergentes(self.toiture_a), 0)
        variante.refresh_from_db()
        self.assertEqual(variante.statut, VarianteCalepinage.Statut.PERIME)

    def test_appel_direct_renvoie_le_compte(self):
        self._variante(self.toiture_a)
        self._variante(self.toiture_c)
        self.toiture_a.contour_local_m = [[0, 0], [40, 0], [40, 10], [0, 10]]
        self.toiture_a.save(update_fields=['contour_local_m'])
        # Le receiver a déjà périmé : un second appel ne recompte pas.
        self.assertEqual(perimer_variantes_divergentes(self.toiture_a), 0)
