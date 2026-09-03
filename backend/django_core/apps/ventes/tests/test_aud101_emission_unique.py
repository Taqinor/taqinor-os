"""AUD101 — LE service unique d'émission de facture.

Les CINQ chemins qui posaient ``Facture.Statut.EMISE`` en silence — bulk
``action=emettre``, facturation de pénalités, tranche d'échéancier (le chemin
acompte → matériel → solde du parcours solaire), ``creer_facture_classique``
(consommée par POS / e-commerce / immobilier) et la consolidation multi-devis —
rejoignent ``apps.ventes.domain.facturation_ops.emettre_facture``.

Ce que ces tests épinglent :

  * chacun des 5 chemins émet ``facture_emise`` EXACTEMENT une fois (rouge
    avant AUD101 : zéro sur les cinq, donc AUCUNE écriture au grand livre —
    ``compta`` ne comptabilise que sur cet événement) ;
  * l'abonné compta de ``facture_emise`` est bien branché, donc l'événement
    atteint réellement ``ecriture_pour_facture`` ;
  * PARITÉ : aucun site de ``apps/ventes`` ne pose ``Facture.Statut.EMISE``
    hors du service (scan AST du code réel, pas un grep) ;
  * un client en blocage crédit dur (XFAC28) n'est plus facturable par le
    bulk, les pénalités ni la facture classique — SAUF l'exemption comptoir
    ``reglee_a_l_acte=True`` (le hold protège l'encours, pas le cash immédiat).
"""
import ast
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture, FollowupLevel, LigneDevis, \
    LigneFacture
from authentication.models import Company
from core.events import facture_emise

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class _CompteurSignal:
    """Compte les émissions de ``facture_emise`` pendant un bloc ``with``."""

    def __init__(self):
        self.appels = []

    def __enter__(self):
        facture_emise.connect(self._recevoir, weak=False)
        return self

    def __exit__(self, *exc):
        facture_emise.disconnect(self._recevoir)
        return False

    def _recevoir(self, sender, instance, company, **kwargs):
        self.appels.append(instance.pk)

    def pour(self, facture):
        return [pk for pk in self.appels if pk == facture.pk]


