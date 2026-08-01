"""NTEDU17 — bulletin scolaire PDF (renderer dédié, hors quote_engine).

WeasyPrint n'est PAS installé partout (libs natives absentes sur le poste de
build) : ces tests portent donc sur le CONTEXTE calculé et sur le GABARIT HTML,
jamais sur les octets rendus — ``core.pdf.render_pdf`` est stubbé pour la route.
"""
import ast
from datetime import date, time
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .models import (
    AnneeScolaire, Bulletin, Classe, Eleve, Evaluation, Famille, Matiere,
    MatiereClasse, Niveau, Note, PeriodeScolaire, Presence, Seance)
from .services import donnees_bulletin, mention_bulletin

User = get_user_model()


class BulletinFixtureMixin:
    def setUp(self):
        super().setUp()
        self.company, _ = Company.objects.get_or_create(
            slug='ecole-bulletin-test',
            defaults={'nom': 'École Bulletin Test'})
        self.user = User.objects.create_user(
            username='admin@ecole-bulletin-test.ma', password='x',
            company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.annee = AnneeScolaire.objects.create(
            company=self.company, libelle='2026-2027',
            date_debut=date(2026, 9, 1), date_fin=date(2027, 6, 30))
        self.periode = PeriodeScolaire.objects.create(
            company=self.company, annee_scolaire=self.annee,
            libelle='Trimestre 1', ordre=1,
            date_debut=date(2026, 9, 1), date_fin=date(2026, 12, 15))
        self.niveau = Niveau.objects.create(
            company=self.company, nom='CP', cycle=Niveau.Cycle.PRIMAIRE,
            ordre=1)
        self.classe = Classe.objects.create(
            company=self.company, annee_scolaire=self.annee,
            niveau=self.niveau, nom='CP A', capacite_max=30)
        self.famille = Famille.objects.create(
            company=self.company, nom='Bennani')

        self.eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine', classe=self.classe, numero_dossier='ELV00001')
        self.eleve2 = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Karim', classe=self.classe)
        self.eleve_sans_note = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Alaoui',
            prenom='Sara', classe=self.classe)

        francais = Matiere.objects.create(
            company=self.company, nom='Français', code='FR')
        maths = Matiere.objects.create(
            company=self.company, nom='Maths', code='MA')
        self.mc_francais = MatiereClasse.objects.create(
            company=self.company, classe=self.classe, matiere=francais,
            coefficient=Decimal('3'))
        self.mc_maths = MatiereClasse.objects.create(
            company=self.company, classe=self.classe, matiere=maths,
            coefficient=Decimal('2'))

        self.eval_fr = Evaluation.objects.create(
            company=self.company, matiere_classe=self.mc_francais,
            date=date(2026, 10, 5), bareme=Decimal('20'),
            coefficient_evaluation=Decimal('1'))
        # Barème /10 : la note DOIT être ramenée sur /20 avant pondération.
        self.eval_maths = Evaluation.objects.create(
            company=self.company, matiere_classe=self.mc_maths,
            date=date(2026, 11, 3), bareme=Decimal('10'),
            coefficient_evaluation=Decimal('1'))

        Note.objects.create(
            company=self.company, evaluation=self.eval_fr, eleve=self.eleve,
            valeur=Decimal('15'), appreciation='Bon trimestre')
        Note.objects.create(
            company=self.company, evaluation=self.eval_maths, eleve=self.eleve,
            valeur=Decimal('8'))
        Note.objects.create(
            company=self.company, evaluation=self.eval_fr, eleve=self.eleve2,
            valeur=Decimal('10'))
        Note.objects.create(
            company=self.company, evaluation=self.eval_maths,
            eleve=self.eleve2, valeur=Decimal('5'))
        # Élève ABSENT à l'évaluation : valeur NULL, jamais un 0 fictif.
        Note.objects.create(
            company=self.company, evaluation=self.eval_fr,
            eleve=self.eleve_sans_note, valeur=None)


