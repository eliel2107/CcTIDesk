/* CcTI Desk — Kanban Touch Support (SortableJS)
   Ativo apenas em dispositivos touch — preserva o drag HTML5 no desktop.
*/
(function () {
  /* Detecta touch primário (exclui notebooks com trackpad touch) */
  var isTouch = ('ontouchstart' in window || navigator.maxTouchPoints > 0) &&
                window.matchMedia('(pointer: coarse)').matches;

  if (!isTouch || typeof Sortable === 'undefined') return;

  /* Remove draggable nativo para evitar conflito com SortableJS */
  document.querySelectorAll('.kb-card').forEach(function (card) {
    card.removeAttribute('draggable');
  });

  function getCsrf() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.content : '';
  }

  /* Inicializa Sortable em cada dropzone do kanban */
  document.querySelectorAll('.kanban-dropzone').forEach(function (zone) {
    Sortable.create(zone, {
      group:               'kanban',
      animation:           150,
      ghostClass:          'dragging',
      touchStartThreshold: 8,
      delay:               80,
      delayOnTouchOnly:    true,

      onEnd: async function (evt) {
        var card      = evt.item;
        var oldZone   = evt.from;                /* zona de origem — capturada antes de qualquer mutação */
        var nextSib   = evt.item.nextSibling;    /* próximo irmão para rollback correto */
        var newZone   = evt.to;
        var ticketId  = card.dataset.id;
        var newStatus = newZone.dataset.status;
        var oldStatus = card.dataset.status;

        if (oldStatus === newStatus) return;

        try {
          var res = await fetch('/api/tickets/' + ticketId + '/status', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken':  getCsrf()
            },
            body: JSON.stringify({ status: newStatus })
          });

          if (!res.ok) throw new Error('Falha ao atualizar status');

          card.dataset.status = newStatus;
          location.reload();

        } catch (e) {
          alert('Não foi possível salvar o novo status. Tente novamente.');

          /* Reverte posição visual usando evt.from e nextSibling capturados antes da mutação */
          oldZone.insertBefore(card, nextSib);
          card.dataset.status = oldStatus;
        }
      }
    });
  });
}());
