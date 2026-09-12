"""NTAPI12 — abonnements webhook par filtre fin (évènement + condition).

Critère d'acceptation, dans les deux sens :
  * un webhook abonné à `facture.paid` avec un filtre « montant ≥ 10000 » ne
    reçoit PAS une facture de 500 ;
  * sans filtre, le comportement est INCHANGÉ (tout part).

Couvre aussi le mode d'échec qui compte : une condition malformée ne doit
JAMAIS faire taire un webhook (une faute de frappe dans un écran de réglages
deviendrait sinon une panne silencieuse d'intégration).
"""
from unittest.mock import patch

from django.test import TestCase

from authentication.models import Company

from . import delivery
from .constants import EVENT_FACTURE_PAID, EVENT_LEAD_CREATED
from .models import Webhook
from .webhook_filters import (
    erreurs_de_filtres, lookup_vers_feuille, payload_passe, webhook_accepte,
)


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


class Ntapi12FiltreTraductionTests(TestCase):
    """La traduction « lookup Django » → feuille `core.rules` (pur, sans DB)."""

    def test_suffixe_reconnu(self):
        self.assertEqual(
            lookup_vers_feuille('montant_ttc__gte', 10000),
            {'field': 'montant_ttc', 'operator': 'gte', 'value': 10000})

    def test_sans_suffixe_egalite(self):
        self.assertEqual(
            lookup_vers_feuille('canal', 'site_web'),
            {'field': 'canal', 'operator': 'eq', 'value': 'site_web'})

    def test_suffixe_inconnu_nest_jamais_devine(self):
        # `__zzz` n'est pas un opérateur : la clé ENTIÈRE devient un nom de
        # champ (condition simplement fausse), jamais une comparaison inventée.
        feuille = lookup_vers_feuille('montant__zzz', 1)
        self.assertEqual(feuille['field'], 'montant__zzz')
        self.assertEqual(feuille['operator'], 'eq')

    def test_plusieurs_lookups_sont_un_ET(self):
        self.assertTrue(payload_passe(
            {'statut': 'payee', 'montant_ttc__gte': 100},
            {'statut': 'payee', 'montant_ttc': 500}))
        self.assertFalse(payload_passe(
            {'statut': 'payee', 'montant_ttc__gte': 1000},
            {'statut': 'payee', 'montant_ttc': 500}))

    def test_arbre_core_rules_accepte_tel_quel(self):
        arbre = {'op': 'or', 'conditions': [
            {'field': 'montant_ttc', 'operator': 'gte', 'value': 10000},
            {'field': 'statut', 'operator': 'eq', 'value': 'urgente'},
        ]}
        self.assertTrue(payload_passe(arbre, {'montant_ttc': 1, 'statut': 'urgente'}))
        self.assertFalse(payload_passe(arbre, {'montant_ttc': 1, 'statut': 'normale'}))

    def test_champ_absent_du_payload_vaut_faux(self):
        self.assertFalse(
            payload_passe({'montant_ttc__gte': 10}, {'reference': 'F-1'}))

    def test_filtre_malforme_ne_fait_jamais_taire(self):
        for casse in ('pas un dict', 42, [1, 2, 3]):
            self.assertTrue(payload_passe(casse, {'montant_ttc': 1}))

    def test_absence_de_filtre_laisse_tout_passer(self):
        self.assertTrue(payload_passe(None, {'montant_ttc': 1}))
        self.assertTrue(payload_passe({}, {'montant_ttc': 1}))


