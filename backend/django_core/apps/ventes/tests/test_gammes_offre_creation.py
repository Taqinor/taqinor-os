"""GAMMES — 1. Création de la variante de gamme.

Partie 1 sur 6 de l'ancien `test_gammes_offre.py`, scindé PAR CLASSE le
2026-08-21 (voir `_gammes_offre_common.py`). Aucune assertion n'a changé.

Décisions fondateur 2026-08-18 couvertes ici :
  * une gamme = une VARIANTE de devis (devis frère complet, version_parent) —
    jamais un second axe DANS un devis (l'axe batterie reste intact) ;
  * le libellé est une DONNÉE (``etude_params['gamme']``) — aucune marque
    codée en dur, aucun changement de modèle.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_gammes_offre_creation -v 2
"""
from apps.ventes.models import Devis
from apps.ventes.services import gamme_nom
from apps.ventes.tests._gammes_offre_common import (
    GammeBase, add_ligne, make_client_obj, make_company, make_devis, make_user,
    url_gamme,
)


class TestCreerVarianteGamme(GammeBase):
    """La gamme réutilise la mécanique de variantes : devis frère complet."""

    def test_soeur_liee_par_version_parent_et_active(self):
        source, soeur = self._paire('DEV-GAM-010')
        self.assertEqual(soeur.version_parent_id, source.pk)
        self.assertTrue(soeur.is_active)
        self.assertEqual(soeur.statut, Devis.Statut.BROUILLON)
        # Règle #4 : la source ne change pas de statut.
        self.assertEqual(source.statut, Devis.Statut.BROUILLON)

    def test_lignes_clonees_a_lidentique(self):
        source, soeur = self._paire('DEV-GAM-011')
        self.assertEqual(soeur.lignes.count(), source.lignes.count())
        qtes = sorted(float(x) for x in
                      soeur.lignes.values_list('quantite', flat=True))
        self.assertEqual(qtes, sorted(float(x) for x in
                                      source.lignes.values_list('quantite',
                                                                flat=True)))

    def test_libelles_poses_des_deux_cotes(self):
        source, soeur = self._paire('DEV-GAM-012', nom='Premium')
        self.assertEqual(gamme_nom(soeur), 'Premium')
        self.assertEqual(gamme_nom(source), 'Essentielle')
        # Par défaut le devis PORTEUR est la gamme recommandée.
        self.assertTrue(source.etude_params['gamme']['recommandee'])
        self.assertFalse(soeur.etude_params['gamme']['recommandee'])

    def test_libelle_libre_aucune_marque_codee_en_dur(self):
        source, soeur = self._paire('DEV-GAM-013', nom='Confort Atlas')
        self.assertEqual(gamme_nom(soeur), 'Confort Atlas')
        self.assertEqual(gamme_nom(source), 'Essentielle')

    def test_recommandee_sur_la_nouvelle_gamme(self):
        source, soeur = self._paire('DEV-GAM-014', recommandee=True)
        self.assertTrue(soeur.etude_params['gamme']['recommandee'])
        self.assertFalse(source.etude_params['gamme']['recommandee'])

    def test_etude_params_non_partages_entre_soeurs(self):
        source, soeur = self._paire('DEV-GAM-015')
        self.assertIsNot(source.etude_params, soeur.etude_params)
        self.assertNotEqual(source.etude_params['gamme']['nom'],
                            soeur.etude_params['gamme']['nom'])

    def test_endpoint_cree_la_paire(self):
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-GAM-016')
        add_ligne(d, self.panneau, qty='8')
        resp = self.api.post(url_gamme(d.id), {'nom': 'Premium'},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['gamme']['statut'], 'brouillon')
        noms = {g['nom'] for g in resp.data['gammes']}
        self.assertEqual(noms, {'Essentielle', 'Premium'})

    def test_endpoint_autre_societe_404(self):
        autre = make_company('gamme-autre')
        etranger = make_devis(autre, make_user(autre, 'u_gamme_autre'),
                              make_client_obj(autre), 'DEV-GAM-X')
        resp = self.api.post(url_gamme(etranger.id), {}, format='json')
        self.assertEqual(resp.status_code, 404)
