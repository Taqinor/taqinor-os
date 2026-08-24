"""UNE SEULE VÉRITÉ POUR LA CONSOMMATION PUBLIÉE (24/08/2026).

Le devis de production DEV-202608-0023 servait ``monthly_consumption: []``
alors qu'il vient du générateur avec un lead PORTEUR DE FACTURES : le graphe
journalier perdait la ligne « votre consommation : N kWh/jour », juste à côté
d'économies calculées sur cette même consommation.

CAUSE RACINE. Il y avait DEUX chemins pour la même donnée :

  1. ``etude_horaire.profil_depuis_factures`` — LE résolveur du moteur (12 kWh
     saisis › 12 factures réelles › facture d'hiver/été), back-calculé au
     barème de la société ou à la grille nationale du millésime. Sa sortie est
     persistée sur le devis (``etude_params['etude_horaire']``) et sert TOUT le
     reste : économies mensuelles, synthèse du PDF, dimensionnement.
  2. ``public_views._monthly_consumption`` — un SECOND chemin, plus étroit :
     ``pricing.kwh_from_bill`` exige le ``distributeur`` du lead et, sans lui,
     signale une estimation que la garde M10 traduit (à juste titre) par une
     série vide. Or le webhook du tunnel pose explicitement « autre » quand le
     visiteur répond « inconnu » — et « autre » n'est dans aucune table.

Le second chemin devient un REPLI : la charge utile publique lit d'abord la
série que le moteur a déjà résolue. La garde M10 reste entièrement en place sur
ce repli, et rien n'est inventé au passage — le chemin prioritaire ne divise
JAMAIS une facture par un prix moyen (``bareme.kwh_depuis_facture_mad`` inverse
la vraie fonction de facturation par dichotomie).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_conso_publique_source_unique -v 2
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes import public_views
from apps.ventes.services import rafraichir_etude_horaire_devis

from .test_cj2b_economies_publiques import _CJ2bBase


def _bloc(source='facture_hiver', valeurs=None):
    """Bloc horaire MINIMAL de la forme réellement persistée par le moteur."""
    valeurs = valeurs if valeurs is not None else [100 + m for m in range(12)]
    return {
        'source_consommation': source,
        'mois': [{'mois': m + 1, 'consommation_kwh': float(valeurs[m])}
                 for m in range(12)],
    }


def _devis_stub(etude_params):
    return SimpleNamespace(etude_params=etude_params, lead=None, client_id=None,
                           company_id=None)


# ═══════════════════════════════════════════════════════════════════════════
# La lecture du bloc horaire — pure, sans base de données
# ═══════════════════════════════════════════════════════════════════════════

class LectureDuBlocHoraireTests(SimpleTestCase):
    def _lire(self, etude_params):
        return public_views._monthly_consumption_etude(
            _devis_stub(etude_params))

    def test_les_douze_mois_sont_rendus_dans_l_ordre_du_calendrier(self):
        valeurs = [110, 120, 130, 140, 150, 160,
                   170, 180, 190, 200, 210, 220]
        bloc = _bloc(valeurs=valeurs)
        # Ordre volontairement mélangé : la clé « mois » fait foi, pas la
        # position dans la liste persistée.
        bloc['mois'] = list(reversed(bloc['mois']))
        self.assertEqual(self._lire({'etude_horaire': bloc}), valeurs)

    def test_les_quatre_sources_reelles_sont_acceptees(self):
        for source in ('kwh_mensuels_saisis', 'factures_mensuelles_reelles',
                       'facture_hiver', 'facture_hiver_ete'):
            self.assertEqual(len(self._lire({'etude_horaire': _bloc(source)})),
                             12, source)

    def test_une_source_non_reelle_est_refusee(self):
        """Z2 — pas d'ancrage réel, pas de chiffre : jamais une supposition."""
        for source in ('absente', 'inconnue', '', None, 'forfait_maison'):
            self.assertEqual(self._lire({'etude_horaire': _bloc(source)}), [],
                             repr(source))

    def test_un_bloc_incomplet_ou_corrompu_ne_sert_rien(self):
        bloc_court = _bloc()
        bloc_court['mois'] = bloc_court['mois'][:11]
        bloc_texte = _bloc()
        bloc_texte['mois'][3]['consommation_kwh'] = 'beaucoup'
        bloc_negatif = _bloc()
        bloc_negatif['mois'][7]['consommation_kwh'] = -5.0
        bloc_doublon = _bloc()
        bloc_doublon['mois'][5]['mois'] = 1
        bloc_zero = _bloc(valeurs=[0] * 12)
        for cas, bloc in (('11 mois', bloc_court), ('texte', bloc_texte),
                          ('négatif', bloc_negatif),
                          ('mois dupliqué', bloc_doublon),
                          ('année nulle', bloc_zero),
                          ('pas de bloc', None), ('bloc texte', 'oui')):
            self.assertEqual(
                self._lire({} if bloc is None else {'etude_horaire': bloc}),
                [], cas)

    def test_aucun_etude_params_ne_casse_rien(self):
        self.assertEqual(
            public_views._monthly_consumption_etude(object()), [])


