"""AUD312 — `decider_demande_achat` converge avec le chemin normal FG310/NTP2P2.

Défaut d'origine : le chemin normal (`DemandeAchatViewSet.approuver` /
`.refuser`) bloque en 400 si `workflow_approbation_achat_actif(da)` et, au
refus, annule les étapes `en_attente`. `decider_demande_achat` — seul point
d'entrée de la boîte d'approbations centralisée
(`apps/reporting/approbations.py`) — ne vérifiait que `statut == SOUMISE` puis
basculait directement APPROUVEE/REFUSEE, sans cette garde ; et
`demandes_achat_en_attente` n'excluait pas non plus les demandes sous workflow
actif.

REQUALIFICATION (audit R3) : ce n'est PAS une élévation de privilège — le rôle
exigé est identique des deux côtés. Ce qui était perdu : le nombre
d'approbations (N→1) et la séparation des tâches.

Run :
    python manage.py test apps.installations.tests_aud312_decider_demande_achat -v2
"""
import itertools

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

    def test_le_refus_direct_refuse_la_demande(self):
        da = make_demande(self.company, self.user, montant=500)
        services.decider_demande_achat(
            da, approuver=False, user=self.decideur,
            motif_refus='Hors budget')
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.REFUSEE)
        self.assertEqual(da.motif_refus, 'Hors budget')

    def test_decision_exige_le_droit_et_la_separation(self):
        """AAPV32 — sans `approuver_demande_achat` : refus (403 au service et
        aux actions), DA inchangée ; `sod_stricte` + créateur = décideur :
        409 sur `approuver/` et DecisionError au service."""
        from django.core.exceptions import PermissionDenied
        from django.core.management import call_command
        from rest_framework.test import APIClient
        from apps.roles.models import Role
        from apps.stock.models import AchatsParametres
        call_command('init_roles', verbosity=0)
        tech = User.objects.create_user(
            username=f'aud312-tech-{next(_seq)}', password='x',
            company=self.company,
            role=Role.objects.get(company=self.company, nom='Technicien'))
        da = make_demande(self.company, self.user, montant=500)
        for approuver in (True, False):
            with self.assertRaises(PermissionDenied):
                services.decider_demande_achat(
                    da, approuver=approuver, user=tech, motif_refus='x')
        api = APIClient()
        api.force_authenticate(tech)
        base = f'/api/django/installations/demandes-achat/{da.id}'
        for action in ('refuser', 'rejeter-etape', 'marquer_commandee'):
            r = api.post(f'{base}/{action}/', {'motif_refus': 'x'}, format='json')
            self.assertEqual(r.status_code, 403, (action, r.status_code))
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.SOUMISE)

        AchatsParametres.objects.update_or_create(
            company=self.company, defaults={'sod_stricte': True})
        with self.assertRaises(services.DecisionError):
            services.decider_demande_achat(da, approuver=True, user=self.user)
        api.force_authenticate(self.user)
        r = api.post(f'{base}/approuver/', {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('Séparation des tâches', r.data['detail'])
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.SOUMISE)
        services.decider_demande_achat(da, approuver=True, user=self.decideur)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.APPROUVEE)
