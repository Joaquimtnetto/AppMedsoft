(function () {
    var script = document.currentScript;
    var autoAttach = !script || script.dataset.navigationAuto !== 'false';

    function ensureStyles() {
        if (document.querySelector('link[data-navigation-styles]')) return;
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/static/css/navigation.css';
        link.dataset.navigationStyles = 'true';
        document.head.appendChild(link);
    }

    function back(fallback) {
        if (typeof window.appNavigateBack === 'function') {
            window.appNavigateBack();
            return;
        }
        var sameOriginReferrer = document.referrer &&
            new URL(document.referrer, window.location.href).origin === window.location.origin;
        if (sameOriginReferrer && window.history.length > 1) {
            window.history.back();
            return;
        }
        window.location.href = fallback || '/';
    }

    function attach(options) {
        options = options || {};
        ensureStyles();
        var container = options.container || document.body;
        var existing = container.querySelector(':scope > .app-back-button');
        if (existing) return existing;
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'app-back-button ' +
            (options.inline ? 'app-back-button-inline' : 'app-back-button-fixed');
        button.title = options.title || 'Voltar';
        button.setAttribute('aria-label', options.title || 'Voltar');
        button.innerHTML = '<span class="app-back-icon" aria-hidden="true">&#8592;</span>' +
            '<span class="app-back-label">Voltar</span>';
        button.onclick = function () {
            if (options.onBack) options.onBack();
            else back(options.fallback);
        };
        container.prepend(button);
        return button;
    }

    window.NavigationUI = {attach: attach, back: back};
    if (autoAttach) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function () { attach(); });
        } else attach();
    }
}());
