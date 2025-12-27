let currentPage = 1;
let enhancedEnabled = true;

const page1Continue = document.getElementById('page1Continue');
const page2Continue = document.getElementById('page2Continue');
const page2Back = document.getElementById('page2Back');
const page3Back = document.getElementById('page3Back');
const propertyNameInput = document.getElementById('propertyName');
const enhancedToggle = document.getElementById('enhancedToggle');
const copyBtn = document.getElementById('copyBtn');
const clearUrlBtn = document.getElementById('clearUrlBtn');
const testUrlInput = document.getElementById('testUrl');
const tabBuilder = document.getElementById('tabBuilder');
const tabManual = document.getElementById('tabManual');

function showPage(pageNum) {
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    document.getElementById('page' + pageNum).classList.add('active');

    const step1Circle = document.getElementById('step1Circle');
    const step1Label = document.getElementById('step1Label');
    const step2Circle = document.getElementById('step2Circle');
    const step2Label = document.getElementById('step2Label');

    if (pageNum >= 2) {
        step1Circle.classList.remove('active');
        step1Circle.classList.add('inactive');
        step1Label.classList.remove('active');
        step1Label.classList.add('inactive');
        step2Circle.classList.remove('inactive');
        step2Circle.classList.add('active');
        step2Label.classList.remove('inactive');
        step2Label.classList.add('active');
    } else {
        step1Circle.classList.remove('inactive');
        step1Circle.classList.add('active');
        step1Label.classList.remove('inactive');
        step1Label.classList.add('active');
        step2Circle.classList.remove('active');
        step2Circle.classList.add('inactive');
        step2Label.classList.remove('active');
        step2Label.classList.add('inactive');
    }

    currentPage = pageNum;
}

function validatePropertyName() {
    const value = propertyNameInput.value.trim();
    if (value) {
        page1Continue.disabled = false;
    } else {
        page1Continue.disabled = true;
    }
}

propertyNameInput.addEventListener('input', validatePropertyName);
validatePropertyName();

page1Continue.addEventListener('click', function() {
    if (propertyNameInput.value.trim()) {
        showPage(2);
    }
});

page2Continue.addEventListener('click', function() {
    showPage(3);
});

page2Back.addEventListener('click', function() {
    showPage(1);
});

page3Back.addEventListener('click', function() {
    showPage(2);
});

enhancedToggle.addEventListener('click', function() {
    enhancedEnabled = !enhancedEnabled;
    if (enhancedEnabled) {
        enhancedToggle.classList.add('active');
    } else {
        enhancedToggle.classList.remove('active');
    }
});

copyBtn.addEventListener('click', function() {
    const codeText = document.querySelector('.code-block').textContent;
    navigator.clipboard.writeText(codeText).then(function() {
        copyBtn.innerHTML = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>';
        copyBtn.style.color = '#10b981';
        setTimeout(function() {
            copyBtn.innerHTML = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
            copyBtn.style.color = '';
        }, 2000);
    });
});

clearUrlBtn.addEventListener('click', function() {
    testUrlInput.value = '';
});

tabBuilder.addEventListener('click', function() {
    tabManual.classList.remove('active');
    tabBuilder.classList.add('active');
});

tabManual.addEventListener('click', function() {
    tabBuilder.classList.remove('active');
    tabManual.classList.add('active');
});