class Ntapi12LivraisonFiltreeTests(TestCase):
    """Le filtre s'applique VRAIMENT à l'émission automatique."""

    def setUp(self):
        self.co = _company('ntapi12', 'NTAPI12')

    def _webhook(self, filtres=None, events=None):
        return Webhook.objects.create(
            company=self.co, label='client',
            target_url='https://client.test/hook',
            secret=Webhook.generate_secret(),
            events=events or [EVENT_FACTURE_PAID],
            filtres=filtres or {})

    def _dispatch(self, payload, event=EVENT_FACTURE_PAID):
        with patch('apps.publicapi.tasks.deliver_webhook.delay') as envoi:
            delivery.dispatch_event(self.co.id, event, payload)
        return envoi

    # ── Le cœur du critère ────────────────────────────────────────────────
    def test_facture_de_500_bloquee_par_filtre_10000(self):
        self._webhook({EVENT_FACTURE_PAID: {'montant_ttc__gte': 10000}})
        envoi = self._dispatch({'montant_ttc': 500, 'reference': 'F-1'})
        envoi.assert_not_called()

    def test_facture_de_20000_passe_le_filtre_10000(self):
        self._webhook({EVENT_FACTURE_PAID: {'montant_ttc__gte': 10000}})
        envoi = self._dispatch({'montant_ttc': 20000, 'reference': 'F-2'})
        self.assertEqual(envoi.call_count, 1)

    def test_sans_filtre_le_comportement_est_inchange(self):
        self._webhook()
        envoi = self._dispatch({'montant_ttc': 1, 'reference': 'F-3'})
        self.assertEqual(envoi.call_count, 1)

    def test_filtre_sur_un_autre_evenement_ne_bloque_pas_celui_ci(self):
        # Filtre posé sur `lead.created` : `facture.paid` n'est pas filtré.
        wh = self._webhook({EVENT_LEAD_CREATED: {'canal': 'salon'}})
        wh.events = [EVENT_FACTURE_PAID, EVENT_LEAD_CREATED]
        wh.save(update_fields=['events'])
        envoi = self._dispatch({'montant_ttc': 1, 'reference': 'F-4'})
        self.assertEqual(envoi.call_count, 1)

    def test_deux_webhooks_filtres_independamment(self):
        self._webhook({EVENT_FACTURE_PAID: {'montant_ttc__gte': 10000}})
        self._webhook()  # sans filtre
        envoi = self._dispatch({'montant_ttc': 500, 'reference': 'F-5'})
        self.assertEqual(envoi.call_count, 1)  # seul le non-filtré reçoit

    def test_filtre_casse_livre_quand_meme(self):
        self._webhook({EVENT_FACTURE_PAID: 'pas une condition'})
        envoi = self._dispatch({'montant_ttc': 1, 'reference': 'F-6'})
        self.assertEqual(envoi.call_count, 1)

    def test_webhook_accepte_est_independant_de_labonnement(self):
        wh = self._webhook({EVENT_FACTURE_PAID: {'montant_ttc__gte': 10000}})
        self.assertFalse(
            webhook_accepte(wh, EVENT_FACTURE_PAID, {'montant_ttc': 5}))
        self.assertTrue(
            webhook_accepte(wh, EVENT_FACTURE_PAID, {'montant_ttc': 50000}))


class Ntapi12ValidationTests(TestCase):
    """La validation à l'enregistrement (écran Paramètres / API)."""

    def test_filtres_vides_valides(self):
        self.assertEqual(erreurs_de_filtres({}), [])
        self.assertEqual(erreurs_de_filtres(None), [])

    def test_evenement_inconnu_refuse(self):
        erreurs = erreurs_de_filtres({'facture.inexistante': {'x': 1}})
        self.assertTrue(erreurs)
        self.assertIn('Évènement inconnu', erreurs[0])

    def test_condition_non_objet_refusee(self):
        erreurs = erreurs_de_filtres({EVENT_FACTURE_PAID: 'zut'})
        self.assertTrue(erreurs)

    def test_condition_valide_acceptee(self):
        self.assertEqual(
            erreurs_de_filtres(
                {EVENT_FACTURE_PAID: {'montant_ttc__gte': 10000}}),
            [])

    def test_filtres_non_dict_refuses(self):
        self.assertTrue(erreurs_de_filtres(['pas', 'un', 'dict']))
