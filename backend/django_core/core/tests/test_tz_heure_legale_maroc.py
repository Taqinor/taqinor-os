"""Heure légale marocaine — les deux gardes de ``core/checks_tz.py``.

LE FAIT. Le Maroc est repassé DÉFINITIVEMENT à l'heure GMT (UTC+0) dans la nuit
du 19 au 20 septembre 2026 (02:00 → 01:00) : décret n° 2.26.530 relatif à
l'heure légale, Bulletin officiel n° 7521 du 29/06/2026, qui abroge le décret
2.18.855 de 2018 (UTC+1 permanent, retour à UTC+0 pendant le Ramadan). Plus
aucune bascule saisonnière ni Ramadan.

CE QUE CES TESTS PROUVENT :

* le contrôle Python rend ``[]`` avec la base de fuseaux RÉELLE de cet
  environnement (donc : le pin ``tzdata==2026.4`` est bien en place) ;
* il rend une ERREUR qui NOMME la cause quand la base est périmée — simulée en
  remplaçant ``ZoneInfo`` par un fuseau figé à UTC+1, c'est-à-dire exactement ce
  que rendait ``tzdata`` avant la version 2026c ;
* il rend une ERREUR distincte quand le fuseau est introuvable (paquet
  ``tzdata`` absent alors que ``PYTHONTZPATH`` est vide) ;
* le contrôle Postgres ne touche PAS la base tant que Django ne demande pas les
  contrôles de base de données, interroge la VRAIE base sans rien casser quand
  elle est à jour, et avertit (sans bloquer) quand elle est périmée.

Lancer :
    docker compose exec django_core python manage.py test \
        core.tests.test_tz_heure_legale_maroc -v 2
"""
import datetime as dt
from unittest import mock

from django.core.checks import ERROR, WARNING
from django.db import connection
from django.test import SimpleTestCase, TestCase

from core import checks_tz

#: La base de fuseaux d'AVANT le décret : Africa/Casablanca y vaut UTC+1 même
#: le 21/09/2026. ``timezone(timedelta(hours=1))`` est un vrai ``tzinfo``, donc
#: ``astimezone()`` le traite comme n'importe quel fuseau.
FUSEAU_PERIME = dt.timezone(dt.timedelta(hours=1))