class NTEDU17DonneesBulletinTests(BulletinFixtureMixin, TestCase):
    def test_moyennes_ponderees_et_notes_ramenees_sur_20(self):
        data = donnees_bulletin(self.eleve, self.periode)
        moyennes = {m['matiere']: m['moyenne'] for m in data['matieres']}
        self.assertEqual(moyennes['Français'], Decimal('15'))
        # 8/10 -> 16/20 (jamais 8 brut, qui pénaliserait l'élève).
        self.assertEqual(moyennes['Maths'], Decimal('16'))
        # (15*3 + 16*2) / 5 = 15.4
        self.assertEqual(data['moyenne_generale'], Decimal('15.4'))
        self.assertEqual(data['mention'], 'Bien')

    def test_rang_et_effectif_sur_les_eleves_notes(self):
        premier = donnees_bulletin(self.eleve, self.periode)
        second = donnees_bulletin(self.eleve2, self.periode)
        self.assertEqual(premier['rang'], 1)
        self.assertEqual(second['rang'], 2)
        # L'élève sans note ne fausse pas l'effectif classé.
        self.assertEqual(premier['effectif_classe'], 2)

    def test_note_absente_exclue_pas_de_moyenne_ni_de_rang(self):
        data = donnees_bulletin(self.eleve_sans_note, self.periode)
        self.assertIsNone(data['moyenne_generale'])
        self.assertIsNone(data['rang'])
        self.assertEqual(data['mention'], '')

    def test_seules_les_evaluations_de_la_periode_comptent(self):
        hors_periode = Evaluation.objects.create(
            company=self.company, matiere_classe=self.mc_francais,
            date=date(2027, 3, 10), bareme=Decimal('20'),
            coefficient_evaluation=Decimal('1'))
        Note.objects.create(
            company=self.company, evaluation=hors_periode, eleve=self.eleve,
            valeur=Decimal('2'))
        data = donnees_bulletin(self.eleve, self.periode)
        self.assertEqual(data['moyenne_generale'], Decimal('15.4'))

    def test_presences_comptees_sur_la_periode_uniquement(self):
        dans = Seance.objects.create(
            company=self.company, classe=self.classe, matiere='Français',
            date=date(2026, 10, 6), heure_debut=time(8, 0),
            heure_fin=time(9, 0))
        dehors = Seance.objects.create(
            company=self.company, classe=self.classe, matiere='Français',
            date=date(2027, 2, 6), heure_debut=time(8, 0),
            heure_fin=time(9, 0))
        Presence.objects.create(
            company=self.company, seance=dans, eleve=self.eleve,
            statut=Presence.Statut.ABSENT)
        Presence.objects.create(
            company=self.company, seance=dehors, eleve=self.eleve,
            statut=Presence.Statut.ABSENT)
        data = donnees_bulletin(self.eleve, self.periode)
        self.assertEqual(data['presences']['absent'], 1)

    def test_appreciation_generale_vient_du_bulletin(self):
        Bulletin.objects.create(
            company=self.company, eleve=self.eleve, periode=self.periode,
            appreciation_generale='Trimestre solide, poursuivre les efforts.')
        data = donnees_bulletin(self.eleve, self.periode)
        self.assertEqual(
            data['appreciation_generale'],
            'Trimestre solide, poursuivre les efforts.')

    def test_mentions(self):
        self.assertEqual(mention_bulletin(Decimal('16')), 'Très bien')
        self.assertEqual(mention_bulletin(Decimal('14')), 'Bien')
        self.assertEqual(mention_bulletin(Decimal('12')), 'Assez bien')
        self.assertEqual(mention_bulletin(Decimal('10')), 'Passable')
        self.assertEqual(mention_bulletin(Decimal('9.99')), 'Insuffisant')
        self.assertEqual(mention_bulletin(None), '')


