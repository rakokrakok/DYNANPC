// ============================================================
// NPC-DynaSurv — Auth Logic (Login / Register)
// ============================================================

function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '隐藏';
    } else {
        input.type = 'password';
        btn.textContent = '显示';
    }
}

function switchTab(tab) {
    document.getElementById('tab-login').classList.toggle('active', tab === 'login');
    document.getElementById('tab-register').classList.toggle('active', tab === 'register');
    document.getElementById('login-form').classList.toggle('active', tab === 'login');
    document.getElementById('register-form').classList.toggle('active', tab === 'register');

    // Clear errors
    document.getElementById('login-error').style.display = 'none';
    document.getElementById('register-error').style.display = 'none';
    document.getElementById('register-success').style.display = 'none';
}

async function handleLogin(e) {
    e.preventDefault();
    const errEl = document.getElementById('login-error');
    errEl.style.display = 'none';

    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        const data = await res.json();
        if (!res.ok) {
            errEl.textContent = data.error || '登录失败';
            errEl.style.display = 'block';
            return;
        }
        window.location.href = '/dashboard';
    } catch (err) {
        errEl.textContent = '网络错误，请检查服务器连接';
        errEl.style.display = 'block';
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const errEl = document.getElementById('register-error');
    const okEl = document.getElementById('register-success');
    errEl.style.display = 'none';
    okEl.style.display = 'none';

    const payload = {
        username: document.getElementById('reg-username').value.trim(),
        email: document.getElementById('reg-email').value.trim(),
        password: document.getElementById('reg-password').value,
        full_name: document.getElementById('reg-fullname').value.trim(),
        department: document.getElementById('reg-department').value.trim(),
        hospital: document.getElementById('reg-hospital').value.trim(),
    };

    try {
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) {
            errEl.textContent = data.error || '注册失败';
            errEl.style.display = 'block';
            return;
        }
        okEl.textContent = '注册成功！正在跳转...';
        okEl.style.display = 'block';
        setTimeout(() => { window.location.href = '/dashboard'; }, 800);
    } catch (err) {
        errEl.textContent = '网络错误，请检查服务器连接';
        errEl.style.display = 'block';
    }
}