class BaseDeFuseauxDePythonTests(SimpleTestCase):
    """Le contrôle BLOQUANT — ``verifier_heure_legale_marocaine``."""

    def test_la_base_reelle_de_cet_environnement_connait_le_decret(self):
        """Le test qui compte : avec la tzdata RÉELLEMENT installée ici, le
        Maroc est à UTC+0 le 21/09/2026 et le contrôle ne dit rien."""
        self.assertEqual(checks_tz.decalage_maroc(), dt.timedelta(0))
        self.assertEqual(checks_tz.verifier_heure_legale_marocaine(), [])

    def test_la_veille_de_la_bascule_le_maroc_est_encore_a_utc_plus_1(self):
        """Contrôle POSITIF de la base installée : elle ne dit pas « 0 »
        partout, elle connaît la bascule elle-même. 19/09/2026 = encore UTC+1."""
        veille = dt.datetime(2026, 9, 19, 12, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(checks_tz.decalage_maroc(veille),
                         dt.timedelta(hours=1))

    def test_plus_aucune_bascule_saisonniere_ni_ramadan(self):
        """Le décret supprime les DEUX bascules : un hiver, un été et un mois
        de Ramadan postérieurs valent tous UTC+0."""
        for instant in (dt.datetime(2027, 3, 1, 12, tzinfo=dt.timezone.utc),
                        dt.datetime(2027, 7, 1, 12, tzinfo=dt.timezone.utc),
                        dt.datetime(2028, 2, 10, 12, tzinfo=dt.timezone.utc)):
            self.assertEqual(checks_tz.decalage_maroc(instant),
                             dt.timedelta(0), instant.isoformat())

    def test_une_base_perimee_est_une_erreur_bloquante_qui_nomme_la_cause(self):
        with mock.patch.object(checks_tz, 'ZoneInfo',
                               return_value=FUSEAU_PERIME):
            constats = checks_tz.verifier_heure_legale_marocaine()
        self.assertEqual([c.id for c in constats],
                         [checks_tz.ID_PYTHON_PERIMEE])
        constat = constats[0]
        self.assertEqual(constat.level, ERROR)
        # La CAUSE est nommée (le texte, pas seulement un identifiant)…
        self.assertIn('PÉRIMÉE', constat.msg)
        self.assertIn('2.26.530', constat.msg)
        self.assertIn('UTC+1', constat.msg)
        # …et le REMÈDE aussi.
        self.assertIn('tzdata==2026.4', constat.hint)
        self.assertIn('PYTHONTZPATH', constat.hint)
        self.assertIn('--build', constat.hint)

    def test_un_fuseau_introuvable_est_une_erreur_distincte(self):
        with mock.patch.object(checks_tz, 'ZoneInfo',
                               side_effect=KeyError('Africa/Casablanca')):
            self.assertIsNone(checks_tz.decalage_maroc())
            constats = checks_tz.verifier_heure_legale_marocaine()
        self.assertEqual([c.id for c in constats],
                         [checks_tz.ID_PYTHON_ABSENTE])
        self.assertIn('tzdata', constats[0].hint)

    def test_le_controle_est_enregistre_sans_etiquette_donc_il_bloque_le_boot(self):
        """Sans étiquette, il tourne à CHAQUE commande ``manage.py`` — c'est
        tout l'objet : le service ne démarre pas avec une heure fausse."""
        from django.core.checks.registry import registry

        enregistres = {getattr(c, '__name__', ''): c
                       for c in registry.get_checks()}
        self.assertIn('verifier_heure_legale_marocaine', enregistres)
        self.assertEqual(
            getattr(enregistres['verifier_heure_legale_marocaine'], 'tags', ()),
            ())


class BaseDeFuseauxDePostgresTests(TestCase):
    """Le contrôle AVERTISSEUR — ``verifier_heure_legale_postgres``."""

    def test_sans_databases_il_ne_touche_pas_la_base(self):
        """Convention Django des contrôles ``database`` : ``manage.py check``
        sans ``--database`` passe ``databases=None`` et rien ne doit s'ouvrir."""
        with mock.patch('django.db.connections') as connexions:
            self.assertEqual(checks_tz.verifier_heure_legale_postgres(), [])
            self.assertEqual(
                checks_tz.verifier_heure_legale_postgres(databases=[]), [])
        connexions.__getitem__.assert_not_called()

    def test_contre_la_vraie_base_il_ne_plante_pas(self):
        """Vrai SELECT sur la base de test. On n'affirme RIEN sur sa tzdata
        (elle vient de l'image Postgres, pas du dépôt) : on prouve que le
        contrôle s'exécute et rend au plus un avertissement — jamais une
        erreur, jamais une exception."""
        constats = checks_tz.verifier_heure_legale_postgres(
            databases=[connection.alias])
        self.assertLessEqual(len(constats), 1)
        for constat in constats:
            self.assertEqual(constat.id, checks_tz.ID_POSTGRES_PERIMEE)
            self.assertEqual(constat.level, WARNING)   # ne bloque pas

    def test_une_tzdata_postgres_perimee_avertit_avec_le_remede(self):
        """Cas périmé simulé au curseur : Postgres rendrait 13:00 (UTC+1)."""
        curseur = mock.MagicMock()
        curseur.fetchone.return_value = (dt.datetime(2026, 9, 21, 13, 0),)
        connexion = mock.MagicMock(vendor='postgresql')
        connexion.cursor.return_value.__enter__.return_value = curseur

        with mock.patch('django.db.connections', {'default': connexion}):
            constats = checks_tz.verifier_heure_legale_postgres(
                databases=['default'])

        self.assertEqual([c.id for c in constats],
                         [checks_tz.ID_POSTGRES_PERIMEE])
        constat = constats[0]
        self.assertEqual(constat.level, WARNING)
        self.assertIn('PÉRIMÉE', constat.msg)
        self.assertIn('2.26.530', constat.msg)
        self.assertIn('docker compose pull db', constat.hint)
        curseur.execute.assert_called_once_with(checks_tz.SQL_TEMOIN)

    def test_une_base_non_postgres_est_ignoree(self):
        connexion = mock.MagicMock(vendor='sqlite')
        with mock.patch('django.db.connections', {'default': connexion}):
            self.assertEqual(
                checks_tz.verifier_heure_legale_postgres(databases=['default']),
                [])
        connexion.cursor.assert_not_called()

    def test_une_base_injoignable_ne_fait_pas_tomber_le_controle(self):
        connexion = mock.MagicMock(vendor='postgresql')
        connexion.cursor.side_effect = RuntimeError('base injoignable')
        with mock.patch('django.db.connections', {'default': connexion}):
            self.assertEqual(
                checks_tz.verifier_heure_legale_postgres(databases=['default']),
                [])

    def test_le_controle_porte_bien_l_etiquette_database(self):
        from django.core.checks import Tags
        from django.core.checks.registry import registry

        enregistres = {getattr(c, '__name__', ''): c
                       for c in registry.get_checks()}
        self.assertIn('verifier_heure_legale_postgres', enregistres)
        self.assertIn(
            Tags.database,
            getattr(enregistres['verifier_heure_legale_postgres'], 'tags', ()))
