(function ($) {
  $(function () {

    // Sombra sticky al hacer scroll
    var $stickyWrap = $('#cx-sticky-wrap');
    if ($stickyWrap.length) {
      $(window).on('scroll.cxSticky', function () {
        if ($(this).scrollTop() > 10) {
          $stickyWrap.addClass('cx-scrolled');
        } else {
          $stickyWrap.removeClass('cx-scrolled');
        }
      });
    }


    let $tabs = $('#aboutTabs .nav-link');

    // Helper function to scroll a tab element into view(centered)
    function scrollToCenter($element, containerSelector = '.custom-tabs') {
      const $container = $(containerSelector);
      if (!$element.length || !$container.length) return;

      const container = $container[0];
      const element = $element[0];

      const containerRect = container.getBoundingClientRect();
      const elementRect = element.getBoundingClientRect();

      // Calculate how far to scroll so the element is centered
      const scrollLeft = elementRect.left - containerRect.left + container.scrollLeft - containerRect.width / 2 + elementRect.width / 2;

      // Use smooth native scroll if supported
      if ('scrollTo' in container) {
        container.scrollTo({
          left: scrollLeft,
          behavior: 'smooth'
        });
      } else {
        // Fallback for older browsers
        $(container).animate({ scrollLeft: scrollLeft }, 300);
      }
    }

    function ensureTabVisible($navItem) {
      if (window.innerWidth <= 768) {
        setTimeout(() => scrollToCenter($navItem), 50);
      }
    }

    function activateTabById(tabId) {
      let $tab = $tabs.filter('[href="#' + tabId + '"]');
      if ($tab.length) {
        $tab.tab('show');
        // Scroll the tab into view (centered) on small screens
        ensureTabVisible($tab.closest('.nav-item'));
      }
    }

    // Handle ?tab=faq OR #faq
    let urlParams = new URLSearchParams(window.location.search);
    let queryTab = urlParams.get('tab');
    let hashTab = window.location.hash.substring(1);

    if (queryTab) {
      activateTabById(queryTab);
    } else if (hashTab) {
      activateTabById(hashTab);
    }

    // Existing prev/next logic …
    function activateTab(index) {
      if (!$tabs.length) return;
      index = ((index % $tabs.length) + $tabs.length) % $tabs.length;

      const $targetTab = $tabs.eq(index);
      $targetTab.tab('show');

      // Scroll the tab into view (centered) on small screens
      ensureTabVisible($targetTab.closest('.nav-item'));
    }

    $('#aboutTabs .nav-link').on('click', function () {
      ensureTabVisible($(this).closest('.nav-item'));
    });

    $('#tabPrev').on('click', function () {
      let current = $tabs.index($('#aboutTabs .nav-link.active'));
      if (current < 0) current = 0;
      activateTab(current - 1);
    });

    $('#tabNext').on('click', function () {
      let current = $tabs.index($('#aboutTabs .nav-link.active'));
      if (current < 0) current = 0;
      activateTab(current + 1);
    });
  });
})(jQuery);

(function () {
    function initWhatsAppWidget() {
        var widget = document.getElementById('cxWaWidget');
        if (!widget) return;
        var toggle = document.getElementById('cxWaToggle');
        var closeBtn = document.getElementById('cxWaClose');
        var number = widget.getAttribute('data-number') || '5355555555';

        function open() { widget.classList.add('cx-wa-open'); toggle.classList.add('cx-wa-active'); }
        function close() { widget.classList.remove('cx-wa-open'); toggle.classList.remove('cx-wa-active'); }
        function isOpen() { return widget.classList.contains('cx-wa-open'); }

        toggle.addEventListener('click', function (e) {
            e.stopPropagation();
            if (isOpen()) close(); else open();
        });

        closeBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            close();
        });

        widget.querySelectorAll('.cx-wa-question').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var msg = btn.getAttribute('data-msg') || '';
                var url = 'https://wa.me/' + number + '?text=' + encodeURIComponent(msg);
                window.open(url, '_blank', 'noopener');
                close();
            });
        });

        document.addEventListener('click', function (e) {
            if (!isOpen()) return;
            if (!widget.contains(e.target)) close();
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && isOpen()) close();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWhatsAppWidget);
    } else {
        initWhatsAppWidget();
    }
})();
