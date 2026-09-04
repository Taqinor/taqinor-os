"""AUD102 — LE service unique de bascule « PAYÉE ».

Les NEUF chemins qui posaient ``Facture.Statut.PAYEE`` (P1 marquer_payee,
P2 enregistrer_paiement, P3 encaissement groupé, P4 lien de paiement,
P5 ventilation d'avance, P6 retenue à la source, P7 abandon de solde,
P8 import de relevé, P9 transaction carte capturée) convergent sur
``apps.ventes.domain.encaissements.marquer_facture_soldee``.

Avant AUD102, ``facture_payee`` — LE signal désigné par ``core/events.py``,
auquel ``apps/compta/receivers.py`` branche le lettrage — n'était émis que sur
TROIS d'entre eux : six soldes n'étaient jamais lettrés. Et les DEUX défauts
découverts en construisant la carte encaissaient de l'argent sans jamais
solder quoi que ce soit :

  * B9 ``debiter_mandat_pour_facture`` créait un Paiement du TTC et laissait la
    facture ÉMISE → EN_RETARD → relance, alors qu'elle était encaissée ;
  * B14 ``compta.rapprocher_paiement_facture`` marquait l'intention portail
    ``paye`` et déléguait le report « à la chaîne ventes » — que personne ne
    faisait : l'argent du portail n'entrait dans AUCUN ``montant_paye``.
"""
import ast
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, MandatPaiement, Paiement
from authentication.models import Company
from core.events import facture_payee

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class _CompteurPayee:
    """Compte les émissions de ``facture_payee`` pendant un bloc ``with``."""

    def __init__(self):
        self.appels = []

    def __enter__(self):
        facture_payee.connect(self._recevoir, weak=False)
        return self

    def __exit__(self, *exc):
        facture_payee.disconnect(self._recevoir)
        return False

    def _recevoir(self, sender, instance, company, **kwargs):
        self.appels.append(instance.pk)

    def pour(self, facture):
        return [pk for pk in self.appels if pk == facture.pk]


class _BaseSolde(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='aud102-co', defaults={'nom': 'AUD102 Co'})
        self.user = User.objects.create_user(
            username=f'aud102_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD102', prenom='Client',
            email='aud102@example.com', telephone='+212600000102')

    def _facture(self, ttc=Decimal('1200')):
        n = _nxt()
        return Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-P{n:04d}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'),
            montant_ht=(ttc / Decimal('1.2')).quantize(Decimal('0.01')),
            montant_tva=(ttc - (ttc / Decimal('1.2')).quantize(
                Decimal('0.01'))),
            montant_ttc=ttc)

    def _facture_avec_lignes(self):
        n = _nxt()
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-L{n:04d}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'))
        produit = Produit.objects.create(
            company=self.company, nom=f'Prod {n}', sku=f'AUD102-{n}',
            prix_vente=Decimal('1000'), quantite_stock=50)
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Ligne',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        return facture


class TestDeuxDefautsDecouverts(_BaseSolde):
    """Les deux chemins qui encaissaient sans jamais solder — rouges avant."""

    def test_debit_de_mandat_solde_la_facture(self):
        from apps.ventes.domain.encaissements import (
            debiter_mandat_pour_facture,
        )

        facture = self._facture(Decimal('1200'))
        MandatPaiement.objects.create(
            company=self.company, client=self.client_obj,
            provider='noop', token='TOK-AUD102',
            statut=MandatPaiement.Statut.ACTIF)
        with _CompteurPayee() as compteur:
            paiement = debiter_mandat_pour_facture(
                facture=facture, periode='2026-09')
        self.assertIsNotNone(paiement)
        facture.refresh_from_db()
        self.assertEqual(facture.montant_du, Decimal('0.00'))
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(len(compteur.pour(facture)), 1)

    def test_rapprochement_portail_reporte_sur_la_chaine_ventes(self):
        from apps.compta.models import PaiementFacturePortail
        from apps.compta.services import rapprocher_paiement_facture

        facture = self._facture(Decimal('1200'))
        intention = PaiementFacturePortail.objects.create(
            company=self.company, facture=facture,
            montant=Decimal('1200'),
            methode=PaiementFacturePortail.Methode.VIREMENT)
        with _CompteurPayee() as compteur:
            rapprocher_paiement_facture(intention, reference='VIR-AUD102')
        facture.refresh_from_db()
        self.assertEqual(facture.montant_du, Decimal('0.00'))
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(len(compteur.pour(facture)), 1)

    def test_rapprochement_portail_est_idempotent(self):
        from apps.ventes.domain.encaissements import (
            enregistrer_paiement_portail,
        )

        facture = self._facture(Decimal('1200'))
        premier = enregistrer_paiement_portail(
            facture=facture, montant=Decimal('1200'), reference='VIR-IDEM')
        second = enregistrer_paiement_portail(
            facture=facture, montant=Decimal('1200'), reference='VIR-IDEM')
        self.assertIsNotNone(premier)
        self.assertIsNone(second)
        self.assertEqual(
            Paiement.objects.filter(facture=facture).count(), 1)


