"""AOF151 — le ZIP de dépôt exclut par CONSTRUCTION, et refuse sur rouge.

Quatre promesses :
  1. contrôle rouge → génération REFUSÉE, avec le motif ;
  2. une pièce `interne` ou `directeur` ne peut PAS entrer, même demandée
     explicitement — c'est la visibilité qui décide, pas l'opérateur ;
  3. ratchet d'étanchéité (AOF129) étendu au ZIP : ni nom de fichier ni
     manifeste ne portent un mot réservé au directeur ;
  4. mémoire bornée : le pic d'allocation reste très inférieur au volume
     écrit — mesuré par `tracemalloc`, pas affirmé.

Run :
    python manage.py test apps.ao.tests.test_aof_pack_zip -v2
"""
import io
import json
import tracemalloc
import zipfile

from django.test import SimpleTestCase

from apps.ao.fabrique.pack_zip import (
    NOM_MANIFESTE, PackRefuse, ecrire_pack_zip, nom_de_fichier,
    pieces_deposables,
)


def flux(contenu):
    def _produire():
        yield contenu
    return _produire


def pieces_reelles():
    return [
        {'code': '00', 'libelle': 'Checklist partenaire',
         'visibilite': 'interne', 'format': 'docx', 'empreinte': '0' * 64,
         'flux': flux(b'checklist')},
        {'code': '01', 'libelle': 'Lettre de soumission',
         'visibilite': 'client', 'format': 'pdf', 'empreinte': '1' * 64,
         'flux': flux(b'%PDF lettre')},
        {'code': '04', 'libelle': 'Bordereau des prix',
         'visibilite': 'client', 'format': 'pdf', 'empreinte': '4' * 64,
         'flux': flux(b'%PDF bordereau')},
        {'code': '06', 'libelle': 'Planches A3', 'visibilite': 'client',
         'format': 'pdf', 'empreinte': '6' * 64, 'flux': flux(b'%PDF planche')},
        {'code': '09', 'libelle': 'Rentabilité attendue (direction)',
         'visibilite': 'directeur', 'format': 'xlsx', 'empreinte': '9' * 64,
         'flux': flux(b'PK xlsx')},
    ]


def ecrire(pieces=None, **options):
    tampon = io.BytesIO()
    manifeste = ecrire_pack_zip(
        tampon, pieces_reelles() if pieces is None else pieces,
        reference_dossier='AODOS-2026-08-0001',
        empreinte_pack='e' * 64, **options)
    tampon.seek(0)
    return tampon, manifeste


class RefusSurControleRougeTest(SimpleTestCase):
    def test_un_controle_rouge_refuse_le_zip_avec_son_motif(self):
        controle = {'bloquants': [
            {'code': 'LETTRES_CHIFFRES',
             'message': 'Arrêté en lettres divergent du total.'},
        ]}
        with self.assertRaises(PackRefuse) as capture:
            ecrire(controle=controle)
        self.assertIn('LETTRES_CHIFFRES', str(capture.exception))
        self.assertIn('divergent', str(capture.exception))

    def test_un_controle_vert_laisse_passer(self):
        tampon, _ = ecrire(controle={'bloquants': []})
        self.assertTrue(zipfile.is_zipfile(tampon))

    def test_aucune_piece_deposable_refuse_le_zip(self):
        interne = [p for p in pieces_reelles()
                   if p['visibilite'] != 'client']
        with self.assertRaises(PackRefuse) as capture:
            ecrire(interne)
        self.assertIn('aucune pièce déposable', str(capture.exception))


class ExclusionStructurelleTest(SimpleTestCase):
    def test_le_filtre_de_visibilite_est_isole_et_lisible(self):
        retenues, exclues = pieces_deposables(pieces_reelles())
        self.assertEqual([p['code'] for p in retenues], ['01', '04', '06'])
        self.assertEqual(sorted(p['visibilite'] for p in exclues),
                         ['directeur', 'interne'])

    def test_aucune_piece_interne_ou_directeur_dans_le_zip(self):
        tampon, manifeste = ecrire()
        with zipfile.ZipFile(tampon) as archive:
            noms = archive.namelist()
        joint = ' '.join(noms).lower()
        self.assertNotIn('rentabilité', joint)
        self.assertNotIn('checklist', joint)
        self.assertEqual([e['code'] for e in manifeste['pieces']],
                         ['01', '04', '06'])
        self.assertEqual(manifeste['exclues'], 2)

    def test_une_piece_directeur_demandee_explicitement_reste_dehors(self):
        """On ne peut pas « forcer » : la visibilité prime sur la demande."""
        demande = [p for p in pieces_reelles() if p['code'] == '09']
        demande += [p for p in pieces_reelles() if p['code'] == '01']
        tampon, manifeste = ecrire(demande)
        with zipfile.ZipFile(tampon) as archive:
            noms = [n for n in archive.namelist() if n != NOM_MANIFESTE]
        self.assertEqual(len(noms), 1)
        self.assertIn('Lettre de soumission', noms[0])

    def test_le_manifeste_compte_les_exclues_sans_les_nommer(self):
        tampon, _ = ecrire()
        with zipfile.ZipFile(tampon) as archive:
            manifeste = json.loads(archive.read(NOM_MANIFESTE).decode('utf-8'))
        self.assertEqual(manifeste['exclues'], 2)
        brut = json.dumps(manifeste, ensure_ascii=False).lower()
        self.assertNotIn('rentabilité', brut)
        self.assertNotIn('direction', brut)


