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
        'click .register_business_button': 'validateForm',
        'keyup .is-invalid': '_removeInvalid',
        'click .is-invalid': '_removeInvalid',
        'change input[name="parent_company_name"]': '_onchangeParentCompanyName',
        'change input[name="legal_documentation"]': '_onchangeFile',
        'change input[name="ficha_cliente"]': '_onchangeFile',
        'change select[name="contact_type"]': '_onchangeContactType',
        'change input[name="need_mincex_code"]': '_showHideNoMincexCodeDocumentation',
        'change input[name="has_cuban_partner"]': '_showHideCubanPartner',
        'change select[name="fgne_type"]': '_onchangeFGNEType',
        'change select[name="country"]': '_reloadStates',
        'change select[name="state"]': '_reloadCities',
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
        this._toggleFields();
        this._showHideNoMincexCodeDocumentation();
        this._showHideCubanPartner();
        this._onchangeContactType();
        this._reloadStates();
        return def;
    },
    contact_type: null, 
    fgne_type: null, 
    showWhenForeignElements: ['need_mincex_code','license_holder', 'has_cuban_partner', 'country'],
    showWhenNationalElements: ['fgne_type', 'nit', 'dap', 'state', 'city'],
    showWhenProviderElements: ['supplier_type', 'perfil_proveedor'],
    _setContactType(){
        this.contact_type = $('select[name="contact_type"]').find('option:selected').text().trim();
    },
    _setFgneType(){
        this.fgne_type = $('div[name="fgne_type"] select[name="fgne_type"]').find('option:selected').text().trim();
    },
    _onchangeFGNEType:  function () {
        this._setFgneType()
        this._showHideFichaCliente()
        this._showHideDeedInput()
        this._showHideLegalDocumentation()
    },
    _onchangeContactType:  function () {
        this._setContactType()
        this.showWhenForeignElements.forEach(elementName => {
            this._showWhenForeign(elementName)
        });
        this.showWhenNationalElements.forEach(elementName => {
            this._showWhenNational(elementName)
        });
        this.showWhenProviderElements.forEach(elementName => {
            this._showWhenProvider(elementName)
        });
        this._onchangeFGNEType()
        this._reloadManagementTypes()
    },
    _onchangeParentCompanyName:  function () {
        const parent_company_name = document.querySelector('input[name="parent_company_name"]').value;
        const contact1 = document.getElementById('contact1');
        contact1.value = 'Solicitud de acreditación ('+ parent_company_name + ')'
    },
    _showWhen:  function (contactTypes, elementName) {
        var element = document.querySelector(`div[name="${elementName}"]`);
        var elementInput = document.querySelector(`div[name="${elementName}"] input`);
        var elementSelect = document.querySelector(`div[name="${elementName}"] select`);

        if (contactTypes.includes(this.contact_type)){
            element?.classList.remove("d-none");
            if(elementInput?.type != 'checkbox')
                elementInput?.setAttribute("required", "");
            elementSelect?.setAttribute("required", "");
            if(elementInput)
                elementInput.disabled = false;
        }
        else {
            element?.classList.add("d-none");
            elementInput?.removeAttribute("required");
            elementSelect?.removeAttribute("required");
            if(elementInput)
                elementInput.disabled = true;
        }
    },
    // Si es nacional se muestra el element
    _showWhenNational:  function (elementName) {
        this._showWhen(['Cliente', 'Proveedor'], elementName)
    },
    // Si es proveedor se muestra el element
    _showWhenProvider:  function (elementName) {
        this._showWhen(['Proveedor', 'Proveedor extranjero'], elementName)
    },
    // Si es extranjero se muestra el element
    _showWhenForeign:  function (elementName) {
        this._showWhen(['Cliente extranjero', 'Proveedor extranjero'], elementName)
    },
    _showHideFichaCliente:  function () {
        var ficha_cliente_fgne_tcp = document.getElementById('ficha_cliente_fgne_tcp');
        var ficha_cliente_estatal = document.getElementById('ficha_cliente_estatal');
        var ficha_cliente = document.querySelector('div[name="ficha_cliente"]');
        var ficha_cliente_input = document.querySelector('div[name="ficha_cliente"] input');

        // TODO: Si es cliente nacional se muestra el ficha_cliente
        if (this.contact_type == 'Cliente') {
            ficha_cliente?.classList.remove("d-none");
            ficha_cliente_input?.setAttribute("required", "");
            if(ficha_cliente_input)
                ficha_cliente_input.disabled = false;
        } else {
            ficha_cliente?.classList.add("d-none");
            ficha_cliente_input?.removeAttribute("required");
            if(ficha_cliente_input)
                ficha_cliente_input.disabled = true;
        }

        if (this.fgne_type == 'Estatal') {
            ficha_cliente_estatal?.classList.remove("d-none");
            ficha_cliente_fgne_tcp?.classList.add("d-none");
        } else {
            ficha_cliente_fgne_tcp?.classList.remove("d-none");
            ficha_cliente_estatal?.classList.add("d-none");
        }
    },
    _showHideDeedInput:  function () {
        var deed_for_mipyme_cna_pdl = document.getElementById('deed_for_mipyme_cna_pdl');
        var deed_for_tcp = document.getElementById('deed_for_tcp');
        var deed_for_state = document.getElementById('deed_for_state');
        var deed_input = document.querySelector('div[name="deed_input"]');
        var deed_input_number = document.querySelector('div[name="deed_input"] input[name="deed_input_number"]');
        var deed_input_date = document.querySelector('div[name="deed_input"] input[name="deed_input_date"]');

        if(deed_input_number && deed_input_date){
            if (!this.fgne_type || ['Persona Natural', 'Sucursal Extranjera'].includes(this.fgne_type)) {
                deed_input_number.removeAttribute("required");
                deed_input_number.disabled = true;
                deed_input_date.removeAttribute("required");
                deed_input_date.disabled = true;
            } else {
                deed_input_number.setAttribute("required", "");
                deed_input_number.disabled = false;
                deed_input_date.setAttribute("required", "");
                deed_input_date.disabled = false;
            }
        }

        if (this.fgne_type == 'TCP') {
            deed_input?.classList.remove("d-none");
            deed_for_state?.classList.add("d-none");
            deed_for_tcp?.classList.remove("d-none");
            deed_for_mipyme_cna_pdl?.classList.add("d-none");
        }
        else if (this.fgne_type == 'Estatal') {
            deed_input?.classList.remove("d-none");
            deed_for_state?.classList.remove("d-none");
            deed_for_tcp?.classList.add("d-none");
            deed_for_mipyme_cna_pdl?.classList.add("d-none");
        }
        else if (['Mipyme', 'CNA', 'PDL'].includes(this.fgne_type)) {
            deed_input?.classList.remove("d-none");
            deed_for_state?.classList.add("d-none");
            deed_for_tcp?.classList.add("d-none");
            deed_for_mipyme_cna_pdl?.classList.remove("d-none");
        } else {
            deed_input?.classList.add("d-none");
        }
    },
    _showHideCubanPartner:  function () {
        var cuban_partner = document.querySelector('div[name="cuban_partner"]');
        var cuban_partner_input = document.querySelector('div[name="cuban_partner"] input');
        var has_cuban_partner = document.querySelector('div[name="has_cuban_partner"] input');

        if (has_cuban_partner?.checked) {
            cuban_partner?.classList.remove("d-none");
            cuban_partner_input?.setAttribute("required", "");
            if(cuban_partner_input)
                cuban_partner_input.disabled = false;
        } else {
            cuban_partner?.classList.add("d-none");
            cuban_partner_input?.removeAttribute("required");
            if(cuban_partner_input)
                cuban_partner_input.disabled = true;
        }
    },
    _showHideLegalDocumentation:  function () {
        var legal_documentation_tcp = document.querySelector("div[name='legal_documentation_tcp']");
        var legal_documentation_mipyme = document.querySelector("div[name='legal_documentation_mipyme']");
        var legal_documentation_natural_person = document.querySelector("div[name='legal_documentation_natural_person']");
        var legal_documentation_natural_foreign_branch = document.querySelector("div[name='legal_documentation_natural_foreign_branch']");
        var legal_documentation_natural_state = document.querySelector("div[name='legal_documentation_natural_state']");
        var legal_documentation_pdl = document.querySelector("div[name='legal_documentation_pdl']");
        var legal_documentation_cna = document.querySelector("div[name='legal_documentation_cna']");
        var legal_documentation_foreign_contact_type = document.querySelector("div[name='legal_documentation_foreign_contact_type']");


        if (['Cliente extranjero', 'Proveedor extranjero'].includes(this.contact_type))
            legal_documentation_foreign_contact_type?.classList.remove("d-none");
        else
            legal_documentation_foreign_contact_type?.classList.add("d-none");
        if (this.fgne_type == 'TCP') {
            legal_documentation_tcp?.classList.remove("d-none");
            legal_documentation_mipyme?.classList.add("d-none");
            legal_documentation_natural_person?.classList.add("d-none");
            legal_documentation_natural_foreign_branch?.classList.add("d-none");
            legal_documentation_natural_state?.classList.add("d-none");
            legal_documentation_pdl?.classList.add("d-none");
            legal_documentation_cna?.classList.add("d-none");
        }
        else if(this.fgne_type == 'Mipyme'){
            legal_documentation_tcp?.classList.add("d-none");
            legal_documentation_mipyme?.classList.remove("d-none");
            legal_documentation_natural_person?.classList.add("d-none");
            legal_documentation_natural_foreign_branch?.classList.add("d-none");
            legal_documentation_natural_state?.classList.add("d-none");
            legal_documentation_pdl?.classList.add("d-none");
            legal_documentation_cna?.classList.add("d-none");
        }
        else if(this.fgne_type == 'Persona Natural'){
            legal_documentation_tcp?.classList.add("d-none");
            legal_documentation_mipyme?.classList.add("d-none");
            legal_documentation_natural_person?.classList.remove("d-none");
            legal_documentation_natural_foreign_branch?.classList.add("d-none");
            legal_documentation_natural_state?.classList.add("d-none");
            legal_documentation_pdl?.classList.add("d-none");
            legal_documentation_cna?.classList.add("d-none");
        }
        else if(this.fgne_type == 'Sucursal Extranjera'){
            legal_documentation_tcp?.classList.add("d-none");
            legal_documentation_mipyme?.classList.add("d-none");
            legal_documentation_natural_person?.classList.add("d-none");
            legal_documentation_natural_foreign_branch?.classList.remove("d-none");
            legal_documentation_natural_state?.classList.add("d-none");
            legal_documentation_pdl?.classList.add("d-none");
            legal_documentation_cna?.classList.add("d-none");
        }
        else if(this.fgne_type == 'Estatal'){
            legal_documentation_tcp?.classList.add("d-none");
            legal_documentation_mipyme?.classList.add("d-none");
            legal_documentation_natural_person?.classList.add("d-none");
            legal_documentation_natural_foreign_branch?.classList.add("d-none");
            legal_documentation_natural_state?.classList.remove("d-none");
            legal_documentation_pdl?.classList.add("d-none");
            legal_documentation_cna?.classList.add("d-none");
        }
        else if(this.fgne_type == 'CNA'){
            legal_documentation_tcp?.classList.add("d-none");
            legal_documentation_mipyme?.classList.add("d-none");
            legal_documentation_natural_person?.classList.add("d-none");
            legal_documentation_natural_foreign_branch?.classList.add("d-none");
            legal_documentation_natural_state?.classList.add("d-none");
            legal_documentation_cna?.classList.remove("d-none");
            legal_documentation_pdl?.classList.add("d-none");
        }
        else if(this.fgne_type == 'PDL'){
            legal_documentation_tcp?.classList.add("d-none");
            legal_documentation_mipyme?.classList.add("d-none");
            legal_documentation_natural_person?.classList.add("d-none");
            legal_documentation_natural_foreign_branch?.classList.add("d-none");
            legal_documentation_natural_state?.classList.add("d-none");
            legal_documentation_cna?.classList.add("d-none");
            legal_documentation_pdl?.classList.remove("d-none");
        }
        else{
            legal_documentation_tcp?.classList.add("d-none");
            legal_documentation_mipyme?.classList.add("d-none");
            legal_documentation_natural_person?.classList.add("d-none");
            legal_documentation_natural_foreign_branch?.classList.add("d-none");
            legal_documentation_natural_state?.classList.add("d-none");
            legal_documentation_cna?.classList.add("d-none");
            legal_documentation_pdl?.classList.add("d-none");
        }
        
    },
    // En caso de no tener código de MINCEX se solicitan un conjunto de documentos legales
    _showHideNoMincexCodeDocumentation:  function () {
        const need_mincex_code = document.getElementById("need_mincex_code")
        const license_holder = document.querySelector("div[name='license_holder']");
        const license_holder_input = document.querySelector("div[name='license_holder'] input");
        const no_mincex_code_documentation = document.querySelector("div[name='no_mincex_code_documentation']");

        if (need_mincex_code?.checked) {
            no_mincex_code_documentation?.classList.remove("d-none");
            // if(['Cliente extranjero', 'Proveedor extranjero'].includes())
            license_holder?.classList.add("d-none");
            license_holder_input?.removeAttribute("required");
            if(license_holder_input)
                license_holder_input.disabled = true;
        }
        else{
            no_mincex_code_documentation?.classList.add("d-none");
            license_holder?.classList.remove("d-none");
            license_holder_input?.setAttribute("required", "");
            if(license_holder_input)
                license_holder_input.disabled = false;
        }
    },
    async _onchangeFile(ev) {
        if(ev?.target?.id)
            this._validateFileType(ev.target.id)
    },
    async _validateFileType(inputFileId) {
        const fileInput = document.getElementById(inputFileId);
        
        if(fileInput.files[0]){
            const file_type = fileInput.files[0].type
            const errorElement = document.getElementById(`${inputFileId}_error`);
            // const fileDelete = document.querySelector(`div[name='${ev.target.name}_input_group'] .o_file_delete`);
            let valid = true
            if(fileInput.id !='legal_documentation'){
                const fileDownloadLink = document.querySelector(`div[name='${inputFileId}_input_group'] a:not(d-none)`)
                valid = await this.rpc('/check_file_type', { config_param: fileDownloadLink.id, file_type});
            }
            else
                valid = file_type == 'application/pdf'
            if(errorElement){
                if(valid){
                    errorElement.style.display = "none";
                    fileInput?.classList?.add('is-valid');
                    fileInput?.classList?.remove('is-invalid');
                } else {
                    errorElement.style.display = "block";
                    errorElement.style.margin = "10px 0px 10px";
                    fileInput?.classList?.add('is-invalid');
                    fileInput?.classList?.remove('is-valid');
                    // fileDelete.click() 
                }
            }
            return valid
        }
    },
    async _reloadManagementTypes() {
        const $contactTypeSel = $('select[name="contact_type"]');
        const contact_type_id  = $contactTypeSel.length ? $contactTypeSel.val() : 1; // 1 → Cliente Nacional
        const managementTypes = await this.rpc('/get_form_management_types', { contact_type_id });
        $('#fgne_type').each(function () {
            const $sel = $(this).empty();
            // $sel.append('<option value="">Tipos de Gestión Empresarial...</option>');
            $.each(managementTypes, (id, name) => $sel.append(new Option(name, id)));
        });
        $('#fgne_type').change()
    },
   async _reloadStates() {
        var country = $('div[name="country"]');
        const $countrySel = $('select[name="country"]');
        const country_code  = !country.hasClass('d-none') && $countrySel.length ? $countrySel.val() : 'CU'; // CU → Cuba
        // const country_id  = !country.hasClass('d-none') && $countrySel.length ? $countrySel.val() : 56; // 56 → Cuba
        
        const states = await this.rpc('/get_form_states', { country_code });
        $('#state').each(function () {
            const $sel = $(this).empty();
            $sel.append('<option value="">Provincia…</option>');
            $.each(states, (id, name) => $sel.append(new Option(name, id)));
        });
     
        this._reloadCities();
    },
    async _reloadCities(ev) {
        const map = {
            state          : '#city',
        };
        const stateSelectID = ev ? $(ev.target).attr('id') :
                               $('select[name="state"]:visible').attr('id');

        if (!stateSelectID) { return; }

        const $stateSel = $('#' + stateSelectID);
        const state_id  = $stateSel.val() || 0;
        const cities = state_id ? await this.rpc('/get_form_cities', { state_id }) : {};
        const $citySel = $(map[stateSelectID]).empty();

        $citySel.append('<option value="">Municipio…</option>');
        $.each(cities, (id, name) => $citySel.append(new Option(name, id)));
    },
    _changeCountry:  function () {
        var selectStates = $("select[name='state']");
        var selectCountry = $("select[name='country']");
        selectStates.find("option").filter('[country-id!="' + selectCountry.val() + '"]').hide();
        var options = selectStates.find("option").filter('[country-id="' + selectCountry.val() + '"]');
        options.show()
        if (options.length > 0){
            selectStates.val(options[0].value).change();
        }else{}
    },
    _checkProducts() {
        var valid = true;
        var productRequired = document.getElementById("select2-productRequired-container");
        var productOnure = document.getElementById("select2-productOnure-container");
        var errorEnvolt = document.getElementById("error_envolt");
        var productError = document.getElementById("product-error");
            if (productRequired?.childElementCount === 0 && productOnure?.childElementCount === 0) { 
                valid = false;
            }
        // var x = document.getElementsByClassName("js-example-basic-multiple");
        // for (let i = 0; i < x.length; i++) {
        //     if (x[i].childElementCount === 0) { 
        //         valid = false;
        //     }
        // }
        
        if (errorEnvolt && productError) {
            if (valid) {
                errorEnvolt.style.border = "none";
                productError.style.display = "none";
            } else {
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
        this._checkProducts();
       
        if ($("#password").length > 0 && $("#confirm_password").length > 0) {
            if ($("#password").val() !== $("#confirm_password").val()) {
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
    validateForm: function(ev) {
        const billOfLandingField = document.getElementById('x_studio_bill_of_landing_number');
        if (billOfLandingField && billOfLandingField.value === "") {
            billOfLandingField.value = "0";
        }
        // This function deals with validation of the form fields
        var tabs, inputs, textAreas, i, valid = true;
        tabs = document.getElementsByClassName("tab");
        inputs = tabs[this.currentTab].getElementsByTagName("input");
        textAreas = tabs[this.currentTab].getElementsByTagName("textarea");

        valid = this._checkProducts();
        // for(const inputFileId of ['ficha_cliente']){
        //     this._validateFileType(inputFileId)
        //     console.log('valid2',valid2)
        // }
        // if(!valid2)
        //     valid = false

        const nationalClient = document.getElementById('acreditationis_client_nacional');
        const nationalProvider = document.getElementById('acreditationis_provider_nacional');
        const foreignClient = document.getElementById('acreditationis_client_extranjero');
        const foreignProvider = document.getElementById('acreditationis_provider_extranjero');

        const phone = document.querySelector('input[name="phone"]');
        const phoneError = document.getElementById("phone-error")
         if (phone && phoneError) {
            // If there is no radio button selected or it is a national client/provider
            if ((!nationalClient?.checked && !nationalProvider?.checked && !foreignClient?.checked && !foreignProvider?.checked) || (nationalClient?.checked || nationalProvider?.checked)) {
                if(!/^\+53\d{8}$/.test(phone.value)){
                    valid = false
                    phoneError.style.display = "block";
                    phoneError.style.margin = "10px 0px 10px";
                } else {
                    phoneError.style.display = "none";
                }
            } else {
                if(!/^\+\d{1,17}$/.test(phone.value)){
                    valid = false
                    phoneError.style.display = "block";
                    phoneError.style.margin = "10px 0px 10px";
                } else {
                    phoneError.style.display = "none";
                }
            }
        }
        const testEmail = /^[A-Z0-9._%+-]+@([A-Z0-9-]+\.)+[A-Z]{2,4}$/i;
        if (textAreas.length >=1){
            for (i = 0; i < textAreas.length; i++) {
                // If a field is empty...
                const array= ["productOnure","productRequired","x_studio_bill_of_landing_number","x_studio_certificate_of_origin_co","x_studio_bill_of_lading_bl","x_comercial_invoice","x_package_list","x_export_certify","x_quality_certify"];
                const valueToCheck = inputs[i].id;
                
                if (array.indexOf(valueToCheck) === -1 &&
                    ((inputs[i].value == "" && inputs[i].disabled == false) || 
                    (inputs[i].type == 'email' && inputs[i].disabled == false && !testEmail.test(inputs[i].value)) || 
                    inputs[i].className.indexOf('is-invalid') >= 0)) {
                    // add an "invalid" class to the field:

                    inputs[i].className += " is-invalid";
                    // and set the current valid status to false:
                    valid = false;
                }
            }
         }
        // A loop that checks every input field in the current tab:
        for (i = 0; i < inputs.length; i++) {
            // If a field is empty...
            const array= ["productOnure","productRequired","x_studio_bill_of_landing_number","x_studio_certificate_of_origin_co","x_studio_bill_of_lading_bl","x_comercial_invoice","x_package_list","x_export_certify","x_quality_certify"];
            const valueToCheck = inputs[i].id;
            if (array.indexOf(valueToCheck) === -1 &&((inputs[i].value == "" && inputs[i].disabled == false) ||(inputs[i].type == 'email' && inputs[i].disabled == false && !testEmail.test(inputs[i].value)) || inputs[i].className.indexOf('is-invalid') >= 0)){
                // add an "invalid" class to the field:
                inputs[i].className += " is-invalid";
                // and set the current valid status to false:
                valid = false;
            }
            if (inputs[i].id === 'nit' && inputs[i].disabled == false) {
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
        if (valid) {
            document.getElementsByClassName("step")[this.currentTab].className += " finish complete";
        }
        if (ev && !valid) {
            ev.preventDefault();
            ev.stopImmediatePropagation();
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