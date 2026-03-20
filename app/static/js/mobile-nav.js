/* CcTI Desk — Mobile Navigation (Hamburger + Sidebar Drawer) */
(function () {
  var sidebar = document.querySelector('.sidebar');
  var overlay = document.getElementById('sidebarOverlay');
  var btn     = document.getElementById('hamburgerBtn');

  if (!btn || !sidebar) return;

  /* Aviso de regressão: sem overlay o drawer não fecha ao tocar fora */
  if (!overlay) {
    console.warn('[mobile-nav] #sidebarOverlay não encontrado — fechar ao tocar fora não funcionará.');
  }

  function openSidebar() {
    document.body.classList.add('sidebar-open');
    btn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeSidebar() {
    document.body.classList.remove('sidebar-open');
    btn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  btn.addEventListener('click', function () {
    document.body.classList.contains('sidebar-open') ? closeSidebar() : openSidebar();
  });

  if (overlay) overlay.addEventListener('click', closeSidebar);

  /* Fecha ao navegar (mobile: clique em link fecha o menu) */
  document.querySelectorAll('.sidebar-nav a').forEach(function (a) {
    a.addEventListener('click', closeSidebar);
  });

  /* Fecha com a tecla Escape */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && document.body.classList.contains('sidebar-open')) {
      closeSidebar();
    }
  });
}());