class NTEDU17GabaritTests(BulletinFixtureMixin, TestCase):
    def test_html_contient_matieres_moyenne_mention_et_appreciation(self):
        from .bulletin_pdf import render_bulletin_html

        Bulletin.objects.create(
            company=self.company, eleve=self.eleve, periode=self.periode,
            appreciation_generale='Élève sérieuse.')
        html = render_bulletin_html(donnees_bulletin(self.eleve, self.periode))
        self.assertIn('Bulletin scolaire', html)
        self.assertIn('Trimestre 1', html)
        self.assertIn('Yasmine Bennani', html)
        self.assertIn('Français', html)
        self.assertIn('Maths', html)
        self.assertIn('15.40', html)
        self.assertIn('Bien', html)
        self.assertIn('1 / 2', html)
        self.assertIn('Élève sérieuse.', html)

    def test_html_sans_matiere_notee_reste_valide(self):
        from .bulletin_pdf import render_bulletin_html

        html = render_bulletin_html(
            donnees_bulletin(self.eleve_sans_note, self.periode))
        self.assertIn('Aucune note saisie sur la période.', html)

    def test_regle_4_le_renderer_ignore_totalement_le_quote_engine(self):
        """Règle #4 : le bulletin n'emprunte JAMAIS le chemin des devis.

        Contrôle sur les IMPORTS RÉELS (AST), pas sur le texte du module :
        une mention en commentaire/docstring ne doit pas faire échouer, un
        import de ``ventes.quote_engine`` (ou de ``weasyprint`` en direct,
        ARC11) doit faire échouer."""
        source = (Path(__file__).resolve().parent / 'bulletin_pdf.py'
                  ).read_text(encoding='utf-8')
        modules = set()
        for noeud in ast.walk(ast.parse(source)):
            if isinstance(noeud, ast.Import):
                modules.update(alias.name for alias in noeud.names)
            elif isinstance(noeud, ast.ImportFrom):
                modules.add(noeud.module or '')
        for module in modules:
            self.assertNotIn('quote_engine', module)
            self.assertNotIn('ventes', module)
            self.assertNotEqual(module, 'weasyprint')
        self.assertIn('core.pdf', modules)


class NTEDU17EndpointTests(BulletinFixtureMixin, TestCase):
    def test_bulletin_pdf_telechargeable(self):
        with mock.patch(
                'apps.education.bulletin_pdf.render_pdf',
                return_value=b'%PDF-1.4 fake') as rendu:
            resp = self.client.get(
                f'/api/django/education/eleves/{self.eleve.id}/bulletin/'
                f'?periode={self.periode.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', resp['Content-Disposition'])
        html = rendu.call_args.kwargs['html']
        self.assertIn('Trimestre 1', html)

    def test_periode_manquante_refusee(self):
        resp = self.client.get(
            f'/api/django/education/eleves/{self.eleve.id}/bulletin/')
        self.assertEqual(resp.status_code, 400)

    def test_periode_non_numerique_refusee_sans_500(self):
        resp = self.client.get(
            f'/api/django/education/eleves/{self.eleve.id}/bulletin/'
            '?periode=abc')
        self.assertEqual(resp.status_code, 400)

    def test_periode_d_une_autre_societe_refusee(self):
        autre, _ = Company.objects.get_or_create(
            slug='ecole-bulletin-autre',
            defaults={'nom': 'École Bulletin Autre'})
        annee_autre = AnneeScolaire.objects.create(
            company=autre, libelle='2026-2027',
            date_debut=date(2026, 9, 1), date_fin=date(2027, 6, 30))
        periode_autre = PeriodeScolaire.objects.create(
            company=autre, annee_scolaire=annee_autre, libelle='Trimestre 1',
            ordre=1, date_debut=date(2026, 9, 1),
            date_fin=date(2026, 12, 15))
        resp = self.client.get(
            f'/api/django/education/eleves/{self.eleve.id}/bulletin/'
            f'?periode={periode_autre.id}')
        self.assertEqual(resp.status_code, 400)
