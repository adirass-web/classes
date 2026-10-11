(function () {
    function setDirection() {
        document.querySelectorAll('.cyber-acq input[type="text"], .cyber-acq textarea')
            .forEach(function (element) { element.setAttribute('dir', 'auto'); });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setDirection, { once: true });
    } else { setDirection(); }
})();
