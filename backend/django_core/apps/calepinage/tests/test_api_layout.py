"""CAL18 — l'action ``layout`` (GET/POST) du calepinage.

Ce qui est prouvé ici :

* le POST accepte le layout NU et les deux enveloppes (``layout`` /
  ``roof_layout``) — les mêmes que côté ventes et côté AO ;
* renvoyer le MÊME document répond ``{"inchange": true}`` et n'ajoute AUCUNE
  version ; un document modifié en ajoute exactement une ;
* aucun statut n'est écrit (règle #4) : le calepinage reste où il est ;
* un corps vide est refusé 400 avec un message français nommant le champ ;
* un calepinage d'une AUTRE société est introuvable (404), jamais interdit ;
* sans ``calepinage_gerer``, le POST répond 403 (la lecture, elle, suffit au
  GET).

Run :
    python manage.py test apps.calepinage.tests.test_api_layout -v2
"""
from apps.calepinage.models import Calepinage, CalepinageVersion

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {'schema_version': 2, 'result': {'panels': 12}, 'zones': [{'id': 1}]}
LAYOUT_2 = {'schema_version': 2, 'result': {'panels': 14}, 'zones': [{'id': 1}]}


def url_layout(pk):
    return f'{url_detail(pk)}layout/'


class ActionLayoutTest(BaseApiCalepinage):
    def _poster(self, pk, corps, api=None):
        """ACAL316 — If-Match obligatoire : le jeton lu juste avant d'écrire
        (``""`` pour un document encore vide)."""
        reponse = self.api.get(url_layout(pk))
        donnees = getattr(reponse, 'data', None) or {}
        jeton = donnees.get('empreinte_document') or ''
        return (api or self.api).post(url_layout(pk), corps, format='json',
                                      HTTP_IF_MATCH=f'"{jeton}"')

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=42, titre='Chez la voisine')

    def _versions(self):
        return CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()

    def test_get_rend_la_conception_et_son_empreinte(self):
        reponse = self.api.get(url_layout(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNone(reponse.data['roof_layout'])
        self.assertIsNone(reponse.data['layout_hash'])

    def test_post_nu_enregistre_et_historise(self):
        reponse = self._poster(self.calepinage.pk, LAYOUT)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(reponse.data['inchange'])
        self.assertIsNotNone(reponse.data['version'])
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.roof_layout, LAYOUT)
        self.assertEqual(len(self.calepinage.layout_hash), 64)
        self.assertEqual(self._versions(), 1)

    def test_post_enveloppes_acceptees(self):
        for enveloppe in ('layout', 'roof_layout'):
            with self.subTest(enveloppe=enveloppe):
                reponse = self._poster(self.calepinage.pk, {enveloppe: LAYOUT})
                self.assertEqual(reponse.status_code, 200, reponse.data)
                self.calepinage.refresh_from_db()
                self.assertEqual(self.calepinage.roof_layout, LAYOUT)

    def test_renvoi_a_l_identique_est_inchange(self):
        self._poster(self.calepinage.pk, LAYOUT)
        reponse = self._poster(self.calepinage.pk, LAYOUT)
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.data['inchange'])
        self.assertIsNone(reponse.data['version'])
        self.assertEqual(self._versions(), 1)

    def test_layout_modifie_ajoute_une_version(self):
        self._poster(self.calepinage.pk, LAYOUT)
        self._poster(self.calepinage.pk, LAYOUT_2)
        self.assertEqual(self._versions(), 2)

    def test_aucun_statut_n_est_ecrit(self):
        avant = self.calepinage.statut
        self._poster(self.calepinage.pk, LAYOUT)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.statut, avant)

    def test_corps_vide_refuse_en_francais(self):
        # ENF11 nocturne : l'If-Match manquant est jugé AVANT le corps (428) —
        # le corps vide se juge donc avec le jeton, comme l'écran l'envoie.
        reponse = self._poster(self.calepinage.pk, {})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('roof_layout', reponse.data)

    def test_autre_societe_introuvable(self):
        reponse = self._poster(self.etranger.pk, LAYOUT)
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_d_ecriture_403(self):
        reponse = self._poster(self.calepinage.pk, LAYOUT, api=self.api_sans)
        self.assertEqual(reponse.status_code, 403)

    def test_caractere_nul_en_cle_ou_en_valeur_est_un_conflit_409(self):
        """ENF11 (api-fuzz-full 24/10) : le document est un objet libre, un
        NUL (clé OU texte imbriqué) ne se dit pas au schéma -> 409, jamais 400
        sur un corps « conforme » ni 500 à l'INSERT JSONB ; rien n'est écrit."""
        for corps in ({'zones': [{'id': 1}], 'cl\x00e': 1},
                      {'zones': [{'id': 1, 'nom': 'a\x00b'}]}):
            with self.subTest(corps=corps):
                reponse = self._poster(self.calepinage.pk, corps)
                self.assertEqual(reponse.status_code, 409, reponse.data)
        self.calepinage.refresh_from_db()
        self.assertIsNone(self.calepinage.roof_layout)


