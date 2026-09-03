"""AUD312 — `decider_demande_achat` converge avec le chemin normal FG310/NTP2P2.

Défaut d'origine : le chemin normal (`DemandeAchatViewSet.approuver` /
`.refuser`) bloque en 400 si `workflow_approbation_achat_actif(da)` et, au
refus, annule les étapes `en_attente` puis appelle
`liberer_budget_demande_achat`. `decider_demande_achat` — seul point d'entrée
de la boîte d'approbations centralisée (`apps/reporting/approbations.py`) — ne
vérifiait que `statut == SOUMISE` puis basculait directement APPROUVEE/REFUSEE,
sans AUCUNE des deux gardes ; et `demandes_achat_en_attente` n'excluait pas non
plus les demandes sous workflow actif.

REQUALIFICATION (audit R3) : ce n'est PAS une élévation de privilège — le rôle
exigé est identique des deux côtés. Ce qui était perdu : le nombre
d'approbations (N→1), la séparation des tâches, et la cohérence
étapes/budget.

Le volet budget est prouvé par un espion sur `liberer_budget_demande_achat`
(la construction d'un budget départemental réel relève d'`apps/stock`, hors
périmètre de cette lane) : l'audit reproche exactement l'ABSENCE de cet appel.

Run :
    python manage.py test apps.installations.tests_aud312_decider_demande_achat -v2
"""
import itertools
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.installations import selectors, services
from apps.installations.models import (
    DemandeAchat, DemandeAchatLigne, EtapeApprobationAchat,
    RegleApprobationAchat,
)

User = get_user_model()
_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'aud312-co-{n}', defaults={'nom': f'AUD312 Co {n}'})
    return company


def make_user(company):
    return User.objects.create_user(
        username=f'aud312-{next(_seq)}', password='x',
        role_legacy='responsable', company=company)


def make_demande(company, user, *, montant, soumise=True):
    da = DemandeAchat.objects.create(
        company=company, reference=f'DA-AUD312-{next(_seq):04d}',
        objet='Réquisition AUD312', created_by=user)
    DemandeAchatLigne.objects.create(
        demande=da, designation='Article', quantite=1, prix_estime=montant)
    if soumise:
        da.statut = DemandeAchat.Statut.SOUMISE
        da.save(update_fields=['statut'])
    return da


class DeciderDemandeAchatSousWorkflowTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.decideur = make_user(self.company)
        RegleApprobationAchat.objects.create(
            company=self.company, libelle='Direction ×2',
            montant_min=1000, nombre_approbateurs=2, actif=True)
        self.da = make_demande(self.company, self.user, montant=50000)
        self.etapes = services.lancer_workflow_approbation_achat(self.da)
        self.assertEqual(len(self.etapes), 2)

    def test_approbation_en_un_coup_refusee(self):
        """ROUGE avant AUD312 : approuvée d'un coup, étapes orphelines."""
        with self.assertRaises(services.DecisionError):
            services.decider_demande_achat(
                self.da, approuver=True, user=self.decideur)
        self.da.refresh_from_db()
        self.assertEqual(self.da.statut, DemandeAchat.Statut.SOUMISE)
        self.assertEqual(
            self.da.etapes_approbation.filter(
                statut=EtapeApprobationAchat.Statut.EN_ATTENTE).count(), 2)

    def test_refus_en_un_coup_refuse_aussi(self):
        with self.assertRaises(services.DecisionError):
            services.decider_demande_achat(
                self.da, approuver=False, user=self.decideur,
                motif_refus='Trop cher')
        self.da.refresh_from_db()
        self.assertEqual(self.da.statut, DemandeAchat.Statut.SOUMISE)

    def test_le_selecteur_exclut_les_demandes_sous_workflow(self):
        """ROUGE avant AUD312 : la boîte d'approbations la proposait."""
        ids = list(selectors.demandes_achat_en_attente(
            self.company).values_list('id', flat=True))
        self.assertNotIn(self.da.id, ids)


class DeciderDemandeAchatSansWorkflowTests(TestCase):
    """Non-régression : sans plan d'approbation, le chemin reste ouvert."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.decideur = make_user(self.company)

    def test_approbation_directe_toujours_possible(self):
        da = make_demande(self.company, self.user, montant=500)
        services.decider_demande_achat(
            da, approuver=True, user=self.decideur)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.APPROUVEE)
        self.assertEqual(da.approuvee_par_id, self.decideur.id)

    def test_le_selecteur_liste_toujours_les_demandes_sans_workflow(self):
        da = make_demande(self.company, self.user, montant=500)
        ids = list(selectors.demandes_achat_en_attente(
            self.company).values_list('id', flat=True))
        self.assertIn(da.id, ids)

    def test_le_refus_libere_le_budget_engage(self):
        """ROUGE avant AUD312 : l'enveloppe engagée n'était jamais rendue."""
        da = make_demande(self.company, self.user, montant=500)
        with mock.patch.object(
                services, 'liberer_budget_demande_achat') as liberer:
            services.decider_demande_achat(
                da, approuver=False, user=self.decideur,
                motif_refus='Hors budget')
        liberer.assert_called_once_with(da)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.REFUSEE)
        self.assertEqual(da.motif_refus, 'Hors budget')

    def test_lapprobation_ne_libere_aucun_budget(self):
        da = make_demande(self.company, self.user, montant=500)
        with mock.patch.object(
                services, 'liberer_budget_demande_achat') as liberer:
            services.decider_demande_achat(
                da, approuver=True, user=self.decideur)
        liberer.assert_not_called()
