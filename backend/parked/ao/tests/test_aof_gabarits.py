"""AOF116 — moteur de gabarits + seed du pack + bibliothèque de sections.

Ce qui est prouvé ici :

* le seed est REJOUABLE sans doublon (et le pack se recrée en UN appel) ;
* un gabarit contenant un LITTÉRAL CHIFFRÉ fait échouer un test — la règle est
  vérifiable en machine, pas une consigne de relecture ;
* les exceptions normatives (NF C 15-100, loi 13-09, article 12) passent ;
* le rendu délègue à ``core.templating.rendre`` (aucun ``eval``).

Run :
    python manage.py test apps.ao.tests.test_aof_gabarits -v2
"""
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.ao.fabrique.gabarits import (
    LitteralChiffreRefuse, literaux_chiffres, rendre_gabarit,
    valider_gabarit, variables_du_gabarit,
)
from apps.ao.management.commands.seed_pack_ao import CODE_PACK, PIECES_PACK
from apps.ao.management.commands.seed_sections_memoire import SECTIONS_MEMOIRE
from apps.ao.models import ModelePack, PieceModele, SectionMemoire
from authentication.models import Company


class TestDetecteurDeLitteraux(SimpleTestCase):
    def test_un_montant_en_dur_est_refuse(self):
        with self.assertRaises(LitteralChiffreRefuse) as ctx:
            valider_gabarit('Batteries à 2 800 DH HT/kWh', origine='mémoire')
        message = str(ctx.exception)
        self.assertIn('2 800', message)
        self.assertIn('mémoire', message)

    def test_le_meme_montant_en_placeholder_passe(self):
        self.assertTrue(
            valider_gabarit('Batteries à {{ prix_kwh_batterie }} DH HT/kWh'))

    def test_les_references_normatives_sont_tolerees(self):
        for texte in ('Conforme NF C 15-100.',
                      'Loi 13-09 et décret 2-12-349.',
                      "Article 12 du CPS, annexe 3.",
                      'Modules certifiés IEC 61215.'):
            self.assertEqual(literaux_chiffres(texte), [], texte)

    def test_une_duree_en_dur_est_bien_vue_comme_un_litteral(self):
        """« 25 ans » est une GRANDEUR du dossier, pas une norme."""
        self.assertTrue(literaux_chiffres('Simulation sur 25 ans'))

    def test_variables_du_gabarit(self):
        self.assertEqual(
            variables_du_gabarit('{{ a.b }} puis {{ c }} puis {{ a.b }}'),
            ['a.b', 'c'])

    def test_rendu_sans_eval(self):
        rendu = rendre_gabarit(
            'Total : {{ bordereau.total_ttc }} MAD',
            {'bordereau': {'total_ttc': '4 999 920,00'}})
        self.assertEqual(rendu, 'Total : 4 999 920,00 MAD')

    def test_le_rendu_refuse_un_gabarit_vestigial(self):
        with self.assertRaises(LitteralChiffreRefuse):
            rendre_gabarit('Total : 4 999 920 MAD', {})


class TestGabaritsSeedes(SimpleTestCase):
    """Le seed livré est lui-même conforme — sinon la règle est décorative."""

    def test_aucune_piece_du_pack_ne_porte_de_chiffre(self):
        for piece in PIECES_PACK:
            self.assertEqual(
                literaux_chiffres(piece['gabarit']), [], piece['code'])

    def test_aucune_section_de_memoire_ne_porte_de_chiffre(self):
        for section in SECTIONS_MEMOIRE:
            self.assertEqual(
                literaux_chiffres(section['corps']), [], section['code'])

    def test_les_neuf_pieces_du_pack_reel(self):
        codes = [p['code'] for p in PIECES_PACK]
        self.assertEqual(
            codes, ['00', '01', '02', '03', '04', '05', '06', '07', '08'])

    def test_les_huit_sections_recurrentes(self):
        codes = {s['code'] for s in SECTIONS_MEMOIRE}
        self.assertEqual(codes, {
            'ORGANISATION', 'METHODOLOGIE', 'MATERIEL', 'SECURITE',
            'PLANNING', 'GARANTIES', 'MAINTENANCE', 'REFERENCES'})


class TestSeedIdempotent(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF116 Co',
                                              slug='aof116-co')

    def test_le_pack_se_recree_en_un_appel(self):
        call_command('seed_pack_ao', company='aof116-co', stdout=StringIO())
        modele = ModelePack.objects.get(company=self.company, code=CODE_PACK)
        self.assertEqual(modele.pieces.count(), 9)
        self.assertEqual(
            [p.code for p in modele.pieces.all()],
            ['00', '01', '02', '03', '04', '05', '06', '07', '08'])

    def test_rejouer_le_seed_ne_duplique_rien(self):
        call_command('seed_pack_ao', company='aof116-co', stdout=StringIO())
        call_command('seed_pack_ao', company='aof116-co', stdout=StringIO())
        self.assertEqual(
            ModelePack.objects.filter(company=self.company).count(), 1)
        self.assertEqual(PieceModele.objects.filter(
            company=self.company).count(), 9)

    def test_le_seed_est_additif_il_ne_reecrit_pas(self):
        call_command('seed_pack_ao', company='aof116-co', stdout=StringIO())
        piece = PieceModele.objects.get(company=self.company, code='04')
        piece.gabarit = 'Gabarit retouché à la main : {{ bordereau.total_ht }}'
        piece.save(update_fields=['gabarit'])
        call_command('seed_pack_ao', company='aof116-co', stdout=StringIO())
        piece.refresh_from_db()
        self.assertIn('retouché', piece.gabarit)

    def test_les_visibilites_sont_declarees(self):
        call_command('seed_pack_ao', company='aof116-co', stdout=StringIO())
        checklist = PieceModele.objects.get(company=self.company, code='00')
        self.assertEqual(checklist.visibilite, 'interne')
        bordereau = PieceModele.objects.get(company=self.company, code='04')
        self.assertEqual(bordereau.visibilite, 'client')

    def test_sections_seedees_et_rejouables(self):
        call_command('seed_sections_memoire', company='aof116-co',
                     stdout=StringIO())
        call_command('seed_sections_memoire', company='aof116-co',
                     stdout=StringIO())
        self.assertEqual(
            SectionMemoire.objects.filter(company=self.company).count(), 8)

    def test_isolation_multi_societe_du_seed(self):
        autre = Company.objects.create(nom='AOF116 X', slug='aof116-x')
        call_command('seed_pack_ao', company='aof116-co', stdout=StringIO())
        self.assertFalse(ModelePack.objects.filter(company=autre).exists())

    def test_les_gabarits_persistes_passent_la_validation(self):
        call_command('seed_pack_ao', company='aof116-co', stdout=StringIO())
        call_command('seed_sections_memoire', company='aof116-co',
                     stdout=StringIO())
        for piece in PieceModele.objects.filter(company=self.company):
            self.assertTrue(
                valider_gabarit(piece.gabarit, origine=piece.libelle))
        for section in SectionMemoire.objects.filter(company=self.company):
            self.assertTrue(
                valider_gabarit(section.corps, origine=section.titre))
