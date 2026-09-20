"""CAL206 — feu vert bureau d'études, réutilisant VT3 (aucun second
mécanisme de validation).

Ce qui est prouvé ici :

* option DÉSACTIVÉE (comportement par défaut) : retenir une variante marche
  toujours, feu vert ou pas ;
* option ACTIVÉE, lead SANS feu vert : retenir refuse, 400, champ
  ``feu_vert`` nommé ;
* option ACTIVÉE, lead AVEC feu vert (``Lead.visite_effectuee``) : retenir
  marche ;
* la visite qui débloque est celle du LEAD du calepinage, à défaut celle du
  lead de son DEVIS lié ;
* sans lead ni devis, la règle ne s'applique JAMAIS, même option activée.

Run :
    python manage.py test apps.calepinage.tests.test_cal206_feu_vert -v2
"""
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.calepinage.services.variantes import retenir_variante
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from authentication.models import Company


def _active(company):
    enregistrer_parametres(
        company, {'presets': {'feu_vert_bureau_etudes': True}})


class RetenirAvecFeuVertTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Feu Vert Co',
                                              slug='feu-vert-co-206')
        self.lead = Lead.objects.create(company=self.company,
                                        nom='Lead sans feu vert')
        self.lead_ok = Lead.objects.create(
            company=self.company, nom='Lead avec feu vert',
            visite_effectuee=True)

    def _variante(self, calepinage, *, retenue=False):
        return CalepinageVariante.objects.create(
            company=self.company, calepinage=calepinage, nom='V1',
            retenue=retenue)

    def test_option_desactivee_retenir_marche_toujours(self):
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk)
        variante = self._variante(calepinage)
        retenir_variante(variante)
        variante.refresh_from_db()
        self.assertTrue(variante.retenue)

    def test_option_activee_sans_feu_vert_refuse_400(self):
        _active(self.company)
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk)
        variante = self._variante(calepinage)
        with self.assertRaises(ValidationError) as ctx:
            retenir_variante(variante)
        self.assertIn('feu_vert', ctx.exception.detail)

    def test_option_activee_avec_feu_vert_marche(self):
        _active(self.company)
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_ok.pk)
        variante = self._variante(calepinage)
        retenir_variante(variante)
        variante.refresh_from_db()
        self.assertTrue(variante.retenue)

    def test_lead_du_devis_lie_fait_foi_sans_lead_direct(self):
        _active(self.company)
        client = Client.objects.create(company=self.company, nom='Client')
        devis = Devis.objects.create(
            company=self.company, client=client, lead=self.lead,
            reference='DEV-CAL206-1')
        calepinage = Calepinage.objects.create(
            company=self.company, client=client, devis=devis)
        variante = self._variante(calepinage)
        with self.assertRaises(ValidationError):
            retenir_variante(variante)

        devis.lead = self.lead_ok
        devis.save(update_fields=['lead'])
        retenir_variante(variante)
        variante.refresh_from_db()
        self.assertTrue(variante.retenue)

    def test_sans_lead_ni_devis_la_regle_ne_s_applique_pas(self):
        _active(self.company)
        client = Client.objects.create(company=self.company, nom='Client 2')
        calepinage = Calepinage.objects.create(
            company=self.company, client=client)
        variante = self._variante(calepinage)
        retenir_variante(variante)
        variante.refresh_from_db()
        self.assertTrue(variante.retenue)
