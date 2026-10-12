"""ATOT33 (C-ATOT-021) — le registre de cohérence garde l'argent des
factures : ``AVOIR_DEPASSE_FACTURE``, ``FACTURE_STATUT_RESTE_INCOHERENT``,
``NUMEROTATION_TROUS_DOUBLONS`` (réutilise
``numbering_audit.find_gaps_and_dupes``), et ``DOC_FACTURATION_DEPASSE_DEVIS``
lit les factures CONSOLIDÉES liées par ``FactureSource``.

Objets ORM réels, ``Facture.montant_du`` / ``avoirs_total`` réels, aucun mock.
Test-du-test : retirer la lecture ``FactureSource`` (``_parts_consolidees``)
⇒ ``test_consolidee_comptee`` échoue.
"""
from decimal import Decimal

from apps.ventes.coherence.moteur import _Ctx
from apps.ventes.models import Avoir, Devis, Facture
from apps.ventes.models_facturation import FactureSource
from apps.ventes.tests.test_coherence_regles import _Base, _n


class CoherenceArgentTests(_Base):
    def _facture(self, ttc, **kw):
        ht = (Decimal(ttc) / Decimal('1.2')).quantize(Decimal('0.01'))
        return self.facture(montant_ht=ht, montant_tva=Decimal(ttc) - ht,
                            montant_ttc=Decimal(ttc), **kw)

    def test_avoir_depasse_facture(self):
        f = self._facture('1200')
        self.assertEqual(self.run_rule('AVOIR_DEPASSE_FACTURE', f), [])
        Avoir.objects.create(
            company=self.company, reference=f'AV-ATOT-{_n()}', facture=f,
            client=self.client_obj, montant_ht=Decimal('1250'),
            montant_tva=Decimal('250'), montant_ttc=Decimal('1500'))
        f = Facture.objects.get(pk=f.pk)
        out = self.run_rule('AVOIR_DEPASSE_FACTURE', f)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].valeurs['avoirs_ttc'], 1500.0)
        self.assertEqual(out[0].reference, f.reference)

    def test_facture_payee_avec_reste(self):
        f = self._facture('1200', statut=Facture.Statut.PAYEE)
        out = self.run_rule('FACTURE_STATUT_RESTE_INCOHERENT', f)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].valeurs['montant_du'], 1200.0)
        emise = self._facture('1200', statut=Facture.Statut.EMISE)
        self.assertEqual(
            self.run_rule('FACTURE_STATUT_RESTE_INCOHERENT', emise), [])

    def test_numerotation_trous_doublons(self):
        # Le doublon est impossible en base (``unique_together``) : la
        # fonction pure le détecte (testée par N31) ; ici, le TROU.
        for ref in ('FAC-202610-0001', 'FAC-202610-0002', 'FAC-202610-0004'):
            Facture.objects.create(company=self.company,
                                   client=self.client_obj, reference=ref,
                                   statut=Facture.Statut.BROUILLON)
        out = self.run_rule('NUMEROTATION_TROUS_DOUBLONS', self.company)
        series = [v for v in out if v.reference == 'FAC-202610']
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0].valeurs['manquants'], [3])
        self.assertEqual(series[0].company_id, self.company.pk)

    def test_consolidee_comptee(self):
        devis = self.devis()  # 10 000 HT / 12 000 TTC
        conso = self.facture(montant_ht=Decimal('15000'),
                             montant_tva=Decimal('3000'),
                             montant_ttc=Decimal('18000'))
        FactureSource.objects.create(company=self.company, facture=conso,
                                     devis=devis,
                                     sous_total_ht=Decimal('15000'))
        devis = Devis.objects.get(pk=devis.pk)
        out = self.run_rule('DOC_FACTURATION_DEPASSE_DEVIS', devis,
                            _Ctx(self.company))
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].valeurs['net_facture'], 18000.0,
                               places=2)

    def test_base_saine(self):
        devis = self.devis()
        self.facture(devis=devis, montant_ht=Decimal('10000'),
                     montant_tva=Decimal('2000'), montant_ttc=Decimal('12000'))
        self.assertEqual(self.run_rule('DOC_FACTURATION_DEPASSE_DEVIS', devis,
                                       _Ctx(self.company)), [])

    def test_vnt64_une_chaine_jugee_comme_une_seule_vente(self):
        """VNT64 — V1 (remplacée) et V2 (acceptée) forment UNE vente : la
        règle lit ``plan_facturation`` de la tête et la juge UNE fois.
        7 200 sur V1 + 7 200 sur V2 = 14 400 > 12 000 : signalé sur V2 seule
        (hier : chaque version passait seule, 7 200 ≤ 12 000)."""
        v1 = self.devis()
        v2 = self.devis(version=2, version_parent=v1)
        Devis.objects.filter(pk=v1.pk).update(superseded_by=v2,
                                              is_active=False)
        for devis in (v1, v2):
            self._facture('7200', devis=devis, statut=Facture.Statut.EMISE)
        v1, v2 = Devis.objects.get(pk=v1.pk), Devis.objects.get(pk=v2.pk)
        ctx = _Ctx(self.company)
        self.assertEqual(
            self.run_rule('DOC_FACTURATION_DEPASSE_DEVIS', v1, ctx), [])
        out = self.run_rule('DOC_FACTURATION_DEPASSE_DEVIS', v2, ctx)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].valeurs['net_facture'], 14400.0,
                               places=2)

    def test_vnt87_deux_brouillons_ne_depassent_rien(self):
        """VNT87 — acompte automatique (7 200) + complète (12 000) en
        BROUILLON : PRÉVU, jamais FACTURÉ ⇒ aucune violation ; le contexte
        ne rend que les émises."""
        devis = self.devis()  # 10 000 HT / 12 000 TTC
        self._facture('7200', devis=devis,
                      type_facture=Facture.TypeFacture.ACOMPTE)
        self._facture('12000', devis=devis)
        ctx = _Ctx(self.company)
        self.assertEqual(ctx.factures_actives_du_devis(devis.pk), [])
        self.assertEqual(
            self.run_rule('DOC_FACTURATION_DEPASSE_DEVIS', devis, ctx), [])
        emise = self._facture('12000', devis=devis,
                              statut=Facture.Statut.EMISE)
        self.assertEqual(
            [f.pk for f in _Ctx(self.company).factures_actives_du_devis(
                devis.pk)], [emise.pk])
