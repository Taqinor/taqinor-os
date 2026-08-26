"""AUTO-PIPELINE — le webhook du site met en file un devis, sans jamais le payer.

Ordre fondateur du 26/08/2026 : « une fois que le lead arrive dans notre ERP ça
crée automatiquement le devis automatique ».

Ce module épingle la moitié CRM du câblage — celle qui touche une surface
PUBLIQUE, donc celle où une erreur coûte le plus cher :

* un lead RÉELLEMENT nouveau met UNE tâche en file, jamais deux ;
* un webhook re-livré (dédup DUR) et une complétion dans la fenêtre anti-rejeu
  de 60 s n'en mettent AUCUNE de plus — « un lead, un devis » se joue déjà ici,
  avant même la garde d'idempotence du service ;
* rien de tout cela ne s'exécute DANS la requête : le webhook met en file et
  rend la main (le service de mise en file est appelé, jamais la composition) ;
* un échec de mise en file ne remet jamais le lead en cause.

Run:
    python manage.py test apps.crm.tests_auto_devis_tunnel -v 2
"""
import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from .models import Lead

SECRET = 'test-secret-auto-devis'

CONTOUR = [[33.5731, -7.5898], [33.5731, -7.5896],
           [33.5733, -7.5896], [33.5733, -7.5898]]

CIBLE = 'apps.ventes.services.planifier_devis_automatique_pour_lead'


def payload(**extra):
    """Charge utile du tunnel, avec assez de donnée RÉELLE pour être chiffrée."""
    base = {
        'fullName': 'Amina Benali',
        'phoneE164': '+212661850411',
        'city': 'Casablanca',
        'roofType': 'villa',
        'consent': True,
        'factureHiver': 1800,
        'roofOutline': CONTOUR,
        'qualified': True,
        'page': '/',
    }
    base.update(extra)
    return base


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class WebhookMetEnFileLeDevisAutoTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Auto', slug='taqinor-auto')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_un_lead_nouveau_met_une_tache_en_file(self):
        with patch(CIBLE) as planifier:
            res = self.post(payload())
        self.assertEqual(res.status_code, 201)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.roof_outline, CONTOUR)
        planifier.assert_called_once_with(lead.pk, self.company.pk)

    def test_un_webhook_relivre_ne_met_rien_de_plus_en_file(self):
        """Dédup DUR (`dedupe_event`) : le second envoi ne crée aucun lead,
        donc aucune seconde tâche — un devis, jamais deux."""
        corps = payload(idempotencyKey='cle-rejeu-1')
        with patch(CIBLE) as planifier:
            premier = self.post(corps)
            second = self.post(corps)
        self.assertEqual(premier.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(planifier.call_count, 1)

    def test_une_completion_dans_la_fenetre_anti_rejeu_ne_replanifie_pas(self):
        """Même téléphone, payload différent, < 60 s : le webhook COMPLÈTE la
        fiche existante (`created=False`) — pas de second devis."""
        with patch(CIBLE) as planifier:
            premier = self.post(payload(idempotencyKey='a'))
            second = self.post(payload(idempotencyKey='b', city='Rabat'))
        self.assertEqual(premier.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(planifier.call_count, 1)

    def test_un_ping_dengagement_ne_met_jamais_rien_en_file(self):
        """QW7 — « le client a ouvert sa proposition » n'est pas un lead."""
        with patch(CIBLE) as planifier:
            res = self.post({'event_type': 'proposal_opened',
                             'phoneE164': '+212661850411'})
        self.assertEqual(res.status_code, 200)
        planifier.assert_not_called()

    def test_la_composition_ne_tourne_jamais_dans_la_requete(self):
        """Le webhook est une surface publique : il met en file et rend la
        main. La création réelle (secondes de composition + étude horaire) ne
        doit JAMAIS être appelée depuis la vue."""
        with patch(CIBLE), \
                patch('apps.ventes.services.'
                      'creer_devis_automatique_depuis_lead') as creation:
            self.post(payload())
        creation.assert_not_called()

    def test_un_echec_de_mise_en_file_ne_casse_pas_le_webhook(self):
        with patch(CIBLE, side_effect=RuntimeError('boom')):
            res = self.post(payload())
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Lead.objects.count(), 1)
