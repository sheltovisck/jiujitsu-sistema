// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
        document.querySelectorAll('.alert.alert-dismissible').forEach(function (alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});

// Arrastar atletas para reordenar dentro de uma chave (ou absoluto) e alterar
// os confrontos. Soltar o atleta arrastado sobre outro TROCA os dois de
// lugar (nao empurra os demais). Reutilizado em qualquer tela que tenha um
// container ".chave-atletas" com "data-reorder-url".
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.chave-atletas').forEach(function(container) {
        let dragEl = null;

        function trocarNodes(a, b) {
            const aNext = a.nextSibling;
            const bNext = b.nextSibling;
            b.parentNode.insertBefore(a, bNext);
            a.parentNode.insertBefore(b, aNext);
        }

        function salvarOrdemChave() {
            const ids = Array.from(container.querySelectorAll('.atleta-card')).map(function(c) {
                return c.dataset.inscId;
            });
            fetch(container.dataset.reorderUrl, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ordem: ids}),
            }).then(function(r) {
                if (r.ok) window.location.reload();
            });
        }

        container.querySelectorAll('.atleta-card[draggable="true"]').forEach(function(card) {
            card.addEventListener('dragstart', function() {
                dragEl = card;
                card.classList.add('opacity-50');
            });
            card.addEventListener('dragend', function() {
                card.classList.remove('opacity-50');
            });
            card.addEventListener('dragover', function(e) {
                e.preventDefault();
            });
            card.addEventListener('drop', function(e) {
                e.preventDefault();
                if (!dragEl || card === dragEl) return;
                trocarNodes(dragEl, card);
                salvarOrdemChave();
            });
        });
    });
});
