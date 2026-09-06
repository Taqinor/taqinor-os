"""AUD135 — remise d'encaissement terrain : un même paiement pouvait être
déclaré dans plusieurs remises, et le verrou annoncé après clôture n'existait pas.

`LigneRemiseEncaissement.Meta.unique_together = [('remise','paiement')]` :
l'unicité était PAR REMISE, jamais par paiement — rien n'empêchait le même
Paiement d'apparaître dans N remises, et `montant_lignes` le comptait dans
chacune. Le docstring de la ligne affirmait « Une fois la remise clôturée, ses
lignes sont VERROUILLÉES (…) appliqué côté service » : aucun service ne
l'appliquait. Et `perform_create` n'exigeait pas que le paiement soit en
espèces ou par chèque, contrairement au docstring du modèle.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import (
    Facture, LigneRemiseEncaissement, Paiement, RemiseEncaissement,
)

User = get_user_model()

URL = '/api/django/ventes/remises-encaissement/'


class TestAud135RemiseEncaissement(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='aud135-co', defaults={'nom': 'AUD135 Co'})[0]
        self.user = User.objects.create_user(
            username='aud135_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client AUD135',
            telephone='+212600000135')
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD135-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), libelle='Prestation',
            montant_ht=Decimal('50000.00'))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _paiement(self, montant='15000.00', mode='cheque', **kwargs):
        return Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal(montant), mode=mode,
            date_paiement=date.today(), created_by=self.user, **kwargs)

    def _creer_remise(self, paiements, montant_declare='15000.00'):
        # `technicien` est un champ obligatoire du contrat XFSM19 (FK non
        # nullable, PROTECT) : l'écran l'envoie explicitement — l'omettre ici
        # rendait VERT pour la mauvaise raison les cas « virement refusé » et
        # « paiement rejeté » (400 sur le champ manquant, jamais sur le motif).
        return self.api.post(URL, {
            'technicien': self.user.id,
            'date_collecte': date.today().isoformat(),
            'montant_declare': montant_declare,
            'lignes': [{'paiement': p.id} for p in paiements],
        }, format='json')

    # ── (1) unicité par PAIEMENT, pas par remise ─────────────────────────
    def test_deuxieme_remise_sur_le_meme_paiement_est_refusee(self):
        paiement = self._paiement()
        r1 = self._creer_remise([paiement])
        self.assertEqual(r1.status_code, 201, r1.data)

        r2 = self._creer_remise([paiement])
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertIn('lignes', r2.data)
        # Le message NOMME la remise déjà porteuse.
        self.assertIn(
            RemiseEncaissement.objects.first().reference,
            str(r2.data['lignes']))
        # Aucune seconde remise n'a été créée au passage.
        self.assertEqual(RemiseEncaissement.objects.count(), 1)
        self.assertEqual(
            LigneRemiseEncaissement.objects.filter(paiement=paiement).count(),
            1)

    def test_la_contrainte_base_refuse_meme_en_ecriture_directe(self):
        paiement = self._paiement()
        r1 = RemiseEncaissement.objects.create(
            company=self.company, technicien=self.user, reference='REM-A',
            date_collecte=date.today(), montant_declare=Decimal('15000.00'))
        r2 = RemiseEncaissement.objects.create(
            company=self.company, technicien=self.user, reference='REM-B',
            date_collecte=date.today(), montant_declare=Decimal('15000.00'))
        LigneRemiseEncaissement.objects.create(remise=r1, paiement=paiement)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LigneRemiseEncaissement.objects.create(
                    remise=r2, paiement=paiement)

    # ── (2) éligibilité du mode et du statut ─────────────────────────────
    def test_un_paiement_par_virement_est_refuse(self):
        paiement = self._paiement(mode='virement')
        resp = self._creer_remise([paiement])
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(RemiseEncaissement.objects.count(), 0)

    def test_un_paiement_rejete_est_refuse(self):
        paiement = self._paiement()
        paiement.statut = Paiement.Statut.REJETE
        paiement.save(update_fields=['statut'])
        resp = self._creer_remise([paiement])
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_especes_et_cheque_restent_acceptes(self):
        especes = self._paiement(montant='500.00', mode='especes')
        cheque = self._paiement(montant='15000.00', mode='cheque')
        resp = self._creer_remise([especes, cheque],
                                  montant_declare='15500.00')
        self.assertEqual(resp.status_code, 201, resp.data)
        remise = RemiseEncaissement.objects.get()
        self.assertEqual(remise.lignes.count(), 2)
        self.assertEqual(remise.montant_lignes, Decimal('15500.00'))
        self.assertEqual(remise.ecart, Decimal('0.00'))

    # ── (3) le verrou post-clôture, RÉEL ─────────────────────────────────
    def test_modifier_une_ligne_d_une_remise_cloturee_est_refuse(self):
        paiement = self._paiement()
        self.assertEqual(self._creer_remise([paiement]).status_code, 201)
        remise = RemiseEncaissement.objects.get()
        cloture = self.api.post(f'{URL}{remise.id}/cloturer/', {},
                                format='json')
        self.assertEqual(cloture.status_code, 200, cloture.data)

        remise.refresh_from_db()
        ligne = remise.lignes.get()
        ligne.remise = remise  # recharge le statut clôturé
        with self.assertRaises(DjangoValidationError):
            ligne.save()
        with self.assertRaises(DjangoValidationError):
            ligne.delete()

    def test_patch_sur_une_remise_cloturee_est_refuse(self):
        paiement = self._paiement()
        self.assertEqual(self._creer_remise([paiement]).status_code, 201)
        remise = RemiseEncaissement.objects.get()
        self.api.post(f'{URL}{remise.id}/cloturer/', {}, format='json')

        resp = self.api.patch(
            f'{URL}{remise.id}/', {'montant_declare': '99999.00'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        remise.refresh_from_db()
        self.assertEqual(remise.montant_declare, Decimal('15000.00'))

    def test_une_remise_ouverte_reste_modifiable(self):
        paiement = self._paiement()
        self.assertEqual(self._creer_remise([paiement]).status_code, 201)
        remise = RemiseEncaissement.objects.get()
        resp = self.api.patch(
            f'{URL}{remise.id}/', {'note': 'collecte du matin'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
