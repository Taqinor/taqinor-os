"""CAL215 — webhook « calepinage validé » (`calepinage.valide`).

Retenir une variante déclenche la livraison signée ; l'évènement figure au
catalogue public (donc à la référence FR et au flux d'évènements, chacun sous
le scope de lecture de sa famille).

Le modèle est obtenu par ``apps.get_model`` et l'écriture passe par le SERVICE
de bascule (``apps.calepinage.services.variantes.retenir_variante``, le chemin
d'écriture unique de CAL9/CAL14) : ce module n'importe jamais
``apps.calepinage.models``.
"""
from unittest import mock

from django.apps import apps as django_apps
from django.test import TestCase

from authentication.models import Company

from . import delivery
from .constants import (
    ALL_EVENTS, EVENT_CALEPINAGE_VALIDE, SCOPE_READ_CALEPINAGES,
)
from .models import Webhook

RESULTAT = {
    'kwc': 8.64,
    'total_modules': 12,
    'plans': [{'surface': 'PAN-A', 'modules': 12}],
}


def modele(nom):
    return django_apps.get_model('calepinage', nom)


class CalepinageValideWebhookTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='pa-cal215', defaults={'nom': 'PA CAL215'})
        self.cal = modele('Calepinage').objects.create(
            company=self.co, lead_id=1, titre='Toiture')
        self.variante = modele('CalepinageVariante').objects.create(
            company=self.co, calepinage=self.cal, nom='Variante A',
            layout_hash='a' * 64, resultat=RESULTAT)

    def retenir(self, variante):
        from apps.calepinage.services.variantes import retenir_variante
        return retenir_variante(variante)

    # ── Le geste déclenche la livraison ──────────────────────────────────────
    def test_retenir_une_variante_livre_calepinage_valide(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            self.retenir(self.variante)
        m.assert_called_once()
        args, _kwargs = m.call_args
        self.assertEqual(args[0], self.co.id)
        self.assertEqual(args[1], EVENT_CALEPINAGE_VALIDE)
        charge = args[2]
        self.assertEqual(charge['calepinage_id'], self.cal.id)
        self.assertEqual(charge['variante_id'], self.variante.id)
        self.assertEqual(charge['nom'], 'Variante A')
        self.assertEqual(charge['kwc'], 8.64)
        self.assertEqual(charge['modules'], 12)

    def test_la_charge_utile_ne_porte_ni_geometrie_ni_cout(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            self.retenir(self.variante)
        charge = m.call_args[0][2]
        self.assertEqual(set(charge.keys()), {
            'calepinage_id', 'variante_id', 'nom', 'layout_hash', 'kwc',
            'modules',
        })
        self.assertNotIn('PAN-A', str(charge))

    def test_sans_calcul_kwc_et_modules_valent_null_jamais_zero(self):
        nue = modele('CalepinageVariante').objects.create(
            company=self.co, calepinage=self.cal, nom='Sans calcul')
        with mock.patch.object(delivery, 'dispatch_event') as m:
            self.retenir(nue)
        charge = m.call_args[0][2]
        self.assertIsNone(charge['kwc'])
        self.assertIsNone(charge['modules'])

    # ── Une TRANSITION, pas une copie, pas un doublon ────────────────────────
    def test_dupliquer_un_calepinage_retenu_ne_renotifie_pas(self):
        """Duplication : le choix a été fait sur l'original, pas sur la copie."""
        from apps.calepinage.services.variantes import dupliquer

        self.retenir(self.variante)
        with mock.patch.object(delivery, 'dispatch_event') as m:
            copie = dupliquer(self.cal)
        self.assertNotEqual(copie.pk, self.cal.pk)
        m.assert_not_called()

    def test_resauvegarder_une_variante_deja_retenue_ne_renotifie_pas(self):
        self.retenir(self.variante)
        deja = modele('CalepinageVariante').objects.get(pk=self.variante.pk)
        with mock.patch.object(delivery, 'dispatch_event') as m:
            deja.nom = 'Variante A (renommée)'
            deja.save(update_fields=['nom', 'updated_at'])
        m.assert_not_called()

    # ── La livraison est celle, signée, de tous les autres webhooks ──────────
    def test_un_webhook_abonne_recoit_la_livraison(self):
        webhook = Webhook.objects.create(
            company=self.co, label='client',
            target_url='https://exemple.invalid/hook',
            secret=Webhook.generate_secret(),
            events=[EVENT_CALEPINAGE_VALIDE], enabled=True)
        from . import tasks
        with mock.patch.object(tasks.deliver_webhook, 'delay') as envoi:
            self.retenir(self.variante)
        envoi.assert_called_once()
        args, _kwargs = envoi.call_args
        self.assertEqual(args[0], webhook.id)
        self.assertEqual(args[1], EVENT_CALEPINAGE_VALIDE)

    def test_un_webhook_non_abonne_ne_recoit_rien(self):
        Webhook.objects.create(
            company=self.co, label='autre',
            target_url='https://exemple.invalid/autre',
            secret=Webhook.generate_secret(),
            events=['lead.created'], enabled=True)
        from . import tasks
        with mock.patch.object(tasks.deliver_webhook, 'delay') as envoi:
            self.retenir(self.variante)
        envoi.assert_not_called()

    # ── Catalogue + cohérence de contrat ─────────────────────────────────────
    def test_l_evenement_figure_au_catalogue_et_a_la_reference(self):
        from .docs import public_api_reference

        self.assertIn(EVENT_CALEPINAGE_VALIDE, ALL_EVENTS)
        codes = {e['code'] for e in public_api_reference()['evenements']}
        self.assertIn(EVENT_CALEPINAGE_VALIDE, codes)

    def test_le_flux_exige_le_scope_de_lecture_de_sa_famille(self):
        from .events_feed import SCOPE_PAR_EVENEMENT

        self.assertEqual(SCOPE_PAR_EVENEMENT[EVENT_CALEPINAGE_VALIDE],
                         SCOPE_READ_CALEPINAGES)
