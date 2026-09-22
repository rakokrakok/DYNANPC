// ============================================================
// NPC-DynaSurv — Dashboard Logic
// ============================================================

let selectedFile = null;

document.addEventListener('DOMContentLoaded', () => {
    loadDoctorInfo();
    loadPatients();
    setupDragDrop();
});

async function loadDoctorInfo() {
    try {
        const res = await fetch('/api/me');
        if (!res.ok) { window.location.href = '/'; return; }
        const data = await res.json();
        const d = data.doctor;
        document.getElementById('sidebar-name').textContent = d.full_name;
        document.getElementById('sidebar-dept').textContent = d.department || '未设置科室';
        document.getElementById('sidebar-hospital').textContent = d.hospital || '';
    } catch (e) {
        console.error('Failed to load doctor info:', e);
    }
}

async function loadPatients() {
    const container = document.getElementById('patient-list');

    try {
        const res = await fetch('/api/patients');
        if (!res.ok) { window.location.href = '/'; return; }
        const data = await res.json();

        if (!data.patients.length) {
            container.innerHTML = `
                <div class="empty-state" style="grid-column:1/-1;">
                    <div class="icon">📋</div>
                    <p>暂无患者记录</p>
                    <p style="font-size:13px;margin-bottom:16px;">点击「加载示例患者」载入默认病例</p>
                </div>`;
            return;
        }

        container.innerHTML = data.patients.map(p => `
            <div class="patient-card">
                <div onclick="location.href='/ppt/${p.id}'" style="flex:1;">
                    <div class="card-id">🆔 ${p.patient_id}</div>
                    <div class="card-name">${p.name}</div>
                    <div class="card-meta">
                        <span>${p.sex || '-'}</span>
                        <span>Age ${p.age || '-'}</span>
                        <span>Stage ${p.overall_stage || '-'}</span>
                        <span>${p.treatment || '-'}</span>
                    </div>
                    <div style="margin-top:10px;font-size:12px;color:#aaa;">
                        录入时间：${new Date(p.created_at).toLocaleDateString('zh-CN')}
                    </div>
                </div>
                <button class="btn btn-sm" style="color:#e74c3c;background:none;border:none;cursor:pointer;font-size:20px;padding:0 4px;"
                    onclick="event.stopPropagation();deletePatient(${p.id})" title="删除患者">🗑</button>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = '<div class="empty-state" style="grid-column:1/-1;"><p>加载失败，请刷新页面</p></div>';
    }
}

// ---------- Upload ----------
function openUploadModal() {
    document.getElementById('upload-modal').classList.add('active');
    document.getElementById('upload-error').style.display = 'none';
    document.getElementById('upload-filename').textContent = '';
    document.getElementById('upload-btn').disabled = true;
    selectedFile = null;
    document.getElementById('file-input').value = '';
    document.getElementById('upload-text').textContent = '拖拽文件到此处上传';
}

function closeUploadModal() {
    document.getElementById('upload-modal').classList.remove('active');
}

function onFileSelected(event) {
    const file = event.target.files[0];
    if (file) {
        selectedFile = file;
        document.getElementById('upload-filename').textContent = '📎 ' + file.name;
        document.getElementById('upload-btn').disabled = false;
    }
}

function setupDragDrop() {
    const dropArea = document.getElementById('drop-area');
    if (!dropArea) return;
    dropArea.addEventListener('dragover', (e) => { e.preventDefault(); dropArea.style.borderColor = '#1B3A5C'; dropArea.style.background = '#F0F4F8'; });
    dropArea.addEventListener('dragleave', () => { dropArea.style.borderColor = '#ccc'; dropArea.style.background = ''; });
    dropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dropArea.style.borderColor = '#ccc';
        dropArea.style.background = '';
        const file = e.dataTransfer.files[0];
        if (file) {
            selectedFile = file;
            document.getElementById('upload-filename').textContent = '📎 ' + file.name;
            document.getElementById('upload-btn').disabled = false;
            document.getElementById('upload-text').textContent = '已选择文件';
        }
    });
}

async function handleUpload() {
    if (!selectedFile) return;
    const btn = document.getElementById('upload-btn');
    const errEl = document.getElementById('upload-error');
    btn.disabled = true;
    btn.textContent = '上传中...';
    errEl.style.display = 'none';

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
        const res = await fetch('/api/patients/upload', {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();
        if (!res.ok) {
            errEl.textContent = data.error || '上传失败';
            errEl.style.display = 'block';
            btn.disabled = false;
            btn.textContent = '上传并导入';
            return;
        }
        window.location.href = data.redirect;
    } catch (e) {
        errEl.textContent = '网络错误，请重试';
        errEl.style.display = 'block';
        btn.disabled = false;
        btn.textContent = '上传并导入';
    }
}

// ---------- Profile ----------
function showProfile() {
    fetch('/api/me')
        .then(r => r.json())
        .then(data => {
            const d = data.doctor;
            document.getElementById('profile-content').innerHTML = `
                <table class="profile-table">
                    <tr><td>用户名</td><td>${d.username}</td></tr>
                    <tr><td>邮箱</td><td>${d.email}</td></tr>
                    <tr><td>姓名</td><td>${d.full_name}</td></tr>
                    <tr><td>科室</td><td>${d.department || '-'}</td></tr>
                    <tr><td>医院</td><td>${d.hospital || '-'}</td></tr>
                    <tr><td>注册时间</td><td>${new Date(d.created_at).toLocaleString('zh-CN')}</td></tr>
                </table>`;
            document.getElementById('profile-modal').classList.add('active');
        });
}

function closeProfile() {
    document.getElementById('profile-modal').classList.remove('active');
}

async function deletePatient(patientId) {
    if (!confirm('确认删除该患者及所有随访记录？')) return;
    try {
        const res = await fetch(`/api/patients/${patientId}`, { method: 'DELETE' });
        const data = await res.json();
        if (!res.ok) { alert(data.error); return; }
        loadPatients();
    } catch (e) { alert('网络错误'); }
}

async function handleLogout() {
    await fetch('/api/logout', { method: 'POST' });
    window.location.href = '/';
}
