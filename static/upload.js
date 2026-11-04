/* Meridian — interface da página de upload.
   Só cuida da parte visual (pré-visualização, arrastar e soltar, cartões de resultado).
   O envio/leitura do comprovante NÃO está aqui: veja o ponto "FUTURO" em lerfoto(). */
(function () {
    var input = document.getElementById('foto-comprovante');
    var zone = document.getElementById('dropzone');
    var preview = document.getElementById('up-preview');
    var thumb = document.getElementById('up-thumb');
    var nameEl = document.getElementById('up-name');
    var sizeEl = document.getElementById('up-size');
    var busy = document.getElementById('up-busy');
    var empty = document.getElementById('resultado-vazio');
    var container = document.getElementById('resultado-container');
    var totalEl = document.getElementById('total-mes');
    var countEl = document.getElementById('total-lidos');
    if (!input) return;

    var totalMes = 0, lidos = 0, objectUrl = null;

    var brl = function (v) {
        return Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    };
    var fmtSize = function (b) {
        return b < 1048576 ? Math.max(1, Math.round(b / 1024)) + ' KB' : (b / 1048576).toFixed(1).replace('.', ',') + ' MB';
    };

    function limparSelecao() {
        if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
        input.value = '';
        preview.hidden = true;
        busy.hidden = true;
        zone.classList.remove('has-file');
        thumb.innerHTML = '';
    }

    function mostrarPreview(file) {
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        thumb.innerHTML = '';
        if (file.type.indexOf('image/') === 0) {
            objectUrl = URL.createObjectURL(file);
            var img = document.createElement('img');
            img.src = objectUrl;
            img.alt = 'Pré-visualização do comprovante';
            thumb.appendChild(img);
        } else {
            thumb.textContent = '📄';
        }
        nameEl.textContent = file.name;
        sizeEl.textContent = fmtSize(file.size);
        preview.hidden = false;
        zone.classList.add('has-file');
    }

    /* Chamada pelo onchange do input (nome mantido do código original) */
    window.lerfoto = function () {
        var file = input.files && input.files[0];
        if (!file) { limparSelecao(); return; }
        mostrarPreview(file);

        /* FUTURO: aqui entra o envio ao Python, por exemplo:
             setProcessando(true);
             fetch('/upload', { method: 'POST', body: formData })
                 .then(r => r.json())
                 .then(d => { renderComprovante(d); limparSelecao(); })
                 .finally(() => setProcessando(false));
        */
    };

    /* Mostra/oculta o indicador "Lendo comprovante…" */
    window.setProcessando = function (on) { busy.hidden = !on; };

    /* Cria o cartão de um comprovante e atualiza o resumo.
       d = { estabelecimento, itens: [{ nome, valor, qtd? }], total? } */
    window.renderComprovante = function (d) {
        var itens = d.itens || [];
        var soma = itens.reduce(function (s, i) { return s + Number(i.valor || 0); }, 0);
        var total = d.total != null ? Number(d.total) : soma;

        var card = document.createElement('div');
        card.className = 'card-comprovante';

        var head = document.createElement('div');
        head.className = 'estabelecimento';
        head.textContent = d.estabelecimento || 'Estabelecimento';
        card.appendChild(head);

        var list = document.createElement('div');
        list.className = 'lista-itens';
        itens.forEach(function (i) {
            var row = document.createElement('div');
            row.className = 'item-linha';
            var n = document.createElement('span');
            n.textContent = (i.qtd ? i.qtd + 'x ' : '') + i.nome;
            var v = document.createElement('span');
            v.textContent = brl(i.valor);
            row.appendChild(n);
            row.appendChild(v);
            list.appendChild(row);
        });
        card.appendChild(list);

        var hr = document.createElement('hr');
        hr.className = 'divisor';
        card.appendChild(hr);

        var tot = document.createElement('div');
        tot.className = 'total-nota-linha';
        tot.innerHTML = '<span>Total</span><span></span>';
        tot.lastChild.textContent = brl(total);
        card.appendChild(tot);

        container.insertBefore(card, container.firstChild);
        if (empty) empty.hidden = true;

        totalMes += total;
        lidos += 1;
        totalEl.textContent = brl(totalMes);
        countEl.textContent = lidos;
    };

    document.getElementById('up-remove').addEventListener('click', limparSelecao);

    /* Arrastar e soltar */
    ['dragenter', 'dragover'].forEach(function (ev) {
        zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add('is-drag'); });
    });
    ['dragleave', 'drop'].forEach(function (ev) {
        zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove('is-drag'); });
    });
    zone.addEventListener('drop', function (e) {
        if (e.dataTransfer && e.dataTransfer.files.length) {
            input.files = e.dataTransfer.files;
            window.lerfoto();
        }
    });
})();