def url_brouillon(pk):
    return f'{url_detail(pk)}brouillon/'


class BrouillonServeurTest(BaseApiCalepinage):
    """ACAL400 — le brouillon d'atelier côté serveur, privé à l'auteur.

    Écrire un brouillon ne crée AUCUNE version et ne change ni
    ``layout_hash``, ni l'empreinte « document », ni ``updated_at``, ni le
    journal (D-ACAL-4/21) ; il est périmé dès que le document change.
    Mutant : ``save()`` au lieu de ``update()`` ⇒ ``updated_at`` bouge, rouge.
    """

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=42, titre='Chez la voisine')

    _poster = ActionLayoutTest._poster
    _versions = ActionLayoutTest._versions

    def _corps(self, base, layout=LAYOUT_2):
        return {'layout': layout, 'horodatage': '2026-11-20T09:15:00.000Z',
                'base_empreinte': base}

    def _base(self):
        reponse = self.api.get(url_layout(self.calepinage.pk))
        return reponse.data['empreinte_document'] or ''

    def _etat(self):
        from apps.records.models import Activity

        self.calepinage.refresh_from_db()
        return (self._versions(), self.calepinage.layout_hash, self._base(),
                self.calepinage.updated_at,
                Activity.objects.filter(object_id=self.calepinage.pk).count())

    def test_put_ne_cree_ni_version_ni_empreinte_ni_journal(self):
        self._poster(self.calepinage.pk, LAYOUT)
        avant = self._etat()
        reponse = self.api.put(url_brouillon(self.calepinage.pk),
                               self._corps(avant[2]), format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._etat(), avant)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.roof_layout, LAYOUT)

    def test_get_rend_la_forme_du_contrat_puis_null_apres_delete(self):
        import json
        from pathlib import Path

        contrat = json.loads(
            (Path(__file__).resolve().parent.parent / 'contract_samples'
             / 'calepinage_brouillon.json').read_text(encoding='utf-8'))
        url = url_brouillon(self.calepinage.pk)
        self.assertIsNone(contrat['exemple_vide'])
        self.assertIsNone(self.api.get(url).data)
        self.api.put(url, self._corps(self._base()), format='json')
        lu = self.api.get(url).data
        self.assertEqual(set(lu), set(contrat['exemple']))
        self.assertEqual(lu['layout'], LAYOUT_2)
        self.assertEqual(self.api.delete(url).status_code, 200)
        self.assertIsNone(self.api.get(url).data)

    def test_base_perimee_get_null(self):
        url = url_brouillon(self.calepinage.pk)
        self.api.put(url, self._corps(self._base()), format='json')
        self.assertIsNotNone(self.api.get(url).data)
        self._poster(self.calepinage.pk, LAYOUT)  # le document change
        self.assertIsNone(self.api.get(url).data)

    def test_un_autre_utilisateur_ne_lit_pas_le_brouillon(self):
        from django.contrib.auth import get_user_model

        url = url_brouillon(self.calepinage.pk)
        self.api.put(url, self._corps(self._base()), format='json')
        collegue = get_user_model().objects.create_user(
            username='cal_api_collegue', password='x', company=self.company,
            role=self.role)
        reponse = self._client(collegue).get(url)
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNone(reponse.data)
        self.assertIsNotNone(self.api.get(url).data)

    def test_autre_societe_404(self):
        url = url_brouillon(self.etranger.pk)
        self.assertEqual(self.api.get(url).status_code, 404)
        reponse = self.api.put(url, self._corps(''), format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_corps_refuses_en_nommant_le_champ(self):
        url = url_brouillon(self.calepinage.pk)
        reponse = self.api.put(url, {'layout': 3, 'horodatage': 'x',
                                     'base_empreinte': ''}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('layout', reponse.data)
        reponse = self.api.put(url, self._corps(
            '', layout={'zones': [{'nom': 'a\x00b'}]}), format='json')
        self.assertEqual(reponse.status_code, 409)
        self.assertIn('layout', reponse.data)
        self.assertIsNone(self.api.get(url).data)

    def test_brouillons_absents_du_detail_et_de_l_export(self):
        from .acal_livrables_helpers import patch_materiel

        self.api.put(url_brouillon(self.calepinage.pk),
                     self._corps(self._base()), format='json')
        detail = self.api.get(url_detail(self.calepinage.pk))
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn('brouillons_atelier', detail.data)
        with patch_materiel():
            export = self.api.get(
                f'{url_detail(self.calepinage.pk)}export-projet.json/')
        self.assertEqual(export.status_code, 200)
        self.assertNotIn(b'brouillons_atelier', export.content)
