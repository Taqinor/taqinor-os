"""QJR406 (S3-F2) — les deux surfaces CLIENT passent enfin ``jour_reference``.

CE QUE LE ROUGE PROUVAIT. QJR164 avait bien câblé le paramètre
``jour_reference`` dans ``etude_horaire.jours_types_publics`` et
``etude_horaire.couverture_batterie_publique``, mais AUCUN des deux appelants
de production ne le passait :

    public_views._jours_types_publique      → jours_types_publics(kwc=…, …)
    public_views._couverture_batterie_publique
                                            → couverture_batterie_publique(…)

Les deux surfaces retombaient donc sur l'horloge du serveur
(``timezone.localdate()``, posée au fond de ``jours_types_annee``) pendant que
le devis persisté, lui, porte SON jour de référence (QJR232,
``domain.entrees.jour_reference_du_devis``). Le client qui rouvrait son lien
voyait une journée type qui n'était pas celle de son devis — écart visible
autour du Ramadan, dont la fenêtre décale la courbe de charge du soir.

Le test QJR164 ne pouvait pas l'attraper : il exerçait la SIGNATURE des deux
fonctions, jamais le chemin de production. Ici on appelle les DEUX VUES.

DATES. ``JOUR_A``/``JOUR_B`` sont les mêmes que celles de QJR164, lues sur la
table ``ramadan.RAMADAN_PLAGES`` (2027 : 8 fév → 8 mars ; 2028 : 28 jan →
25 fév) — jamais inventées : leurs Ramadans tombent sur des MOIS différents,
donc les jours types de janvier/février diffèrent. Aucun test ne compare quoi
que ce soit à « aujourd'hui » : deux devis de dates DIFFÉRENTES doivent rendre
des sorties différentes, ce qui reste vrai quelle que soit la date d'exécution
(pas de flakiness d'horloge).
"""
from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes import courbes_journalieres as CJ
from apps.ventes import etude_horaire as EH
from apps.ventes import public_views


#: Profil horaire figé servi aux deux vues (le chemin de lecture du devis
#: n'est pas le sujet de cette tâche : c'est la TRANSMISSION de la date).
_KWC = 6.0
_CONSO = [420.0] * 12
_VILLE = 'Casablanca'
_PROFIL = (_KWC, _CONSO, _VILLE, None, None, CJ.OCCUPATION_PRESENCE, None)

#: Banque de batteries figée (une seule ligne batterie de 4,6 kWh utiles).
_BANQUE = {
    'nb_packs': 1,
    'capacite_utile_totale_kwh': 4.6,
    'capacite_utile_pack_kwh': 4.6,
    'pack_decharge_kw': None,
    'pack_charge_kw': None,
    'ond_decharge_kw': None,
    'ond_charge_kw': None,
}

JOUR_A = date(2027, 1, 5)
JOUR_B = date(2028, 1, 5)


def _devis(date_creation=None, overrides=None):
    """Devis minimal : seules la date et le registre D12 comptent ici."""
    return SimpleNamespace(date_creation=date_creation,
                           overrides=overrides or {})


class _BaseSurfacesPubliques(SimpleTestCase):
    """Outillage commun : profil figé, banque figée, moteur RÉEL."""

    def _jours_types(self, devis):
        with mock.patch.object(public_views, '_profil_horaire_pour_devis',
                               return_value=_PROFIL):
            return public_views._jours_types_publique(devis)

    def _couverture(self, devis):
        with mock.patch.object(public_views, '_profil_horaire_pour_devis',
                               return_value=_PROFIL), \
                mock.patch.object(EH, 'banque_batterie_du_devis',
                                  return_value=dict(_BANQUE)):
            return public_views._couverture_batterie_publique(
                devis, {'avec_ok': True}, True, None)


class JoursTypesPubliqueAppelantTests(_BaseSurfacesPubliques):
    """Surface CLIENT n°1 : le bloc ``jours_types`` du payload public."""

    def test_deux_devis_de_dates_differentes_rendent_deux_journees_types(self):
        """ROUGE avant QJR406 : les deux sorties étaient IDENTIQUES (horloge)."""
        a = self._jours_types(_devis(date_creation=JOUR_A))
        b = self._jours_types(_devis(date_creation=JOUR_B))
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertNotEqual(a, b)

    def test_la_journee_type_servie_est_celle_du_devis(self):
        """La vue rend EXACTEMENT ce que le moteur rend pour CETTE date."""
        servi = self._jours_types(_devis(date_creation=JOUR_A))
        attendu = EH.jours_types_publics(
            kwc=_KWC, conso_kwh_mensuelles=_CONSO, ville=_VILLE,
            lat=None, lon=None, occupation=CJ.OCCUPATION_PRESENCE,
            equipements=None, jour_reference=JOUR_A)
        self.assertIsNotNone(attendu)
        self.assertEqual(servi, attendu)

    def test_surcharge_d12_prime_sur_la_date_du_devis(self):
        """QJR232 — ``etude.jour_reference`` déclaré prime, comme partout."""
        devis = _devis(
            date_creation=JOUR_A,
            overrides={'etude.jour_reference': {'valeur': JOUR_B.isoformat(),
                                                'origine': 'manuel'}})
        self.assertEqual(self._jours_types(devis),
                         self._jours_types(_devis(date_creation=JOUR_B)))


