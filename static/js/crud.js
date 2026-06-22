(function () {
    function escapeHtml(value) {
        var element = document.createElement('div');
        element.textContent = value == null ? '' : String(value);
        return element.innerHTML;
    }

    async function request(url, options) {
        var response = await fetch(url, options || {});
        var data = await response.json().catch(function () { return {}; });
        if (!response.ok || data.success === false) {
            throw new Error(data.message || 'Não foi possível concluir a operação.');
        }
        return data;
    }

    function notify(message, type) {
        var previous = document.querySelector('.crud-toast');
        if (previous) previous.remove();
        var toast = document.createElement('div');
        toast.className = 'crud-toast' + (type === 'error' ? ' crud-toast-error' : '');
        toast.setAttribute('role', 'status');
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(function () { toast.remove(); }, 3500);
    }

    function openForm(options) {
        var backdrop = document.createElement('div');
        backdrop.className = 'crud-modal-backdrop';
        var fields = options.fields.map(function (field) {
            var required = field.required ? ' required' : '';
            var wide = field.wide ? ' crud-field-wide' : '';
            var placeholder = field.placeholder ? ' placeholder="' + escapeHtml(field.placeholder) + '"' : '';
            var maxLength = field.maxLength ? ' maxlength="' + Number(field.maxLength) + '"' : '';
            var inputMode = field.inputMode ? ' inputmode="' + escapeHtml(field.inputMode) + '"' : '';
            var mask = field.mask ? ' data-crud-mask="' + escapeHtml(field.mask) + '"' : '';
            return '<div class="crud-field' + wide + '">' +
                '<label for="crud-field-' + escapeHtml(field.name) + '">' + escapeHtml(field.label) + '</label>' +
                '<input class="crud-input" id="crud-field-' + escapeHtml(field.name) + '" name="' +
                escapeHtml(field.name) + '" type="' + escapeHtml(field.type || 'text') + '" value="' +
                escapeHtml(field.value || '') + '"' + required + placeholder + maxLength + inputMode + mask + '>' +
                '</div>';
        }).join('');
        backdrop.innerHTML = '<section class="crud-modal" role="dialog" aria-modal="true">' +
            '<h3 class="crud-modal-title">' + escapeHtml(options.title) + '</h3>' +
            '<form class="crud-form">' + fields +
            '<div class="crud-modal-actions">' +
            '<button type="button" class="crud-button crud-button-secondary" data-crud-cancel>Cancelar</button>' +
            '<button type="submit" class="crud-button"><i class="fa fa-check"></i> Salvar</button>' +
            '</div></form></section>';

        function close() { backdrop.remove(); }
        backdrop.querySelector('[data-crud-cancel]').onclick = close;
        backdrop.addEventListener('click', function (event) {
            if (event.target === backdrop) close();
        });
        backdrop.querySelector('form').onsubmit = async function (event) {
            event.preventDefault();
            var submit = event.currentTarget.querySelector('[type="submit"]');
            submit.disabled = true;
            try {
                await options.onSubmit(Object.fromEntries(new FormData(event.currentTarget).entries()));
                close();
            } catch (error) {
                notify(error.message, 'error');
                submit.disabled = false;
            }
        };
        document.body.appendChild(backdrop);
        backdrop.querySelectorAll('[data-crud-mask="phone-br-landline"]').forEach(function (input) {
            function applyPhoneMask() {
                var digits = input.value.replace(/\D/g, '').slice(0, 10);
                var formatted = '';
                if (digits.length) formatted = '(' + digits.slice(0, 2);
                if (digits.length >= 2) formatted += ')' + digits.slice(2, 6);
                if (digits.length > 6) formatted += '-' + digits.slice(6, 10);
                input.value = formatted;
            }
            input.addEventListener('input', applyPhoneMask);
            applyPhoneMask();
        });
        backdrop.querySelector('input').focus();
    }

    function Controller(options) {
        this.options = options;
        this.items = [];
    }

    Controller.prototype.mount = function (elements) {
        var self = this;
        this.root = elements.root;
        this.list = elements.list;
        elements.includeButton.onclick = function () { self.openEditor(); };
        this.root.addEventListener('click', function (event) {
            var edit = event.target.closest('[data-crud-edit]');
            var deletion = event.target.closest('[data-crud-delete]');
            var action = event.target.closest('[data-crud-action]');
            if (edit) self.openEditor(self.find(edit.dataset.crudEdit));
            if (deletion) self.remove(self.find(deletion.dataset.crudDelete));
            if (action && self.options.onAction) {
                self.options.onAction(action.dataset.crudAction, self.find(action.dataset.crudId));
            }
        });
        return this;
    };

    Controller.prototype.find = function (id) {
        var getId = this.options.getId;
        return this.items.find(function (item) { return String(getId(item)) === String(id); });
    };

    Controller.prototype.render = function () {
        if (!this.items.length) {
            this.list.innerHTML = '<div class="crud-empty">' +
                escapeHtml(this.options.emptyMessage || 'Nenhum registro encontrado.') + '</div>';
            return;
        }
        this.list.innerHTML = this.items.map(this.options.renderItem).join('');
    };

    Controller.prototype.reload = async function () {
        this.list.innerHTML = '<div class="crud-loading">Carregando...</div>';
        try {
            this.items = await this.options.list();
            this.render();
        } catch (error) {
            this.list.innerHTML = '<div class="crud-error">' + escapeHtml(error.message) + '</div>';
        }
    };

    Controller.prototype.openEditor = function (item) {
        var self = this;
        openForm({
            title: item ? this.options.editTitle : this.options.createTitle,
            fields: this.options.fields(item),
            onSubmit: async function (values) {
                var result = item
                    ? await self.options.update(item, values)
                    : await self.options.create(values);
                if (self.options.afterSave) self.options.afterSave(values, item);
                notify(result.message || 'Registro salvo com sucesso.');
                await self.reload();
            }
        });
    };

    Controller.prototype.remove = async function (item) {
        if (!item || !window.confirm(this.options.confirmDelete(item))) return;
        try {
            var result = await this.options.delete(item);
            notify(result.message || 'Registro excluído com sucesso.');
            await this.reload();
        } catch (error) {
            notify(error.message, 'error');
        }
    };

    window.CrudUI = {
        escapeHtml: escapeHtml,
        notify: notify,
        openForm: openForm,
        request: request,
        Controller: Controller
    };
}());
