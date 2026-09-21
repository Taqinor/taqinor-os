"""CALX244 — l'action ``raccordement`` (contrat CALX205), en HTTP.

Ce qui est prouvé ici :

* ``GET`` répond 200 avec les TROIS blocs du contrat et les CINQ verdicts,
  même sur un calepinage nu — l'état ``exemple_vide`` ;
* ``POST`` enregistre la saisie dans ``Calepinage.resultat`` (JSONField
  existant, aucune migration) et REND le raccordement recalculé : aucun
  second appel à enchaîner ;
* un ``GET`` qui suit un ``POST`` republie la MÊME saisie — c'est ce qui
  distingue une saisie persistée d'un aller-retour sans mémoire ;
* une limite d'élévation SANS sa source est refusée 400 en NOMMANT
  ``source_limite`` — le nom NU que le contrat CALX205 fige dans
  ``refus_limite_sans_source`` ; idem pour le cos φ et pour un régime de
  branchement hors 1/3 (règle fondateur : l'erreur désigne le champ) ;
* la saisie refusée n'entre PAS en base : un refus ne laisse aucune trace ;
* les clés inconnues du corps sont ignorées — le contrat fige sept champs ;
* sans ``calepinage_gerer``, le ``POST`` répond 403 alors que le ``GET``
  passe (garde ``PeutLireOuEcrireCalepinage``, CAL18) ;
* un calepinage d'une AUTRE société est INTROUVABLE (404), jamais
  « interdit » ;
* AUCUNE clé d'argent ne sort de la réponse (D-CALX 5).

Ces tests ont besoin de l'ORM : ils NE PEUVENT PAS être exécutés sur un
poste sans base (aucun docker, aucun PostgreSQL). La CI est leur gate.

Run :
    python manage.py test apps.calepinage.tests.test_api_raccordement -v2
"""
import re

from django.contrib.auth import get_user_model

from apps.calepinage.models import Calepinage
from apps.calepinage.permissions import CAL_VOIR
from apps.calepinage.views.raccordement import CLE_SAISIE
from apps.roles.models import Role

from .test_api_liste import BaseApiCalepinage, url_detail

User = get_user_model()

#: Les cinq contrôles, dans l'ordre où le contrat CALX205 les publie.
CODES = ['elevation_tension', 'puissance_souscrite', 'regime_phases',
         'tension_nominale', 'desequilibre_phases']

#: Les mots d'argent qui n'ont rien à faire dans une pièce électrique.
HORS_SUJET = ('prix', 'montant', 'mad', 'tva', 'remise')


def url_raccordement(pk):
    return f'{url_detail(pk)}raccordement/'


