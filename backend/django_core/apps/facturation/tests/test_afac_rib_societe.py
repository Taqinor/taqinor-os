"""AFAC59 (C-AFAC-051) — le RIB de l'acompte (e-mail de confirmation
d'acceptation, charge utile post-signature) vient du profil de la SOCIÉTÉ
émettrice (``parametres.selectors.company_identity``), plus du réglage global
jamais défini ``settings.COMPANY_RIB``.

Rejoue la sonde FEVT-4 (RIB posé sur le profil : bloc sans « par virement
sur », `payload rib = ''`). Services réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_rib_societe"
"""
from decimal import Decimal

from django.test import TestCase, override_settings

RIB = '011780000012345678901234'
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class RibSocieteTests(TestCase):
    def _devis(self, rib=''):
        from apps.crm.models import Client
        from apps.parametres.models import CompanyProfile
        from apps.ventes.models import Devis, LigneDevis
        from authentication.models import Company
        n = _nxt()
        company = Company.objects.create(nom=f'AFAC59 {n}', slug=f'afac59-{n}')
        profile = CompanyProfile.get(company=company)
        profile.rib = rib
        profile.save()
        client = Client.objects.create(
            company=company, nom='Client', prenom='AFAC59',
            email=f'afac59-{n}@example.invalid')
        devis = Devis.objects.create(
            company=company, reference=f'DEV-AFAC59-{n}', client=client,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, designation='Centrale', quantite=Decimal('1'),
            prix_unitaire=Decimal('10000'), remise=Decimal('0'),
            taux_tva=Decimal('20'))
        return devis

    def test_bloc_acompte_rib_societe(self):
        from apps.ventes.domain.cycle_vie import _acceptance_deposit_block
        bloc = _acceptance_deposit_block(self._devis(rib=RIB))
        self.assertIn(f'par virement sur : {RIB}', bloc)

    def test_payload_rib_societe(self):
        from apps.ventes.public.paiement_views import _deposit_success_payload
        payload = _deposit_success_payload(self._devis(rib=RIB), 'jeton')
        self.assertEqual(payload['rib'], RIB)

    def test_deux_societes_deux_rib(self):
        from apps.ventes.domain.cycle_vie import _acceptance_deposit_block
        from apps.ventes.public.paiement_views import _deposit_success_payload
        avec = self._devis(rib=RIB)
        sans = self._devis(rib='')
        self.assertEqual(_deposit_success_payload(sans, 'j')['rib'], '')
        self.assertNotIn('par virement sur', _acceptance_deposit_block(sans))
        self.assertEqual(_deposit_success_payload(avec, 'j')['rib'], RIB)

    def test_vnt63_acompte_prevu_egal_a_la_facture_d_acompte(self):
        """VNT63 — une fois le brouillon d'acompte posé, le mail et la page
        lisent CE montant (1re tranche du plan), jamais la tranche suivante."""
        from apps.ventes.domain.cycle_vie import _acceptance_deposit_block
        from apps.ventes.domain.facturation_vente import facturer_vente
        from apps.ventes.public.paiement_views import _deposit_success_payload
        from django.contrib.auth import get_user_model
        devis = self._devis(rib=RIB)
        user = get_user_model().objects.create_user(
            username=f'afac59-vnt63-{_nxt()}', password='x',
            role_legacy='responsable', company=devis.company)
        facture, _p = facturer_vente(devis, nature='acompte', user=user)
        ttc = Decimal(str(facture.total_ttc))
        self.assertGreater(ttc, Decimal('0'))
        payload = _deposit_success_payload(devis, 'jeton')
        self.assertEqual(Decimal(payload['acompte_ttc']), ttc)
        montant = f'{ttc:,.2f}'.replace(',', ' ') + ' MAD'
        self.assertIn(montant, _acceptance_deposit_block(devis))

    @override_settings(ENTREPRISE_TELEPHONE='+212599999999', ENTREPRISE_ADRESSE='Rue globale 1')
    def test_identite_sans_repli_global(self):
        """AMSG41 (C-AMSG-028, D-APDF) — une société au profil sans téléphone
        ni adresse fige ces champs VIDES, jamais les ``ENTREPRISE_*`` globaux ;
        la première société garde les siens."""
        from apps.parametres.models import CompanyProfile
        from apps.ventes.utils.pdf import _company_context, identite_vendeur_courante
        premiere, seconde = self._devis().company, self._devis().company
        CompanyProfile.objects.filter(company=premiere).update(
            nom='Première SARL', telephone='+212500000001', adresse='Rue A')
        CompanyProfile.objects.filter(company=seconde).update(
            nom='Seconde SARL', telephone='', adresse='')
        for identite in (identite_vendeur_courante(seconde), _company_context(seconde)):
            self.assertEqual(identite['entreprise_telephone'], '')
            self.assertEqual(identite['entreprise_adresse'], '')
            self.assertEqual(identite['entreprise_nom'], 'Seconde SARL')
        a = identite_vendeur_courante(premiere)
        self.assertEqual((a['entreprise_nom'], a['entreprise_telephone'], a['entreprise_adresse']),
                         ('Première SARL', '+212500000001', 'Rue A'))
