"""ERR-QAC-I7-BLOCS-PERIMES-REPARATION — la commande qui répare les blocs
horaires déjà stockés sur la SOMME des deux options (avant I7).

DRY-RUN par défaut (rien n'est écrit, le diff est imprimé), ``--appliquer``
pour écrire ; les devis envoyés/acceptés sont listés à part ; aucun statut
n'est touché (règle #4).

Lancer :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_err_rafraichir_blocs_horaires"
"""
from io import StringIO

from django.core.management import call_command

from apps.ventes.domain.etudes import blocs_horaires_perimes
from apps.ventes.models import Devis
from apps.ventes.tests.test_etude_horaire_par_option import (
    KWC_AVEC, KWC_SANS, KWC_SOMME, LIGNES_COMMUNES, _Base)


class RafraichirBlocsHorairesTests(_Base):

    def _devis_perime(self, slug, statut='brouillon'):
        """Un devis divergent dont le bloc a été rangé AVANT I7 : bloc
        principal sur la somme des deux options, pas de bloc « sans »."""
        devis = self._rafraichir(self._devis(slug), force=True)
        ep = dict(devis.etude_params)
        self.assertIsInstance(ep.get('etude_horaire'), dict,
                              'étude horaire non calculée')
        ep['etude_horaire'] = dict(ep['etude_horaire'], kwc=KWC_SOMME)
        ep.pop('etude_horaire_sans', None)
        Devis.objects.filter(pk=devis.pk).update(etude_params=ep,
                                                 statut=statut)
        return Devis.objects.get(pk=devis.pk)

    def _lancer(self, *args):
        sortie = StringIO()
        call_command('rafraichir_blocs_horaires', *args, stdout=sortie)
        return sortie.getvalue()

    def test_detection_kwc_seulement(self):
        devis = self._devis_perime('i7r-detect')
        cles = [c for c, _kb, _att in blocs_horaires_perimes(devis)]
        self.assertEqual(cles, ['etude_horaire', 'etude_horaire_sans'])
        frais = self._rafraichir(self._devis('i7r-frais'), force=True)
        self.assertEqual(blocs_horaires_perimes(frais), [])
        commun = self._rafraichir(
            self._devis('i7r-commun', lignes=LIGNES_COMMUNES), force=True)
        self.assertEqual(blocs_horaires_perimes(commun), [])

    def test_dry_run_par_defaut_n_ecrit_rien(self):
        devis = self._devis_perime('i7r-dry')
        avant = dict(devis.etude_params)
        sortie = self._lancer()
        self.assertIn(devis.reference, sortie)
        self.assertIn('DRY-RUN', sortie)
        # Le diff montre le kWc recalculé.
        self.assertIn('9.94 → 5.68', sortie)
        apres = Devis.objects.get(pk=devis.pk)
        self.assertEqual(apres.etude_params, avant)
        self.assertEqual(apres.etude_params['etude_horaire']['kwc'], KWC_SOMME)

    def test_appliquer_repare_par_option_sans_toucher_au_statut(self):
        devis = self._devis_perime('i7r-app', statut='envoye')
        total_avant = devis.total_ttc
        sortie = self._lancer('--appliquer', '--refs', devis.reference)
        self.assertIn('APPLIQUÉ', sortie)
        frais = Devis.objects.get(pk=devis.pk)
        self.assertEqual(frais.statut, 'envoye')
        self.assertEqual(frais.total_ttc, total_avant)
        self.assertEqual(frais.etude_params['etude_horaire']['kwc'], KWC_AVEC)
        self.assertEqual(frais.etude_params['etude_horaire_sans']['kwc'],
                         KWC_SANS)
        self.assertEqual(blocs_horaires_perimes(frais), [])
        # Idempotente : une seconde passe ne trouve plus rien.
        self.assertIn('0 devis', self._lancer('--appliquer'))

    def test_appliquer_sans_refs_n_ecrit_pas_un_devis_envoye(self):
        envoye = self._devis_perime('i7r-noref', statut='envoye')
        avant = Devis.objects.get(pk=envoye.pk).etude_params
        sortie = self._lancer('--appliquer')
        self.assertIn('NON écrit', sortie)
        self.assertEqual(Devis.objects.get(pk=envoye.pk).etude_params, avant)

    def test_devis_envoyes_listes_a_part(self):
        envoye = self._devis_perime('i7r-env', statut='envoye')
        brouillon = self._devis_perime('i7r-bro')
        sortie = self._lancer()
        section = sortie.split('DEVIS ENVOYÉS/ACCEPTÉS', 1)
        self.assertEqual(len(section), 2, sortie)
        self.assertIn(envoye.reference, section[1])
        self.assertNotIn(brouillon.reference, section[1])

    def test_refs_filtre(self):
        a = self._devis_perime('i7r-ra')
        b = self._devis_perime('i7r-rb')
        sortie = self._lancer('--refs', a.reference)
        self.assertIn(a.reference, sortie)
        self.assertNotIn(b.reference, sortie)