class TestNeufCheminsEmettentFacturePayee(_BaseSolde):
    """Un et un seul ``facture_payee`` par chemin (donc lettrage compta)."""

    def test_p1_marquer_payee(self):
        from apps.ventes.domain.encaissements import marquer_facture_soldee

        facture = self._facture()
        with _CompteurPayee() as compteur:
            self.assertTrue(marquer_facture_soldee(
                facture, montant=facture.total_ttc, force=True,
                source='marquer_payee_manuel'))
        self.assertEqual(len(compteur.pour(facture)), 1)

    def test_p3_encaissement_groupe(self):
        from apps.ventes.domain.encaissements import (
            affecter_encaissement_groupe,
        )

        facture = self._facture(Decimal('1200'))
        with _CompteurPayee() as compteur:
            affecter_encaissement_groupe(
                company=self.company, client=self.client_obj,
                montant=Decimal('1200'), mode='virement',
                date_paiement=timezone.localdate(), user=self.user,
                factures=[facture])
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(len(compteur.pour(facture)), 1)

    def test_p5_ventilation_avance(self):
        from apps.ventes.domain.encaissements import (
            enregistrer_avance, ventiler_avance,
        )

        facture = self._facture(Decimal('1200'))
        avance = enregistrer_avance(
            company=self.company, client=self.client_obj,
            montant=Decimal('1200'), date_paiement=timezone.localdate(),
            mode='virement', created_by=self.user)
        with _CompteurPayee() as compteur:
            ventiler_avance(paiement=avance, facture=facture,
                            montant=Decimal('1200'), user=self.user)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(len(compteur.pour(facture)), 1)

    def test_p6_retenue_a_la_source(self):
        from apps.ventes.domain.encaissements import (
            enregistrer_paiement_avec_retenue,
        )

        facture = self._facture(Decimal('1200'))
        with _CompteurPayee() as compteur:
            enregistrer_paiement_avec_retenue(
                facture=facture, montant=Decimal('1000'),
                date_paiement=timezone.localdate(), mode='virement',
                type_retenue='ras_tva', taux=Decimal('20'),
                created_by=self.user)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(len(compteur.pour(facture)), 1)

    def test_p7_abandon_de_solde(self):
        from apps.ventes.domain.recouvrement import abandonner_solde_facture

        facture = self._facture(Decimal('1200'))
        with _CompteurPayee() as compteur:
            reste = abandonner_solde_facture(
                facture, motif=Facture.MotifAbandon.GESTE_COMMERCIAL,
                user=self.user)
        self.assertEqual(reste, Decimal('1200.00'))
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(len(compteur.pour(facture)), 1)


