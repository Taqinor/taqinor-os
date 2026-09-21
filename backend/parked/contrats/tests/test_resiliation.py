"""Tests CONTRAT25 — Résiliation d'un contrat (motif / préavis / solde).

Couvre :
- ``resilier_contrat`` crée une ``Resiliation`` ET fait basculer le contrat vers
  ``resilie`` via la machine d'états GARDÉE (``changer_statut``) — jamais une
  écriture directe du statut.
- Refus depuis un état NON résiliable (la machine d'états enforce la garde) : le
  statut est laissé inchangé et AUCUNE résiliation n'est créée (atomicité).
- motif / préavis / solde / date d'effet stockés.
- Garde d'idempotence : pas de seconde résiliation active sur un même contrat ;
  une résiliation ``annulee`` ne bloque pas une nouvelle demande.
- Un instantané immuable (``VersionContrat`` — CONTRAT18) est figé et relié.
- Multi-tenant : résiliations scopées société ; endpoints scopés société ;
  société/auteur/statut posés CÔTÉ SERVEUR (jamais lus du corps).
- Endpoints : resilier / lister (+ accès réservé au palier admin/responsable +
  lecture seule de la ressource ``/resiliations/``).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors, services
from apps.contrats.models import (
    Contrat,
    PartieContrat,
    Resiliation,
    VersionContrat,
)

User = get_user_model()

CONTRATS = "/api/django/contrats/contrats/"
RESILIATIONS = "/api/django/contrats/resiliations/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def make_contrat(company, statut="actif", objet="Contrat test",
                 montant="80000"):
    contrat = Contrat.objects.create(
        company=company, objet=objet, montant=Decimal(montant),
        type_contrat="vente", statut=statut,
        date_debut=timezone.localdate() - timedelta(days=30))
    PartieContrat.objects.create(
        company=company, contrat=contrat,
        type_partie="client", nom="Client SARL", ordre=0)
    PartieContrat.objects.create(
        company=company, contrat=contrat,
        type_partie="prestataire", nom="Taqinor", ordre=1)
    return contrat


# ---------------------------------------------------------------------------
# Service — résiliation via la machine d'états gardée
# ---------------------------------------------------------------------------

class ResilierContratServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("res-svc", "ResSvc")
        self.user = make_user(self.co, "res-svc-admin", role="admin")

    def test_resilie_un_contrat_actif_via_machine_etats(self):
        contrat = make_contrat(self.co, statut="actif")
        r = services.resilier_contrat(
            contrat, motif="Non-paiement", auteur=self.user)
        # Le statut a basculé via la machine d'états.
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.RESILIE)
        # La résiliation est enregistrée, scopée société, auteur côté serveur.
        self.assertEqual(r.statut, Resiliation.Statut.DEMANDE)
        self.assertEqual(r.motif, "Non-paiement")
        self.assertEqual(r.company_id, self.co.id)
        self.assertEqual(r.cree_par_id, self.user.id)
        self.assertEqual(r.date_demande, timezone.localdate())

    def test_motif_preavis_solde_dates_stockes(self):
        contrat = make_contrat(self.co, statut="signe")
        date_effet = timezone.localdate() + timedelta(days=30)
        r = services.resilier_contrat(
            contrat, motif="Rupture conventionnelle",
            date_effet=date_effet, preavis_jours=30,
            solde=Decimal("12500.50"), auteur=self.user)
        self.assertEqual(r.preavis_jours, 30)
        self.assertEqual(r.solde, Decimal("12500.50"))
        self.assertEqual(r.date_effet, date_effet)

    def test_fige_une_version_immuable_et_la_relie(self):
        contrat = make_contrat(self.co, statut="actif",
                               objet="Contrat solaire 12 kWc")
        r = services.resilier_contrat(contrat, auteur=self.user)
        self.assertIsNotNone(r.version_creee)
        versions = VersionContrat.objects.filter(contrat=contrat)
        self.assertEqual(versions.count(), 1)
        self.assertEqual(r.version_creee_id, versions.first().id)
        self.assertIn("Résiliation", r.version_creee.motif)
        # Le contenu figé reflète le contrat (corps fusionné).
        self.assertIn("Contrat solaire 12 kWc", r.version_creee.contenu)

    def test_refuse_depuis_un_etat_non_resiliable(self):
        """Un contrat déjà ``resilie`` (état terminal) ne peut pas être résilié :
        la machine d'états refuse la transition → ``ResiliationError``."""
        contrat = make_contrat(self.co, statut="resilie")
        with self.assertRaises(services.ResiliationError):
            services.resilier_contrat(contrat, auteur=self.user)
        # Aucune résiliation n'a été créée (atomicité).
        self.assertEqual(
            Resiliation.objects.filter(contrat=contrat).count(), 0)

    def test_refuse_depuis_expire(self):
        contrat = make_contrat(self.co, statut="expire")
        with self.assertRaises(services.ResiliationError):
            services.resilier_contrat(contrat, auteur=self.user)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.EXPIRE)

    def test_resilie_depuis_brouillon(self):
        """``brouillon → resilie`` est permise par la machine d'états."""
        contrat = make_contrat(self.co, statut="brouillon")
        services.resilier_contrat(contrat, auteur=self.user)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.RESILIE)

    def test_garde_idempotence_pas_de_seconde_resiliation_active(self):
        """Une résiliation active existante bloque une nouvelle demande."""
        contrat = make_contrat(self.co, statut="suspendu")
        services.resilier_contrat(contrat, auteur=self.user)
        # Le contrat est désormais ``resilie`` (terminal) ET une résiliation
        # active existe : un second appel lève ResiliationError.
        with self.assertRaises(services.ResiliationError):
            services.resilier_contrat(contrat, auteur=self.user)
        self.assertEqual(
            Resiliation.objects.filter(contrat=contrat).count(), 1)

    def test_resiliation_annulee_ne_bloque_pas(self):
        """Une résiliation ``annulee`` ne compte pas comme active : la garde
        d'idempotence autorise une nouvelle demande (ici via un autre contrat
        car le statut courant est terminal après la 1re bascule)."""
        contrat = make_contrat(self.co, statut="actif")
        r1 = services.resilier_contrat(contrat, auteur=self.user)
        # On annule la 1re résiliation et on remet le contrat dans un état
        # résiliable pour vérifier que la garde ne bloque plus.
        r1.statut = Resiliation.Statut.ANNULEE
        r1.save(update_fields=["statut"])
        Contrat.objects.filter(pk=contrat.pk).update(statut="actif")
        contrat.refresh_from_db()
        # resiliation_active ne voit plus de résiliation active.
        self.assertIsNone(services.resiliation_active(contrat))
        r2 = services.resilier_contrat(contrat, auteur=self.user)
        self.assertEqual(r2.statut, Resiliation.Statut.DEMANDE)

    def test_journalise_la_bascule(self):
        contrat = make_contrat(self.co, statut="actif")
        services.resilier_contrat(contrat, auteur=self.user)
        logs = contrat.activites.filter(field="statut")
        self.assertTrue(
            logs.filter(new_value=Contrat.Statut.RESILIE).exists())