class NommageTest(SimpleTestCase):
    def test_les_noms_sont_numerotes_et_en_francais(self):
        tampon, _ = ecrire()
        with zipfile.ZipFile(tampon) as archive:
            noms = sorted(n for n in archive.namelist() if n != NOM_MANIFESTE)
        self.assertEqual(noms, ['01 - Lettre de soumission.pdf',
                                '02 - Bordereau des prix.pdf',
                                '03 - Planches A3.pdf'])

    def test_les_caracteres_interdits_sont_nettoyes(self):
        nom = nom_de_fichier({'libelle': 'Note/calcul: v2*', 'format': 'pdf'},
                             numero=3)
        self.assertEqual(nom, '03 - Note calcul v2.pdf')

    def test_le_sommaire_est_inclus_quand_il_est_fourni(self):
        tampon, _ = ecrire(sommaire_html='<html>sommaire</html>')
        with zipfile.ZipFile(tampon) as archive:
            self.assertIn('00 - Sommaire.html', archive.namelist())


class EtancheiteZipTest(SimpleTestCase):
    def test_un_intitule_de_cout_refuse_le_zip(self):
        for mot in ('marge', 'coût de revient', 'rentabilité',
                    "prix d'achat"):
            pieces = pieces_reelles()
            pieces[1]['libelle'] = 'Note de {}'.format(mot)
            with self.assertRaises(PackRefuse, msg=mot) as capture:
                ecrire(pieces)
            self.assertIn(mot, str(capture.exception))

    def test_le_zip_produit_ne_porte_aucun_mot_interdit(self):
        tampon, _ = ecrire()
        with zipfile.ZipFile(tampon) as archive:
            joint = (' '.join(archive.namelist())
                     + archive.read(NOM_MANIFESTE).decode('utf-8')).lower()
        for mot in ('marge', 'coût de revient', "prix d'achat", 'bénéfice'):
            self.assertNotIn(mot, joint)


class MemoireBorneeTest(SimpleTestCase):
    """Le pic d'allocation est MESURÉ, pas affirmé."""

    OCTETS_PAR_BLOC = 256 * 1024
    BLOCS_PAR_PIECE = 8
    PIECES = 6  # 6 × 8 × 256 Kio = 12 Mio écrits

    def _piece(self, index):
        def _produire():
            for _ in range(self.BLOCS_PAR_PIECE):
                yield bytes(self.OCTETS_PAR_BLOC)
        return {'code': '{:02d}'.format(index), 'libelle': 'Planche',
                'visibilite': 'client', 'format': 'pdf',
                'empreinte': str(index) * 64, 'flux': _produire}

    def test_le_pic_memoire_reste_tres_inferieur_au_volume_ecrit(self):
        pieces = [self._piece(i) for i in range(1, self.PIECES + 1)]
        volume = self.OCTETS_PAR_BLOC * self.BLOCS_PAR_PIECE * self.PIECES
        tampon = io.BytesIO()
        tracemalloc.start()
        try:
            ecrire_pack_zip(tampon, pieces, reference_dossier='AODOS-1',
                            empreinte_pack='e' * 64)
            _courant, pic = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        # Le ZIP lui-même est en mémoire (BytesIO) mais les blocs de zéros se
        # compressent à quasi rien : ce qui est mesuré ici, c'est bien qu'AUCUNE
        # pièce entière (2 Mio) ni le pack entier (12 Mio) n'est matérialisé.
        self.assertLess(pic, 4 * 1024 * 1024,
                        'pic {} octets pour {} écrits'.format(pic, volume))

    def test_un_flux_non_callable_est_refuse(self):
        pieces = [{'code': '01', 'libelle': 'Lettre', 'visibilite': 'client',
                   'format': 'pdf', 'flux': b'octets entiers'}]
        with self.assertRaises(PackRefuse) as capture:
            ecrire(pieces)
        self.assertIn('CALLABLE', str(capture.exception))
