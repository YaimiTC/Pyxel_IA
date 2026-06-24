/** @odoo-module **/

import { BusinessRegistrationForm } from '@pyxel_import_website/js/business_registration';
import publicWidget from '@web/legacy/js/public/public_widget';

const CustomBusinessRegistrationForm = BusinessRegistrationForm.extend({
    // DE MOMENTO (acreditación en diseño): NINGÚN campo es obligatorio. Se listan aquí
    // todos los campos que el base muestra/oculta para que _showWhen NO les re-imponga
    // 'required' al cambiar de tipo. La validación real es humana (abogado en el CRM).
    optionalFields: ['dap', 'perfil_proveedor', 'nit', 'state', 'city', 'fgne_type',
                     'country', 'supplier_type', 'need_mincex_code', 'license_holder',
                     'has_cuban_partner', 'cuban_partner', 'deed_input'],
    // El tipo de entidad y la gestión se eligen con las TARJETAS de arriba; ya no se
    // muestran como campos abajo. Se quitan fgne_type/dap/deed_input del control nacional.
    showWhenNationalElements: ['nit', 'state', 'city'],

    start: function () {
        const res = this._super.apply(this, arguments);
        // Ocultar los selects que ya fijan las tarjetas (no volver a pedir el tipo abajo).
        ['contact_type', 'fgne_type'].forEach((nm) => {
            const sel = document.querySelector('select[name="' + nm + '"]');
            if (sel) {
                sel.removeAttribute('required');
                const field = sel.closest('.s_website_form_field');
                if (field) { field.style.display = 'none'; }
            }
        });
        // Al subir un documento: mostrar el nombre y marcar la tarjeta como completada.
        document.querySelectorAll('.en-doc-input').forEach((inp) => {
            inp.addEventListener('change', function () {
                const card = inp.closest('.en-doc-card');
                const fn = inp.parentElement && inp.parentElement.querySelector('.en-doc-fname');
                if (inp.files && inp.files.length) {
                    if (card) { card.classList.add('is-done'); }
                    if (fn) { fn.textContent = inp.files.length > 1 ? (inp.files.length + ' archivos seleccionados') : inp.files[0].name; }
                } else {
                    if (card) { card.classList.remove('is-done'); }
                    if (fn) { fn.textContent = ''; }
                }
            });
        });
        // Ocultar la planilla/perfil del proveedor (equivalente a la Ficha de Cliente).
        this._showHidePerfilProveedor();
        // DE MOMENTO: dejar TODO el formulario como no obligatorio.
        this._enFijarTodoOpcional();
        return res;
    },

    // DE MOMENTO (acreditación en diseño): ningún campo ni documento es obligatorio.
    // Se quitan los 'required', las clases de obligatorio y los asteriscos (*) de todo
    // el formulario. La validación real la hace el abogado en el CRM (revisa por NIT).
    _enFijarTodoOpcional: function () {
        const form = document.querySelector('#business_registration_form');
        if (!form) { return; }
        form.querySelectorAll('input, select, textarea').forEach((el) => {
            el.removeAttribute('required');
            el.classList.remove('s_website_form_required', 's_website_form_model_required');
        });
        form.querySelectorAll('.s_website_form_field').forEach((f) => {
            f.classList.remove('s_website_form_required', 's_website_form_model_required');
        });
        form.querySelectorAll('.s_website_form_mark, .en-doc-name .text-danger').forEach((m) => {
            m.style.display = 'none';
        });
    },

    // ENETRADEX: al cambiar el tipo de contacto, el base recarga (RPC) las opciones de
    // gestión y, al no haber placeholder, dejaba seleccionada la PRIMERA (Pymes) y
    // disparaba change, PISANDO la opción que fijó la tarjeta (p. ej. Sucursal
    // Extranjera) -> se mostraban documentos de empresa cubana. Aquí preservamos la
    // selección previa si la opción sigue existiendo tras repoblar.
    _reloadManagementTypes: async function () {
        const contactTypeSel = document.querySelector('select[name="contact_type"]');
        const contact_type_id = contactTypeSel ? contactTypeSel.value : 1;
        const managementTypes = await this.rpc('/get_form_management_types', { contact_type_id });
        // IMPORTANTE: leer la selección a preservar AQUÍ (tras el await). Para entonces
        // la tarjeta ya fijó el tipo deseado (p. ej. "Sucursal Extranjera"); si lo
        // leyéramos antes del await capturaríamos el valor viejo (Pymes) y lo
        // re-impondríamos, pisando la tarjeta.
        const sel = document.querySelector('#fgne_type') || document.querySelector('select[name="fgne_type"]');
        const prevText = sel && sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text.trim() : '';
        document.querySelectorAll('#fgne_type').forEach((s) => {
            s.innerHTML = '';
            Object.entries(managementTypes).forEach(([id, name]) => {
                s.appendChild(new Option(name, id));
            });
            // Preservar la selección actual (la que dejó la tarjeta) tras repoblar.
            if (prevText) {
                const keep = Array.from(s.options).find((o) => o.text.trim() === prevText);
                if (keep) { s.value = keep.value; }
            }
        });
        if (sel) { sel.dispatchEvent(new Event('change', { bubbles: true })); }
    },

    // ENETRADEX: muestra el SET (grid) de documentos del tipo de cliente seleccionado
    // (Pymes/Sucursal Extranjera/Estatal/CNA) o el de Proveedor, y marca como
    // obligatorios solo los visibles. Los ocultos se deshabilitan.
    _showHideLegalDocumentation: function () {
        const providerTypes = ['Proveedor nacional', 'Proveedor extranjero'];
        const isProvider = providerTypes.includes(this.contact_type);
        const activeName = isProvider ? 'endoc_proveedor' : ('endoc_' + (this.fgne_type || ''));

        document.querySelectorAll('.en-doc-set').forEach((set) => {
            const active = set.getAttribute('name') === activeName;
            set.classList.toggle('en-active', active);
            set.querySelectorAll('input[type="file"]').forEach((inp) => {
                if (active) {
                    inp.disabled = false;
                    // DE MOMENTO: documentos NO obligatorios (no se impone required).
                } else {
                    inp.disabled = true;
                    inp.removeAttribute('required');
                    inp.value = '';
                    const card = inp.closest('.en-doc-card');
                    if (card) { card.classList.remove('is-done'); }
                    const fn = inp.parentElement && inp.parentElement.querySelector('.en-doc-fname');
                    if (fn) { fn.textContent = ''; }
                }
            });
        });
    },

    // ENETRADEX: se elimina la "Ficha de cliente" (descargar/subir). El formulario
    // recoge sus datos. Se oculta y se deshabilita para que no sea obligatoria.
    _showHideFichaCliente: function () {
        const ficha = document.querySelector('div[name="ficha_cliente"]');
        if (ficha) {
            ficha.style.display = 'none';
            ficha.querySelectorAll('input').forEach((i) => {
                i.disabled = true;
                i.removeAttribute('required');
            });
        }
    },

    // ENETRADEX: la "planilla/perfil del proveedor" (descargar/subir) es el equivalente
    // a la Ficha de Cliente. Igual que la ficha, se elimina: el formulario recoge los
    // datos y el grid de documentos del proveedor (endoc_proveedor) cubre sus adjuntos.
    _showHidePerfilProveedor: function () {
        const perfil = document.querySelector('div[name="perfil_proveedor"]');
        if (perfil) {
            perfil.style.display = 'none';
            perfil.querySelectorAll('input').forEach((i) => {
                i.disabled = true;
                i.removeAttribute('required');
            });
        }
    },

    // ENETRADEX: se oculta el bloque genérico de escritura (número/fecha).
    _showHideDeedInput: function () {
        const deed = document.querySelector('div[name="deed_input"]');
        if (deed) {
            deed.style.display = 'none';
            deed.querySelectorAll('input').forEach((i) => {
                i.disabled = true;
                i.removeAttribute('required');
            });
        }
    },
});
publicWidget.registry.BusinessRegistrationForm = CustomBusinessRegistrationForm;
