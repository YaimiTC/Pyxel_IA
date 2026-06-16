/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';

export const ImportRegistrationForm = publicWidget.Widget.extend({
    selector: '#import_registration_form',
    events: {
        'click #prevBtn': 'clickPrev',
        'click #nextBtn': 'clickNext',
        'click .register_business_button': 'validateForm',
        'keyup .is-invalid': '_removeInvalid',
        'click .is-invalid': '_removeInvalid',
        'change input[name="solicitud"]': '_onchangeFile',
        'change input[name="load_products"]': '_onchangeFile',
        'change #hiddenTestInput': '_onHiddenInputChange',
        'blur input[name="presupuesto_disponible"]': '_formatPresupuesto',
        'click #btn-preview': '_previewSolicitud',
        'click #btn-add-product-row': '_addProductRow',
        'click .btn-remove-row': '_removeProductRow',
        'change .product-row-product': '_onProductRowChange',
        'click a[href*="nomenclador"]': '_onNomencladorClick',
        'change input:not([type="file"])': '_saveFormState',
        'change select': '_saveFormState',
        'change textarea': '_saveFormState',
    },
    init() {
        this._super(...arguments);
        this.rpc = this.bindService("rpc");
        this.currentTab = 0;
        this._allProducts = [];
    },
    start: function () {
        var def = this._super.apply(this, arguments);
        this.showTab(this.currentTab);
        this._initProductRows();
        const dateInput = document.getElementById('commitment_date');
        if (dateInput) {
            dateInput.min = new Date().toISOString().split('T')[0];
        }
        // Guardar estado del formulario al navegar fuera (ej. al nomenclador)
        window.addEventListener('beforeunload', this._saveFormState.bind(this));
        return def;
    },

    _saveFormState: function () {
        const form = document.getElementById('import_registration_form');
        if (!form) return;
        const SKIP = new Set(['productRequired', 'product_rows_json', 'csrf_token']);
        const SKIP_CLS = ['product-row-product', 'product-row-cantidad', 'product-row-tipo_envase'];
        const state = {};
        form.querySelectorAll('input[name], select[name], textarea[name]').forEach(el => {
            if (el.type === 'file') return;
            if (SKIP.has(el.name)) return;
            if (SKIP_CLS.some(c => el.classList.contains(c))) return;
            if (el.value) state[el.name] = el.value;
        });
        console.log('[FORM_STATE] guardando:', JSON.stringify(state));
        try { sessionStorage.setItem('import_form_state', JSON.stringify(state)); } catch(e) { console.error('[FORM_STATE] error al guardar:', e); }
    },

    _restoreFormState: function () {
        let saved;
        try { saved = sessionStorage.getItem('import_form_state'); } catch(e) { return; }
        console.log('[FORM_STATE] restaurando, sessionStorage tiene:', saved);
        if (!saved) return;
        try {
            const state = JSON.parse(saved);
            const form = document.getElementById('import_registration_form');
            if (!form) return;
            Object.entries(state).forEach(([name, value]) => {
                const el = form.querySelector(`[name="${name}"]`);
                if (el && value) {
                    el.value = value;
                    console.log('[FORM_STATE] restaurado:', name, '=', value);
                } else if (!el) {
                    console.warn('[FORM_STATE] campo no encontrado en DOM:', name);
                }
            });
            sessionStorage.removeItem('import_form_state');
        } catch(e) { console.error('[FORM_STATE] error al restaurar:', e); }
    },

    _onNomencladorClick: function (ev) {
        ev.preventDefault();
        const form = document.getElementById('import_registration_form');
        const SKIP = new Set(['productRequired', 'product_rows_json', 'csrf_token', 'register_type']);
        const SKIP_CLS = ['product-row-product', 'product-row-cantidad', 'product-row-tipo_envase'];
        const state = {};
        if (form) {
            form.querySelectorAll('input[name], select[name], textarea[name]').forEach(el => {
                if (el.type === 'file') return;
                if (SKIP.has(el.name)) return;
                if (SKIP_CLS.some(c => el.classList.contains(c))) return;
                state[el.name] = el.value || '';
            });
        }
        // Guardar cantidades y tipo_envase de cada fila de producto
        const rows = [];
        document.querySelectorAll('#product-rows-container .product-row').forEach(function (row) {
            const prodSel = row.querySelector('.product-row-product');
            const cantInput = row.querySelector('.product-row-cantidad');
            const tipoSel = row.querySelector('.product-row-tipo_envase');
            if (prodSel && prodSel.value) {
                rows.push({
                    product_id: prodSel.value,
                    cantidad: cantInput ? (cantInput.value || '') : '',
                    tipo_envase: tipoSel ? (tipoSel.value || '') : '',
                });
            }
        });
        state['_product_rows'] = JSON.stringify(rows);
        const href = ev.currentTarget ? ev.currentTarget.href : '/nomenclador?from=import_registration';
        this.rpc('/business-register/save_header_state', state).then(() => {
            window.location.href = href;
        }).catch(() => {
            window.location.href = href;
        });
    },

    // ── Product rows ────────────────────────────────────────────────────────────

    _initProductRows: function () {
        const productSelect = document.getElementById('productRequired');
        if (!productSelect) return;

        try {
            this._allProducts = JSON.parse(productSelect.dataset.alimentos || '[]');
        } catch (e) {
            this._allProducts = [];
        }

        const container = document.getElementById('product-rows-container');
        const existingRows = container ? container.querySelectorAll('.product-row').length : 0;
        const fromNomenclador = (document.getElementById('fromNomenclador') || {}).value === '1';

        if (existingRows > 0 || fromNomenclador) {
            // Rows were server-rendered (return from nomenclador)
            // NO llamar _refilterAllRows: limpiaría innerHTML y perdería la selección de QWeb
            this._updateAddButton();
            this._syncAll();
            this._syncSession();
            this._restoreFormState();
            return;
        }

        // Fresh form load: clear any stale state
        try { sessionStorage.removeItem('import_form_state'); } catch(e) {}
        this._insertRow(null, '', '');
        this._syncAll();
        this._syncSession();
    },

    _getTiposEnvase: function () {
        if (!this._tiposEnvaseCache) {
            try {
                const el = document.getElementById('tipos_envase_json');
                this._tiposEnvaseCache = el ? JSON.parse(el.dataset.tipos || '[]') : [];
            } catch (e) {
                this._tiposEnvaseCache = [];
            }
        }
        return this._tiposEnvaseCache;
    },

    _insertRow: function (productId, cantidad, tipoEnvase) {
        const container = document.getElementById('product-rows-container');
        if (!container) return;

        const allProducts = this._allProducts;
        const currentRows = container.querySelectorAll('.product-row').length;
        if (currentRows >= allProducts.length && allProducts.length > 0) return;

        const selectedElsewhere = this._getSelectedProductIds();

        const row = document.createElement('div');
        row.className = 'product-row d-flex align-items-center gap-1 mb-2';

        // Product dropdown
        const prodSel = document.createElement('select');
        prodSel.className = 'form-select product-row-product flex-grow-1';
        prodSel.style.minWidth = '0';
        this._fillProductOptions(prodSel, allProducts, selectedElsewhere, productId);

        // Cantidad
        const cantInput = document.createElement('input');
        cantInput.type = 'number';
        cantInput.className = 'form-control product-row-cantidad';
        cantInput.min = '1';
        cantInput.step = '1';
        cantInput.placeholder = 'Cant.';
        cantInput.style.width = '75px';
        cantInput.style.flexShrink = '0';
        if (cantidad) cantInput.value = cantidad;

        // Tipo envase
        const tipoSel = document.createElement('select');
        tipoSel.className = 'form-select product-row-tipo_envase';
        tipoSel.style.width = '160px';
        tipoSel.style.flexShrink = '0';
        const emptyOpt = document.createElement('option');
        emptyOpt.value = '';
        emptyOpt.textContent = '-- Tipo Envase --';
        tipoSel.appendChild(emptyOpt);
        this._getTiposEnvase().forEach(function (te) {
            const opt = document.createElement('option');
            opt.value = String(te.id);
            opt.textContent = te.name;
            if (String(te.id) === String(tipoEnvase)) opt.selected = true;
            tipoSel.appendChild(opt);
        });

        // Remove button
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'btn btn-outline-danger btn-sm btn-remove-row flex-shrink-0';
        removeBtn.textContent = '×';
        removeBtn.title = 'Eliminar fila';

        row.appendChild(prodSel);
        row.appendChild(cantInput);
        row.appendChild(tipoSel);
        row.appendChild(removeBtn);
        container.appendChild(row);

        // Set selected option explicitly after DOM attachment
        if (productId) {
            const targetVal = String(productId);
            let matched = false;
            Array.from(prodSel.options).forEach(opt => {
                if (opt.value === targetVal) { opt.selected = true; matched = true; }
                else opt.selected = false;
            });
            console.log('[IMPORT] _insertRow', productId, matched ? 'OK' : 'NO MATCH', Array.from(prodSel.options).map(o => o.value));
        }
        if (tipoEnvase) tipoSel.value = tipoEnvase;

        this._updateAddButton();
    },

    _fillProductOptions: function (selectEl, allProducts, selectedElsewhere, currentVal) {
        selectEl.innerHTML = '';
        const defOpt = document.createElement('option');
        defOpt.value = '';
        defOpt.textContent = '-- Seleccione producto --';
        selectEl.appendChild(defOpt);

        allProducts.forEach(p => {
            if (selectedElsewhere.includes(p.id) && p.id !== currentVal) return;
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = typeof p.name === 'object'
                ? (p.name.es_ES || p.name.en_US || String(p.id))
                : p.name;
            selectEl.appendChild(opt);
        });

        // Set selected value after all options exist (more reliable than opt.selected)
        if (currentVal !== null && currentVal !== undefined) {
            selectEl.value = String(currentVal);
        }
    },

    _getSelectedProductIds: function () {
        return Array.from(document.querySelectorAll('.product-row-product'))
            .map(s => parseInt(s.value))
            .filter(id => !isNaN(id) && id > 0);
    },

    _refilterAllRows: function () {
        const allProducts = this._allProducts;
        const rows = document.querySelectorAll('#product-rows-container .product-row');
        const selectedIds = this._getSelectedProductIds();

        rows.forEach(row => {
            const prodSel = row.querySelector('.product-row-product');
            if (!prodSel) return;
            const currentVal = parseInt(prodSel.value) || null;
            const others = selectedIds.filter(id => id !== currentVal);
            this._fillProductOptions(prodSel, allProducts, others, currentVal);
        });
    },

    _updateAddButton: function () {
        const btn = document.getElementById('btn-add-product-row');
        const container = document.getElementById('product-rows-container');
        if (!btn || !container) return;
        const rows = container.querySelectorAll('.product-row').length;
        btn.disabled = rows >= this._allProducts.length && this._allProducts.length > 0;
    },

    _syncAll: function () {
        // Sync selected product IDs to hidden #productRequired (for Odoo form compat)
        const productSelect = document.getElementById('productRequired');
        if (productSelect) {
            productSelect.innerHTML = '';
            this._getSelectedProductIds().forEach(id => {
                const opt = document.createElement('option');
                opt.value = id;
                opt.selected = true;
                productSelect.appendChild(opt);
            });
        }

        // Sync rows as JSON for preview / controller
        const rows = document.querySelectorAll('#product-rows-container .product-row');
        const rowData = Array.from(rows).map(row => ({
            product_id: parseInt(row.querySelector('.product-row-product')?.value) || 0,
            cantidad: row.querySelector('.product-row-cantidad')?.value || '',
            tipo_envase: row.querySelector('.product-row-tipo_envase')?.value || '',
        })).filter(r => r.product_id > 0);

        const jsonInput = document.getElementById('product_rows_json');
        if (jsonInput) jsonInput.value = JSON.stringify(rowData);
    },

    _syncSession: async function () {
        const ids = this._getSelectedProductIds().map(String);
        try {
            await this.rpc('/business-register/update_session_products', {
                selected_products: ids,
                action: 'replace',
            });
        } catch (e) {
            console.error('Error al actualizar sesión de productos', e);
        }
    },

    _addProductRow: function (ev) {
        if (ev && ev.preventDefault) ev.preventDefault();
        this._insertRow(null, '', '');
        this._refilterAllRows();
        this._syncAll();
    },

    _removeProductRow: function (ev) {
        const btn = ev.currentTarget || ev.target;
        const row = btn.closest('.product-row');
        if (row) {
            row.remove();
            this._refilterAllRows();
            this._updateAddButton();
            this._syncAll();
            this._syncSession();
        }
    },

    _onProductRowChange: function () {
        this._refilterAllRows();
        this._updateAddButton();
        this._syncAll();
        this._syncSession();
        this._checkProducts();
    },

    _onHiddenInputChange: function () {
        this._syncAll();
        this._syncSession();
    },

    // ── Validation ───────────────────────────────────────────────────────────────

    _checkProducts: function () {
        const errorEl = document.getElementById('product-error');
        const rows = document.querySelectorAll('#product-rows-container .product-row');
        let hasProduct = false;
        let rowsValid = true;

        rows.forEach(row => {
            const prodSel = row.querySelector('.product-row-product');
            const cantInput = row.querySelector('.product-row-cantidad');
            const tipoSel = row.querySelector('.product-row-tipo_envase');
            const productId = parseInt(prodSel?.value) || 0;

            if (productId > 0) {
                hasProduct = true;
                const cant = parseFloat(cantInput?.value) || 0;
                if (cant <= 0) {
                    cantInput?.classList.add('is-invalid');
                    rowsValid = false;
                } else {
                    cantInput?.classList.remove('is-invalid');
                }
                if (!tipoSel?.value) {
                    tipoSel?.classList.add('is-invalid');
                    rowsValid = false;
                } else {
                    tipoSel?.classList.remove('is-invalid');
                }
            }
        });

        if (errorEl) {
            errorEl.style.display = hasProduct ? 'none' : 'block';
        }
        return hasProduct && rowsValid;
    },

    // ── File validation ──────────────────────────────────────────────────────────

    async _onchangeFile(ev) {
        if (ev?.target?.id) {
            const fileZone = ev?.target.previousElementSibling;
            if (fileZone) fileZone.classList.add('o_files_zone_custom');
            this._validateFileType(ev.target.id);
        }
    },

    async _validateFileType(inputFileId) {
        const fileInput = document.getElementById(inputFileId);
        if (fileInput?.files?.length > 0) {
            let valid = true;
            for (const file of fileInput.files) {
                const file_type = file.type;
                const errorElement = document.getElementById(`${inputFileId}_error`);
                const fileDownloadLink = document.querySelector(`div[name='${inputFileId}_input_group'] a:not(d-none)`);
                valid = await this.rpc('/check_file_type', { config_param: fileDownloadLink.id, file_type });
                if (errorElement) {
                    if (valid) {
                        errorElement.style.display = 'none';
                        fileInput?.classList?.add('is-valid');
                        fileInput?.classList?.remove('is-invalid');
                    } else {
                        errorElement.style.display = 'block';
                        errorElement.style.margin = '10px 0px 10px';
                        fileInput?.classList?.add('is-invalid');
                        fileInput?.classList?.remove('is-valid');
                        return false;
                    }
                }
            }
            return valid;
        }
    },

    _removeInvalid: function (n) {
        if (this.$(n.currentTarget).closest('.is-invalid').attr('id') != 'confirm_password') {
            this.$(n.currentTarget).closest('.is-invalid').removeClass('is-invalid');
        }
    },

    // ── Tabs ─────────────────────────────────────────────────────────────────────

    showTab: function (n) {
        var x = document.getElementsByClassName('tab');
        x[n].style.display = 'block';

        if (n == 0) {
            document.getElementById('prevBtn').style.display = 'none';
        } else {
            document.getElementById('prevBtn').style.display = 'inline';
        }
        if (n == (x.length - 1)) {
            $('#nextBtn').addClass('d-none');
            $('#button-submit').removeClass('d-none');
            $('#btn-preview').removeClass('d-none');
        } else {
            $('#nextBtn').removeClass('d-none');
            $('#button-submit').addClass('d-none');
            $('#btn-preview').addClass('d-none');
        }
    },

    clickPrev: function () {
        var n = -1;
        var x = document.getElementsByClassName('tab');
        if (n == 1 && !this.validateForm()) return false;
        x[this.currentTab].style.display = 'none';
        this.currentTab = this.currentTab + n;
        if (this.currentTab >= x.length) {
            document.getElementById('j').submit();
            return false;
        }
        this.showTab(this.currentTab);
        var wrapwrapEl = document.getElementById('wrapwrap');
        wrapwrapEl.scrollTo({ top: 0, behavior: 'smooth' });
        var progress = (this.currentTab + 1) / x.length * 360;
        var left_progress = progress - 180;
        var right_degree = (progress >= 180) ? '180' : progress.toString();
        var left_degree = (left_progress >= 180) ? left_progress.toString() : '0';
        $('.o_wizard_circle_progress').css({ '--leftProgress': left_degree.concat('deg') });
        $('.o_wizard_circle_progress').css({ '--rightProgress': right_degree.concat('deg') });
        $('.step_counter').text('1 de 2');
    },

    clickNext: function () {
        var n = 1;
        var x = document.getElementsByClassName('tab');
        if (n == 1 && !this.validateForm()) return false;
        x[this.currentTab].style.display = 'none';
        this.currentTab = this.currentTab + n;
        if (this.currentTab >= x.length) {
            document.getElementById('w').submit();
            return false;
        }
        this.showTab(this.currentTab);
        var wrapwrapEl = document.getElementById('wrapwrap');
        wrapwrapEl.scrollTo({ top: 0, behavior: 'smooth' });
        var progress = (this.currentTab + 1) / x.length * 360;
        var left_progress = progress - 180;
        var right_degree = (progress >= 180) ? '180' : progress.toString();
        var left_degree = (left_progress >= 180) ? left_progress.toString() : '0';
        $('.o_wizard_circle_progress').css({ '--leftProgress': left_degree.concat('deg') });
        $('.o_wizard_circle_progress').css({ '--rightProgress': right_degree.concat('deg') });
        $('.step_counter').text('2 de 2');
    },

    validateForm: function (ev) {
        var tabs, inputs, i, valid = true;
        tabs = document.getElementsByClassName('tab');
        inputs = tabs[this.currentTab].getElementsByTagName('input');

        valid = this._checkProducts();
        if (!this._validateFileType('legal_documentation')) valid = false;

        // Validate required <select> elements (not covered by the inputs loop)
        const selects = tabs[this.currentTab].querySelectorAll('select[required]');
        selects.forEach(sel => {
            if (sel.classList.contains('product-row-product') || sel.classList.contains('product-row-tipo_envase')) return;
            if (!sel.value) {
                sel.classList.add('is-invalid');
                valid = false;
            } else {
                sel.classList.remove('is-invalid');
            }
        });

        for (i = 0; i < inputs.length; i++) {
            const array = ['productRequired'];
            const valueToCheck = inputs[i].id;
            if (
                array.indexOf(valueToCheck) === -1 &&
                ((inputs[i].required && inputs[i].value == '' && inputs[i].disabled == false) ||
                    inputs[i].className.indexOf('is-invalid') >= 0)
            ) {
                inputs[i].className += ' is-invalid';
                valid = false;
            }
        }
        if (ev && !valid) {
            ev.preventDefault();
            ev.stopImmediatePropagation();
        }
        return valid;
    },

    // ── Preview DOCX ─────────────────────────────────────────────────────────────

    _previewSolicitud: function (ev) {
        ev.preventDefault();
        this._syncAll();

        // Validate required fields before preview
        if (!this._checkProducts()) return;
        const commitmentDate = document.querySelector('[name="commitment_date"]');
        const formaPago = document.querySelector('[name="forma_pago"]');
        const presupuesto = document.querySelector('[name="presupuesto_disponible"]');
        if (!commitmentDate?.value || !formaPago?.value || !presupuesto?.value) {
            alert('Complete los campos requeridos antes de previsualizar.');
            return;
        }

        const form = document.getElementById('import_registration_form');
        const previewForm = document.createElement('form');
        previewForm.method = 'POST';
        previewForm.action = '/business-register/preview-solicitud';
        previewForm.target = '_blank';

        const fieldNames = [
            'product_rows_json',
            'commitment_date', 'forma_pago',
            'presupuesto_disponible', 'note', 'observaciones_solicitud',
        ];
        fieldNames.forEach(name => {
            const el = form.querySelector(`[name="${name}"]`);
            const hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = name;
            hidden.value = el ? (el.value || '') : '';
            previewForm.appendChild(hidden);
        });

        document.body.appendChild(previewForm);
        previewForm.submit();
        document.body.removeChild(previewForm);
    },

    // ── Presupuesto format ────────────────────────────────────────────────────────

    _formatPresupuesto: function (ev) {
        const input = ev.currentTarget;
        setTimeout(() => {
            if (input.value === '') return;
            const val = parseFloat(input.value);
            if (isNaN(val)) return;
            input.value = (val % 1 === 0) ? String(val) : val.toFixed(3);
        }, 50);
    },
});

publicWidget.registry.ImportRegistrationForm = ImportRegistrationForm;
