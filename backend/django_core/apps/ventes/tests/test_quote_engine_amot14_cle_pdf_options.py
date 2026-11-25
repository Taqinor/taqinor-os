"""AMOT14 (C-AMOT-012) — seul un rendu PERSISTÉ écrit sous la clé MinIO du
devis (``fichier_pdf``) : un rendu ``persist=False`` (aperçu interne avec ses
paramètres, pièce jointe d'e-mail, PDF public) part sous une clé d'aperçu
distincte ; ``cle_pdf_a_jour`` compare aussi les options du dernier écrit.

Le téléversement est intercepté par un faux stockage EN MÉMOIRE (dict clé →
octets), pas par un espion d'appel ; moteur réel.

Test-du-test : remettre l'écriture sous la clé historique pour un rendu non
persisté ⇒ ``test_apercu_n_ecrase_pas_le_fichier_memorise`` échoue.
"""
from unittest import mock

from django.test import TestCase

from apps.ventes.quote_engine import builder
from apps.ventes.quote_engine.builder import (
    cle_pdf_a_jour, clean_pdf_options, generate_premium_devis_pdf,
)
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)


class ClePdfOptionsTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot14-co', nom='AMOT14')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '12', '1100'),
                ('Onduleur réseau 5kW', '1', '11700'),
            ], reference='DEV-AMOT14-1')
        self.stockage = {}

        def _upload(pdf_bytes, key, *a, **k):
            self.stockage[key] = pdf_bytes
            return key
        for cible, kwargs in (
                ('apps.ventes.quote_engine.builder._ensure_pdf_bucket', {}),
                ('apps.ventes.utils.pdf._upload_pdf', {'side_effect': _upload})):
            p = mock.patch(cible, **kwargs)
            p.start()
            self.addCleanup(p.stop)

    def test_apercu_n_ecrase_pas_le_fichier_memorise(self):
        cle = generate_premium_devis_pdf(
            self.devis.id, clean_pdf_options({'pdf_mode': 'onepage'}),
            persist=True)
        octets_memorises = self.stockage[cle]
        cle_apercu = generate_premium_devis_pdf(
            self.devis.id, clean_pdf_options({'pdf_mode': 'full',
                                              'langue_sortie': 'en'}),
            persist=False)
        self.assertNotEqual(cle_apercu, cle)
        self.assertEqual(self.stockage[cle], octets_memorises)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.fichier_pdf, cle)
        self.assertEqual(cle_apercu, builder._pdf_key(self.devis, apercu=True))

    def test_cle_pdf_a_jour_options_differentes_re_rend(self):
        generate_premium_devis_pdf(
            self.devis.id, clean_pdf_options({'pdf_mode': 'onepage'}),
            persist=True)
        self.devis.refresh_from_db()
        with mock.patch.object(
                builder, 'generate_premium_devis_pdf',
                wraps=builder.generate_premium_devis_pdf) as moteur:
            # Mêmes options : fichier mémorisé servi tel quel.
            cle_pdf_a_jour(self.devis)
            self.assertFalse(moteur.called)
            # Options différentes : re-rendu.
            cle_pdf_a_jour(self.devis, {'pdf_mode': 'full'})
            self.assertTrue(moteur.called)


class EmpreintePhrasesProfilTests(TestCase):
    """D-ACAL-102 (correction K1) — le drapeau de rendu marque le cas OUVERT :
    l'empreinte des données d'un devis C&I dont le rendu change BOUGE (son
    fichier stocké est re-rendu), celle d'un devis envoyé avant la coupure ne
    bouge pas (son fichier reçu est servi tel quel)."""

    def setUp(self):
        self.company = make_company(slug='k1-co', nom='K1')
        self.user = make_user(self.company)

    def _devis(self, ref, **champs):
        from apps.ventes.models import Devis
        devis = make_devis(self.company, self.user, make_client(self.company), [
            ('Onduleur réseau Huawei 50kW Triphasé', '1', '60000', '20'),
            ('Panneau mono 550W', '100', '1100', '20'),
        ], reference=ref)
        Devis.objects.filter(pk=devis.pk).update(mode_installation='industriel', **champs)
        return Devis.objects.get(pk=devis.pk)

    def _cle_avec_empreinte(self, devis, empreinte):
        from apps.ventes.models import Devis
        Devis.objects.filter(pk=devis.pk).update(
            fichier_pdf='devis/k1.pdf',
            pdf_render_meta={'empreinte': empreinte, 'options': clean_pdf_options({})})
        devis = Devis.objects.get(pk=devis.pk)
        with mock.patch.object(builder, 'generate_premium_devis_pdf',
                               return_value='devis/k1-neuf.pdf') as moteur:
            cle = cle_pdf_a_jour(devis)
        return cle, moteur.called

    def test_brouillon_c_i_empreinte_bouge_et_fichier_re_rendu(self):
        devis = self._devis('DEV-K1-B')
        data = builder.build_quote_data(devis, clean_pdf_options({}))
        self.assertIs(data.get('phrases_profil_ouvertes'), True)
        avant = {k: v for k, v in data.items() if k != 'phrases_profil_ouvertes'}
        empreinte_avant = builder.empreinte_donnees_pdf(avant)
        self.assertNotEqual(empreinte_avant, builder.empreinte_donnees_pdf(data))
        cle, re_rendu = self._cle_avec_empreinte(devis, empreinte_avant)
        self.assertTrue(re_rendu)
        self.assertEqual(cle, 'devis/k1-neuf.pdf')

    def test_envoye_avant_la_coupure_donnees_et_fichier_intacts(self):
        from datetime import datetime, timezone
        devis = self._devis('DEV-K1-E', statut='envoye',
                            date_envoi=datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc))
        data = builder.build_quote_data(devis, clean_pdf_options({}))
        self.assertNotIn('phrases_profil_ouvertes', data)
        self.assertNotIn('phrases_profil_historique', data)
        cle, re_rendu = self._cle_avec_empreinte(devis, builder.empreinte_donnees_pdf(data))
        self.assertFalse(re_rendu)
        self.assertEqual(cle, 'devis/k1.pdf')