class CouvertureBatteriePubliqueAppelantTests(_BaseSurfacesPubliques):
    """Surface CLIENT n°2 : le curseur « N batteries »."""

    def test_deux_devis_de_dates_differentes_rendent_deux_couvertures(self):
        """ROUGE avant QJR406 : les deux sorties étaient IDENTIQUES (horloge)."""
        a = self._couverture(_devis(date_creation=JOUR_A))
        b = self._couverture(_devis(date_creation=JOUR_B))
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertNotEqual(a, b)

    def test_la_couverture_servie_est_celle_du_devis(self):
        servi = self._couverture(_devis(date_creation=JOUR_A))
        attendu = EH.couverture_batterie_publique(
            kwc=_KWC, conso_kwh_mensuelles=_CONSO,
            capacite_utile_pack_kwh=_BANQUE['capacite_utile_pack_kwh'],
            nb_packs_max=public_views._paliers_curseur_batterie(
                None, _BANQUE['nb_packs'],
                capacite_utile_pack_kwh=_BANQUE['capacite_utile_pack_kwh']),
            nb_packs_plancher=_BANQUE['nb_packs'],
            ville=_VILLE, lat=None, lon=None,
            occupation=CJ.OCCUPATION_PRESENCE, equipements=None,
            puissances_par_pack=dict(_BANQUE), jour_reference=JOUR_A)
        self.assertIsNotNone(attendu)
        self.assertEqual(servi, attendu)


class DevisSansJourDeReferenceTests(_BaseSurfacesPubliques):
    """Second test du `Done` : le devis SANS date garde l'horloge, inchangé."""

    def test_jours_types_sans_date_garde_le_repli_d_horloge(self):
        from django.utils import timezone
        servi = self._jours_types(_devis(date_creation=None))
        attendu = EH.jours_types_publics(
            kwc=_KWC, conso_kwh_mensuelles=_CONSO, ville=_VILLE,
            lat=None, lon=None, occupation=CJ.OCCUPATION_PRESENCE,
            equipements=None, jour_reference=timezone.localdate())
        self.assertEqual(servi, attendu)

    def test_couverture_sans_date_garde_le_repli_d_horloge(self):
        from django.utils import timezone
        servi = self._couverture(_devis(date_creation=None))
        attendu = EH.couverture_batterie_publique(
            kwc=_KWC, conso_kwh_mensuelles=_CONSO,
            capacite_utile_pack_kwh=_BANQUE['capacite_utile_pack_kwh'],
            nb_packs_max=public_views._paliers_curseur_batterie(
                None, _BANQUE['nb_packs'],
                capacite_utile_pack_kwh=_BANQUE['capacite_utile_pack_kwh']),
            nb_packs_plancher=_BANQUE['nb_packs'],
            ville=_VILLE, lat=None, lon=None,
            occupation=CJ.OCCUPATION_PRESENCE, equipements=None,
            puissances_par_pack=dict(_BANQUE),
            jour_reference=timezone.localdate())
        self.assertEqual(servi, attendu)


class ResolutionDeLaDateTests(SimpleTestCase):
    """``_jour_reference_publique`` n'invente aucune seconde règle."""

    def test_delegue_a_la_source_unique_du_domaine(self):
        from apps.ventes.domain.entrees import jour_reference_du_devis
        devis = _devis(date_creation=JOUR_A)
        self.assertEqual(public_views._jour_reference_publique(devis),
                         jour_reference_du_devis(devis))

    def test_une_resolution_impossible_ne_leve_pas(self):
        """Best-effort : ``None`` ⇒ repli d'horloge, jamais une page cassée."""
        with mock.patch('apps.ventes.domain.entrees.jour_reference_du_devis',
                        side_effect=RuntimeError('boom')):
            self.assertIsNone(
                public_views._jour_reference_publique(_devis()))
