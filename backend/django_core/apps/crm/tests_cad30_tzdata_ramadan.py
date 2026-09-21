"""CAD30 — la base de fuseaux de l'IMAGE fait foi, et on le prouve en CI.

Le constat d'audit annonçait deux bascules Africa/Casablanca en mars 2027
(UTC+0 le 12/03, UTC+1 le 14/03) : c'est la règle du décret 2.18.855 de 2018
— UTC+1 permanent, retour à UTC+0 pendant le Ramadan —, telle que la voyait
la tzdata 2025.2 de l'hôte du critique.

**Cette règle est ABROGÉE.** Le Maroc est repassé DÉFINITIVEMENT à l'heure
GMT (UTC+0) dans la nuit du 19 au 20 septembre 2026 (02:00 → 01:00) : décret
n° 2.26.530 relatif à l'heure légale, Bulletin officiel n° 7521 du
29/06/2026. IANA l'encode depuis tzdata 2026c ; `requirements.txt` épingle
`tzdata==2026.4` et les Dockerfiles posent `PYTHONTZPATH=""` pour que
`zoneinfo` ignore `/usr/share/zoneinfo` (l'image Debian peut être EN RETARD)
et ne lise QUE ce paquet.

Ce fichier ne fige donc PAS des dates de 2027 qu'aucune tzdata à jour ne
produit plus. Il verrouille ce qui compte vraiment, et qui ne dépendra pas de
la prochaine mise à jour du paquet :

  * la base de fuseaux est bien PRÉSENTE dans l'image, et c'est le paquet
    ÉPINGLÉ qui répond (la version installée est comparée à celle de
    `requirements.txt`, jamais à un numéro recopié ici) ;
  * la bascule du DÉCRET est connue de l'image : +01:00 le 19/09/2026,
    +00:00 le 21/09/2026, et la marche 02:00 → 01:00 dans la nuit ;
  * plus AUCUNE bascule ensuite — ni saisonnière, ni Ramadan ;
  * le chemin « heure cible × transition » est sain : une heure LOCALE
    imposée reste cette heure-là des deux côtés de la bascule, parce que le
    moteur combine avec une `ZoneInfo` et jamais avec un décalage figé.
"""
import datetime
import importlib.metadata
import zoneinfo
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.crm import horaires
from apps.parametres.models import CompanyProfile

User = get_user_model()

CLE_FUSEAU = 'Africa/Casablanca'

#: La nuit du décret n° 2.26.530 (BO n° 7521 du 29/06/2026) : 02:00 → 01:00.
VEILLE_DU_DECRET = datetime.date(2026, 9, 19)
NUIT_DU_DECRET = datetime.date(2026, 9, 20)
LENDEMAIN_DU_DECRET = datetime.date(2026, 9, 21)

UTC_PLUS_UN = datetime.timedelta(hours=1)
UTC_ZERO = datetime.timedelta(0)

#: Jusqu'où on vérifie qu'aucune bascule ne revient. Cinq ans après le
#: décret : au-delà, une future réforme serait une NOUVELLE décision, pas une
#: régression de ce lot.
ANNEES_SANS_BASCULE = 5

REQUIREMENTS = (Path(__file__).resolve().parents[2] / 'requirements.txt')


def _decalage(jour, heure=12):
    return datetime.datetime(
        jour.year, jour.month, jour.day, heure, 0,
        tzinfo=zoneinfo.ZoneInfo(CLE_FUSEAU)).utcoffset()


def _version_epinglee():
    """La version de `tzdata` telle que `requirements.txt` l'épingle — lue,
    jamais recopiée ici."""
    for ligne in REQUIREMENTS.read_text(encoding='utf-8').splitlines():
        nette = ligne.strip()
        if nette.lower().startswith('tzdata=='):
            return nette.split('==', 1)[1].strip()
    return None


class LaBaseDeFuseauxEstDansLimageTests(SimpleTestCase):
    """« Une assertion sur la présence de tzdata dans l'image. »"""

    def test_le_fuseau_du_terrain_se_resout(self):
        self.assertIn(CLE_FUSEAU, zoneinfo.available_timezones())
        self.assertIsNotNone(zoneinfo.ZoneInfo(CLE_FUSEAU))

    def test_le_paquet_tzdata_est_installe(self):
        """Pas la tzdata du système : le paquet PyPI, seul lu par `zoneinfo`
        quand `PYTHONTZPATH` est vide (Dockerfiles)."""
        self.assertTrue(importlib.metadata.version('tzdata'))

    def test_la_version_installee_est_celle_qui_est_EPINGLEE(self):
        epinglee = _version_epinglee()
        self.assertIsNotNone(epinglee, str(REQUIREMENTS))
        self.assertEqual(importlib.metadata.version('tzdata'), epinglee)

    def test_le_moteur_dhoraires_utilise_une_ZoneInfo(self):
        """Un décalage FIGÉ (`timezone(timedelta(hours=1))`) donnerait la
        bonne heure onze mois sur douze et la mauvaise le douzième."""
        self.assertIsInstance(horaires.CASABLANCA, zoneinfo.ZoneInfo)
        self.assertEqual(str(horaires.CASABLANCA), CLE_FUSEAU)


