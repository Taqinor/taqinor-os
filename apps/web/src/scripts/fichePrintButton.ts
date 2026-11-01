// W348 — bouton d'impression de la fiche de dimensionnement (/pompage-solaire fr/en/ar) :
// window.print() déclenche les règles @media print de styles/pompage-solaire.css
// (fond clair, chrome du site masqué).
document.getElementById('fiche-print-btn')?.addEventListener('click', () => {
  window.print();
});
