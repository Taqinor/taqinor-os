"""AUD823 — `DEVIS_ACCEPTED` écoute le BUS métier, plus le `post_save` brut.

Défaut corrigé : `signals._devis_saved` était branché sur `post_save` du Devis
et comparait ancienne/nouvelle valeur — il s'exécutait donc pour TOUT `.save()`
laissant `statut='accepte'`, qu'il vienne du chemin gardé (`accept_devis()`) ou
d'un PATCH brut, d'un import ou d'une correction en base. Une règle « Lien
WhatsApp à l'acceptation d'un devis » envoyait ainsi une confirmation au client
alors qu'AUCUN contrôle métier n'avait eu lieu — et le défaut de conception se
rouvrait à chaque future écriture non gardée.

Test ROUGE d'abord : sur l'arbre d'avant AUD823, un `.save()` direct posant
`statut='accepte'` déclenchait `evaluate(DEVIS_ACCEPTED, …)` et journalisait un
`AutomationRun`. Après : seul `core.events.devis_accepted` — émis par l'UNIQUE
chemin gardé (`apps.ventes.domain.cycle_vie`) — déclenche.
"""
from django.test import TestCase

from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType,
)
from apps.crm.models import Client
from apps.ventes.models import Devis
from authentication.models import Company
from core.events import devis_accepted


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class DevisAcceptedSurLeBusTests(TestCase):
    def setUp(self):
        self.co = make_company('aud823-co', 'AUD823')
        self.regle = AutomationRule.objects.create(
            company=self.co, nom='Confirmation acceptation',
            trigger_type=TriggerType.DEVIS_ACCEPTED, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'Merci !'}, enabled=True)
        self.client_crm = Client.objects.create(company=self.co, nom='Cli823')

    def _devis(self, reference='DEV-823', statut='brouillon'):
        return Devis.objects.create(
            company=self.co, reference=reference, statut=statut,
            client=self.client_crm)

    def _runs(self):
        return AutomationRun.objects.filter(
            company=self.co, rule=self.regle)

    def test_un_save_brut_ne_declenche_plus_lautomatisation(self):
        """Le cœur d'AUD823 : un PATCH non gardé ne « confirme » plus au client."""
        devis = self._devis()
        devis.statut = 'accepte'
        devis.save(update_fields=['statut'])
        self.assertEqual(self._runs().count(), 0)

    def test_une_creation_directe_en_accepte_ne_declenche_pas(self):
        self._devis(reference='DEV-823-B', statut='accepte')
        self.assertEqual(self._runs().count(), 0)

    def test_levenement_metier_declenche_lautomatisation(self):
        devis = self._devis(reference='DEV-823-C', statut='accepte')
        devis_accepted.send(
            sender=Devis, devis=devis, user=None, ancien_statut='envoye')
        self.assertEqual(self._runs().count(), 1)

    def test_le_declencheur_est_abonne_au_bus_m6(self):
        # `Signal.receivers` : chaque entrée commence par sa lookup_key, dont
        # le premier élément est le `dispatch_uid` quand il est fourni (même
        # patron que test_aud127_avoir_annule/test_aud102_bascule_payee —
        # l'arité de ces entrées est un détail interne qui a changé en 5.1).
        uids = [entree[0][0] for entree in devis_accepted.receivers]
        self.assertIn(
            'automation_on_devis_accepted', uids,
            "L'abonnement AUD823 au bus core.events n'est pas câblé "
            f'(récepteurs : {uids}).')

    def test_un_devis_sans_societe_est_ignore(self):
        """`devis_accepted` est un signal PARTAGÉ : un émetteur d'un autre
        domaine peut envoyer un objet minimal — le récepteur l'ignore proprement
        au lieu de lever (appel direct : on ne fait pas transiter un objet
        factice par le bus, où d'autres apps sont abonnées)."""
        from apps.automation import signals

        class _DevisMinimal:
            company = None
            statut = 'accepte'
            pk = 0

        signals._on_devis_accepted(
            sender=Devis, devis=_DevisMinimal(), user=None,
            ancien_statut='envoye')
        self.assertEqual(self._runs().count(), 0)

    def test_le_run_pointe_le_devis_accepte(self):
        devis = self._devis(reference='DEV-823-D', statut='accepte')
        devis_accepted.send(
            sender=Devis, devis=devis, user=None, ancien_statut='envoye')
        run = self._runs().get()
        self.assertEqual(run.target_id, devis.pk)
        self.assertEqual(run.target_model, 'ventes.devis')
