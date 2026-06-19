/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';

// Tarjetas visuales de "Tipo de entidad". Cada tarjeta fija el <select name="contact_type">
// real (oculto) y, si corresponde, el tipo de gestión <select name="fgne_type"> (Pymes/
// Sucursal Extranjera/Estatal/CNA). Los selects disparan change para que el formulario
// reaccione igual (mostrar campos y el set de documentos del tipo).
publicWidget.registry.AgrimpexTypeCards = publicWidget.Widget.extend({
    selector: '#business_registration_form',
    events: {
        'click .ag-typecard': '_onCardClick',
    },
    start() {
        const def = this._super(...arguments);
        try {
            const params = new URLSearchParams(window.location.search);
            if (params.get('next') === 'import') {
                const form = this.el || document.querySelector('#business_registration_form');
                if (form) { form.setAttribute('data-success-page', '/en/wizard'); }
            }
        } catch (e) { /* noop */ }
        return def;
    },
    _select() {
        return this.el.querySelector('#contact_type') || this.el.querySelector('select[name="contact_type"]');
    },
    _onCardClick(ev) {
        const card = ev.currentTarget;
        const ct = card.getAttribute('data-ct');
        const mt = card.getAttribute('data-mt');
        const sel = this._select();
        if (sel && ct) {
            sel.value = ct;
            sel.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (mt) {
            this._setManagementWhenReady(mt, 0);
        }
        this._highlightCard(card);
    },
    // El select de tipo de gestión se rellena de forma asíncrona (RPC) tras cambiar
    // el contact_type; esperamos a que aparezca la opción y la seleccionamos.
    _setManagementWhenReady(mtName, tries) {
        const fgne = this.el.querySelector('#fgne_type') || this.el.querySelector('select[name="fgne_type"]');
        if (fgne) {
            const opt = Array.from(fgne.options).find((o) => o.text.trim() === mtName);
            if (opt) {
                fgne.value = opt.value;
                fgne.dispatchEvent(new Event('change', { bubbles: true }));
                return;
            }
        }
        if (tries < 40) {
            setTimeout(() => this._setManagementWhenReady(mtName, tries + 1), 100);
        }
    },
    _highlightCard(card) {
        this.el.querySelectorAll('.ag-typecard').forEach((c) => c.classList.remove('active'));
        if (card) { card.classList.add('active'); }
    },
});

export default publicWidget.registry.AgrimpexTypeCards;
