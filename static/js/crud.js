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

    var loadingNotices = 0;

    function showLoading(message) {
        loadingNotices += 1;
        var notice = document.querySelector('.crud-loading-notice');
        if (!notice) {
            notice = document.createElement('div');
            notice.className = 'crud-loading-notice';
            notice.setAttribute('role', 'status');
            notice.setAttribute('aria-live', 'polite');
            notice.innerHTML = '<i class="fa fa-spinner fa-spin" aria-hidden="true"></i><span></span>';
            document.body.appendChild(notice);
        }
        notice.querySelector('span').textContent = message || 'Carregando informações. Aguarde...';
        notice.classList.add('crud-loading-notice-visible');

        var closed = false;
        return function () {
            if (closed) return;
            closed = true;
            loadingNotices = Math.max(0, loadingNotices - 1);
            if (loadingNotices === 0) {
                var current = document.querySelector('.crud-loading-notice');
                if (current) current.remove();
            }
        };
    }

    function openForm(options) {
        var backdrop = document.createElement('div');
        backdrop.className = 'crud-modal-backdrop';
        var pageCount = options.pageCount || (options.hasComplement ? 2 : 1);
        var fields = options.fields.map(function (field) {
            var required = field.required ? ' required' : '';
            var wide = field.wide ? ' crud-field-wide' : '';
            var page = Number(field.page || (field.complement ? 2 : 1));
            var pageClass = ' crud-field-page crud-field-page-' + page + (page === 1 ? '' : ' crud-field-hidden');
            var placeholder = field.placeholder ? ' placeholder="' + escapeHtml(field.placeholder) + '"' : '';
            var maxLength = field.maxLength ? ' maxlength="' + Number(field.maxLength) + '"' : '';
            var inputMode = field.inputMode ? ' inputmode="' + escapeHtml(field.inputMode) + '"' : '';
            var min = field.min !== undefined ? ' min="' + escapeHtml(field.min) + '"' : '';
            var max = field.max !== undefined ? ' max="' + escapeHtml(field.max) + '"' : '';
            var step = field.step !== undefined ? ' step="' + escapeHtml(field.step) + '"' : '';
            var mask = field.mask ? ' data-crud-mask="' + escapeHtml(field.mask) + '"' : '';
            var fieldClass = field.className ? ' ' + escapeHtml(field.className) : '';
            var commonAttrs = ' class="crud-input" id="crud-field-' + escapeHtml(field.name) +
                '" name="' + escapeHtml(field.name) + '"' + required + placeholder + maxLength + inputMode +
                min + max + step + mask;
            var control = '';
            if (field.type === 'textarea') {
                control = '<textarea' + commonAttrs + ' rows="' + Number(field.rows || 4) + '">' +
                    escapeHtml(field.value || '') + '</textarea>';
            } else if (field.type === 'checkbox') {
                control = '<label class="crud-checkbox-option"><input id="crud-field-' +
                    escapeHtml(field.name) + '" name="' + escapeHtml(field.name) +
                    '" type="checkbox" value="true"' + (field.value ? ' checked' : '') +
                    '> <span>' + escapeHtml(field.checkboxLabel || field.label) + '</span></label>';
            } else if (field.type === 'permission-grid') {
                control = '<div class="crud-permission-grid"><div class="crud-permission-header">' +
                    '<span>Menu</span><span>Abre Menu</span><span>Edita</span></div>' +
                    (field.rows || []).map(function (row) {
                        var menuOptions = (field.menuOptions || []).map(function (option) {
                            return '<option value="' + escapeHtml(option.value) + '"' +
                                (String(option.value) === String(row.menu) ? ' selected' : '') + '>' +
                                escapeHtml(option.label) + '</option>';
                        }).join('');
                        return '<div class="crud-permission-row">' +
                            '<select class="crud-input" name="' + escapeHtml(row.name) + '_menu">' + menuOptions + '</select>' +
                            '<select class="crud-input" name="' + escapeHtml(row.name) + '_open">' +
                                '<option value="AM"' + (row.open === 'AM' ? ' selected' : '') + '>AM - Abre</option>' +
                                '<option value="NAM"' + (row.open === 'NAM' ? ' selected' : '') + '>NAM - Não abre</option></select>' +
                            '<select class="crud-input" name="' + escapeHtml(row.name) + '_edit">' +
                                '<option value="ET"' + (row.edit === 'ET' ? ' selected' : '') + '>ET - Edita</option>' +
                                '<option value="NET"' + (row.edit === 'NET' ? ' selected' : '') + '>NET - Não edita</option></select>' +
                            '</div>';
                    }).join('') + '</div>';
            } else if (field.type === 'static') {
                control = '<div class="crud-static-field">' + escapeHtml(field.value || '') + '</div>';
            } else if (field.type === 'image') {
                var imageClass = field.value ? 'crud-image-preview' : 'crud-image-preview crud-field-hidden';
                control = '<div class="crud-image-field">' +
                    '<img class="' + imageClass + '" data-crud-image-preview="' + escapeHtml(field.name) +
                    '" src="' + escapeHtml(field.value || '') + '" alt="Foto">' +
                    '<input type="hidden" name="' + escapeHtml(field.name) + '" value="' +
                    escapeHtml(field.value || '') + '">' +
                    '<input class="crud-input" id="crud-field-' + escapeHtml(field.name) +
                    '" type="file" accept="image/*" data-crud-image-input="' + escapeHtml(field.name) + '">' +
                    '</div>';
            } else if (field.type === 'select') {
                var optionsHtml = (field.options || []).map(function (option) {
                    var value = typeof option === 'string' ? option : option.value;
                    var label = typeof option === 'string' ? option : option.label;
                    var selected = String(field.value || '') === String(value || '') ? ' selected' : '';
                    return '<option value="' + escapeHtml(value || '') + '"' + selected + '>' +
                        escapeHtml(label || '') + '</option>';
                }).join('');
                control = '<select' + commonAttrs + '>' + optionsHtml + '</select>';
            } else {
                control = '<input' + commonAttrs + ' type="' + escapeHtml(field.type || 'text') +
                    '" value="' + escapeHtml(field.value || '') + '">';
            }
            var fieldLabel = field.type === 'checkbox' ? '' :
                '<label for="crud-field-' + escapeHtml(field.name) + '">' + escapeHtml(field.label) + '</label>';
            return '<div class="crud-field' + wide + pageClass + fieldClass + '" data-crud-page="' + page + '">' +
                fieldLabel +
                control +
                '</div>';
        }).join('');
        var complementDisabled = options.complementDisabled ? ' disabled aria-disabled="true"' : '';
        var pageButtons = '';
        if (pageCount > 1) {
            for (var pageIndex = 1; pageIndex <= pageCount; pageIndex++) {
                var disabled = pageIndex > 1 ? complementDisabled : '';
                var pageLabel = options.pageLabels && options.pageLabels[pageIndex - 1]
                    ? options.pageLabels[pageIndex - 1]
                    : 'Cadastro ' + pageIndex + '/' + pageCount;
                pageButtons += '<button type="button" class="crud-button crud-button-secondary" data-crud-page-button="' +
                    pageIndex + '"' + disabled + '>' + escapeHtml(pageLabel) + '</button>';
            }
        }
        var hasComplementHeader = options.hasComplement && options.complementHeader !== undefined && options.complementHeader !== null;
        var complementHeader = hasComplementHeader
            ? '<div class="crud-complement-header crud-field-hidden" data-crud-complement-header>' +
                escapeHtml(options.complementHeader || '') + '</div>'
            : '';
        var duplicateButton = options.onDuplicate
            ? '<button type="button" class="crud-button crud-button-secondary" data-crud-duplicate>' +
                '<i class="fa fa-copy"></i> ' + escapeHtml(options.duplicateLabel || 'Duplicar') + '</button>'
            : '';
        backdrop.innerHTML = '<section class="crud-modal" role="dialog" aria-modal="true">' +
            '<h3 class="crud-modal-title">' + escapeHtml(options.title) + '</h3>' +
            complementHeader +
            '<form class="crud-form' + (options.formClass ? ' ' + escapeHtml(options.formClass) : '') + '">' + fields +
            '<div class="crud-modal-actions">' +
            pageButtons +
            duplicateButton +
            '<button type="button" class="crud-button crud-button-secondary" data-crud-cancel>Cancelar</button>' +
            '<button type="submit" class="crud-button"><i class="fa fa-check"></i> ' +
            escapeHtml(options.submitLabel || 'Salvar') + '</button>' +
            '</div></form></section>';

        function close() { backdrop.remove(); }
        function setComplementDisabled(disabled) {
            backdrop.querySelectorAll('[data-crud-page-button]').forEach(function (button) {
                if (button.dataset.crudPageButton === '1') return;
                button.disabled = !!disabled;
                button.setAttribute('aria-disabled', disabled ? 'true' : 'false');
            });
        }
        function setComplementHeader(text) {
            var header = backdrop.querySelector('[data-crud-complement-header]');
            if (!header) return;
            header.textContent = text || '';
        }
        function setTitle(text) {
            var title = backdrop.querySelector('.crud-modal-title');
            if (title) title.textContent = text || '';
        }
        function focusField(name) {
            var field = backdrop.querySelector('[name="' + name + '"]');
            if (field) field.focus();
        }
        function hideDuplicate() {
            var button = backdrop.querySelector('[data-crud-duplicate]');
            if (button) button.hidden = true;
        }
        function currentFormApi() {
            return {
                close: close,
                setComplementDisabled: setComplementDisabled,
                setComplementHeader: setComplementHeader,
                setTitle: setTitle,
                focusField: focusField,
                hideDuplicate: hideDuplicate,
                showPage: showPage
            };
        }
        function showPage(page) {
            page = Number(page || 1);
            var header = backdrop.querySelector('[data-crud-complement-header]');
            var title = backdrop.querySelector('.crud-modal-title');
            if (title) {
                title.textContent = (options.pageTitles && options.pageTitles[page - 1]) || options.title;
            }
            if (header) header.classList.toggle('crud-field-hidden', page === 1);
            backdrop.querySelectorAll('[data-crud-page]').forEach(function (field) {
                field.classList.toggle('crud-field-hidden', Number(field.dataset.crudPage) !== page);
            });
            backdrop.querySelectorAll('[data-crud-page-button]').forEach(function (button) {
                button.classList.toggle('crud-button-active', Number(button.dataset.crudPageButton) === page);
            });
        }
        backdrop.querySelector('[data-crud-cancel]').onclick = close;
        var duplicate = backdrop.querySelector('[data-crud-duplicate]');
        if (duplicate) {
            duplicate.onclick = function () {
                var form = backdrop.querySelector('form');
                options.onDuplicate(
                    Object.fromEntries(new FormData(form).entries()),
                    currentFormApi()
                );
            };
        }
        backdrop.querySelectorAll('[data-crud-page-button]').forEach(function (button) {
            button.onclick = function () {
                if (button.disabled) return;
                showPage(button.dataset.crudPageButton);
            };
        });
        showPage(options.initialPage || (options.initialComplement ? 2 : 1));
        backdrop.addEventListener('click', function (event) {
            if (event.target === backdrop) close();
        });
        backdrop.querySelector('form').onsubmit = async function (event) {
            event.preventDefault();
            var submit = event.currentTarget.querySelector('[type="submit"]');
            submit.disabled = true;
            try {
                var result = await options.onSubmit(
                    Object.fromEntries(new FormData(event.currentTarget).entries()),
                    currentFormApi()
                );
                if (!result || result.close !== false) close();
                submit.disabled = false;
            } catch (error) {
                notify(error.message, 'error');
                submit.disabled = false;
            }
        };
        document.body.appendChild(backdrop);
        backdrop.querySelectorAll('[data-crud-mask="phone-br-landline"], [data-crud-mask="phone-br"]').forEach(function (input) {
            function applyPhoneMask() {
                var landline = input.dataset.crudMask === 'phone-br-landline';
                var digits = input.value.replace(/\D/g, '').slice(0, landline ? 10 : 11);
                var formatted = '';
                if (digits.length) formatted = '(' + digits.slice(0, 2);
                if (digits.length >= 2 && (landline || digits.length <= 10)) formatted += ')' + digits.slice(2, 6);
                if (!landline && digits.length > 10) formatted += ')' + digits.slice(2, 7);
                if (digits.length > 6 && (landline || digits.length <= 10)) formatted += '-' + digits.slice(6, 10);
                if (!landline && digits.length > 10) formatted += '-' + digits.slice(7, 11);
                input.value = formatted;
            }
            input.addEventListener('input', applyPhoneMask);
            applyPhoneMask();
        });
        backdrop.querySelectorAll('[data-crud-mask="cep-br"]').forEach(function (input) {
            function applyCepMask() {
                var digits = input.value.replace(/\D/g, '').slice(0, 8);
                input.value = digits.length > 5 ? digits.slice(0, 5) + '-' + digits.slice(5) : digits;
            }
            input.addEventListener('input', applyCepMask);
            applyCepMask();
        });
        backdrop.querySelectorAll('[data-crud-mask="cpf-br"]').forEach(function (input) {
            function applyCpfMask() {
                var digits = input.value.replace(/\D/g, '').slice(0, 11);
                var formatted = digits;
                if (digits.length > 3) formatted = digits.slice(0, 3) + '.' + digits.slice(3);
                if (digits.length > 6) formatted = digits.slice(0, 3) + '.' + digits.slice(3, 6) + '.' + digits.slice(6);
                if (digits.length > 9) formatted = digits.slice(0, 3) + '.' + digits.slice(3, 6) + '.' + digits.slice(6, 9) + '-' + digits.slice(9);
                input.value = formatted;
            }
            input.addEventListener('input', applyCpfMask);
            applyCpfMask();
        });
        backdrop.querySelectorAll('[data-crud-mask="cnpj-br"]').forEach(function (input) {
            function applyCnpjMask() {
                var digits = input.value.replace(/\D/g, '').slice(0, 14);
                var formatted = digits;
                if (digits.length > 2) formatted = digits.slice(0, 2) + '.' + digits.slice(2);
                if (digits.length > 5) formatted = digits.slice(0, 2) + '.' + digits.slice(2, 5) + '.' + digits.slice(5);
                if (digits.length > 8) formatted = digits.slice(0, 2) + '.' + digits.slice(2, 5) + '.' + digits.slice(5, 8) + '/' + digits.slice(8);
                if (digits.length > 12) formatted = digits.slice(0, 2) + '.' + digits.slice(2, 5) + '.' + digits.slice(5, 8) + '/' + digits.slice(8, 12) + '-' + digits.slice(12);
                input.value = formatted;
            }
            input.addEventListener('input', applyCnpjMask);
            applyCnpjMask();
        });
        backdrop.querySelectorAll('[data-crud-image-input]').forEach(function (input) {
            input.addEventListener('change', function () {
                var file = input.files && input.files[0];
                if (!file) return;
                var reader = new FileReader();
                reader.onload = function () {
                    var value = String(reader.result || '');
                    var hidden = backdrop.querySelector('input[type="hidden"][name="' + input.dataset.crudImageInput + '"]');
                    var preview = backdrop.querySelector('[data-crud-image-preview="' + input.dataset.crudImageInput + '"]');
                    if (hidden) hidden.value = value;
                    if (preview) {
                        preview.src = value;
                        preview.classList.remove('crud-field-hidden');
                    }
                };
                reader.readAsDataURL(file);
            });
        });
        if (options.onFormReady) options.onFormReady(backdrop, options.currentItem);
        var firstControl = backdrop.querySelector('input, select, textarea, button');
        if (firstControl) firstControl.focus();
    }

    function Controller(options) {
        this.options = options;
        this.items = [];
    }

    Controller.prototype.mount = function (elements) {
        var self = this;
        this.root = elements.root;
        this.list = elements.list;
        var readOnly = window.MedsoftCurrentMenuEditable === false;
        if (readOnly) elements.includeButton.hidden = true;
        elements.includeButton.onclick = function () { if (!readOnly) self.openEditor(); };
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
        if (window.MedsoftCurrentMenuEditable === false) {
            this.list.querySelectorAll('[data-crud-edit], [data-crud-delete]').forEach(function (button) {
                button.remove();
            });
        }
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

    Controller.prototype.openEditor = async function (item, editorOptions) {
        if (window.MedsoftCurrentMenuEditable === false) {
            notify('Seu perfil possui acesso somente para visualização.', 'error');
            return;
        }
        var self = this;
        var currentItem = item;
        editorOptions = editorOptions || {};
        if (this.options.beforeOpen) {
            try {
                await this.options.beforeOpen(item);
            } catch (error) {
                notify(error.message, 'error');
                return;
            }
        }
        openForm({
            title: currentItem ? this.options.editTitle : this.options.createTitle,
            fields: this.options.fields(currentItem),
            formClass: this.options.formClass,
            hasComplement: typeof this.options.hasComplement === 'function'
                ? this.options.hasComplement(item)
                : this.options.hasComplement,
            pageCount: this.options.pageCount,
            pageLabels: this.options.pageLabels,
            pageTitles: this.options.pageTitles,
            complementDisabled: typeof this.options.complementDisabled === 'function'
                ? this.options.complementDisabled(item)
                : this.options.complementDisabled,
            complementHeader: typeof this.options.complementHeader === 'function'
                ? this.options.complementHeader(currentItem)
                : this.options.complementHeader,
            initialComplement: editorOptions.initialComplement,
            initialPage: editorOptions.initialPage,
            currentItem: currentItem,
            onFormReady: this.options.onFormReady,
            duplicateLabel: this.options.duplicateLabel,
            onDuplicate: currentItem && this.options.allowDuplicate ? function (values, formApi) {
                currentItem = null;
                if (self.options.onDuplicate) self.options.onDuplicate(values, formApi);
                if (formApi && formApi.setTitle) {
                    formApi.setTitle(self.options.duplicateTitle || self.options.createTitle);
                }
                if (formApi && formApi.hideDuplicate) formApi.hideDuplicate();
                if (formApi && formApi.focusField) {
                    formApi.focusField(self.options.duplicateFocusField || 'data');
                }
                notify(self.options.duplicateMessage || 'Dados copiados. Ajuste o novo registro e clique em Salvar.');
            } : null,
            onSubmit: async function (values, formApi) {
                var isCreating = !currentItem;
                var result = currentItem
                    ? await self.options.update(currentItem, values)
                    : await self.options.create(values);
                if (isCreating && self.options.itemFromCreate) {
                    currentItem = self.options.itemFromCreate(values, result);
                }
                if (self.options.afterSave) self.options.afterSave(values, currentItem);
                notify(result.message || 'Registro salvo com sucesso.');
                await self.reload();
                if (isCreating && self.options.keepOpenAfterCreate) {
                    if (formApi && formApi.setComplementDisabled) formApi.setComplementDisabled(false);
                    if (formApi && formApi.setComplementHeader && self.options.complementHeader) {
                        formApi.setComplementHeader(
                            typeof self.options.complementHeader === 'function'
                                ? self.options.complementHeader(currentItem)
                                : self.options.complementHeader
                        );
                    }
                    return {close: false};
                }
            }
        });
    };

    Controller.prototype.remove = async function (item) {
        if (window.MedsoftCurrentMenuEditable === false) {
            notify('Seu perfil possui acesso somente para visualização.', 'error');
            return;
        }
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
        showLoading: showLoading,
        openForm: openForm,
        request: request,
        Controller: Controller
    };
}());
