"""Tests XCTR12 — Devis de renouvellement généré avant échéance.

Couvre :
- devis créé et lié (ContratLien type devis) ;
- double clic = pas de doublon (refus si un devis de renouvellement ouvert
  existe déjà) ;
- acceptation reflétée sur le contrat (via l'événement devis_accepted) ;
- endpoint POST /contrats/<id>/generer-devis-renouvellement/.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.ventes.models import Devis
from core.events import devis_accepted

from apps.contrats import services
from apps.contrats.models import Contrat, ContratActivity, ContratLien

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def make_contrat(company, *, client=True, montant=Decimal("1000")):
    cli = Client.objects.create(company=company, nom="Client SARL") if client \
        else None
    return Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=montant,
        type_contrat="om", statut=Contrat.Statut.ACTIF,
        client_id=cli.id if cli else None, date_debut=date(2026, 1, 1))


class GenererDevisRenouvellementServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("renouv-devis-svc", "RenouvDevisSvc")
        self.user = make_user(self.co, "renouv-devis-svc-admin")

    def test_cree_devis_et_lien(self):
        contrat = make_contrat(self.co, montant=Decimal("1000"))
        devis = services.generer_devis_renouvellement(
            contrat, auteur=self.user)
        self.assertEqual(devis.company_id, self.co.id)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        lien = ContratLien.objects.get(
            contrat=contrat, type_cible=ContratLien.TypeCible.DEVIS)
        self.assertEqual(lien.cible_id, devis.id)

    def test_double_clic_refuse(self):
        contrat = make_contrat(self.co)
        services.generer_devis_renouvellement(contrat, auteur=self.user)
        with self.assertRaises(services.RenouvellementDevisError):
            services.generer_devis_renouvellement(contrat, auteur=self.user)

    def test_nouveau_devis_possible_apres_refus_du_premier(self):
        contrat = make_contrat(self.co)
        devis1 = services.generer_devis_renouvellement(
            contrat, auteur=self.user)
        devis1.statut = Devis.Statut.REFUSE
        devis1.save(update_fields=['statut'])
        devis2 = services.generer_devis_renouvellement(
            contrat, auteur=self.user)
        self.assertNotEqual(devis1.id, devis2.id)

    def test_sans_client_refuse(self):
        contrat = make_contrat(self.co, client=False)
        with self.assertRaises(services.RenouvellementDevisError):
            services.generer_devis_renouvellement(contrat, auteur=self.user)

    def test_indexation_revise_montant(self):
        contrat = make_contrat(self.co, montant=Decimal("1000"))
        from apps.contrats.models import IndexationPrix
        IndexationPrix.objects.create(
            company=self.co, contrat=contrat, indice="IPC",
            valeur_base=Decimal("100"), actif=True)
        devis = services.generer_devis_renouvellement(
            contrat, auteur=self.user, valeur_indice=Decimal("110"))
        self.assertIn('montant_propose', devis.etude_params)
        # 1000 * (110/100) = 1100.
        self.assertEqual(
            devis.etude_params['montant_propose'], '1100.00')


class AcceptationRenouvellementTests(TestCase):
    def setUp(self):
        self.co = make_company("renouv-devis-accept", "RenouvDevisAccept")
        self.user = make_user(self.co, "renouv-devis-accept-admin")

    def test_acceptation_via_evenement_reflete_sur_chatter(self):
        contrat = make_contrat(self.co)
        devis = services.generer_devis_renouvellement(
            contrat, auteur=self.user)

        devis_accepted.send(
            sender=Devis, devis=devis, user=self.user, ancien_statut='envoye')

        activite = ContratActivity.objects.filter(
            contrat=contrat,
            field='devis_renouvellement_accepte').first()
        self.assertIsNotNone(activite)
        # Le statut du contrat n'a jamais bougé (préservation des statuts).
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

    def test_devis_sans_lien_contrat_est_un_noop(self):
        """Un devis ORDINAIRE (sans lien contrat) n'a aucun effet ici."""
        cli = Client.objects.create(company=self.co, nom="Client normal")
        devis = Devis.objects.create(
            reference='DEV-TEST-0001', company=self.co, client=cli,
            statut=Devis.Statut.ENVOYE)
        # Ne doit lever aucune exception.
        devis_accepted.send(
            sender=Devis, devis=devis, user=self.user, ancien_statut='envoye')
        self.assertEqual(ContratActivity.objects.count(), 0)


class GenererDevisRenouvellementApiTests(TestCase):
    def setUp(self):
        self.co = make_company("renouv-devis-api", "RenouvDevisApi")
        self.admin = make_user(self.co, "renouv-devis-api-admin")

    def test_action_genere_devis(self):
        contrat = make_contrat(self.co, montant=Decimal("1500"))
        api = auth(self.admin)
        res = api.post(
            f"/api/django/contrats/contrats/{contrat.id}/"
            f"generer-devis-renouvellement/", {}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertIsNotNone(res.data['devis_id'])

    def test_action_double_clic_400(self):
        contrat = make_contrat(self.co)
        api = auth(self.admin)
        url = (
            f"/api/django/contrats/contrats/{contrat.id}/"
            f"generer-devis-renouvellement/")
        res1 = api.post(url, {}, format="json")
        self.assertEqual(res1.status_code, 201)
        res2 = api.post(url, {}, format="json")
        self.assertEqual(res2.status_code, 400)

    def test_role_gate(self):
        contrat = make_contrat(self.co)
        commercial = make_user(
            self.co, "renouv-devis-api-com", role="commercial")
        api = auth(commercial)
        res = api.post(
            f"/api/django/contrats/contrats/{contrat.id}/"
            f"generer-devis-renouvellement/", {}, format="json")
        self.assertEqual(res.status_code, 403)
