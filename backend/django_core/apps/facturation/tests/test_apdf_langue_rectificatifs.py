"""APDF31 (C-APDF-018, D-APDF-3 a — tranché le 08/10/2026) — langue des
documents de facturation dérivés pour un client arabe :

* TRADUITS (dictionnaire de la facture) : avoir, note de débit, reçu,
  lettre de relance → ``<html lang="ar" dir="rtl">``, ≥ 50 caractères
  arabes, libellés structurels arabes ;
* en FRANÇAIS avec mention de repli IMPRIMÉE : bon de commande, pro-forma ;
* société ``langue_repli='en'`` : facture française + mention de repli
  (jamais silencieux).

Rejoue la sonde PLANG-6 (reçu, BC, lettre de relance : 0 caractère arabe ;
avoir / ND ``<html lang="fr">`` en dur). Générateurs RÉELS ; seul l'upload
MinIO est neutralisé et le HTML capturé autour du vrai ``_render_html``.

Test-du-test : retirer ``_contexte_langue`` de ``generate_avoir_pdf`` ⇒
``test_avoir_ar`` échoue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_apdf_langue_rectificatifs"
"""
import re
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

ARABE = re.compile('[؀-ۿ]')
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class LangueRectificatifsTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        from apps.ventes.utils import pdf as pdf_mod
        from authentication.models import Company
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'APDF31 {n}', slug=f'apdf31-{n}')
        self.client_ar = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Hind',
            email=f'apdf31-ar-{n}@example.invalid', langue_document='ar')
        self.client_fr = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Marc',
            email=f'apdf31-fr-{n}@example.invalid')
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-APDF31-{n:04d}',
            client=self.client_ar, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
            date_echeance=date(2026, 9, 1))
        self.html = []
        self.objets = {}
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.objets.__setitem__(k, b))
        p_up.start()
        self.addCleanup(p_up.stop)
        vrai = pdf_mod._render_html

        def _capture(nom, ctx):
            html = vrai(nom, ctx)
            self.html.append(html)
            return html
        p_html = patch('apps.ventes.utils.pdf._render_html',
                       side_effect=_capture)
        p_html.start()
        self.addCleanup(p_html.stop)
        # Rendu PDF neutralisé pour les gabarits rendus à la volée : seul le
        # HTML (langue, libellés) est vérifié ici.
        p_pdf = patch('apps.ventes.utils.pdf._html_to_pdf',
                      return_value=b'%PDF-1.4 test')
        p_pdf.start()
        self.addCleanup(p_pdf.stop)

    def _assert_arabe(self, html):
        self.assertIn('lang="ar"', html)
        self.assertIn('dir="rtl"', html)
        self.assertGreaterEqual(len(ARABE.findall(html)), 50)

    def _avoir(self, client):
        from apps.ventes.models import Avoir
        return Avoir.objects.create(
            company=self.company, reference=f'AV-APDF31-{_nxt():04d}',
            facture=self.facture, client=client,
            statut=Avoir.Statut.EMISE, taux_tva=Decimal('20'),
            motif='Geste commercial')

    def _nd(self, client):
        from apps.ventes.models import NoteDebit
        return NoteDebit.objects.create(
            company=self.company, reference=f'ND-APDF31-{_nxt():04d}',
            facture=self.facture, client=client,
            statut=NoteDebit.Statut.EMISE, motif='Complément',
            taux_tva=Decimal('20'))

    def test_avoir_ar(self):
        from apps.ventes.utils.pdf import generate_avoir_pdf
        generate_avoir_pdf(self._avoir(self.client_ar).id)
        html = self.html[-1]
        self._assert_arabe(html)
        self.assertIn('إشعار دائن', html)
        self.assertNotIn('Avoir au profit de', html)
        # Client français : rendu français, aucune mention.
        generate_avoir_pdf(self._avoir(self.client_fr).id)
        html = self.html[-1]
        self.assertIn('<html lang="fr">', html)
        self.assertIn('Avoir au profit de', html)
        self.assertNotIn('uniquement', html)

    def test_nd_ar(self):
        from apps.ventes.utils.pdf import generate_note_debit_pdf
        generate_note_debit_pdf(self._nd(self.client_ar).id)
        html = self.html[-1]
        self._assert_arabe(html)
        self.assertIn('إشعار مدين', html)
        self.assertNotIn('Note de débit à charge de', html)

    def test_autres_selon_decision(self):
        from apps.ventes.models import Paiement
        from apps.ventes.utils.pdf import (
            generate_lettre_relance_pdf, generate_recu_pdf,
        )
        # Reçu et lettre de relance : TRADUITS.
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('500'), date_paiement=date.today(),
            mode=Paiement.Mode.VIREMENT)
        generate_recu_pdf(paiement)
        self._assert_arabe(self.html[-1])
        self.assertIn('وصل أداء', self.html[-1])
        generate_lettre_relance_pdf(self.facture, None, '')
        self._assert_arabe(self.html[-1])
        self.assertIn('تذكير', self.html[-1])
        # Bon de commande : FRANÇAIS + mention de repli imprimée.
        from apps.ventes.models import BonCommande, Devis, LigneDevis
        from apps.ventes.utils.pdf import generate_bon_commande_pdf
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-APDF31-{_nxt()}',
            client=self.client_ar, statut='accepte', taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, designation='Centrale PV', quantite=Decimal('1'),
            prix_unitaire=Decimal('10000'), remise=Decimal('0'),
            taux_tva=Decimal('20'))
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-APDF31-{_nxt()}',
            devis=devis, client=self.client_ar,
            statut=BonCommande.Statut.EN_ATTENTE)
        generate_bon_commande_pdf(bc.id)
        html = self.html[-1]
        self.assertIn('<html lang="fr">', html)
        self.assertIn('Document disponible en français uniquement', html)
        self.assertIn('هذه الوثيقة متوفرة باللغة الفرنسية فقط', html)

    def test_en_repli_dit(self):
        from apps.parametres.models import CompanyProfile
        from apps.ventes.utils.pdf import generate_facture_pdf
        profil = CompanyProfile.get(company=self.company)
        if not hasattr(profil, 'langue_repli'):  # pragma: no cover
            self.skipTest('langue_repli absent du profil société')
        profil.langue_repli = 'en'
        profil.save()
        from apps.crm.models import Client
        sans_langue = Client.objects.create(
            company=self.company, nom='Smith', prenom='John',
            email=f'apdf31-en-{_nxt()}@example.invalid',
            langue_document='')
        self.facture.client = sans_langue
        self.facture.save(update_fields=['client'])
        from apps.ventes.utils.libelles_ar import document_langue
        langue = document_langue(sans_langue, company=self.company)
        generate_facture_pdf(self.facture.id)
        html = self.html[-1]
        if langue == 'en':
            self.assertIn('lang="fr"', html)
            self.assertIn('This document is available in French only', html)
        else:  # client explicitement FR : jamais de mention
            self.assertNotIn('uniquement', html)
