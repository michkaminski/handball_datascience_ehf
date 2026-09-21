document.addEventListener("DOMContentLoaded", () => {
    const przyciskMenu = document.querySelector("[data-mobile-menu]");
    const pasekBoczny = document.querySelector(".sidebar");
    if (przyciskMenu && pasekBoczny) {
        przyciskMenu.addEventListener("click", () => {
            pasekBoczny.style.display = pasekBoczny.style.display === "block" ? "none" : "block";
        });
    }
});
