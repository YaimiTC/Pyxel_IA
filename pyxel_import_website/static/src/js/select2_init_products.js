(function ($) {
    $(document).ready(function () {

        console.log("✅ jQuery version:", $.fn.jquery);
        const $selector = $('#productRequired');

        $selector.select2({
            width: '50%',
            placeholder: "Seleccione los productos",
            language: {
                noResults: function () {
                    let message = '¡No pudimos encontrar ninguna coincidencia! Para más detalles, ';

                    let div = document.createElement('div');
                    div.textContent = message;

                    let mailLink = document.createElement('a');
                    mailLink.href = 'mailto:comercial@importadora.com';
                    mailLink.textContent = 'contacte con nuestro equipo comercial.';

                    div.appendChild(mailLink);

                    return div;
                }
            },
        });
        let alimentosDeImportacion = JSON.parse($selector.attr("data-alimentos") || "[]");
        let selectedProducts = JSON.parse($selector.attr("data-alimentos-selected") || "[]");

        // Función para cargar las opciones en el select
        function loadSelect2Options(products, selectedProducts) {
            $selector.empty(); // Limpiar las opciones existentes
            products.forEach(function (product) {

                let isSelected = selectedProducts.includes(parseInt(product.id));
                let newOption = new Option(product.name, product.id, isSelected, isSelected);
                $selector.append(newOption);
            });
            $selector.trigger('change');
            // Notificar a select2 de los cambios
        }

        loadSelect2Options(alimentosDeImportacion, selectedProducts);
        console.log("Sincronización de productos de importación lista");

        // Aplicar los estilos del select2 cuando se abre/cierra
        $selector.on('select2:open', function () {
            $('.select2-selection').addClass('custom-select-focus');
        });

        $selector.on('select2:close', function () {
            $('.select2-selection').removeClass('custom-select-focus');
        });

        $selector.on('select2:select select2:unselect', function () {
            $('#hiddenTestInput').trigger("change");
        });

        console.log("Select dinámico de productos de importación cargado exitosamente");

        $('.select2-container--default .select2-selection--multiple').css({
            'border': '1px solid rgba(0,0,0,0.15)',
            'font-size': '1rem',
            'padding': '0.375rem 0.75rem',
            'line-height': '1.5',
            'background-color': '#FFFFFF',

        });
        $('.select2-search').css({
            'padding': '0',

        });
        $selector.on('select2:open', function () {
            $('.select2-selection').addClass('custom-select-focus');
        });

        $selector.on('select2:close', function () {
            $('.select2-selection').removeClass('custom-select-focus');
        });

        console.log("SELECT2 INIT PRODUCTS JS OK 200")
    });
})(jQuery);