# ═══════════════════════════════════════════════════════════════════════════
# Le câblage complet — charge utile publique
# ═══════════════════════════════════════════════════════════════════════════

class ConsoPubliqueTests(_CJ2bBase):
    """La fixture CJ2b porte EXACTEMENT le cas cassé : un lead avec une
    facture d'hiver RÉELLE (1 800 MAD) et AUCUN distributeur."""

    def test_la_serie_est_servie_meme_sans_distributeur_sur_le_lead(self):
        devis, link = self._devis(
            'conso-sansdistrib', scenario='Les deux (Sans + Avec)')
        self.assertFalse(devis.lead.distributeur,
                         'fixture invalide : ce test doit porter sur un lead '
                         'SANS distributeur, le cas qui servait []')
        rafraichir_etude_horaire_devis(devis)
        devis.refresh_from_db()
        bloc = (devis.etude_params or {}).get('etude_horaire')
        self.assertIsNotNone(
            bloc, 'fixture invalide : aucun bloc horaire persisté')

        payload = self._payload(link)
        conso = payload['monthly_consumption']
        self.assertEqual(len(conso), 12)
        self.assertTrue(all(v > 0 for v in conso), conso)
        # AUCUN second calcul : ce sont les mois du bloc horaire, arrondis.
        attendu = [round(m['consommation_kwh'])
                   for m in sorted(bloc['mois'], key=lambda m: m['mois'])]
        self.assertEqual(conso, attendu)

    def test_le_bloc_consommation_du_graphe_journalier_est_servi(self):
        """C'est LE symptôme visible : « votre consommation : N kWh/jour »
        n'apparaît que si la série mensuelle atteint les courbes."""
        devis, link = self._devis(
            'conso-courbes', scenario='Les deux (Sans + Avec)')
        rafraichir_etude_horaire_devis(devis)

        payload = self._payload(link)
        courbes = payload.get('courbes_journalieres') or {}
        self.assertIn('consommation', courbes)
        self.assertTrue(courbes['consommation'])
        for saison, serie in courbes['consommation'].items():
            self.assertGreater(serie['kwh_jour'], 0, saison)

    def test_sans_lead_ni_facture_la_serie_reste_vide(self):
        """Comportement actuel INTACT : rien de réel, rien de servi (omission
        honnête, jamais une estimation inventée)."""
        devis, link = self._devis(
            'conso-sanslead', scenario='Sans batterie', avec_lead=False)
        rafraichir_etude_horaire_devis(devis)
        devis.refresh_from_db()
        self.assertIsNone((devis.etude_params or {}).get('etude_horaire'))

        payload = self._payload(link)
        self.assertEqual(payload['monthly_consumption'], [])
        # …et rien ne prétend connaître sa consommation journalière.
        self.assertNotIn(
            'consommation', payload.get('courbes_journalieres') or {})
