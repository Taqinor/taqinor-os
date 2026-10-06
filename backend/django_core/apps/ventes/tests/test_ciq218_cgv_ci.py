"""CIQ218 — conditions générales C&I par mode (commercial, industriel) :
texte de la société relu par un juriste, gelé à l'envoi, servi au moteur
(``cgv_ci``) — jamais généré par lui. Sans mock de la source.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq218_cgv_ci"
"""
from django.test import TestCase

from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

LIGNES = [
    ('Panneau mono 450W', '40', '1500'),
    ('Onduleur réseau 20 kW', '1', '30000'),
]

VARIANTES = {
    'industriel': {
        'titre': 'Conditions générales — industriel',
        'bullets': ['Échéancier : {echeancier}.',
                    'Réserve de propriété jusqu\'au paiement intégral.',
                    '{tva_note}'],
    },
    'commercial': {
        'titre': 'Conditions générales — commercial',
        'bullets': ['Commerce : réception sous 8 jours.'],
    },
}


class _Base(TestCase):
    def setUp(self):
        from apps.parametres.models_documents import DocumentTemplates
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.modele = DocumentTemplates.get(company=self.company)

    def _devis(self, mode, ref):
        devis = make_devis(self.company, self.user, self.client_obj, LIGNES,
                           reference=ref)
        devis.mode_installation = mode
        devis.echeancier = [
            {'pct_or_montant': 30, 'jalon': 'commande'},
            {'pct_or_montant': 70, 'jalon': 'reception_definitive'}]
        devis.save(update_fields=['mode_installation', 'echeancier'])
        return devis

    def _envoyer(self, devis):
        from apps.ventes.domain.envoi import figer_clauses_devis
        figer_clauses_devis(devis)
        devis.refresh_from_db()
        return devis


class GelVarianteTest(_Base):
    def test_industriel_gele_sa_variante_puis_moteur_la_sert(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        self.modele.cgv_par_mode = VARIANTES
        self.modele.save()
        devis = self._envoyer(self._devis('industriel', 'DEV-CIQ218-0010'))
        gelees = [c for c in devis.clauses_appliquees
                  if c.get('type') == 'cgv_gelees']
        self.assertEqual(len(gelees), 1)
        self.assertEqual(gelees[0]['mode'], 'industriel')
        self.assertEqual(gelees[0]['bullets'],
                         VARIANTES['industriel']['bullets'])
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        cgv = data['cgv_ci']
        self.assertEqual(len(cgv), 3)
        self.assertIn('Commande : 30 %', cgv[0])
        self.assertIn('Réception définitive : 70 %', cgv[0])
        self.assertNotIn('{', ''.join(cgv))

    def test_texte_modifie_apres_envoi_ne_change_pas_le_devis(self):
        from apps.ventes.quote_engine.builder import cgv_ci_du_devis
        self.modele.cgv_par_mode = VARIANTES
        self.modele.save()
        devis = self._envoyer(self._devis('industriel', 'DEV-CIQ218-0020'))
        avant = cgv_ci_du_devis(devis)
        self.modele.cgv_par_mode = {'industriel': {
            'titre': 'Nouveau', 'bullets': ['Texte réécrit après envoi.']}}
        self.modele.save()
        self._envoyer(devis)  # re-gel (correction sur place) : inchangé
        self.assertEqual(cgv_ci_du_devis(devis), avant)

    def test_commercial_sans_sa_variante_prend_l_autre_variante_ci(self):
        self.modele.cgv_par_mode = {'industriel': VARIANTES['industriel']}
        self.modele.save()
        devis = self._envoyer(self._devis('commercial', 'DEV-CIQ218-0030'))
        gelees = [c for c in devis.clauses_appliquees
                  if c.get('type') == 'cgv_gelees']
        self.assertEqual(gelees[0]['mode'], 'industriel')

    def test_variante_absente_puces_societe_comme_hier(self):
        from apps.ventes.quote_engine.builder import cgv_ci_du_devis
        self.modele.cgv_bullets = ['Puce société {tva_note}']
        self.modele.save()
        devis = self._envoyer(self._devis('industriel', 'DEV-CIQ218-0040'))
        self.assertEqual(
            [c for c in devis.clauses_appliquees
             if c.get('type') == 'cgv_gelees'],
            [{'type': 'cgv_gelees', 'bullets': ['Puce société {tva_note}']}])
        # Les puces société au ton résidentiel ne sont jamais servies en C&I.
        self.assertIsNone(cgv_ci_du_devis(devis))

    def test_residentiel_ignore_les_variantes(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        self.modele.cgv_par_mode = VARIANTES
        self.modele.cgv_bullets = ['Puce société']
        self.modele.save()
        devis = self._envoyer(self._devis('residentiel', 'DEV-CIQ218-0050'))
        self.assertEqual(
            [c for c in devis.clauses_appliquees
             if c.get('type') == 'cgv_gelees'],
            [{'type': 'cgv_gelees', 'bullets': ['Puce société']}])
        self.assertNotIn('cgv_ci', build_quote_data(devis))

    def test_vide_par_defaut(self):
        from apps.parametres.selectors import cgv_mode_societe
        self.assertEqual(self.modele.cgv_par_mode, {})
        self.assertIsNone(cgv_mode_societe(self.company, 'industriel'))


class SerialiseurTest(_Base):
    def test_mode_inconnu_refuse(self):
        from rest_framework import serializers
        from apps.parametres.serializers_documents import (
            DocumentTemplatesSerializer,
        )
        ser = DocumentTemplatesSerializer()
        with self.assertRaises(serializers.ValidationError):
            ser.validate_cgv_par_mode({'residentiel': {'bullets': ['x']}})
        self.assertEqual(
            ser.validate_cgv_par_mode({'commercial': {
                'titre': ' T ', 'bullets': ['a', '', 'b']}}),
            {'commercial': {'titre': 'T', 'bullets': ['a', 'b']}})
