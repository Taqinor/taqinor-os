"""ATOT5 (C-ATOT-003) — chaque tranche d'échéancier est identifiée par sa CLÉ
(`Facture.cle_tranche`) au lieu de sa position, et le solde se calcule net
des avoirs, borné à > 0 : annuler une tranche re-facture la BONNE, et un
solde nul ou négatif répond 400 au lieu de 500.

Rejoue la sonde V1 TFAC-3 : aujourd'hui, acompte + matériel émis, acompte
annulé, `generer-facture` = « Livraison du matériel 60 % » 90 000 (une
seconde fois) ; et une révision à la baisse fait 500
(`ck_facture_montants_positifs`). Endpoint réel, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_tranche_par_cle"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]
#: Échéancier résidentiel par défaut 30/60/10 sur 150 000 TTC.
ATTENDU = [('acompte', 'Acompte', Decimal('45000.00')),
           ('materiel', 'Livraison du matériel', Decimal('90000.00')),
           ('solde', 'Solde', Decimal('15000.00'))]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TrancheParCleTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ATOT5 Co', slug=f'atot5-co-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Tranche', prenom='ATOT5',
            email=f'atot5-{_nxt()}@example.invalid')
        self.user = User.objects.create_user(
            username=f'atot5_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ATOT5-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel')
        self.ligne = LigneDevis.objects.create(
            devis=devis, designation='Centrale PV', quantite=Decimal('1'),
            prix_unitaire=Decimal('125000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        return devis

    def _generer(self, devis):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/',
            {}, format='json')

    def _actives(self, devis):
        from apps.ventes.models import Facture
        return list(Facture.objects.filter(devis=devis).exclude(
            statut=Facture.Statut.ANNULEE).order_by('id'))

    def test_annuler_tranche_k_puis_regenerer(self):
        from apps.ventes.models import Facture
        for k in range(3):
            with self.subTest(k=k):
                devis = self._devis()
                emises = []
                for _ in range(k + 1):
                    r = self._generer(devis)
                    self.assertEqual(r.status_code, 201, r.data)
                    emises.append(r.data['id'])
                Facture.objects.filter(pk=emises[k]).update(
                    statut=Facture.Statut.ANNULEE)
                r = self._generer(devis)
                self.assertEqual(r.status_code, 201, r.data)
                cle, libelle, ttc = ATTENDU[k]
                facture = Facture.objects.get(pk=r.data['id'])
                self.assertEqual(facture.cle_tranche, cle)
                self.assertTrue(facture.libelle.startswith(libelle),
                                facture.libelle)
                self.assertEqual(Decimal(str(facture.total_ttc)), ttc)
                # On termine l'échéancier : une seule facture active par clé
                # et Σ actives == total du devis.
                while True:
                    r = self._generer(devis)
                    if r.status_code != 201:
                        self.assertEqual(r.status_code, 400, r.data)
                        break
                actives = self._actives(devis)
                cles = [f.cle_tranche for f in actives]
                self.assertEqual(sorted(cles), sorted(c for c, _, _ in ATTENDU))
                self.assertEqual(
                    sum((Decimal(str(f.total_ttc)) for f in actives),
                        Decimal('0')), Decimal('150000.00'))

    def test_revision_baisse_solde_nul_400(self):
        from apps.ventes.models import Avoir, Facture
        devis = self._devis()
        for _ in range(2):
            r = self._generer(devis)
            self.assertEqual(r.status_code, 201, r.data)
        materiel = self._actives(devis)[-1]
        # V2 : 100 000 HT (120 000 TTC) ; avoir de révision 15 000 TTC.
        self.ligne.prix_unitaire = Decimal('100000')
        self.ligne.save(update_fields=['prix_unitaire'])
        Avoir.objects.create(
            company=self.company, reference=f'AV-ATOT5-{_nxt()}',
            facture=materiel, client=self.client_obj,
            statut=Avoir.Statut.EMISE, taux_tva=Decimal('20.00'),
            montant_ht=Decimal('12500.00'), montant_tva=Decimal('2500.00'),
            montant_ttc=Decimal('15000.00'), motif='Révision V2')
        avant = Facture.objects.count()
        r = self._generer(devis)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('soldé', r.data['detail'])
        self.assertEqual(Facture.objects.count(), avant)

    def test_solde_net_des_avoirs(self):
        from apps.ventes.models import Avoir, Facture
        devis = self._devis()
        for _ in range(2):
            self._generer(devis)
        materiel = self._actives(devis)[-1]
        Avoir.objects.create(
            company=self.company, reference=f'AV-ATOT5-{_nxt()}',
            facture=materiel, client=self.client_obj,
            statut=Avoir.Statut.EMISE, taux_tva=Decimal('20.00'),
            montant_ht=Decimal('5000.00'), montant_tva=Decimal('1000.00'),
            montant_ttc=Decimal('6000.00'), motif='Geste')
        r = self._generer(devis)
        self.assertEqual(r.status_code, 201, r.data)
        solde = Facture.objects.get(pk=r.data['id'])
        self.assertEqual(solde.cle_tranche, 'solde')
        self.assertEqual(Decimal(str(solde.total_ttc)), Decimal('21000.00'))

    def _facture_emise(self):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-ATOT35-{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            montant_ht=Decimal('10000.00'), montant_tva=Decimal('2000.00'),
            montant_ttc=Decimal('12000.00'))

    def _put_formulaire(self, facture, **surcharge):
        # Forme exacte de `FactureForm.jsx::handleSubmit` → `updateFacture`
        # (PUT de l'en-tête, valeurs telles que relues du serveur).
        corps = {
            'client': self.client_obj.id, 'bon_commande': None,
            'statut': facture.statut, 'date_echeance': None,
            'date_livraison': None, 'conditions_paiement': '',
            'taux_tva': '20.00', 'remise_globale': '0.00',
            'statut_teledeclaration': facture.statut_teledeclaration,
            'note': None, 'reference_commande_client': '',
        }
        corps.update(surcharge)
        return self.api.put(
            f'/api/django/ventes/factures/{facture.id}/', corps,
            format='json')

    def test_put_formulaire_inchange_sur_facture_emise_passe(self):
        """ATOT35 (C-AMET-001) — le PUT du formulaire sans modification
        d'une facture ÉMISE passe en 200 ; l'argent reste octet-identique."""
        facture = self._facture_emise()
        r = self._put_formulaire(facture)
        self.assertEqual(r.status_code, 200, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.taux_tva, Decimal('20.00'))
        self.assertEqual(facture.remise_globale, Decimal('0'))
        self.assertEqual(facture.montant_ttc, Decimal('12000.00'))
        self.assertEqual(facture.statut, 'emise')

    def test_put_formulaire_remise_modifiee_sur_facture_emise_400(self):
        """ATOT35 — une VALEUR d'argent qui change reste refusée (avoir)."""
        facture = self._facture_emise()
        r = self._put_formulaire(facture, remise_globale='5')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Montant figé', str(r.data))
        facture.refresh_from_db()
        self.assertEqual(facture.remise_globale, Decimal('0'))
