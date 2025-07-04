const sbToggle = document.querySelector('#sidebar-toggle');
sbToggle.addEventListener('click', function() {
    document.querySelector('#sidebar').classList.toggle('collapsed');
});

document.querySelector('.theme-toggle').addEventListener('click', () => {
    toggleLocalStorage();
    toggleRootClass();    
});

function toggleRootClass() {
    const current = document.documentElement.getAttribute('data-bs-theme'); // Fix attribute name
    const inverted = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-bs-theme', inverted);
}

function toggleLocalStorage() {
    if (isLight()) {
        localStorage.removeItem('light');
    } else {
        localStorage.setItem('light', 'set');
    }
}

function isLight() {
    return localStorage.getItem('light');
}

if (isLight()) {
    toggleRootClass(); // Add parentheses to execute the function
}