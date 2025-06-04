/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget'


export const NomenclatorAdd = publicWidget.Widget.extend({
    selector: '#nomenclator_form',
    events: {
       'click button[data-product-id]': '_addToSessionNomenclator',
       'click button[data-electric-id]': '_addToSessionElectric',
       'submit': '_handleFormSubmit', // Manejar el submit de forma global    
       'click .nav-link': '_onTabClick', 
    //    'click #alimentos_tab': '_loadAlimento',
    //    'click #electronicos-tab':'_loadElectronic'
    },


    init() {
        this._super(...arguments);
        this.rpc = this.bindService("rpc");
        this.currentTab = 0;

    },

  // Método para cambiar de pestaña
_onTabClick(ev) {
    const tab = $(ev.currentTarget).data('tab');
    this._setActiveTab(ev.currentTarget);
    // this._loadProductsByTab(tab);
},

// async _loadAlimento(ev){
//     await this.rpc('/nomenclador', '/nomenclador/page/<int:page>')
// },

// async _loadElectronic(ev){
//     await this.rpc('/onure', '/onure/page/<int:page>')
// },


// Establecer la pestaña activa
_setActiveTab(activeTab) {
    // Remover las clases 'active' e 'inactive' de todas las pestañas
    $('#nomenclador-tabs .nav-link').removeClass('active').addClass('inactive');

    // Agregar la clase 'active' solo a la pestaña seleccionada y remover 'inactive'
    $(activeTab).removeClass('inactive').addClass('active');
},

async _addToSessionNomenclator(ev) {
    // Prevenir que el formulario se envíe
    ev.preventDefault();

    // Obtener el ID del producto a partir del botón que fue clickeado
    const $button = $(ev.currentTarget);
    const productId = $button.data('product-id');
    const isRemoving = $button.text().trim() === 'Eliminar';
    const action = isRemoving ? 'remove' : 'add';
    

    console.log("Producto seleccionado JS:", productId);

    if ($button.text().trim() === 'Agregar') {
        $button.text('Eliminar');
        $button.css('background-color', '#B0B0B0');
        $button.removeClass('btn-primary').addClass('btn-secondary');
    } else {
        $button.text('Agregar');
        $button.css('background-color', ''); // Restaurar el color original
        $button.removeClass('btn-secondary').addClass('btn-primary');
    }

    // Llamada RPC para actualizar la sesión
    await this.rpc("/business-register/update_session_products", {

        selected_products: [productId],  // Enviar el producto seleccionado
        action: action

    }).then(function (response) {
        console.log("Sesión actualizada con éxito", response);
    }).catch(function (error) {
        console.error("Error al actualizar la sesión", error);
    });
},

// update_session_electronics

async _addToSessionElectric(ev) {
    // Prevenir que el formulario se envíe
    ev.preventDefault();

    // Obtener el ID del producto a partir del botón que fue clickeado
    const $button = $(ev.currentTarget);
    const electricId = $button.data('electric-id');
    const isRemoving = $button.text().trim() === 'Eliminar';
    const action = isRemoving ? 'remove' : 'add';
    

    console.log("Producto seleccionado JS:", electricId);

    if ($button.text().trim() === 'Agregar') {
        $button.text('Eliminar');
        $button.css('background-color', '#B0B0B0');
        $button.removeClass('btn-primary').addClass('btn-secondary');
    } else {
        $button.text('Agregar');
        $button.css('background-color', ''); // Restaurar el color original
        $button.removeClass('btn-secondary').addClass('btn-primary');
    }

    // Llamada RPC para actualizar la sesión
    await this.rpc("/business-register/update_session_electronics", {

        selected_electronics: [electricId],  // Enviar el producto seleccionado
        action: action

    }).then(function (response) {
        console.log("Sesión actualizada con éxito", response);
    }).catch(function (error) {
        console.error("Error al actualizar la sesión", error);
    });
},
_handleFormSubmit(ev) {
        // Obtener el botón que disparó el evento submit
        const $button = $(ev.originalEvent.submitter);

        // Verificar si es el botón específico
        if ($button.data('trigger') === 'specific-submit') {
            // Prevenir el envío del formulario por defecto
            ev.preventDefault();

            const originalPage = '/business-register?type=import';

            if (originalPage) {
                // Redirigir a la página del formulario ed solicitud de importacion
                window.location.assign(originalPage);
            } else {
                // Si no se encuentra, redirigir al home, esto no debe pasar
                window.location.assign('/fruxelimport.com');
            }
        }
    },

});

publicWidget.registry.NomenclatorAdd = NomenclatorAdd;