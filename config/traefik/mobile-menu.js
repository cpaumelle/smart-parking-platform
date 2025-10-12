// Mobile Menu Toggle Script
(function() {
    function initMobileMenu() {
        // Create hamburger button
        const menuButton = document.createElement("button");
        menuButton.className = "mobile-menu-toggle";
        menuButton.innerHTML = "<span></span><span></span><span></span>";
        menuButton.setAttribute("aria-label", "Toggle menu");
        
        // Create overlay
        const overlay = document.createElement("div");
        overlay.className = "sidebar-overlay";
        
        document.body.appendChild(menuButton);
        document.body.appendChild(overlay);
        
        // Toggle function
        function toggleMenu() {
            const sidebar = document.querySelector(".ant-layout-sider");
            if (sidebar) {
                sidebar.classList.toggle("mobile-menu-open");
                menuButton.classList.toggle("active");
                overlay.classList.toggle("active");
            }
        }
        
        // Event listeners
        menuButton.addEventListener("click", toggleMenu);
        overlay.addEventListener("click", toggleMenu);
        
        // Close menu when clicking menu items
        document.addEventListener("click", function(e) {
            if (e.target.closest(".ant-menu-item")) {
                const sidebar = document.querySelector(".ant-layout-sider");
                if (sidebar && sidebar.classList.contains("mobile-menu-open")) {
                    toggleMenu();
                }
            }
        });
    }
    
    // Wait for React to render
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function() {
            setTimeout(initMobileMenu, 500);
        });
    } else {
        setTimeout(initMobileMenu, 500);
    }
})();