# ---------------------------------------------------------------------------
# Sélecteur — lecture seule, ordonnée, scopée société
# ---------------------------------------------------------------------------

class ResiliationsSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("res-sel", "ResSel")
        self.user = make_user(self.co, "res-sel-admin", role="admin")

    def test_scope_societe(self):
        contrat = make_contrat(self.co, statut="actif")
        autre_co = make_company("res-sel-2", "ResSel2")
        autre = make_contrat(autre_co, statut="actif")
        services.resilier_contrat(contrat, auteur=self.user)
        services.resilier_contrat(autre)
        self.assertEqual(
            selectors.resiliations_contrat(contrat).count(), 1)


# ---------------------------------------------------------------------------
# API — resilier / lister / scope / rôle / lecture seule
# ---------------------------------------------------------------------------

class ResiliationApiTests(TestCase):
    def setUp(self):
        self.co = make_company("res-api", "ResApi")
        self.admin = make_user(self.co, "res-api-admin", role="admin")

    def test_resilier_endpoint(self):
        contrat = make_contrat(self.co, statut="actif")
        api = auth(self.admin)
        url = f"{CONTRATS}{contrat.id}/resilier/"
        res = api.post(
            url,
            {"motif": "Non-conformité", "preavis_jours": 60,
             "solde": "5000"},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["statut"], "demande")
        self.assertEqual(res.data["motif"], "Non-conformité")
        self.assertEqual(res.data["preavis_jours"], 60)
        self.assertIsNotNone(res.data["version_creee"])
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.RESILIE)

    def test_resilier_etat_non_resiliable_400(self):
        contrat = make_contrat(self.co, statut="resilie")
        api = auth(self.admin)
        res = api.post(
            f"{CONTRATS}{contrat.id}/resilier/", {"motif": "X"},
            format="json")
        self.assertEqual(res.status_code, 400, res.content)

    def test_statut_societe_poses_cote_serveur_pas_du_corps(self):
        """Un ``statut``/``company`` envoyé dans le corps est IGNORÉ."""
        contrat = make_contrat(self.co, statut="actif")
        api = auth(self.admin)
        res = api.post(
            f"{CONTRATS}{contrat.id}/resilier/",
            {"motif": "A", "statut": "effective", "company": 12345},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["statut"], "demande")  # pas effective
        r = Resiliation.objects.get(id=res.data["id"])
        self.assertEqual(r.company_id, self.co.id)  # pas 12345

    def test_lister_resiliations_par_contrat(self):
        contrat = make_contrat(self.co, statut="actif")
        services.resilier_contrat(contrat, auteur=self.admin)
        api = auth(self.admin)
        res = api.get(f"{CONTRATS}{contrat.id}/resiliations/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_viewset_resiliations_lecture_seule(self):
        contrat = make_contrat(self.co, statut="actif")
        r = services.resilier_contrat(contrat, auteur=self.admin)
        api = auth(self.admin)
        res_post = api.post(
            RESILIATIONS, {"contrat": contrat.id, "motif": "X"},
            format="json")
        self.assertEqual(res_post.status_code, 405, res_post.content)
        detail = f"{RESILIATIONS}{r.id}/"
        self.assertEqual(
            api.put(detail, {"motif": "x"}, format="json").status_code, 405)
        self.assertEqual(
            api.patch(detail, {"motif": "x"}, format="json").status_code, 405)
        self.assertEqual(api.delete(detail).status_code, 405)
        self.assertEqual(api.get(detail).status_code, 200)

    def test_scope_societe_endpoint(self):
        contrat = make_contrat(self.co, statut="actif")
        services.resilier_contrat(contrat, auteur=self.admin)
        autre_co = make_company("res-api-2", "ResApi2")
        autre_admin = make_user(autre_co, "res-api-2-admin", role="admin")
        api = auth(autre_admin)
        res = api.get(f"{RESILIATIONS}?contrat={contrat.id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 0)
        # Et l'action resilier est 404 sur un contrat hors société.
        res2 = api.post(
            f"{CONTRATS}{contrat.id}/resilier/", {"motif": "X"},
            format="json")
        self.assertEqual(res2.status_code, 404)

    def test_role_gate_refuse_non_privilegie(self):
        contrat = make_contrat(self.co, statut="actif")
        commercial = make_user(self.co, "res-api-com", role="commercial")
        api = auth(commercial)
        res = api.post(
            f"{CONTRATS}{contrat.id}/resilier/", {"motif": "X"},
            format="json")
        self.assertEqual(res.status_code, 403, res.content)
        res2 = api.get(RESILIATIONS)
        self.assertEqual(res2.status_code, 403)

    def test_doublon_resiliation_active_400(self):
        """Une seconde résiliation active sur un contrat (remis dans un état
        résiliable) est refusée par la garde d'idempotence."""
        contrat = make_contrat(self.co, statut="actif")
        api = auth(self.admin)
        res = api.post(
            f"{CONTRATS}{contrat.id}/resilier/", {"motif": "A"},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        # Remet artificiellement le contrat dans un état résiliable : la garde
        # d'idempotence (résiliation active existante) doit alors refuser (400).
        Contrat.objects.filter(pk=contrat.id).update(statut="actif")
        res2 = api.post(
            f"{CONTRATS}{contrat.id}/resilier/", {"motif": "B"},
            format="json")
        self.assertEqual(res2.status_code, 400, res2.content)