class ActionRaccordementTest(BaseApiCalepinage):
    """La porte HTTP du point de raccordement réseau."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')

    def _utilisateur_lecteur(self):
        """Un compte qui VOIT les calepinages, et rien de plus."""
        role = Role.objects.create(company=self.company, nom='Lecteur CALX244',
                                   permissions=[CAL_VOIR])
        return User.objects.create_user(
            username='calx244_lecteur', password='x', company=self.company,
            role=role)

    # ── Lecture ──────────────────────────────────────────────────────────
    def test_get_rend_les_trois_blocs(self):
        reponse = self.api.get(url_raccordement(self.calepinage.pk))

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(sorted(reponse.data),
                         ['calcul', 'saisie', 'verdicts'])

    def test_get_rend_toujours_les_cinq_verdicts(self):
        reponse = self.api.get(url_raccordement(self.calepinage.pk))

        self.assertEqual([v['code'] for v in reponse.data['verdicts']],
                         CODES)

    def test_sans_saisie_chaque_verdict_est_omis_et_dit_pourquoi(self):
        reponse = self.api.get(url_raccordement(self.calepinage.pk))

        for verdict in reponse.data['verdicts']:
            with self.subTest(code=verdict['code']):
                self.assertEqual(verdict['statut'], 'omis')
                self.assertTrue(verdict['detail'].strip())

    def test_aucune_grandeur_n_est_publiee_a_zero(self):
        reponse = self.api.get(url_raccordement(self.calepinage.pk))

        for champ, valeur in reponse.data['calcul'].items():
            with self.subTest(champ=champ):
                self.assertIsNone(valeur)

    # ── Écriture ─────────────────────────────────────────────────────────
    def test_post_enregistre_et_republie(self):
        reponse = self.api.post(
            url_raccordement(self.calepinage.pk),
            {'puissance_souscrite_kva': 12, 'phases': 3,
             'tension_nominale_v': 400},
            format='json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['saisie']['puissance_souscrite_kva'],
                         12.0)
        self.calepinage.refresh_from_db()
        self.assertEqual(
            self.calepinage.resultat[CLE_SAISIE]['tension_nominale_v'],
            400.0)

    def test_la_saisie_survit_au_get_suivant(self):
        self.api.post(url_raccordement(self.calepinage.pk),
                      {'phases': 1, 'tension_nominale_v': 230},
                      format='json')

        reponse = self.api.get(url_raccordement(self.calepinage.pk))

        self.assertEqual(reponse.data['saisie']['phases'], 1)
        self.assertEqual(reponse.data['saisie']['tension_nominale_v'], 230.0)

    def test_une_cle_inconnue_n_entre_pas_en_base(self):
        self.api.post(url_raccordement(self.calepinage.pk),
                      {'phases': 3, 'numero_compteur': 'X1'}, format='json')

        self.calepinage.refresh_from_db()
        self.assertNotIn('numero_compteur',
                         self.calepinage.resultat[CLE_SAISIE])

    def test_le_post_n_ecrase_pas_le_reste_du_resultat(self):
        self.calepinage.resultat = {'sld_edition': {'libelles': {}}}
        self.calepinage.save(update_fields=['resultat'])

        self.api.post(url_raccordement(self.calepinage.pk), {'phases': 3},
                      format='json')

        self.calepinage.refresh_from_db()
        self.assertIn('sld_edition', self.calepinage.resultat)

    # ── Refus : le champ fautif est NOMMÉ ────────────────────────────────
    def test_limite_sans_source_est_refusee_en_nommant_le_champ(self):
        reponse = self.api.post(url_raccordement(self.calepinage.pk),
                                {'limite_elevation_pct': 3}, format='json')

        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('source_limite', reponse.data)

    def test_cos_phi_sans_source_est_refuse_en_nommant_le_champ(self):
        reponse = self.api.post(url_raccordement(self.calepinage.pk),
                                {'cos_phi_impose': 0.9}, format='json')

        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('source_cos_phi', reponse.data)

    def test_un_regime_hors_1_et_3_est_refuse(self):
        reponse = self.api.post(url_raccordement(self.calepinage.pk),
                                {'phases': 2}, format='json')

        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('phases', reponse.data)

    def test_un_refus_ne_laisse_aucune_trace_en_base(self):
        self.api.post(url_raccordement(self.calepinage.pk),
                      {'limite_elevation_pct': 3}, format='json')

        self.calepinage.refresh_from_db()
        self.assertNotIn(CLE_SAISIE, self.calepinage.resultat or {})

    # ── Droits et société ────────────────────────────────────────────────
    def test_le_lecteur_lit_mais_n_ecrit_pas(self):
        """CAL18 — la garde choisit son code par la MÉTHODE, pas par la
        classe."""
        api_lecteur = self._client(self._utilisateur_lecteur())

        lecture = api_lecteur.get(url_raccordement(self.calepinage.pk))
        ecriture = api_lecteur.post(url_raccordement(self.calepinage.pk),
                                    {'phases': 3}, format='json')

        self.assertEqual(lecture.status_code, 200, lecture.data)
        self.assertEqual(ecriture.status_code, 403, ecriture.data)

    def test_sans_aucun_droit_calepinage_la_lecture_est_refusee(self):
        reponse = self.api_sans.get(url_raccordement(self.calepinage.pk))

        self.assertEqual(reponse.status_code, 403, reponse.data)

    def test_un_calepinage_d_une_autre_societe_est_introuvable(self):
        reponse = self.api_autre.get(url_raccordement(self.calepinage.pk))

        self.assertEqual(reponse.status_code, 404, reponse.data)

    def test_le_post_d_une_autre_societe_est_introuvable(self):
        reponse = self.api_autre.post(url_raccordement(self.calepinage.pk),
                                      {'phases': 3}, format='json')

        self.assertEqual(reponse.status_code, 404, reponse.data)

    # ── Hors sujet ───────────────────────────────────────────────────────
    def test_aucun_mot_d_argent_dans_la_reponse(self):
        reponse = self.api.get(url_raccordement(self.calepinage.pk))
        texte = str(reponse.data).lower()

        for mot in HORS_SUJET:
            with self.subTest(mot=mot):
                self.assertIsNone(
                    re.search(r'\b%s\b' % mot, texte),
                    "Le calepinage ne calcule aucun argent (D-CALX 5).")