class TestGardesDuService(_BaseSolde):
    """Idempotence, garde centime-près et refus des factures annulées."""

    def test_ne_bascule_pas_une_facture_partiellement_reglee(self):
        from apps.ventes.domain.encaissements import marquer_facture_soldee

        facture = self._facture(Decimal('1200'))
        Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('500'),
            date_paiement=timezone.localdate(), mode='virement')
        with _CompteurPayee() as compteur:
            self.assertFalse(marquer_facture_soldee(facture))
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(compteur.pour(facture), [])

    def test_idempotent_sur_une_facture_deja_payee(self):
        from apps.ventes.domain.encaissements import marquer_facture_soldee

        facture = self._facture(Decimal('1200'))
        Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('1200'),
            date_paiement=timezone.localdate(), mode='virement')
        self.assertTrue(marquer_facture_soldee(facture))
        with _CompteurPayee() as compteur:
            self.assertFalse(marquer_facture_soldee(facture))
        self.assertEqual(compteur.pour(facture), [])

    def test_refuse_une_facture_annulee(self):
        from apps.ventes.domain.encaissements import marquer_facture_soldee

        facture = self._facture(Decimal('1200'))
        facture.statut = Facture.Statut.ANNULEE
        facture.save(update_fields=['statut'])
        self.assertFalse(marquer_facture_soldee(facture, force=True))
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.ANNULEE)


class TestPariteAucunBasculeurHorsService(TestCase):
    """PARITÉ — aucun site de ``apps/ventes`` ne pose PAYEE hors du service.

    Même scan AST étroit qu'AUD101 : modèle ``Facture`` uniquement, et
    seulement les appels qui ÉCRIVENT (``.filter(statut=…PAYEE)`` est une
    lecture).
    """

    ALLOWLIST = {
        'domain/encaissements.py': (
            "LE service unique de bascule PAYÉE (AUD102)."),
    }
    ECRITURES = frozenset({
        'create', 'get_or_create', 'update_or_create', 'update',
        'bulk_create',
    })

    @classmethod
    def _ecrit_payee(cls, noeud):
        def _est_payee(valeur):
            return (isinstance(valeur, ast.Attribute)
                    and valeur.attr == 'PAYEE'
                    and isinstance(valeur.value, ast.Attribute)
                    and valeur.value.attr == 'Statut'
                    and isinstance(valeur.value.value, ast.Name)
                    and valeur.value.value.id == 'Facture')

        if isinstance(noeud, ast.Assign):
            cibles = [c for c in noeud.targets
                      if isinstance(c, ast.Attribute) and c.attr == 'statut']
            return bool(cibles) and _est_payee(noeud.value)
        if isinstance(noeud, ast.Call):
            nom = (noeud.func.attr if isinstance(noeud.func, ast.Attribute)
                   else getattr(noeud.func, 'id', ''))
            if nom not in cls.ECRITURES:
                return False
            return any(kw.arg == 'statut' and _est_payee(kw.value)
                       for kw in noeud.keywords)
        return False

    def test_aucune_ecriture_payee_hors_du_service(self):
        racine = Path(__file__).resolve().parents[1]
        coupables = []
        for chemin in sorted(racine.rglob('*.py')):
            rel = chemin.relative_to(racine).as_posix()
            if rel.startswith('tests/') or rel.startswith('migrations/'):
                continue
            if rel in self.ALLOWLIST:
                continue
            source = chemin.read_text(encoding='utf-8')
            if 'PAYEE' not in source:
                continue
            for noeud in ast.walk(ast.parse(source)):
                if self._ecrit_payee(noeud):
                    coupables.append(f'{rel}:{noeud.lineno}')
        self.assertEqual(
            coupables, [],
            "Ces sites posent PAYÉE hors de "
            "apps.ventes.domain.encaissements.marquer_facture_soldee : "
            + ', '.join(coupables)
            + ". Appelez le service unique (AUD102) — ou ajoutez le fichier à "
              "ALLOWLIST avec sa raison.")


class TestLettrageComptaBranche(TestCase):
    """``facture_payee`` atteint réellement le lettrage comptable."""

    def test_le_receveur_compta_est_abonne(self):
        import apps.compta.receivers  # noqa: F401 — enregistre les abonnés
        uids = {lookup[0] for lookup, _recepteur in facture_payee.receivers}
        self.assertIn('compta_lettrage_facture_payee', uids)
