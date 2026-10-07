"""ALEA28 — le récap de feu vert d'une visite REMPLACE le précédent.

Constat C-ALEA-012 (sonde V4 LVIS-12 run 2) : valider, renvoyer, corriger la
mesure puis revalider laissait DEUX récaps dans ``Lead.visite_notes`` (R1
périmé + R2). Le récap vit désormais dans un bloc balisé PAR VISITE, que la
revalidation remplace ; le texte saisi à la main autour reste intact.

Chaîne réelle, aucun mock : ``visites.services.valider_visite`` →
``visite_validee`` → récepteur crm → ``ecrire_retour_lead_visite``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Lead
from apps.roles.models import Role
from apps.visites.models import VisiteTerrain
from authentication.models import Company

User = get_user_model()

PERMS_BUREAU = ['visites_voir', 'visites_creer', 'visites_modifier',
                'visites_valider']


class RecapVisiteCourantTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ALEA28 Solaire',
                                              slug='alea28-a')
        role = Role.objects.create(company=self.company, nom='bureau-alea28',
                                   permissions=list(PERMS_BUREAU))
        self.bureau = User.objects.create_user(
            username='alea28-bureau', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', ville='Settat',
            visite_notes='Accès par la cour')

    def _visite(self, longueur, largeur):
        return VisiteTerrain.objects.create(
            company=self.company, lead=self.lead,
            mesures={'toiture': {'longueur_m': longueur,
                                 'largeur_m': largeur}})

    def _valider(self, visite):
        from apps.visites import services
        services.valider_visite(visite, self.bureau)
        self.lead.refresh_from_db()
        return self.lead.visite_notes

    def _renvoyer_et_corriger(self, visite, longueur, largeur):
        from apps.visites import services
        erreur = services.renvoyer_visite(
            visite, self.bureau,
            mesures=[{'categorie': 'toiture', 'code': 'longueur_m'}],
            motif='Mesure à reprendre')
        self.assertEqual(erreur, '')
        visite.refresh_from_db()
        mesures = dict(visite.mesures)
        mesures['toiture'] = {'longueur_m': longueur, 'largeur_m': largeur}
        visite.mesures = mesures
        visite.statut = VisiteTerrain.Statut.TERMINEE
        visite.save(update_fields=['mesures', 'statut'])

    def test_revalidation_remplace_recap(self):
        visite = self._visite(10, 5)
        notes = self._valider(visite)
        self.assertIn('zone utile 10 × 5 m', notes)

        self._renvoyer_et_corriger(visite, 12, 5)
        notes = self._valider(visite)
        self.assertIn('zone utile 12 × 5 m', notes)
        self.assertNotIn('zone utile 10 × 5 m', notes)
        self.assertEqual(notes.count('Visite technique validée'), 1)

    def test_texte_manuel_preserve(self):
        visite = self._visite(10, 5)
        self._valider(visite)
        self._renvoyer_et_corriger(visite, 12, 5)
        notes = self._valider(visite)
        self.assertIn('Accès par la cour', notes)
        self.assertEqual(notes.count('Accès par la cour'), 1)

    def test_deux_visites_deux_blocs(self):
        premiere = self._visite(10, 5)
        self._valider(premiere)
        seconde = self._visite(20, 6)
        notes = self._valider(seconde)
        self.assertIn('zone utile 10 × 5 m', notes)
        self.assertIn('zone utile 20 × 6 m', notes)
        # Corriger la seconde ne touche pas le bloc de la première.
        self._renvoyer_et_corriger(seconde, 22, 6)
        notes = self._valider(seconde)
        self.assertIn('zone utile 10 × 5 m', notes)
        self.assertIn('zone utile 22 × 6 m', notes)
        self.assertNotIn('zone utile 20 × 6 m', notes)
        self.assertIn('Accès par la cour', notes)

    def test_idempotent(self):
        visite = self._visite(10, 5)
        premier = self._valider(visite)
        second = self._valider(visite)
        self.assertEqual(second, premier)
        self.assertEqual(premier.count('Visite technique validée'), 1)
