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
        'change #hiddenTestInput': '_updateSessionProducts',
        'select2:select #productRequired': '_updateSessionProducts',
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
        return def;
    },
    async _onchangeFile(ev) {
        if(ev?.target?.id)
            this._validateFileType(ev.target.id)
    },
    async _validateFileType(inputFileId) {
        const fileInput = document.getElementById(inputFileId);

        if(fileInput?.files?.length > 0){
            let valid = true
            for (const file of fileInput.files) {
                const file_type = file.type
                const errorElement = document.getElementById(`${inputFileId}_error`);
                const fileDownloadLink = document.querySelector(`div[name='${inputFileId}_input_group'] a:not(d-none)`)
                valid = await this.rpc('/check_file_type', { config_param: fileDownloadLink.id, file_type});
                
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
                        return false
                    }
                }
            }
            return valid
        }
    },
    _checkProducts() {
        var valid = true;
        var productRequired = document.querySelector("#s2id_productRequired ul");
        var errorEnvolt = document.getElementById("error_envolt");
        var productError = document.getElementById("product-error");
        if (productRequired?.childElementCount === 1) { 
            valid = false;
        }
        
        if (errorEnvolt && productError) {
            if (valid) {
                errorEnvolt.style.border = "none";
                errorEnvolt.style.padding = "0px 0px 0px";
                productError.style.display = "none";
                productError.style.margin = "0px 0px 0px";
            } else {
                errorEnvolt.style.border = "1px solid red";
                errorEnvolt.style.padding = "10px 10px 0px";
                productError.style.display = "block";
                productError.style.margin = "10px 0px 10px";
            }
        }
        return valid;
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
    validateForm: function(ev) {
        // This function deals with validation of the form fields
        var tabs, inputs, i, valid = true;
        tabs = document.getElementsByClassName("tab");
        inputs = tabs[this.currentTab].getElementsByTagName("input");

        valid = this._checkProducts();
        if(!this._validateFileType('legal_documentation'))
            valid = false

        // A loop that checks every input field in the current tab:
        for (i = 0; i < inputs.length; i++) {
            // If a field is empty...
            const array= ["productRequired"];
            const valueToCheck = inputs[i].id;
            if (array.indexOf(valueToCheck) === -1 &&((inputs[i].required && inputs[i].value == "" && inputs[i].disabled == false) || inputs[i].className.indexOf('is-invalid') >= 0)){
                // add an "invalid" class to the field:
                inputs[i].className += " is-invalid";
                // and set the current valid status to false:
                valid = false;
            }
        }
        if (ev && !valid) {
            ev.preventDefault();
            ev.stopImmediatePropagation();
        }

        return valid; // return the valid status
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
});
publicWidget.registry.ImportRegistrationForm = ImportRegistrationForm;