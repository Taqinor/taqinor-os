/* Coque UNIQUE des maquettes Tâches — ne se recopie jamais dans une page.
   Pose, au chargement, trois éléments communs à toutes les maquettes :
     <div data-coque="statut"></div>    barre d'état iPhone (heure = <body data-heure>)
     <nav data-coque="laterale"></nav>  barre latérale du bureau (256 px, Mes projets comptés)
     <nav data-coque="onglets"></nav>   barre d'onglets iPhone (pastille d'À trier)
   Attributs du <body> :
     data-heure="8:30"        heure de la maquette ; les comptes en découlent (SCENARIO.md §7)
     data-onglet="aujourdhui|a-trier|projets|agenda"   onglet (et section de la barre latérale) actif
     data-pousse              écran poussé (Mon rythme, Réglages…) : aucune section active dans la barre latérale
     data-projet="ambre"      projet ouvert : sa ligne de Mes projets est active
     data-histoire="24-nov|2-nov-vide|2-nov|3-nov|retour"   autre journée que le mardi 24 (défaut 24-nov)
   Chargé par <script src="coque.js" defer></script> dans <head>, après icones.js. */
(function () {
  var PROJETS = [
    ['ambre', 'Chantier Benali 9 kWc', 'benali'],
    ['indigo', 'Salon Solaire Expo', 'salon'],
    ['vert', 'Recrutement technicien', 'recrutement'],
    ['prune', 'Administratif', 'administratif'],
    ['ciel', 'Site web', 'site'],
  ];
  // Tâches OUVERTES par projet selon l'heure du mardi 24 (SCENARIO.md §7). [début, comptes]
  var JOURNEE_24 = [
    ['0:00', { benali: 6, salon: 8 }],   // matin : rien de fait
    ['8:52', { benali: 5, salon: 8 }],   // rails commandés
    ['10:20', { benali: 5, salon: 7 }],  // fournisseur appelé
    ['10:50', { benali: 4, salon: 7 }],  // devis révisé envoyé
    ['16:30', { benali: 4, salon: 6 }],  // stand confirmé
  ];
  var HISTOIRES = {
    '24-nov': function (min) {
      var c = { aTrier: 5, recrutement: 5, administratif: 3, site: 4 };
      JOURNEE_24.forEach(function (p) { if (min >= minutes(p[0])) { c.benali = p[1].benali; c.salon = p[1].salon; } });
      return c;
    },
    'retour': function () { return { aTrier: 3, benali: 6, salon: 8, recrutement: 5, administratif: 3, site: 4 }; },
    '2-nov-vide': function () { return {}; },
    '2-nov': function () { return { salon: 3, recrutement: 3 }; },
    '3-nov': function () { return { salon: 2, recrutement: 2 }; },
  };
  var SECTIONS = [
    ['aujourdhui', 'sun', "Aujourd'hui"],
    ['a-trier', 'inbox', 'À trier'],
    ['projets', 'folder', 'Projets'],
    ['agenda', 'calendar', 'Agenda'],
  ];
  var GLYPHES = '<svg width="18" height="12" viewBox="0 0 18 12"><rect x="0" y="8" width="3" height="4" rx="1"/><rect x="5" y="5.5" width="3" height="6.5" rx="1"/><rect x="10" y="3" width="3" height="9" rx="1"/><rect x="15" y="0" width="3" height="12" rx="1"/></svg><svg width="16" height="12" viewBox="0 0 16 12"><path d="M8 11.6 5.7 9a3.3 3.3 0 0 1 4.6 0zM8 4.3a7.4 7.4 0 0 1 5.2 2.1l1.3-1.4A9.3 9.3 0 0 0 8 2.4 9.3 9.3 0 0 0 1.5 5l1.3 1.4A7.4 7.4 0 0 1 8 4.3zM8 0a11.6 11.6 0 0 1 8 3.2l-1 1.1A10.2 10.2 0 0 0 8 1.5 10.2 10.2 0 0 0 1 4.3L0 3.2A11.6 11.6 0 0 1 8 0z"/></svg><svg width="27" height="13" viewBox="0 0 27 13"><rect x="0.5" y="0.5" width="23" height="12" rx="3.5" style="fill:none;stroke:currentColor;opacity:.4"/><rect x="2" y="2" width="18" height="9" rx="2"/><path d="M25 4.5v4a2 2 0 0 0 0-4z" style="opacity:.4"/></svg>';

  function minutes(h) { var p = String(h).split(':'); return (+p[0]) * 60 + (+p[1] || 0); }
  function icone(nom, classe) { return '<svg class="i' + (classe ? ' ' + classe : '') + '" aria-hidden="true"><use href="#i-' + nom + '"/></svg>'; }
  function compte(n, classe) { return n ? '<span class="' + classe + ' chiffres">' + n + '</span>' : ''; }

  function poser() {
    var b = document.body;
    var heure = b.dataset.heure || '9:41';
    var histoire = HISTOIRES[b.dataset.histoire || '24-nov'] || HISTOIRES['24-nov'];
    var c = histoire(minutes(heure));
    var actif = b.dataset.onglet || 'aujourdhui';
    var pousse = b.hasAttribute('data-pousse') || !!b.dataset.projet;

    document.querySelectorAll('[data-coque="statut"]').forEach(function (e) {
      e.outerHTML = '<div class="barre-statut" aria-hidden="true"><span class="chiffres">' + heure + '</span><span class="glyphes">' + GLYPHES + '</span></div>';
    });

    document.querySelectorAll('[data-coque="laterale"]').forEach(function (e) {
      var h = '<nav class="barre-laterale bureau-seul" aria-label="Tâches"><p class="nom-app">Tâches</p>';
      SECTIONS.forEach(function (s) {
        var cur = !pousse && s[0] === actif ? ' aria-current="page"' : '';
        h += '<a class="nav-item"' + cur + '>' + icone(s[1], 'i-16') + s[2] + (s[0] === 'a-trier' ? compte(c.aTrier, 'compte') : '') + '</a>';
      });
      h += '<p class="nav-titre">Mes projets</p>';
      PROJETS.forEach(function (p) {
        if (c[p[2]] === undefined) return;
        var cur = b.dataset.projet === p[0] ? ' aria-current="page"' : '';
        h += '<a class="nav-item" data-p="' + p[0] + '"' + cur + '><i class="point"></i><span>' + p[1] + '</span>' + compte(c[p[2]], 'compte') + '</a>';
      });
      h += '<button class="nav-item nouveau">' + icone('folder-plus', 'i-16') + 'Nouveau projet</button></nav>';
      e.outerHTML = h;
    });

    document.querySelectorAll('[data-coque="onglets"]').forEach(function (e) {
      var h = '<nav class="onglets mobile-seul" aria-label="Tâches">';
      SECTIONS.forEach(function (s) {
        var cur = s[0] === actif ? ' aria-current="page"' : '';
        h += '<a class="onglet"' + cur + '>' + icone(s[1]) + s[2] + (s[0] === 'a-trier' ? compte(c.aTrier, 'pastille') : '') + '</a>';
      });
      h += '<a class="onglet">' + icone('layout-grid') + 'Apps</a></nav>';
      e.outerHTML = h;
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', poser); else poser();
})();
