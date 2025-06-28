/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';


export const BusinessRegistrationForm = publicWidget.Widget.extend({
    selector: '#business_registration_form',
    events: {
        'keyup #password': '_checkPassword',
        'keyup #confirm_password': '_checkPassword',
        'load #password': '_checkPassword',
        'load #confirm_password': '_checkPassword',
        'click #prevBtn': 'clickPrev',
        'click #nextBtn': 'clickNext',
        'load document': '_checkPassword',
        'click .register_business_button': '_checkPassword',
        'keyup .is-invalid': '_removeInvalid',
        'click .is-invalid': '_removeInvalid',
        'change select[name="FGNE type"]': '_showHideFichaCliente',
        'change select[name="Country"]': '_reloadStates',
        'change select[name="State"]': '_reloadCities',
        'change #hiddenTestInput': '_updateSessionProducts',
        'select2:select #productRequired': '_updateSessionProducts',
        'change #hiddenTestInputElectronic': '_updateSessionProductsElectronic',
        'select2:select #productOnure':'_updateSessionProductsElectronic',
        
        'change #x_studio_certifies_receipt_load': '_toggleFields',

        
        // 'click #addToSession': '_addToSessionNomenclator',

        
        
    },


    init() {
        this._super(...arguments);
        this.rpc = this.bindService("rpc");
        this.currentTab = 0;
    },

    start: function () {
        var def = this._super.apply(this, arguments);
        this.showTab(this.currentTab);
        this._reloadStates();
        this._toggleFields();
        this._showHideFichaCliente();
        return def;
    },
   async _reloadStates() {
      
        const $countrySel = $('select[name="Country"]:visible');
        const country_id  = $countrySel.length ? $countrySel.val() : 56; // 56 → Cuba

        const states = await this.rpc('/get_form_states', { country_id });

       
        $('#state, #state_provider').each(function () {
            const $sel = $(this).empty();
            $sel.append('<option value="">Provincia…</option>');
            $.each(states, (id, name) => $sel.append(new Option(name, id)));
        });

     
        this._reloadCities();
    },
    async _reloadCities(ev) {
  
        const map = {
            state          : '#city',
            state_provider : '#city_provider',
        };

        const stateSelectID = ev ? $(ev.target).attr('id') :
                               $('select[name="State"]:visible').attr('id');

        if (!stateSelectID) { return; }

        const $stateSel = $('#' + stateSelectID);
        const state_id  = $stateSel.val() || 0;

        const cities = state_id ? await this.rpc('/get_form_cities', { state_id }) : {};

        const $citySel = $(map[stateSelectID]).empty();
        $citySel.append('<option value="">Municipio…</option>');
        $.each(cities, (id, name) => $citySel.append(new Option(name, id)));
    },
    _showHideFichaCliente:  function () {
        var ficha_cliente_fgne_tcp = document.querySelector('a[href="/descargar/ficha_cliente_fgne_tcp"]');
        var ficha_cliente_estatal = document.querySelector('a[href="/descargar/ficha_cliente_estatal"]');
        var fgne_type = document.querySelector('div[name="fgne_type_national_client"] select[name="FGNE type"]');

        if (fgne_type?.value == 'Estatal') {
            ficha_cliente_estatal?.classList.remove("d-none");
            ficha_cliente_fgne_tcp?.classList.add("d-none");
        } else {
            ficha_cliente_fgne_tcp?.classList.remove("d-none");
            ficha_cliente_estatal?.classList.add("d-none");
        }
    },
    _changeCountry:  function () {
        var selectStates = $("select[name='State']");
        var selectCountry = $("select[name='Country']");
        selectStates.find("option").filter('[country-id!="' + selectCountry.val() + '"]').hide();
        var options = selectStates.find("option").filter('[country-id="' + selectCountry.val() + '"]');
        options.show()
        if (options.length > 0){
            selectStates.val(options[0].value).change();
        }else{}
    },
    _checkProducts() {
    // _checkProducts(ev) {
        var valid = true;
        var productRequired = document.getElementById("select2-productRequired-container");
        var productOnure = document.getElementById("select2-productOnure-container");
            if (productRequired?.childElementCount === 0 && productOnure?.childElementCount === 0) { 
                valid = false;
            }
        // var x = document.getElementsByClassName("js-example-basic-multiple");
        // for (let i = 0; i < x.length; i++) {
        //     if (x[i].childElementCount === 0) { 
        //         valid = false;
        //     }
        // }
        
        
        var errorEnvolt = document.getElementById("error_envolt");
        var productError = document.getElementById("product-error");
    
        
        if (errorEnvolt && productError) {
            if (valid) {
                console.log('valido');
                errorEnvolt.style.border = "none";
                productError.style.display = "none";
            } else {
                console.log('no valido');
                errorEnvolt.style.border = "1px solid red";
                errorEnvolt.style.padding = "10px 10px 0px";
                productError.style.display = "block";
                productError.style.margin = "10px 0px 10px";
    
                // if (ev) {
                //     ev.preventDefault();
                //     ev.stopImmediatePropagation();
                // }
            }
        }
        return valid;
        },
    _checkPassword(ev) {
        console.log('Pepe el animal');
        this._checkProducts();
        // this._checkProducts(ev);
       
        if ($("#password").length > 0 && $("#confirm_password").length > 0) {
            if ($("#password").val() !== $("#confirm_password").val()) {
                console.log('son diferentes');
                $("#confirm_password").addClass('is-invalid');
                $("#confirm_password").removeClass('is-valid');
            } else {
                $("#confirm_password").addClass('is-valid');
                $("#confirm_password").removeClass('is-invalid');
            }
        }
    },
    
    _removeInvalid: function(n) {

        if (this.$(n.currentTarget).closest('.is-invalid').attr('id') != 'confirm_password'){
            this.$(n.currentTarget).closest('.is-invalid').removeClass('is-invalid');
        }

    },
    showTab: function(n) {
        var x = document.getElementsByClassName("tab");
        x[n].style.display = "block";
        
        if (n == 0) {
            document.getElementById("prevBtn").style.display = "none";
        } else {
            document.getElementById("prevBtn").style.display = "inline";
        }
        if (n == (x.length - 1)) {
            $("#nextBtn").addClass("d-none");
            $("#button-submit").removeClass("d-none");
        } else {
               $("#nextBtn").removeClass("d-none");
            $("#button-submit").addClass("d-none");
        }

        var supplierimporter = document.getElementById("telefono");
        if (supplierimporter) {
            // Definir el comportamiento dinámico basado en el checkbox
            var otherClientCheckbox = document.getElementById("other_client");
            
           

            function updateButtonsBasedOnCheckbox() {
                if (otherClientCheckbox.checked && n < (x.length - 1)) {
                    $("#nextBtn").removeClass("d-none");       // Mostrar "Siguiente"
                    $("#button-submit").addClass("d-none");    // Ocultar "Solicitar servicio"
                } else {
                    $("#nextBtn").addClass("d-none");          // Ocultar "Siguiente"
                    $("#button-submit").removeClass("d-none"); // Mostrar "Solicitar servicio"
                }
            }

            // Llamar la función al cargar la pestaña
            updateButtonsBasedOnCheckbox();

            // Añadir el evento dinámico para cambios en el checkbox
            otherClientCheckbox.addEventListener("change", updateButtonsBasedOnCheckbox);
        }
        // Actualizar los indicadores de progreso
        this.fixStepIndicator(n);
    },
    clickPrev:function() {  
        var n = -1;
        // This function will figure out which tab to display
        var x = document.getElementsByClassName("tab");
        // Exit the function if any field in the current tab is invalid:
        if (n == 1 && !this.validateForm()) return false;
        // Hide the current tab:
        x[this.currentTab].style.display = "none";
        // Increase or decrease the current tab by 1:
        this.currentTab = this.currentTab + n;
        // if you have reached the end of the form... :
        if (this.currentTab >= x.length) {
            //...the form gets submitted:
            document.getElementById("j").submit();
            return false;
        }
        // Otherwise, display the correct tab:
        this.showTab(this.currentTab);
        var wrapwrapEl=document.getElementById("wrapwrap");
        wrapwrapEl.scrollTo({top:0,behavior:"smooth"});

        var progress = (this.currentTab+1) / x.length * 360
        var left_progress = progress - 180
        var right_degree = (progress >= 180 ) ? "180":progress.toString();
        var left_degree = (left_progress >= 180 ) ? left_progress.toString():"0";
        $('.o_wizard_circle_progress').css({"--leftProgress": left_degree.concat("deg")});
        $('.o_wizard_circle_progress').css({"--rightProgress": right_degree.concat("deg")});
         $('.step_counter').text("1 de 2");;
    },
    clickNext:function() {
        var n = 1;
        // This function will figure out which tab to display
        var x = document.getElementsByClassName("tab");
        // Exit the function if any field in the current tab is invalid:
        if (n == 1 && !this.validateForm()) return false;
        // Hide the current tab:
        x[this.currentTab].style.display = "none";
        // Increase or decrease the current tab by 1:
        this.currentTab = this.currentTab + n;
        // if you have reached the end of the form... :
        if (this.currentTab >= x.length) {
            //...the form gets submitted:
            document.getElementById("w").submit();
            return false;
        }
        // Otherwise, display the correct tab:
        this.showTab(this.currentTab);
        var wrapwrapEl=document.getElementById("wrapwrap");
        wrapwrapEl.scrollTo({top:0,behavior:"smooth"});

        var progress = (this.currentTab+1) / x.length * 360
        var left_progress = progress - 180
        var right_degree = (progress >= 180 ) ? "180":progress.toString();
        var left_degree = (left_progress >= 180 ) ? left_progress.toString():"0";

        $('.o_wizard_circle_progress').css({"--leftProgress": left_degree.concat("deg")});
        $('.o_wizard_circle_progress').css({"--rightProgress": right_degree.concat("deg")});
        $('.step_counter').text("2 de 2");

    },
    _toggleFields: function() {
        this._toggleContainerField();
        this._toggleDocumentFields();
    },

    _toggleContainerField: function() {
        if (!$("#container_type").length) {
            return;
        }
        var selectedOption = $("#x_studio_certifies_receipt_load option:selected").text();
        var $containerField = $("#container_type").closest('[data-name="Field"]');
        if (selectedOption.indexOf("FCL") !== -1 || selectedOption.indexOf("LCL") !== -1) {
            $containerField.show();
        } else {
            $containerField.hide();
        }
    },
    _toggleDocumentFields: function() {
        if (!$("#x_studio_bill_of_lading_bl").length) {
            return;
        }
        
        var selectedOption = $("#x_studio_certifies_receipt_load option:selected").text();
        var hideFields = selectedOption.indexOf("DAP") !== -1;
        var fieldSelectors = [
            "#x_studio_bill_of_lading_bl",  // Documentación BL/AWB 
            "#x_studio_package_list",         // Lista de empaque
            "#x_studio_export_certify"        // Certificado de exportación
        ];
        //ocultar o mostrar los campos según la opción seleccionada
        fieldSelectors.forEach(function(selector) {
            var $fieldContainer = $(selector).closest('[data-name="Field"]');
            if (hideFields) {
                $fieldContainer.hide();
            } else {
                $fieldContainer.show();
            }
        });
        
        var $label = $("label[for='x_studio_bill_of_landing_number'] .s_website_form_label_content");
        if (hideFields) {
            $label.text("Número");
        } else {
            $label.text("No. BL/AWB/LCL");
        }
    },
    
    
    
    validateForm: function() {

        const billOfLandingField = document.getElementById('x_studio_bill_of_landing_number');
        if (billOfLandingField && billOfLandingField.value === "") {
            billOfLandingField.value = "0";
        }
        // This function deals with validation of the form fields
        var v, w, x, y, y2, i, valid = true;
        x = document.getElementsByClassName("tab");
        y = x[this.currentTab].getElementsByTagName("input");
        y2 = x[this.currentTab].getElementsByTagName("textarea");
        console.log(y);
        console.log(y2);
        v=document.getElementsByClassName("")

        valid = this._checkProducts();
        // valid = this._checkProducts(ev);

        var testEmail = /^[A-Z0-9._%+-]+@([A-Z0-9-]+\.)+[A-Z]{2,4}$/i;
        if (y2.length >=1){
         for (i = 0; i < y2.length; i++) {
            // If a field is empty...
            const array= ["productOnure","productRequired","x_studio_bill_of_landing_number","x_studio_certificate_of_origin_co","x_studio_bill_of_lading_bl","x_comercial_invoice","x_package_list","x_export_certify","x_quality_certify"];
            const valueToCheck = y[i].id;
            
            if (array.indexOf(valueToCheck) === -1 &&
                ((y[i].value == "" && y[i].disabled == false) || 
                 (y[i].type == 'email' && y[i].disabled == false && !testEmail.test(y[i].value)) || 
                 y[i].className.indexOf('is-invalid') >= 0)) {
                // add an "invalid" class to the field:
                y[i].className += " is-invalid";
                // and set the current valid status to false:
                valid = false;
            }


        }
         }
        // A loop that checks every input field in the current tab:
        for (i = 0; i < y.length; i++) {
            // If a field is empty...
            const array= ["productOnure","productRequired","x_studio_bill_of_landing_number","x_studio_certificate_of_origin_co","x_studio_bill_of_lading_bl","x_comercial_invoice","x_package_list","x_export_certify","x_quality_certify"];
            const valueToCheck = y[i].id;
            if (array.indexOf(valueToCheck) === -1 &&((y[i].value == "" && y[i].disabled == false) ||(y[i].type == 'email' && y[i].disabled == false && !testEmail.test(y[i].value)) || y[i].className.indexOf('is-invalid') >= 0)){
                // add an "invalid" class to the field:
                y[i].className += " is-invalid";
                // and set the current valid status to false:
                valid = false;
            }
            if (y[i].id === 'nit') {
                var nitField = document.getElementById('nit');
                var errorSpan = document.getElementById('nit-error');
    
                // Validar si contiene exactamente 11 dígitos
                if (!/^\d{11}$/.test(nitField.value)) {
                    nitField.classList.add("is-invalid");
                    errorSpan.style.display = 'inline';
                    valid = false;
                } 
                else {
                    nitField.classList.remove("is-invalid");
                    // errorSpan.style.display = 'none';
                }
            }
        }
        // If the valid status is true, mark the step as finished and valid:
        console.log(valid) ;
        if (valid) {
            document.getElementsByClassName("step")[this.currentTab].className += " finish complete";
        }
        return valid; // return the valid status
    },
    fixStepIndicator: function(n) {
        // This function removes the "active" class of all steps...
        var i, x = document.getElementsByClassName("step");
        for (i = 0; i < x.length; i++) {
            x[i].className = x[i].className.replace(" in-progress", "");
            x[i].className = x[i].className.replace("complete", "");
            if (i <= n){
                x[i].className += " complete";
            }
             if (i > n){
                x[i].className = x[i].className.replace("complete", "");
                x[i].className = x[i].className.replace("finish", "");
            }
        }
        //... and adds the "active" class to the current step:
        x[n].className += " in-progress";
    },
    async _updateSessionProducts(ev) {
        
        const $select = $('#productRequired');
        const selectedValues = $select.val()
        console.log("Productos seleccionados js:", selectedValues);// Obtener los valores seleccionados

        // Llamada RPC para actualizar la sesión
        
        await this.rpc("/business-register/update_session_products", {
            selected_products: selectedValues
        }).then(function (response) {
            console.log("Sesión actualizada con éxito", response);
        }).catch(function (error) {
            console.error("Error al actualizar la sesión", error);
        });
    },
    async _updateSessionProductsElectronic(ev) {
        
        const $select = $('#productOnure');
        const selectedValues = $select.val()
        console.log("Productos seleccionados js:", selectedValues);// Obtener los valores seleccionados

        // Llamada RPC para actualizar la sesión
        
        await this.rpc("/business-register/update_session_electronics", {
            selected_electronics: selectedValues
        }).then(function (response) {
            console.log("Sesión actualizada con éxito", response);
        }).catch(function (error) {
            console.error("Error al actualizar la sesión", error);
        });
    },
    
});
publicWidget.registry.BusinessRegistrationForm = BusinessRegistrationForm;