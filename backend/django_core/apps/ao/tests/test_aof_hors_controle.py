"""AOF149 — pièce « hors contrôle » : ce qui n'est pas fabriqué n'est JAMAIS
présumé vert.

Constat. Les invariants d'AOF146 ne s'appliquent qu'aux pièces PRODUITES par
la fabrique. Dès qu'une pièce est fournie à la main (acte d'engagement au
modèle de l'acheteur, attestations, caution bancaire, checklist remplie par le
partenaire), elle échappe aux contrôles et passerait SILENCIEUSEMENT pour
conforme. Un dossier « tout vert » dont un tiers n'a jamais été vérifié est
plus dangereux qu'un dossier orange.

Ce qui est prouvé ici :

* une pièce fournie n'apparaît **jamais « verte »** mais « hors contrôle » ;
* son **motif est obligatoire** (modèle ET serializer) ;
* le rapport de contrôle les **compte et les nomme**.

Run :
    python manage.py test apps.ao.tests.test_aof_hors_controle -v2
"""
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.ao import services
from apps.ao.fabrique import coherence
from apps.ao.models import AppelOffre, PieceDossierAO
from apps.ao.serializers import PieceDossierAOSerializer
from authentication.models import Company


class BaseHorsControle(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF149 Co',
                                              slug='aof149-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-149-1', objet='Hors contrôle')
        self.dossier = services.creer_dossier_ao(self.company, self.ao)

    def _piece(self, code, **kwargs):
        base = {'libelle': f'Pièce {code}', 'presente': True}
        base.update(kwargs)
        return PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, code=code, **base)


class TestEtatDeControle(BaseHorsControle):
    def test_une_piece_fabriquee_et_presente_est_verte(self):
        piece = self._piece('04')
        self.assertEqual(piece.controlee, PieceDossierAO.FABRIQUEE)
        self.assertEqual(piece.etat_controle, 'verte')

    def test_une_piece_absente_est_manquante(self):
        piece = self._piece('04', presente=False)
        self.assertEqual(piece.etat_controle, 'manquante')

    def test_une_piece_fournie_n_est_JAMAIS_verte(self):
        piece = self._piece(
            '01', libelle="Acte d'engagement (modèle acheteur)",
            controlee=PieceDossierAO.HORS_CONTROLE,
            motif="Modèle imposé par l'acheteur, rempli à la main.")
        self.assertEqual(piece.etat_controle, 'hors_controle')
        self.assertNotEqual(piece.etat_controle, 'verte')

    def test_le_defaut_est_fabriquee(self):
        champ = PieceDossierAO._meta.get_field('controlee')
        self.assertEqual(champ.default, 'fabriquee')


class TestMotifObligatoire(BaseHorsControle):
    def test_hors_controle_sans_motif_est_refuse_par_le_modele(self):
        piece = self._piece(
            '08', controlee=PieceDossierAO.HORS_CONTROLE)
        with self.assertRaises(ValidationError) as ctx:
            piece.clean()
        self.assertIn('POURQUOI',
                      ' '.join(ctx.exception.message_dict['motif']))

    def test_hors_controle_sans_motif_est_refuse_par_le_serializer(self):
        serializer = PieceDossierAOSerializer(data={
            'dossier': self.dossier.id, 'code': '08',
            'libelle': 'Caution bancaire',
            'controlee': 'hors_controle', 'motif': '   '})
        self.assertFalse(serializer.is_valid())
        self.assertIn('motif', serializer.errors)

    def test_avec_motif_le_serializer_accepte(self):
        serializer = PieceDossierAOSerializer(data={
            'dossier': self.dossier.id, 'code': '08',
            'libelle': 'Caution bancaire',
            'controlee': 'hors_controle',
            'motif': 'Émise par la banque, hors périmètre de la fabrique.'})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_une_piece_fabriquee_n_exige_aucun_motif(self):
        piece = self._piece('04')
        self.assertEqual(piece.raisons_hors_controle(), [])
        piece.clean()


class TestRapportCompteEtNomme(BaseHorsControle):
    def test_le_rapport_compte_et_nomme_les_pieces_hors_controle(self):
        self._piece('04', libelle='Bordereau des prix')
        self._piece(
            '01', libelle="Acte d'engagement",
            controlee=PieceDossierAO.HORS_CONTROLE,
            motif="Modèle imposé par l'acheteur.")
        self._piece(
            '08', libelle='Caution provisoire',
            controlee=PieceDossierAO.HORS_CONTROLE,
            motif='Émise par la banque.')
        passe = coherence.passer_controle(self.dossier)
        self.assertEqual(passe['nombre_hors_controle'], 2)
        codes = {item['code'] for item in passe['hors_controle']}
        self.assertEqual(codes, {'01', '08'})
        motifs = {item['motif'] for item in passe['hors_controle']}
        self.assertIn("Modèle imposé par l'acheteur.", motifs)

    def test_le_rapport_liste_une_ligne_d_information_dediee(self):
        self._piece(
            '01', libelle="Acte d'engagement",
            controlee=PieceDossierAO.HORS_CONTROLE,
            motif="Modèle imposé par l'acheteur.")
        passe = coherence.passer_controle(self.dossier)
        infos = [item for item in passe['resultats']
                 if item['code_regle'] == 'AO_PIECES_HORS_CONTROLE']
        self.assertEqual(len(infos), 1)
        self.assertIn('1 pièce(s) HORS CONTRÔLE', infos[0]['message'])
        self.assertIn("Acte d'engagement", infos[0]['message'])
        self.assertIn('non vérifiées', infos[0]['message'])

    def test_une_piece_hors_controle_sans_motif_est_BLOQUANTE(self):
        PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, code='08',
            libelle='Caution', presente=True,
            controlee=PieceDossierAO.HORS_CONTROLE)
        passe = coherence.passer_controle(self.dossier)
        codes = {item['code_regle'] for item in passe['bloquants']}
        self.assertIn('AO_HORS_CONTROLE_SANS_MOTIF', codes)

    def test_un_dossier_sans_piece_fournie_n_affiche_rien(self):
        self._piece('04')
        passe = coherence.passer_controle(self.dossier)
        self.assertEqual(passe['nombre_hors_controle'], 0)
        self.assertEqual(passe['hors_controle'], [])
        self.assertNotIn(
            'AO_PIECES_HORS_CONTROLE',
            {item['code_regle'] for item in passe['resultats']})

    def test_une_piece_hors_controle_absente_n_est_pas_comptee(self):
        self._piece(
            '08', presente=False, controlee=PieceDossierAO.HORS_CONTROLE,
            motif='Pas encore reçue de la banque.')
        passe = coherence.passer_controle(self.dossier)
        self.assertEqual(passe['nombre_hors_controle'], 0)
