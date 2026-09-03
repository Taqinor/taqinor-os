"""Tests CONTRAT31 — Lien facturation récurrente (via ventes).

Couvre :
- ``facturer_ligne_echeance`` émet une ``ventes.Facture`` (TTC ventilé HT/TVA),
  relie la facture à la ligne (``facture_id``) et journalise — sans toucher
  ``Contrat.statut``.
- Gardes : facturation non activée, échéance déjà facturée (idempotence),
  montant nul, contrat sans client → ``FacturationError``.
- Le client est résolu par ``crm.selectors`` (frontière cross-app).
- API : action ``facturer`` (201 + référence), refus 400 hors garde, scope/rôle.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.ventes.models import Facture

from apps.contrats import services
from apps.contrats.models import Contrat, EcheancierContrat

User = get_user_model()

LIGNES = "/api/django/contrats/lignes-echeance/"


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


def make_setup(company, *, client=True, facturation_active=True,
               montant="1200"):
    cli = Client.objects.create(company=company, nom="Client SARL") if client \
        else None
    contrat = Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal("120000"),
        type_contrat="om", statut="actif",
        client_id=cli.id if cli else None,
        date_debut=timezone.localdate() - timedelta(days=10))
    ech = EcheancierContrat.objects.create(
        company=company, contrat=contrat, periodicite="mensuelle",
        facturation_active=facturation_active)
    ligne = services.ajouter_ligne_echeance(
        ech, date_echeance=timezone.localdate(), montant=Decimal(montant))
    return contrat, ech, ligne


class FacturationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("facrec-svc", "FacRecSvc")
        self.user = make_user(self.co, "facrec-svc-admin", role="admin")

    def test_facture_emise_et_reliee(self):
        contrat, ech, ligne = make_setup(self.co, montant="1200")
        facture = services.facturer_ligne_echeance(ligne, user=self.user)
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(facture.montant_ttc, Decimal("1200.00"))
        self.assertEqual(facture.company_id, self.co.id)
        # AUD181 — TTC 1200 → HT 1000, TVA 200. Le 20 % ne vient PLUS d'un
        # littéral figé mais du knob société `CompanyProfile.tva_standard`,
        # dont le défaut est 20 : société non éditée => ventilation inchangée.
        self.assertEqual(facture.montant_ht, Decimal("1000.00"))
        self.assertEqual(facture.montant_tva, Decimal("200.00"))
        self.assertEqual(facture.taux_tva, Decimal("20.00"))
        ligne.refresh_from_db()
        self.assertEqual(ligne.facture_id, facture.id)
        # Le statut du contrat n'a pas bougé.
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, "actif")

    def test_garde_facturation_non_activee(self):
        _, _, ligne = make_setup(self.co, facturation_active=False)
        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance(ligne, user=self.user)

    def test_garde_idempotence_deja_facturee(self):
        _, _, ligne = make_setup(self.co)
        services.facturer_ligne_echeance(ligne, user=self.user)
        ligne.refresh_from_db()
        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance(ligne, user=self.user)
        # Une seule facture créée.
        self.assertEqual(Facture.objects.filter(company=self.co).count(), 1)

    def test_garde_montant_nul(self):
        _, _, ligne = make_setup(self.co, montant="0")
        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance(ligne, user=self.user)

    def test_garde_sans_client(self):
        _, _, ligne = make_setup(self.co, client=False)
        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance(ligne, user=self.user)


class FacturationApiTests(TestCase):
    def setUp(self):
        self.co = make_company("facrec-api", "FacRecApi")
        self.admin = make_user(self.co, "facrec-api-admin", role="admin")

    def test_action_facturer(self):
        _, _, ligne = make_setup(self.co, montant="2400")
        api = auth(self.admin)
        res = api.post(f"{LIGNES}{ligne.id}/facturer/", {}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertIsNotNone(res.data["facture_id"])
        self.assertTrue(res.data["facture_reference"])
        self.assertEqual(res.data["ligne"]["facture_id"], res.data["facture_id"])

    def test_action_facturer_non_activee_400(self):
        _, _, ligne = make_setup(self.co, facturation_active=False)
        api = auth(self.admin)
        res = api.post(f"{LIGNES}{ligne.id}/facturer/", {}, format="json")
        self.assertEqual(res.status_code, 400, res.content)

    def test_role_gate(self):
        _, _, ligne = make_setup(self.co)
        commercial = make_user(self.co, "facrec-api-com", role="commercial")
        api = auth(commercial)
        res = api.post(f"{LIGNES}{ligne.id}/facturer/", {}, format="json")
        self.assertEqual(res.status_code, 403)


class IdempotenceVerrouLigneTests(TestCase):
    """AUD183 — clé d'idempotence : verrou en base sur la LigneEcheance.

    La garde « déjà facturée » portait sur l'objet DÉJÀ CHARGÉ EN MÉMOIRE par
    le beat (queryset itéré sans `select_for_update`) : deux exécutions
    concurrentes — double worker Celery, retry après timeout apparent, ou
    `rejouer_cycle` lancé pendant un passage du beat — franchissaient toutes
    deux la garde avant que la première n'ait posé `facture_id`, produisant
    DEUX Factures pour la même échéance. Ce test reproduit exactement ce
    mécanisme de façon déterministe : deux INSTANCES distinctes de la même
    ligne, la seconde restant « périmée » en mémoire.
    """

    def setUp(self):
        self.co = make_company("facrec-idem", "FacRecIdem")
        self.user = make_user(self.co, "facrec-idem-admin", role="admin")

    def test_seconde_execution_sur_instance_perimee_ne_double_facture_pas(self):
        from apps.contrats.models import LigneEcheance
        _, _, ligne = make_setup(self.co, montant="1200")
        # Deux instances SÉPARÉES de la même ligne, toutes deux « fraîches »
        # avant la première facturation : c'est l'état de deux workers.
        instance_a = LigneEcheance.objects.get(pk=ligne.pk)
        instance_b = LigneEcheance.objects.get(pk=ligne.pk)
        self.assertIsNone(instance_b.facture_id)

        services.facturer_ligne_echeance(instance_a, user=self.user)

        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance(instance_b, user=self.user)

        self.assertEqual(Facture.objects.filter(company=self.co).count(), 1)
        ligne.refresh_from_db()
        self.assertIsNotNone(ligne.facture_id)

    def test_rejeu_apres_facturation_ne_double_facture_pas(self):
        from apps.contrats.models import LigneEcheance
        _, _, ligne = make_setup(self.co, montant="1200")
        perimee = LigneEcheance.objects.get(pk=ligne.pk)
        services.facturer_ligne_echeance_journalisee(ligne, user=self.user)
        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance_journalisee(
                perimee, user=self.user)
        self.assertEqual(Facture.objects.filter(company=self.co).count(), 1)

    def test_chemin_nominal_reste_vert(self):
        _, _, ligne = make_setup(self.co, montant="1200")
        facture = services.facturer_ligne_echeance(ligne, user=self.user)
        self.assertEqual(facture.montant_ttc, Decimal("1200.00"))
        ligne.refresh_from_db()
        self.assertEqual(ligne.facture_id, facture.id)


class TauxTvaTraverseTests(TestCase):
    """AUD181 — le taux de TVA société TRAVERSE toute la facturation contrats.

    Sept producteurs figeaient 20 % (`taux_tva=Decimal('20')` ou le littéral
    `/ Decimal('1.2')`) sans aucun chemin pour en changer : un tenant réglant
    `CompanyProfile.tva_standard` à 14 % voyait 14 % sur ses factures SAV et
    20 % sur chaque échéance, caution retenue, frais de retard, dommage et
    facture de régie — même grand livre, deux taux.
    """

    def setUp(self):
        self.co = make_company("facrec-tva14", "TVA14")
        self.user = make_user(self.co, "facrec-tva14-admin", role="admin")
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.get(company=self.co)
        profil.tva_standard = Decimal("14")
        profil.save(update_fields=["tva_standard"])

    def test_echeance_ventilee_au_taux_societe(self):
        _, _, ligne = make_setup(self.co, montant="1000")
        facture = services.facturer_ligne_echeance(ligne, user=self.user)
        # 1000 TTC à 14 % → HT 877.19, TVA 122.81 (aujourd'hui 833.33/166.67).
        self.assertEqual(facture.taux_tva, Decimal("14"))
        self.assertEqual(facture.montant_ttc, Decimal("1000.00"))
        self.assertEqual(facture.montant_ht, Decimal("877.19"))
        self.assertEqual(facture.montant_tva, Decimal("122.81"))

    def test_taux_propre_de_l_echeancier_prioritaire(self):
        _, ech, ligne = make_setup(self.co, montant="1000")
        ech.taux_tva = Decimal("7")
        ech.save(update_fields=["taux_tva"])
        ligne.refresh_from_db()
        facture = services.facturer_ligne_echeance(ligne, user=self.user)
        self.assertEqual(facture.taux_tva, Decimal("7"))

    def test_taux_du_contrat_utilise_si_echeancier_muet(self):
        contrat, _, ligne = make_setup(self.co, montant="1000")
        contrat.taux_tva = Decimal("10")
        contrat.save(update_fields=["taux_tva"])
        ligne.refresh_from_db()
        facture = services.facturer_ligne_echeance(ligne, user=self.user)
        self.assertEqual(facture.taux_tva, Decimal("10"))

    def test_taux_tva_effectif_replie_sur_le_knob_societe(self):
        self.assertEqual(
            services.taux_tva_effectif(self.co), Decimal("14"))
        self.assertEqual(
            services.taux_tva_effectif(self.co, None), Decimal("14"))

    def test_facture_de_regie_suit_le_knob_societe(self):
        from apps.ventes.services import creer_facture_regie
        cli = Client.objects.create(company=self.co, nom="Client régie")
        facture = creer_facture_regie(
            company=self.co, client=cli, user=self.user,
            libelle="Régie", montant_ht=Decimal("1000"))
        # 1000 HT à 14 % → TVA 140 (aujourd'hui 200).
        self.assertEqual(facture.taux_tva, Decimal("14"))
        self.assertEqual(facture.montant_tva, Decimal("140.00"))
        self.assertEqual(facture.montant_ttc, Decimal("1140.00"))

    def test_acompte_de_situation_suit_le_knob_societe(self):
        from apps.ventes.services import creer_facture_acompte_situation
        cli = Client.objects.create(company=self.co, nom="Client situation")
        facture = creer_facture_acompte_situation(
            company=self.co, client=cli, user=self.user,
            libelle="Situation n°1", montant_periode_ht=Decimal("1000"))
        self.assertEqual(facture.taux_tva, Decimal("14"))
        self.assertEqual(facture.montant_tva, Decimal("140.00"))


class TauxTvaLocationTests(TestCase):
    """AUD181 — les quatre producteurs « location » suivent aussi le taux réel.

    Caution retenue, frais de retard, dommages d'inspection et cycle de
    location longue durée figeaient 20 % — les trois derniers via un
    `/ Decimal('1.2')` LITTÉRAL, sans aucun paramètre exposé.
    """

    def setUp(self):
        from apps.stock.models import Produit
        self.co = make_company("facrec-loc14", "Loc14")
        self.user = make_user(self.co, "facrec-loc14-admin", role="admin")
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.get(company=self.co)
        profil.tva_standard = Decimal("14")
        profil.save(update_fields=["tva_standard"])
        self.client_obj = Client.objects.create(
            company=self.co, nom="Client location")
        self.produit = Produit.objects.create(
            company=self.co, nom="Nacelle", prix_vente=Decimal("100"),
            louable=True, tarif_location_jour=Decimal("500"))

    def _ordre(self, **kwargs):
        aujourdhui = timezone.localdate()
        return services.creer_ordre_location(
            self.co, client_id=self.client_obj.id, produit=self.produit,
            date_reservation=aujourdhui - timedelta(days=4),
            date_enlevement_prevue=aujourdhui - timedelta(days=2),
            date_retour_prevue=aujourdhui + timedelta(days=2),
            **kwargs)

    def test_creation_fige_le_taux_societe_sur_l_ordre(self):
        ordre = self._ordre()
        self.assertEqual(ordre.taux_tva, Decimal("14"))

    def test_retenue_de_caution_au_taux_reel(self):
        ordre = self._ordre()
        ordre.caution_montant = Decimal("1000")
        ordre.caution_statut = "encaissee"
        ordre.date_retour_reelle = timezone.localdate()
        ordre.save(update_fields=[
            "caution_montant", "caution_statut", "date_retour_reelle"])
        resultat = services.retenir_caution_partielle(
            ordre, montant_retenu=Decimal("570"), motif="Casse",
            user=self.user)
        facture = resultat["facture"]
        # 570 TTC à 14 % → HT 500.00 (aujourd'hui 475.00 à 20 %).
        self.assertEqual(facture.taux_tva, Decimal("14"))
        self.assertEqual(facture.montant_ht, Decimal("500.00"))

    def test_frais_de_retard_au_taux_reel(self):
        from apps.contrats.models import OrdreLocation
        ordre = self._ordre(frais_retard_jour=Decimal("114"))
        services.changer_statut_ordre_location(
            ordre, OrdreLocation.Statut.ENLEVEE)
        ordre.date_retour_reelle = (
            ordre.date_retour_prevue + timedelta(days=1))
        ordre.statut = OrdreLocation.Statut.RETOURNEE
        ordre.save(update_fields=["date_retour_reelle", "statut"])
        services.cloturer_ordre_location(ordre, user=self.user)
        ordre.refresh_from_db()
        facture = Facture.objects.get(id=ordre.frais_retard_facture_id)
        # 114 TTC à 14 % → HT 100.00 (aujourd'hui 95.00 via / Decimal('1.2')).
        self.assertEqual(facture.taux_tva, Decimal("14"))
        self.assertEqual(facture.montant_ht, Decimal("100.00"))

    def test_dommages_inspection_au_taux_reel(self):
        ordre = self._ordre()
        resultat = services.inspecter_retour(
            ordre, dommages_montant=Decimal("228"), user=self.user)
        facture = resultat["facture"]
        # 228 TTC à 14 % → HT 200.00 (aujourd'hui 190.00 via / Decimal('1.2')).
        self.assertEqual(facture.taux_tva, Decimal("14"))
        self.assertEqual(facture.montant_ht, Decimal("200.00"))

    def test_cycle_location_recurrent_au_taux_reel(self):
        ordre = self._ordre(tarif_jour=Decimal("100"))
        ordre.facturation_recurrente_active = True
        ordre.save(update_fields=["facturation_recurrente_active"])
        facture = services.facturer_ordre_location_recurrent(
            ordre, user=self.user)
        # 100 × 30 = 3000 TTC à 14 % → HT 2631.58 (aujourd'hui 2500.00).
        self.assertEqual(facture.taux_tva, Decimal("14"))
        self.assertEqual(facture.montant_ht, Decimal("2631.58"))