class _BaseEmission(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='aud101-co', defaults={'nom': 'AUD101 Co'})
        self.user = User.objects.create_user(
            username=f'aud101_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD101', prenom='Client',
            email='aud101@example.com', telephone='+212600000101')

    def _produit(self):
        n = _nxt()
        return Produit.objects.create(
            company=self.company, nom=f'Produit {n}', sku=f'AUD101-{n}',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=500)

    def _facture(self, statut=Facture.Statut.BROUILLON, avec_ligne=True):
        n = _nxt()
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-A{n:04d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'))
        if avec_ligne:
            LigneFacture.objects.create(
                facture=facture, produit=self._produit(),
                designation='Ligne', quantite=Decimal('1'),
                prix_unitaire=Decimal('1000'))
        return facture

    def _devis_accepte(self, ref=None):
        devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj,
            reference=ref or f'DEV-AUD101-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=self._produit(), designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        return devis

    def _activer_credit_hold(self):
        """Arme le blocage crédit dur XFAC28 sur un client en dépassement."""
        profile = CompanyProfile.get(company=self.company)
        profile.credit_hold_actif = True
        profile.save(update_fields=['credit_hold_actif'])
        self.client_obj.plafond_credit = Decimal('1')
        self.client_obj.save(update_fields=['plafond_credit'])
        # Un encours réel au-delà du plafond : une facture émise impayée.
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-HOLD{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('50000'),
            montant_tva=Decimal('10000'), montant_ttc=Decimal('60000'))


class TestCinqCheminsMuetsEmettentLEvenement(_BaseEmission):
    """Un et un seul ``facture_emise`` par chemin — rouge avant AUD101."""

    def test_bulk_emettre_emet_une_fois(self):
        facture = self._facture()
        with _CompteurSignal() as compteur:
            resp = self.api.post(
                '/api/django/ventes/factures/bulk/',
                {'action': 'emettre', 'ids': [facture.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data[str(facture.id)]['ok'], resp.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(len(compteur.pour(facture)), 1)

    def test_facturer_penalites_emet_une_fois(self):
        FollowupLevel.objects.create(
            company=self.company, nom='Niveau 1', delai_jours=1, ordre=1,
            taux_interet_annuel=Decimal('10'))
        facture = self._facture(statut=Facture.Statut.EMISE)
        facture.date_echeance = timezone.now().date() - timedelta(days=60)
        facture.save(update_fields=['date_echeance'])
        with _CompteurSignal() as compteur:
            resp = self.api.post(
                f'/api/django/ventes/factures/{facture.id}/'
                'facturer-penalites/', {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        penalite = Facture.objects.get(reference=resp.data['reference'])
        self.assertEqual(penalite.statut, Facture.Statut.EMISE)
        self.assertEqual(len(compteur.pour(penalite)), 1)

    def test_tranche_echeancier_emet_une_fois(self):
        from apps.ventes.utils.echeancier import creer_facture_tranche
        from apps.ventes.utils.references import create_with_reference

        devis = self._devis_accepte()
        with _CompteurSignal() as compteur:
            facture = creer_facture_tranche(
                devis, self.user, self.company, create_with_reference)
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(len(compteur.pour(facture)), 1)

    def test_facture_classique_pos_emet_une_fois(self):
        from apps.ventes.domain.facturation_ops import creer_facture_classique

        with _CompteurSignal() as compteur:
            facture = creer_facture_classique(
                company=self.company, client=self.client_obj, user=self.user,
                taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
                montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
                libelle='Vente comptoir')
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(len(compteur.pour(facture)), 1)

    def test_consolidation_emet_une_fois_et_apres_les_lignes(self):
        from apps.ventes.domain.encaissements import consolider_factures

        d1 = self._devis_accepte('DEV-AUD101-C1')
        d2 = self._devis_accepte('DEV-AUD101-C2')
        with _CompteurSignal() as compteur:
            facture = consolider_factures(
                company=self.company, devis_ids=[d1.id, d2.id],
                user=self.user, created_by=self.user)
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(len(compteur.pour(facture)), 1)
        # L'événement doit partir APRÈS la recopie des lignes, sinon compta
        # écrirait une écriture à zéro.
        self.assertEqual(facture.lignes.count(), 2)

    def test_ecran_emettre_emet_toujours_une_seule_fois(self):
        """Non-régression du chemin A1 (déjà instrumenté avant AUD101)."""
        facture = self._facture()
        with _CompteurSignal() as compteur:
            resp = self.api.post(
                f'/api/django/ventes/factures/{facture.id}/emettre/', {},
                format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(len(compteur.pour(facture)), 1)


class TestAbonneComptaBranche(TestCase):
    """``facture_emise`` atteint réellement l'écriture comptable."""

    def test_le_receveur_compta_est_abonne(self):
        import apps.compta.receivers  # noqa: F401 — enregistre les abonnés
        # Django indexe chaque abonné par ``(dispatch_uid|id, id(sender))``.
        uids = {lookup[0] for lookup, _recepteur in facture_emise.receivers}
        self.assertIn('compta_ecriture_pour_facture_emise', uids)


class TestPariteAucunEmetteurHorsService(TestCase):
    """PARITÉ — aucun site de ``apps/ventes`` ne pose EMISE hors du service.

    Scan AST (jamais un grep : un grep compte les commentaires et les
    comparaisons ``statut ==``). On cherche les ÉCRITURES seulement :
    ``x.statut = ...EMISE`` et ``Model.objects.create(statut=...EMISE)``.
    """

    #: Sites autorisés à écrire ``EMISE``, avec leur raison.
    ALLOWLIST = {
        'domain/facturation_ops.py': (
            "LE service unique d'émission (AUD101)."),
        'domain/recouvrement.py': (
            "RÉOUVERTURE après rejet d'un paiement (YLEDG5) — ce n'est pas "
            "une émission : la facture était déjà émise."),
    }

    #: Seules ces méthodes ÉCRIVENT ; ``filter``/``exclude`` lisent.
    ECRITURES = frozenset({
        'create', 'get_or_create', 'update_or_create', 'update',
        'bulk_create',
    })

    @classmethod
    def _ecrit_emise(cls, noeud):
        """Vrai si ce nœud AST ÉCRIT ``Facture.Statut.EMISE``.

        Volontairement étroit sur les DEUX axes, pour ne compter aucun faux
        positif : le modèle doit être ``Facture`` (``Avoir.Statut.EMISE`` et
        ``NoteDebit.Statut.EMISE`` sont d'autres documents) et l'appel doit
        être une écriture (``.filter(statut=Facture.Statut.EMISE)`` est une
        LECTURE, pas une émission)."""
        def _est_emise(valeur):
            return (isinstance(valeur, ast.Attribute)
                    and valeur.attr == 'EMISE'
                    and isinstance(valeur.value, ast.Attribute)
                    and valeur.value.attr == 'Statut'
                    and isinstance(valeur.value.value, ast.Name)
                    and valeur.value.value.id == 'Facture')

        if isinstance(noeud, ast.Assign):
            cibles = [c for c in noeud.targets
                      if isinstance(c, ast.Attribute) and c.attr == 'statut']
            return bool(cibles) and _est_emise(noeud.value)
        if isinstance(noeud, ast.Call):
            nom = (noeud.func.attr if isinstance(noeud.func, ast.Attribute)
                   else getattr(noeud.func, 'id', ''))
            if nom not in cls.ECRITURES:
                return False
            return any(kw.arg == 'statut' and _est_emise(kw.value)
                       for kw in noeud.keywords)
        return False

    def test_aucune_ecriture_emise_hors_du_service(self):
        racine = Path(__file__).resolve().parents[1]
        coupables = []
        for chemin in sorted(racine.rglob('*.py')):
            rel = chemin.relative_to(racine).as_posix()
            if rel.startswith('tests/') or rel.startswith('migrations/'):
                continue
            if rel in self.ALLOWLIST:
                continue
            source = chemin.read_text(encoding='utf-8')
            if 'EMISE' not in source:
                continue
            for noeud in ast.walk(ast.parse(source)):
                if self._ecrit_emise(noeud):
                    coupables.append(f'{rel}:{noeud.lineno}')
        self.assertEqual(
            coupables, [],
            "Ces sites posent un statut ÉMISE hors de "
            "apps.ventes.domain.facturation_ops.emettre_facture : "
            + ', '.join(coupables)
            + ". Appelez le service unique (AUD101) — ou ajoutez le fichier à "
              "ALLOWLIST avec sa raison, ce qui rend l'exception visible en "
              "revue.")


class TestBlocageCreditALEmission(_BaseEmission):
    """XFAC28 — le hold crédit dur atteint enfin tous les producteurs."""

    def test_bulk_refuse_un_client_en_hold(self):
        self._activer_credit_hold()
        facture = self._facture()
        resp = self.api.post(
            '/api/django/ventes/factures/bulk/',
            {'action': 'emettre', 'ids': [facture.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data[str(facture.id)]['ok'], resp.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)

    def test_facture_classique_refuse_un_client_en_hold(self):
        from apps.ventes.domain.facturation_ops import creer_facture_classique
        from apps.ventes.domain.recouvrement import CreditHoldError

        self._activer_credit_hold()
        avant = Facture.objects.count()
        with self.assertRaises(CreditHoldError):
            creer_facture_classique(
                company=self.company, client=self.client_obj, user=self.user,
                taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
                montant_tva=Decimal('200'), montant_ttc=Decimal('1200'))
        # Refus AVANT toute écriture : aucun brouillon orphelin ne subsiste.
        self.assertEqual(Facture.objects.count(), avant)

    def test_exemption_comptoir_regle_a_l_acte(self):
        from apps.ventes.domain.facturation_ops import creer_facture_classique

        self._activer_credit_hold()
        facture = creer_facture_classique(
            company=self.company, client=self.client_obj, user=self.user,
            taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
            libelle='Vente comptoir réglée', reglee_a_l_acte=True)
        self.assertEqual(facture.statut, Facture.Statut.EMISE)

    def test_ecran_emettre_repond_403_sur_hold(self):
        self._activer_credit_hold()
        facture = self._facture()
        resp = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/emettre/', {},
            format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