class LaBasculeDuDecretTests(SimpleTestCase):
    """Le décret 2.26.530 est-il connu de l'image ?"""

    def test_la_veille_le_maroc_est_encore_a_UTC_plus_un(self):
        self.assertEqual(_decalage(VEILLE_DU_DECRET), UTC_PLUS_UN)

    def test_le_lendemain_il_est_a_UTC_zero(self):
        self.assertEqual(_decalage(LENDEMAIN_DU_DECRET), UTC_ZERO)

    def test_la_marche_se_fait_bien_a_deux_heures_du_matin(self):
        self.assertEqual(_decalage(NUIT_DU_DECRET, heure=1), UTC_PLUS_UN)
        self.assertEqual(_decalage(NUIT_DU_DECRET, heure=2), UTC_ZERO)

    def test_plus_AUCUNE_bascule_ensuite(self):
        """« Plus aucune bascule saisonnière ni Ramadan » — la phrase du
        décret, vérifiée jour par jour sur cinq ans."""
        jour = LENDEMAIN_DU_DECRET
        fin = datetime.date(LENDEMAIN_DU_DECRET.year + ANNEES_SANS_BASCULE,
                            1, 1)
        precedent = _decalage(jour)
        bascules = []
        while jour < fin:
            courant = _decalage(jour)
            if courant != precedent:
                bascules.append((jour, precedent, courant))
            precedent = courant
            jour += datetime.timedelta(days=1)
        self.assertEqual(bascules, [])
        self.assertEqual(precedent, UTC_ZERO)


class UneHeureCibleTraverseLaBasculeTests(TestCase):
    """Le chemin `heure_cible` × transition, sain par CONSTRUCTION — mais
    désormais vérifié plutôt que supposé."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD30 Solaire', slug='cad30-tz')
        CompanyProfile.objects.get_or_create(company=self.company)

    def test_une_heure_locale_imposee_reste_la_meme_des_deux_cotes(self):
        for jour in (VEILLE_DU_DECRET, LENDEMAIN_DU_DECRET):
            quand = horaires._combiner(jour, datetime.time(18, 0))
            self.assertEqual((quand.hour, quand.minute), (18, 0), jour)
            self.assertEqual(quand.date(), jour)

    def test_le_decalage_UTC_change_lui_bien_dun_jour_a_lautre(self):
        """La preuve que ce n'est pas un offset figé : la MÊME heure locale
        ne donne pas le même instant UTC des deux côtés."""
        avant = horaires._combiner(VEILLE_DU_DECRET, datetime.time(18, 0))
        apres = horaires._combiner(LENDEMAIN_DU_DECRET, datetime.time(18, 0))
        self.assertEqual(avant.utcoffset(), UTC_PLUS_UN)
        self.assertEqual(apres.utcoffset(), UTC_ZERO)
        # Deux jours d'écart en heure LOCALE… mais deux jours ET UNE HEURE en
        # instants réels. La soustraction se fait donc en UTC : entre deux
        # datetimes qui partagent le même `tzinfo`, Python soustrait les
        # heures MURALES et le décalage s'évaporerait.
        utc = datetime.timezone.utc
        self.assertEqual(apres.astimezone(utc) - avant.astimezone(utc),
                         datetime.timedelta(days=2, hours=1))

    def test_une_touche_recalee_un_jour_de_transition_garde_son_heure(self):
        """CAD21 × CAD30 : l'heure cible survit au passage au jour ouvré
        suivant, y compris au-dessus de la bascule."""
        # Samedi 19/09/2026 n'est pas ouvré : le recalage part au lundi 21,
        # c'est-à-dire de l'AUTRE côté de la bascule.
        depart = horaires._combiner(VEILLE_DU_DECRET, datetime.time(18, 0))
        self.assertEqual(depart.weekday(), 5)
        recalee = horaires.prochain_creneau_appel(
            depart, self.company, canal='appel',
            heure_cible=datetime.time(18, 0)
        ).astimezone(horaires.CASABLANCA)
        self.assertEqual(recalee.weekday(), 0)
        self.assertEqual((recalee.hour, recalee.minute), (18, 0))
        self.assertEqual(recalee.utcoffset(), UTC_ZERO)
