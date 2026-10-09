"""ADEV54 (C-ADEV-024) — chaque abonné BEST-EFFORT de ``devis_accepted``
tourne dans son PROPRE point de sauvegarde : une panne SQL injectée dans
l'un d'eux est journalisée et n'empêche plus la signature (statut
``accepte`` relu, chantier créé, les autres abonnés ont tourné).

Les abonnés sont découverts sur le signal réel
(``devis_accepted._live_receivers``) et classés par la liste NOMMÉE
``BEST_EFFORT`` ci-dessous ; les abonnés OBLIGATOIRES (création du chantier,
avance d'étape du lead) en sont exclus et nommés dans ``OBLIGATOIRES``.

Test-du-test : retirer le ``transaction.atomic()`` d'un abonné ⇒ son cas
échoue (``InternalError`` : transaction interrompue) à la relecture.
"""
from unittest import mock

from django.db import connection
from django.test import TestCase

from apps.crm import stages
from apps.crm.models import Lead
from apps.ventes.models import Devis
from apps.ventes.tests.test_l_niv_niveau import (
    make_client, make_company, make_devis, make_user,
)
from core.events import devis_accepted

#: abonné best-effort → cible de la panne SQL injectée (doublure de la SEULE
#: fonction fautive appelée par l'abonné).
BEST_EFFORT = {
    'apps.sav.receivers._creer_contrat_maintenance_on_devis_accepted':
        'apps.sav.services.creer_contrat_depuis_devis_accepte',
    'apps.onboarding.receivers._complete_on_devis_accepted':
        'apps.onboarding.receivers.completer_par_evenement',
    'apps.automation.signals._on_devis_accepted':
        'apps.automation.signals.evaluate',
    'apps.crm.receivers._calculer_commission_deal_on_devis_accepted':
        'apps.crm.models.DealEnregistre',
    'apps.crm.receivers._arreter_cadence_on_devis_accepted':
        'apps.crm.services.arreter_cadence',
}

#: abonnés OBLIGATOIRES — une erreur y annule la signature (inchangé).
OBLIGATOIRES = (
    'apps.installations.receivers._creer_chantier_on_devis_accepted',
    'apps.crm.receivers._avancer_stage_on_devis_accepted',
)


def _panne_sql(*args, **kwargs):
    """Une vraie erreur base : la transaction en cours est interrompue."""
    with connection.cursor() as curseur:
        curseur.execute('SELECT * FROM adev54_table_inexistante')


class _PanneDealEnregistre:
    """Doublure du modèle : toute requête lève une erreur base réelle."""

    class Statut:
        APPROUVE = 'approuve'
        A_PAYER = 'a_payer'

    class objects:  # noqa: N801 — imite le gestionnaire du modèle
        filter = staticmethod(_panne_sql)


def _panne_evaluate_devis_accepted(trigger_type, *args, **kwargs):
    """Panne CIBLÉE sur l'abonné ``_on_devis_accepted`` d'automation.

    ``evaluate`` est aussi appelé par les ``post_save`` du même module
    (``_lead_saved`` à l'avance d'étape, ``_installation_saved`` à la
    création du chantier), qui ne sont PAS des abonnés de ``devis_accepted`` :
    les faire tomber testerait un autre chemin. Seul le déclencheur
    ``DEVIS_ACCEPTED`` reçoit la panne ; les autres appels passent au moteur
    réel."""
    from apps.automation.engine import evaluate
    from apps.automation.models import TriggerType
    if trigger_type == TriggerType.DEVIS_ACCEPTED:
        return _panne_sql()
    return evaluate(trigger_type, *args, **kwargs)


#: remplaçants spécifiques (défaut : ``_panne_sql``).
REMPLACANTS = {
    'apps.crm.models.DealEnregistre': _PanneDealEnregistre,
    'apps.automation.signals.evaluate': _panne_evaluate_devis_accepted,
}


def _noms_abonnes():
    vivants = devis_accepted._live_receivers(None)
    if isinstance(vivants, tuple):  # Django 5 : (sync, async)
        vivants = list(vivants[0]) + list(vivants[1])
    noms = set()
    modules = set()
    for recepteur in vivants:
        noms.add(f'{recepteur.__module__}.{recepteur.__qualname__}')
        modules.add(recepteur.__module__)
    return noms, modules


class AbonnesPointDeSauvegardeTests(TestCase):

    def setUp(self):
        self.company = make_company('adev54')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, suffixe):
        # Un lead PAR cas : chaque signature est indépendante.
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Signataire {suffixe}',
            client=self.client_obj, stage=stages.QUOTE_SENT, owner=self.user)
        devis = make_devis(self.company, self.user, self.client_obj,
                           f'DEV-ADEV54-{suffixe}')
        Devis.objects.filter(pk=devis.pk).update(lead=self.lead)
        devis.refresh_from_db()
        return devis

    def _accepter(self, devis):
        from apps.ventes.services import accept_devis
        return accept_devis(devis=devis, user=self.user, nom='Client Signe',
                            option='sans_batterie')

    def test_abonnes_decouverts_et_classes(self):
        noms, modules = _noms_abonnes()
        # automation est enveloppé par ``_safe`` (qualname
        # ``_safe.<locals>.wrapper``) : on le reconnaît par le ``__module__``
        # réel du récepteur (un ``rsplit`` du nom complet donnait
        # ``apps.automation.signals._safe.<locals>`` et ne matchait jamais).
        for nom in BEST_EFFORT:
            module = nom.rsplit('.', 1)[0]
            with self.subTest(abonne=nom):
                self.assertTrue(nom in noms or module in modules, nom)
        for nom in OBLIGATOIRES:
            self.assertIn(nom, noms)

    def test_panne_isolee_par_abonne(self):
        for i, (abonne, cible) in enumerate(sorted(BEST_EFFORT.items())):
            remplacant = REMPLACANTS.get(cible, _panne_sql)
            devis = self._devis(f'{i:04d}')
            with self.subTest(abonne=abonne):
                with mock.patch(cible, remplacant):
                    self._accepter(devis)
                # CLAUSE PERSISTANCE : relecture possible (transaction saine)
                # et devis accepté.
                devis.refresh_from_db()
                self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
                self.lead.refresh_from_db()
                self.assertEqual(self.lead.stage, stages.SIGNED)
                from apps.installations.selectors import (
                    installation_for_devis)
                self.assertIsNotNone(
                    installation_for_devis(devis, company=self.company))

    def test_sans_panne_inchange(self):
        devis = self._devis('9999')
        self._accepter(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
