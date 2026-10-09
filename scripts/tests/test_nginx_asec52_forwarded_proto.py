"""Tests ASEC52 — nginx relaie le `X-Forwarded-Proto` amont (Caddy) seulement
depuis un pair de confiance (backend/nginx/nginx.conf).

Stdlib pure (unittest). Run :
    python -m unittest scripts.tests.test_nginx_asec52_forwarded_proto -v
"""
import ipaddress
import unittest

from scripts.tests.test_nginx_cache_control import (
    analyser,
    bloc_http,
    locations,
    server_principal,
)


def _geo(arbre, variable):
    for nom, args, enfants in bloc_http(arbre):
        if nom == "geo" and args and args[-1] == variable:
            return {cle: (vals[0] if vals else "") for cle, vals, _ in enfants}
    raise AssertionError(f"geo {variable} introuvable")


def _map(arbre, variable):
    for nom, args, enfants in bloc_http(arbre):
        if nom == "map" and len(args) == 2 and args[1] == variable:
            return args[0], {cle: (vals[0] if vals else "")
                             for cle, vals, _ in enfants}
    raise AssertionError(f"map {variable} introuvable")


def _proto_pour(arbre, pair, proto_amont, scheme="http"):
    """Évalue `$proto_transmis` pour un pair TCP et un en-tête amont."""
    geo = _geo(arbre, "$pair_proto_confiance")
    confiance = geo.get("default", "0")
    adresse = ipaddress.ip_address(pair)
    for cle, val in geo.items():
        if cle != "default" and adresse in ipaddress.ip_network(cle):
            confiance = val
    source, table = _map(arbre, "$proto_transmis")
    cle = source.replace("$pair_proto_confiance", confiance).replace(
        "$http_x_forwarded_proto", proto_amont)
    valeur = table.get(cle, table.get("default"))
    return scheme if valeur == "$scheme" else valeur


class ForwardedProtoTests(unittest.TestCase):
    def setUp(self):
        self.arbre = analyser()

    def test_proto_amont_relaye_si_pair_de_confiance(self):
        # Caddy (réseau docker privé) annonce https → relayé.
        self.assertEqual(_proto_pour(self.arbre, "172.18.0.3", "https"), "https")
        # Un appelant direct d'Internet ne peut pas se déclarer en https.
        self.assertEqual(_proto_pour(self.arbre, "203.0.113.9", "https"), "http")
        # Pair de confiance sans en-tête → $scheme.
        self.assertEqual(_proto_pour(self.arbre, "172.18.0.3", ""), "http")
        # Valeur fantaisiste → $scheme.
        self.assertEqual(_proto_pour(self.arbre, "172.18.0.3", "gopher"), "http")

    def test_memes_plages_que_realip(self):
        http = bloc_http(self.arbre)
        realip = {a[0] for n, a, _ in http if n == "set_real_ip_from"}
        geo = {k for k, v in _geo(self.arbre, "$pair_proto_confiance").items()
               if k != "default" and v == "1"}
        self.assertEqual(geo, realip)

    def test_toutes_les_locations_proxy_relaient_proto_transmis(self):
        server = server_principal(self.arbre)
        vues = 0
        for _, motif, enfants in locations(server):
            protos = [a[1] for n, a, _ in enfants
                      if n == "proxy_set_header" and a[0] == "X-Forwarded-Proto"]
            for valeur in protos:
                vues += 1
                self.assertEqual(valeur, "$proto_transmis", motif)
        self.assertGreater(vues, 10)


if __name__ == "__main__":
    unittest.main()
