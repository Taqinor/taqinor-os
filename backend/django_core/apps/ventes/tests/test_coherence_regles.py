"""QA-COHERENCE — chaque règle du registre : un cas qui TIRE, un cas qui ne
tire PAS, sur des objets construits par l'ORM.

Aucune dépendance réseau/MinIO : les règles « étude » lisent des données de
document INJECTÉES dans le contexte (``ContexteAudit.injecter_donnees``) —
le vrai constructeur n'est jamais appelé ici.
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.coherence import regles_etude
from apps.ventes.coherence.moteur import _Ctx
from apps.ventes.coherence.registre import REGISTRE, charger_regles
from apps.ventes.domain.argent import Totaux
from apps.ventes.models import (Avoir, BonCommande, Devis, Facture,
                                LigneDevis, LigneFacture)
from authentication.models import Company

User = get_user_model()
_CTR = [0]


def _n():
    _CTR[0] += 1
    return _CTR[0]


class _Base(TestCase):
    def setUp(self):
        charger_regles()
        self.company = Company.objects.create(
            nom='Cohérence Co', slug=f'coh-regles-{_n()}')
        self.user = User.objects.create_user(
            username=f'coh_{_n()}', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Coh', prenom='Client',
            telephone=f'+2126000{_n():05d}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit PV', sku=f'COH-{_n()}',
            prix_vente=Decimal('10000'), quantite_stock=100)
        self.ctx = _Ctx(self.company)

    def devis(self, statut=Devis.Statut.ACCEPTE, *, ligne=True, **kw):
        kw.setdefault('date_acceptation',
                      datetime.date(2026, 9, 10)
                      if statut == Devis.Statut.ACCEPTE else None)
        d = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-COH-{_n()}',
            statut=statut, taux_tva=Decimal('20'), **kw)
        if ligne:
            LigneDevis.objects.create(
                devis=d, produit=self.produit, designation='Kit PV',
                quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
                taux_tva=Decimal('20'))
        return Devis.objects.prefetch_related('lignes__produit').get(pk=d.pk)

    def facture(self, **kw):
        kw.setdefault('statut', Facture.Statut.BROUILLON)
        return Facture.objects.create(
            company=self.company, client=self.client_obj,
            reference=f'FAC-COH-{_n()}', **kw)

    def run_rule(self, rule_id, obj, ctx=None):
        r = REGISTRE[rule_id]
        return r.check(r, obj, ctx or self.ctx)


# ── Documents ───────────────────────────────────────────────────────────────
class TestReglesDocuments(_Base):
    def test_totaux_devis_propre(self):
        self.assertEqual(self.run_rule('DOC_TOTAUX_DEVIS', self.devis()), [])

    def test_totaux_devis_ttc_faux(self):
        devis = self.devis()
        faux = Totaux(
            ht_brut=Decimal('9000.00'), remise=Decimal('0'),
            ht_net=Decimal('9000.00'),
            tva_par_taux=({'taux': Decimal('20'), 'base': Decimal('9000.00'),
                           'montant': Decimal('1800.00')},),
            tva=Decimal('1800.00'), ttc=Decimal('11000.00'),
            ttc_affiche=Decimal('11000.00'))
        with mock.patch('apps.ventes.domain.argent.totaux',
                        return_value=faux):
            out = self.run_rule('DOC_TOTAUX_DEVIS', devis)
        etages = {v.valeurs['etage'] for v in out}
        self.assertIn('ttc', etages)
        self.assertIn('somme_lignes', etages)
        self.assertTrue(all(v.company_id == self.company.pk for v in out))

    def _data_imprimee(self, ttc):
        return {'discount_pct': 0.0, 'totaux_all': {
            'ht_brut': 10000.0, 'remise': 0.0, 'ht_net': 10000.0,
            'tva': 2000.0, 'ttc': ttc,
            'tva_par_taux': [{'taux': 20.0, 'montant': 2000.0,
                              'ht_net': 10000.0}]}}

    def test_totaux_imprimes_coherents(self):
        devis = self.devis()
        self.ctx.injecter_donnees(devis, self._data_imprimee(12000.0))
        self.assertEqual(self.run_rule('DOC_TOTAUX_IMPRIMES', devis), [])

    def test_totaux_imprimes_faux(self):
        devis = self.devis()
        self.ctx.injecter_donnees(devis, self._data_imprimee(12500.0))
        out = self.run_rule('DOC_TOTAUX_IMPRIMES', devis)
        etages = {v.valeurs.get('etage') for v in out}
        self.assertIn('ttc', etages)
        self.assertTrue(any(v.cle.get('etage') == 'ttc_modele_vs_imprime'
                            for v in out))

    def test_totaux_facture_lignes_ok(self):
        f = self.facture(taux_tva=Decimal('20'))
        LigneFacture.objects.create(
            facture=f, produit=self.produit, designation='Kit',
            quantite=Decimal('2'), prix_unitaire=Decimal('500'),
            taux_tva=Decimal('20'))
        self.assertEqual(self.run_rule('DOC_TOTAUX_FACTURE', f), [])

    def test_totaux_facture_figee_incoherente(self):
        f = self.facture(montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
                         montant_ttc=Decimal('1300'))
        out = self.run_rule('DOC_TOTAUX_FACTURE', f)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].attendu, 1200.0)

    def test_totaux_facture_figee_coherente(self):
        f = self.facture(montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
                         montant_ttc=Decimal('1200.01'))
        self.assertEqual(self.run_rule('DOC_TOTAUX_FACTURE', f), [])

    def test_facturation_depasse_devis(self):
        devis = self.devis()
        self.facture(devis=devis, montant_ht=Decimal('10000'),
                     montant_tva=Decimal('2000'), montant_ttc=Decimal('12000'))
        self.assertEqual(
            self.run_rule('DOC_FACTURATION_DEPASSE_DEVIS', devis, _Ctx(
                self.company)), [])
        f2 = self.facture(devis=devis, montant_ht=Decimal('5000'),
                          montant_tva=Decimal('1000'),
                          montant_ttc=Decimal('6000'))
        out = self.run_rule('DOC_FACTURATION_DEPASSE_DEVIS', devis,
                            _Ctx(self.company))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].valeurs['net_facture'], 18000.0)
        # Un avoir actif du même montant rend le facturé net légitime.
        Avoir.objects.create(
            company=self.company, reference=f'AV-COH-{_n()}', facture=f2,
            client=self.client_obj, montant_ht=Decimal('5000'),
            montant_tva=Decimal('1000'), montant_ttc=Decimal('6000'))
        self.assertEqual(
            self.run_rule('DOC_FACTURATION_DEPASSE_DEVIS', devis,
                          _Ctx(self.company)), [])

    def test_lien_devis_non_accepte(self):
        devis = self.devis(Devis.Statut.ENVOYE)
        BonCommande.objects.create(
            company=self.company, reference=f'BC-COH-{_n()}', devis=devis,
            client=self.client_obj)
        devis = Devis.objects.select_related('bon_commande').get(pk=devis.pk)
        out = self.run_rule('DOC_LIEN_DEVIS_NON_ACCEPTE', devis)
        self.assertEqual(len(out), 1)
        self.assertIn('bon_commande', out[0].valeurs)

    def test_lien_devis_accepte_ou_bc_annule(self):
        accepte = self.devis()
        BonCommande.objects.create(
            company=self.company, reference=f'BC-COH-{_n()}', devis=accepte,
            client=self.client_obj)
        self.assertEqual(
            self.run_rule('DOC_LIEN_DEVIS_NON_ACCEPTE', accepte), [])
        envoye = self.devis(Devis.Statut.ENVOYE)
        BonCommande.objects.create(
            company=self.company, reference=f'BC-COH-{_n()}', devis=envoye,
            client=self.client_obj, statut=BonCommande.Statut.ANNULE)
        self.assertEqual(
            self.run_rule('DOC_LIEN_DEVIS_NON_ACCEPTE', envoye), [])

    def test_accepte_sans_date(self):
        self.assertEqual(len(self.run_rule(
            'DOC_ACCEPTE_SANS_DATE',
            self.devis(date_acceptation=None))), 1)
        self.assertEqual(self.run_rule('DOC_ACCEPTE_SANS_DATE',
                                       self.devis()), [])

    def test_validite_avant_creation(self):
        creation = timezone.make_aware(datetime.datetime(2026, 9, 10, 12, 0))
        avant = self.devis(date_validite=datetime.date(2026, 9, 1))
        apres = self.devis(date_validite=datetime.date(2026, 10, 10))
        Devis.objects.filter(pk__in=[avant.pk, apres.pk]).update(
            date_creation=creation)
        avant.refresh_from_db()
        apres.refresh_from_db()
        self.assertEqual(len(self.run_rule('DOC_VALIDITE_AVANT_CREATION',
                                           avant)), 1)
        self.assertEqual(self.run_rule('DOC_VALIDITE_AVANT_CREATION', apres),
                         [])

    def test_echeance_avant_emission(self):
        mauvaise = self.facture(date_echeance=datetime.date(2026, 9, 1))
        annulee = self.facture(date_echeance=datetime.date(2026, 9, 1),
                               statut=Facture.Statut.ANNULEE)
        bonne = self.facture(date_echeance=datetime.date(2026, 10, 10))
        Facture.objects.filter(
            pk__in=[mauvaise.pk, annulee.pk, bonne.pk]).update(
            date_emission=datetime.date(2026, 9, 10))
        for f in (mauvaise, annulee, bonne):
            f.refresh_from_db()
        self.assertEqual(len(self.run_rule('DOC_ECHEANCE_AVANT_EMISSION',
                                           mauvaise)), 1)
        self.assertEqual(self.run_rule('DOC_ECHEANCE_AVANT_EMISSION',
                                       annulee), [])
        self.assertEqual(self.run_rule('DOC_ECHEANCE_AVANT_EMISSION', bonne),
                         [])

    def test_designation_devis(self):
        devis = self.devis()
        self.assertEqual(self.run_rule('DOC_DESIGNATION_DEVIS', devis), [])
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='  ',
            quantite=Decimal('1'), prix_unitaire=Decimal('10'))
        devis = Devis.objects.prefetch_related('lignes').get(pk=devis.pk)
        self.assertEqual(len(self.run_rule('DOC_DESIGNATION_DEVIS', devis)),
                         1)

    def test_designation_facture(self):
        f = self.facture()
        LigneFacture.objects.create(
            facture=f, produit=self.produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('10'))
        self.assertEqual(self.run_rule('DOC_DESIGNATION_FACTURE', f), [])
        LigneFacture.objects.create(
            facture=f, produit=self.produit, designation='',
            quantite=Decimal('1'), prix_unitaire=Decimal('10'))
        self.assertEqual(len(self.run_rule('DOC_DESIGNATION_FACTURE', f)), 1)

    def test_ligne_sans_prix(self):
        envoye = self.devis(Devis.Statut.ENVOYE)
        brouillon = self.devis(Devis.Statut.BROUILLON)
        for d in (envoye, brouillon):
            LigneDevis.objects.create(
                devis=d, produit=self.produit, designation='Pompe',
                quantite=Decimal('1'), prix_unitaire=None)
        envoye = Devis.objects.prefetch_related('lignes').get(pk=envoye.pk)
        brouillon = Devis.objects.prefetch_related('lignes').get(
            pk=brouillon.pk)
        self.assertEqual(len(self.run_rule('DOC_LIGNE_SANS_PRIX', envoye)), 1)
        self.assertEqual(self.run_rule('DOC_LIGNE_SANS_PRIX', brouillon), [])
        self.assertEqual(self.run_rule('DOC_LIGNE_SANS_PRIX', self.devis()),
                         [])


# ── Étude ───────────────────────────────────────────────────────────────────
class TestReglesEtude(_Base):
    def test_i4_repli_1_20(self):
        tire = self.devis(etude_params={
            'factures_mensuelles_reelles': [600] * 12, 'conso_annuelle': 6000})
        propre = self.devis(etude_params={
            'factures_mensuelles_reelles': [600] * 12, 'conso_annuelle': 4800})
        self.assertEqual(len(self.run_rule('ETU_I4_CONSO_REPLI', tire)), 1)
        self.assertEqual(self.run_rule('ETU_I4_CONSO_REPLI', propre), [])

    def test_params_numeriques(self):
        self.assertEqual(len(self.run_rule(
            'ETU_PARAMS_NUMERIQUES',
            self.devis(etude_params={'puissance_kwc': -3}))), 1)
        self.assertEqual(self.run_rule(
            'ETU_PARAMS_NUMERIQUES',
            self.devis(etude_params={'puissance_kwc': 5,
                                     'factures_mensuelles_reelles':
                                         [500] * 12})), [])

    def test_i7_bloc_perime(self):
        tire = self.devis(etude_params={'etude_horaire': {'kwc': 10.65}})
        propre = self.devis(etude_params={'etude_horaire': {'kwc': 10.65}})
        self.ctx.injecter_donnees(tire, {'puissance_kwc': 4.26})
        self.ctx.injecter_donnees(propre, {'puissance_kwc': 10.6})
        self.assertEqual(len(self.run_rule('ETU_I7_BLOC_HORAIRE_PERIME',
                                           tire)), 1)
        self.assertEqual(self.run_rule('ETU_I7_BLOC_HORAIRE_PERIME', propre),
                         [])

    def _devis_i2(self):
        mois = [{'consommation_kwh': 1500, 'autoconsomme_avec_kwh': 500}
                for _ in range(12)]
        devis = self.devis(mode_installation='residentiel', etude_params={
            'etude_horaire': {'annuel': {'consommation_kwh': 18000},
                              'mois': mois}})
        self.ctx.injecter_donnees(devis, {'deux_options': True})
        self.ctx._tarif = {'top_start': 510.0, 'fixed_mois': 40.0,
                           'tranches': None, 'charges_fixes': None,
                           'src': 'test'}
        return devis

    def test_i2_reduction_incompatible(self):
        devis = self._devis_i2()
        page1 = {'coverage_pct': 40, 'pct_cut': 10, 'annual_before': 24000}
        with mock.patch.object(regles_etude, 'couche_imprimee',
                               return_value=page1):
            out = self.run_rule('ETU_I2_REDUCTION_VS_COUVERTURE', devis)
        self.assertEqual(len(out), 1)

    def test_i2_reduction_compatible(self):
        devis = self._devis_i2()
        page1 = {'coverage_pct': 40, 'pct_cut': 39, 'annual_before': 24000}
        with mock.patch.object(regles_etude, 'couche_imprimee',
                               return_value=page1):
            self.assertEqual(
                self.run_rule('ETU_I2_REDUCTION_VS_COUVERTURE', devis), [])

    def test_i2_arrondi_des_entiers_imprimes_tolere(self):
        # Prod, 30/09/2026 : −67 % imprimé pour 70 % de couverture, part fixe
        # ≈ 0,011 → sans la marge d'arrondi, borne basse 67,23 : faux positif.
        devis = self._devis_i2()
        page1 = {'coverage_pct': 70, 'pct_cut': 67, 'annual_before': 43636}
        with mock.patch.object(regles_etude, 'couche_imprimee',
                               return_value=page1):
            self.assertEqual(
                self.run_rule('ETU_I2_REDUCTION_VS_COUVERTURE', devis), [])

    def test_i5_facture_actuelle(self):
        ep = {'factures_mensuelles_reelles': [1000] * 12}
        tire = self.devis(mode_installation='industriel', etude_params=ep)
        propre = self.devis(mode_installation='industriel', etude_params=ep)
        self.ctx.injecter_donnees(
            tire, {'savings_method': {'facture_actuelle': 17000}})
        self.ctx.injecter_donnees(
            propre, {'savings_method': {'facture_actuelle': 12500}})
        out = self.run_rule('ETU_I5_FACTURE_ACTUELLE', tire)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].cle, {'figure': 'methode_facture_actuelle'})
        self.assertEqual(self.run_rule('ETU_I5_FACTURE_ACTUELLE', propre), [])

    def test_i6_economies(self):
        ep = {'puissance_kwc': 5}
        tire = self.devis(mode_installation='industriel', etude_params=ep)
        propre = self.devis(mode_installation='industriel', etude_params=ep)
        self.ctx.injecter_donnees(tire, {
            'avec_ok': True, 'eco_a_ann': 30000, 'roi_a': 5,
            'total_avec': 100000,
            'savings_method': {'facture_actuelle': 20000}})
        self.ctx.injecter_donnees(propre, {
            'avec_ok': True, 'eco_a_ann': 10000, 'roi_a': 10,
            'total_avec': 100000,
            'savings_method': {'facture_actuelle': 20000}})
        cas = {v.cle['cas'] for v in self.run_rule('ETU_I6_ECONOMIES', tire)}
        self.assertEqual(cas, {'eco_sup_facture', 'retour'})
        self.assertEqual(self.run_rule('ETU_I6_ECONOMIES', propre), [])

    # Courbe cumulée 25 ans qui croise zéro à 13,4 ans (an 13 : −4 000,
    # an 14 : +6 000), alors que prix ÷ économie = 10 ans (×1,34).
    _COURBE_13_4 = ([-92000, -84000, -76000, -68000, -60000, -52000, -44000,
                     -36000, -28000, -20000, -12000, -9000, -4000, 6000]
                    + [16000 + 10000 * i for i in range(11)])

    def _devis_i6_courbe(self, roi, courbe):
        devis = self.devis(mode_installation='industriel',
                           etude_params={'puissance_kwc': 5})
        self.ctx.injecter_donnees(devis, {
            'avec_ok': True, 'eco_a_ann': 10000, 'roi_a': roi,
            'total_avec': 100000, 'cashflow_avec': courbe,
            'savings_method': {'facture_actuelle': 20000}})
        return devis

    def test_i6_retour_egal_au_croisement_de_la_courbe(self):
        # Prod 30/09/2026 (DEV-202609-0108) : 15,4 ans légitimes pour 11,45
        # ans prix ÷ économie — plus de faux positif.
        devis = self._devis_i6_courbe(13.4, self._COURBE_13_4)
        self.assertEqual(self.run_rule('ETU_I6_ECONOMIES', devis), [])

    def test_i6_retour_different_du_croisement(self):
        devis = self._devis_i6_courbe(12.0, self._COURBE_13_4)
        out = self.run_rule('ETU_I6_ECONOMIES', devis)
        self.assertEqual([v.cle['cas'] for v in out], ['retour'])
        self.assertEqual(out[0].valeurs['croisement_courbe'], 13.4)

    def test_i6_jamais_rembourse(self):
        # « Rentabilisé en 25 ans » imprimé sur une courbe qui finit < 0.
        courbe = [-100000 + 2000 * an for an in range(1, 26)]
        devis = self._devis_i6_courbe(25.0, courbe)
        out = self.run_rule('ETU_I6_ECONOMIES', devis)
        self.assertEqual([v.cle['cas'] for v in out], ['jamais_rembourse'])
        self.assertEqual(out[0].valeurs['cumul_final'], -50000)

    def test_document_numerique(self):
        tire = self.devis(mode_installation='industriel')
        propre = self.devis(mode_installation='industriel')
        self.ctx.injecter_donnees(tire, {'prod_kwh': float('nan'),
                                         'eco_s_ann': -5})
        self.ctx.injecter_donnees(propre, {'prod_kwh': 8000.0,
                                           'eco_s_ann': 5000})
        out = self.run_rule('ETU_DOCUMENT_NUMERIQUE', tire)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].valeurs['negatifs'], ['eco_s_ann'])
        self.assertTrue(out[0].valeurs['nan_inf'])
        self.assertEqual(self.run_rule('ETU_DOCUMENT_NUMERIQUE', propre), [])

    def test_i10_graphe_vs_carte(self):
        ep = {'puissance_kwc': 5}
        tire = self.devis(mode_installation='residentiel', etude_params=ep)
        propre = self.devis(mode_installation='residentiel', etude_params=ep)
        self.ctx.injecter_donnees(tire, {'deux_options': True,
                                         'eco_a_ann': 10000})
        self.ctx.injecter_donnees(propre, {'deux_options': True,
                                           'eco_a_ann': 11950})
        with mock.patch.object(regles_etude, 'couche_imprimee',
                               return_value={'eco_mensuelles_total': 12000}):
            self.assertEqual(len(self.run_rule('ETU_I10_GRAPHE_VS_CARTE',
                                               tire)), 1)
            self.assertEqual(self.run_rule('ETU_I10_GRAPHE_VS_CARTE',
                                           propre), [])

    def test_i8_parite_pdf_proposition(self):
        from apps.ventes.quote_engine.residential import renderer as R
        opts = {'pdf_mode': 'full', 'scenario': 'Sans batterie'}
        pub = {'pdf_mode': 'full'}
        tire = self.devis(mode_installation='residentiel',
                          pdf_render_meta={'options': opts})
        propre = self.devis(mode_installation='residentiel',
                            pdf_render_meta={'options': opts})
        self.ctx.injecter_donnees(tire, {'eco_a_ann': 100}, opts)
        self.ctx.injecter_donnees(tire, {'eco_a_ann': 120}, pub)
        self.ctx.injecter_donnees(propre, {'eco_a_ann': 100}, opts)
        self.ctx.injecter_donnees(propre, {'eco_a_ann': 100}, pub)
        with mock.patch.object(R, 'synthese_economies', return_value=None):
            out = self.run_rule('ETU_I8_PARITE_PDF_PROPOSITION', tire)
            self.assertEqual(len(out), 1)
            self.assertIn('eco_a_ann', out[0].valeurs['ecarts'])
            self.assertEqual(
                self.run_rule('ETU_I8_PARITE_PDF_PROPOSITION', propre), [])


# ── CRM ─────────────────────────────────────────────────────────────────────
class TestRegleCrm(_Base):
    def test_signe_sans_devis_accepte(self):
        fantome = Lead.objects.create(company=self.company, nom='Fantôme',
                                      stage=stages.SIGNED)
        signe = Lead.objects.create(company=self.company, nom='Signé',
                                    stage=stages.SIGNED)
        self.devis(lead=signe)
        Lead.objects.create(company=self.company, nom='Odoo',
                            stage=stages.SIGNED,
                            source=Lead.Source.ODOO_IMPORT_TEST)
        Lead.objects.create(company=self.company, nom='Perdu',
                            stage=stages.SIGNED, perdu=True)
        Lead.objects.create(company=self.company, nom='Envoyé',
                            stage=stages.QUOTE_SENT)
        autre = Company.objects.create(nom='Autre Co',
                                       slug=f'coh-autre-{_n()}')
        Lead.objects.create(company=autre, nom='Autre', stage=stages.SIGNED)
        out = self.run_rule('CRM_SIGNE_SANS_DEVIS_ACCEPTE', self.company)
        self.assertEqual([v.object_id for v in out], [fantome.pk])
        self.assertEqual(out[0].object_type, 'lead')
        self.assertEqual(out[0].company_id, self.company.pk)


# ── Sécurité ────────────────────────────────────────────────────────────────
class TestRegleSecurite(_Base):
    def _compte(self, username, *, company=None, actif=True):
        return User.objects.create_user(
            username=username, password='x', role_legacy='responsable',
            company=company or self.company, is_active=actif)

    @override_settings(DEBUG=False)
    def test_compte_demo_actif_signale_en_production(self):
        actif = self._compte('demo_admin')
        self._compte('demo_resp', actif=False)
        self._compte(f'vrai_{_n()}')
        autre = Company.objects.create(nom='Autre Co',
                                       slug=f'coh-sec-{_n()}')
        self._compte('demo_admin_full', company=autre)
        out = self.run_rule('SEC_COMPTE_DEMO_ACTIF', self.company)
        self.assertEqual([v.object_id for v in out], [actif.pk])
        self.assertEqual(out[0].object_type, 'utilisateur')
        self.assertEqual(out[0].reference, 'demo_admin')
        self.assertEqual(out[0].company_id, self.company.pk)

    @override_settings(DEBUG=True)
    def test_muet_en_developpement(self):
        self._compte('demo_admin')
        self.assertEqual(
            self.run_rule('SEC_COMPTE_DEMO_ACTIF', self.company), [])
