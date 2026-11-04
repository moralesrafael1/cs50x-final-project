/* Meridian — comportamentos dos formulários de login e cadastro */
(function () {
    /* Mostrar / ocultar senha */
    document.querySelectorAll('.auth-toggle').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var input = document.getElementById(btn.getAttribute('data-target'));
            if (!input) return;
            var show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            btn.textContent = show ? 'Ocultar' : 'Mostrar';
            btn.setAttribute('aria-pressed', show ? 'true' : 'false');
        });
    });

    /* Cadastro: força da senha e confirmação (só roda se existirem) */
    var pw = document.getElementById('password');
    var cf = document.getElementById('confirm_password');
    var meter = document.querySelector('[data-meter]');
    var hint = document.getElementById('match-hint');
    if (!pw || !cf || !meter) return;

    var labels = ['', 'Fraca', 'Razoável', 'Boa', 'Forte'];
    var label = meter.querySelector('.auth-meter__label');

    function strength(v) {
        if (!v) return 0;
        var s = 0;
        if (v.length >= 8) s++;
        if (v.length >= 12) s++;
        if (/[a-z]/.test(v) && /[A-Z]/.test(v)) s++;
        if (/\d/.test(v)) s++;
        if (/[^A-Za-z0-9]/.test(v)) s++;
        return s <= 1 ? 1 : s === 2 ? 2 : s <= 4 ? 3 : 4;
    }

    function checkMatch() {
        if (!cf.value) {
            hint.textContent = '';
            hint.className = 'auth-hint';
            cf.setCustomValidity('');
        } else if (cf.value === pw.value) {
            hint.textContent = 'As senhas coincidem';
            hint.className = 'auth-hint auth-hint--ok';
            cf.setCustomValidity('');
        } else {
            hint.textContent = 'As senhas não coincidem';
            hint.className = 'auth-hint auth-hint--bad';
            cf.setCustomValidity('As senhas não coincidem');
        }
    }

    pw.addEventListener('input', function () {
        var level = strength(pw.value);
        meter.setAttribute('data-level', level);
        label.textContent = labels[level];
        checkMatch();
    });
    cf.addEventListener('input', checkMatch);
})();
