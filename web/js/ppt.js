// ============================================================
// NPC-DynaSurv — PPT Patient Risk Dashboard Logic
// ============================================================

let chart = null;
let patientId = null;
let currentVisitId = null;
let trajectoryData = [];

// Get patient ID from URL: /ppt/<id>
const pathMatch = window.location.pathname.match(/\/ppt\/(\d+)/);
patientId = pathMatch ? parseInt(pathMatch[1]) : null;

// ---------- Init ----------
document.addEventListener('DOMContentLoaded', async () => {
    if (!patientId) {
        alert('无效的患者 ID');
        window.location.href = '/dashboard';
        return;
    }
    await loadInitialData();
});

async function loadInitialData() {
    // Load visit list first
    try {
        const visitsRes = await fetch(`/api/patients/${patientId}/visits`);
        if (!visitsRes.ok) { window.location.href = '/dashboard'; return; }
        const visitsData = await visitsRes.json();

        if (!visitsData.visits.length) {
            alert('该患者无随访记录');
            window.location.href = '/dashboard';
            return;
        }

        // Populate visit dropdown and sidebar
        populateVisitList(visitsData.visits);

        // Load latest visit detail
        const latestVisit = visitsData.visits[visitsData.visits.length - 1];
        currentVisitId = latestVisit.id;
        document.getElementById('visit-selector').value = currentVisitId;
        highlightSidebarVisit(currentVisitId);

        await loadVisitDetail(currentVisitId);
    } catch (e) {
        console.error('Failed to load data:', e);
    }
}

// ---------- Visit List ----------
function populateVisitList(visits) {
    // Dropdown
    const selector = document.getElementById('visit-selector');
    selector.innerHTML = visits.map(v =>
        `<option value="${v.id}">Follow-up Visit: ${v.label}</option>`
    ).join('');
    selector.value = currentVisitId;

    // Sidebar list
    const list = document.getElementById('followup-list');
    list.innerHTML = visits.map(v =>
        `<li id="fv-${v.id}" onclick="onSidebarVisitClick(${v.id})" class="${v.id === currentVisitId ? 'active' : ''}">
            ${v.label}
        </li>`
    ).join('');
}

function highlightSidebarVisit(visitId) {
    document.querySelectorAll('.followup-list li').forEach(li => li.classList.remove('active'));
    const target = document.getElementById(`fv-${visitId}`);
    if (target) {
        target.classList.add('active');
        target.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
}

// ---------- Visit Selection ----------
function onVisitSelect(visitId) {
    if (!visitId || parseInt(visitId) === currentVisitId) return;
    currentVisitId = parseInt(visitId);
    highlightSidebarVisit(currentVisitId);
    loadVisitDetail(currentVisitId);
}

function onSidebarVisitClick(visitId) {
    if (visitId === currentVisitId) return;
    currentVisitId = visitId;
    document.getElementById('visit-selector').value = visitId;
    highlightSidebarVisit(visitId);
    loadVisitDetail(visitId);
}

// ---------- Load Visit Detail ----------
async function loadVisitDetail(visitId) {
    try {
        const res = await fetch(`/api/patients/${patientId}/visit/${visitId}`);
        if (!res.ok) { throw new Error('Failed to load visit'); }
        const data = await res.json();

        // Update patient profile
        updateProfile(data.patient);

        // Update navbar
        document.getElementById('navbar-patient-id').textContent =
            `Patient ID: ${data.patient.patient_id}`;

        // Store trajectory data
        trajectoryData = data.trajectory || [];

        // Render chart
        renderChart(data.trajectory || [], visitId);

        // Update risk assessment
        updateRiskAssessment(data.risk_assessment);

        // Update AI recommendation
        updateAIRecommendation(data.ai_recommendation);
    } catch (e) {
        console.error('Failed to load visit detail:', e);
    }
}

// ---------- Update Profile ----------
function updateProfile(patient) {
    document.getElementById('prof-name').textContent = patient.name || '[Anonymized]';
    document.getElementById('prof-sex').textContent = patient.sex || '-';
    document.getElementById('prof-age').textContent = patient.age ? `${patient.age} years` : '-';
    document.getElementById('prof-t').textContent = patient.t_stage || '-';
    document.getElementById('prof-n').textContent = patient.n_stage || '-';
    document.getElementById('prof-m').textContent = patient.m_stage || '-';
    document.getElementById('prof-stage').textContent = patient.overall_stage || '-';
    document.getElementById('prof-treatment').textContent = patient.treatment || '-';
    document.getElementById('prof-end').textContent = patient.treatment_end || '-';
}

// ---------- Chart Rendering ----------
function renderChart(trajectory, currentVisitId) {
    const ctx = document.getElementById('trajectory-chart').getContext('2d');

    if (chart) { chart.destroy(); }

    if (!trajectory.length) {
        chart = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets: [] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: { display: true, text: '暂无轨迹数据', color: '#999' }
                }
            }
        });
        return;
    }

    // Sort by months
    trajectory.sort((a, b) => a.months - b.months);

    const labels = trajectory.map(t => `${t.months}`);
    const dfsData = trajectory.map(t => t.dfs);
    const dmfsData = trajectory.map(t => t.dmfs);
    const lrrfsData = trajectory.map(t => t.lrrfs);
    const osData = trajectory.map(t => t.os);

    // Current visit = latest
    const maxVisitNum = Math.max(...trajectory.map(t => t.visit_number));
    const activeIdx = trajectory.findIndex(t => t.visit_number === maxVisitNum);

    // Distinct colors for 4 lines
    const COLORS = {
        dfs:   { line: '#2563EB', fill: '#2563EB' },  // 蓝
        dmfs:  { line: '#F59E0B', fill: '#F59E0B' },  // 琥珀
        lrrfs: { line: '#10B981', fill: '#10B981' },  // 翠绿
        os:    { line: '#EF4444', fill: '#EF4444' },  // 红
    };

    function makeDataset(label, data, color) {
        const lastIdx = data.length - 1;
        return {
            label: label,
            data: data,
            borderColor: color.line,
            backgroundColor: color.fill,
            borderWidth: 3,
            tension: 0.35,
            // 所有点可见
            pointBackgroundColor: data.map((_, i) => i === activeIdx ? color.fill : color.fill),
            pointBorderColor: data.map((_, i) => i === activeIdx ? '#000' : color.line),
            pointRadius: data.map((_, i) => {
                if (i === activeIdx) return 8;  // 当前节点大圆点
                return 4;                       // 其余统一大小
            }),
            pointBorderWidth: data.map((_, i) => i === activeIdx ? 2 : 1),
            pointHoverRadius: 9,
            order: 0,
        };
    }

    const datasets = [
        makeDataset('DFS',   dfsData,   COLORS.dfs),
        makeDataset('DMFS',  dmfsData,  COLORS.dmfs),
        makeDataset('LRRFS', lrrfsData, COLORS.lrrfs),
        makeDataset('OS',    osData,    COLORS.os),
        // Threshold lines
        {
            label: 'Moderate/High threshold (15%)',
            data: labels.map(() => 15),
            borderColor: '#9CA3AF',
            borderWidth: 1.5,
            borderDash: [8, 5],
            pointRadius: 0,
            pointHoverRadius: 0,
            fill: false,
            tension: 0,
            order: 1,
        },
        {
            label: 'Low/Moderate threshold (5%)',
            data: labels.map(() => 5),
            borderColor: '#9CA3AF',
            borderWidth: 1.5,
            borderDash: [8, 5],
            pointRadius: 0,
            pointHoverRadius: 0,
            fill: false,
            tension: 0,
            order: 1,
        },
    ];

    chart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => `治疗后 ${items[0].label} 个月`,
                        label: (item) => {
                            if (item.datasetIndex >= 4) return item.dataset.label;
                            return `${item.dataset.label}: ${item.raw}%`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: 'Months since treatment', color: '#666', font: { size: 12 } },
                    ticks: { color: '#888', font: { size: 11 } },
                    grid: { color: '#f0f0f0' },
                },
                y: {
                    title: { display: true, text: '12-month conditional risk (%)', color: '#666', font: { size: 12 } },
                    min: 0,
                    max: Math.max(30, Math.ceil(Math.max(...dfsData, ...dmfsData, ...lrrfsData, ...osData) / 5) * 5 + 5),
                    ticks: { stepSize: 5, color: '#888', font: { size: 11 }, callback: (val) => val + '%' },
                    grid: { color: '#f0f0f0' },
                },
            },
        },
    });
}

// ---------- Update Risk Assessment ----------
function updateRiskAssessment(risk) {
    if (!risk) {
        document.getElementById('risk-dfs').textContent = '---';
        document.getElementById('risk-dmfs').textContent = '---';
        document.getElementById('risk-lrrfs').textContent = '---';
        document.getElementById('risk-os').textContent = '---';
        document.getElementById('risk-dominant').textContent = '---';
        document.getElementById('risk-interval').textContent = '---';
        return;
    }

    document.getElementById('risk-dfs').textContent = risk.dfs != null ? risk.dfs + '%' : '---';
    document.getElementById('risk-dmfs').textContent = risk.dmfs != null ? risk.dmfs + '%' : '---';
    document.getElementById('risk-lrrfs').textContent = risk.lrrfs != null ? risk.lrrfs + '%' : '---';
    document.getElementById('risk-os').textContent = risk.os != null ? risk.os + '%' : '---';

    // Risk level tag — 匹配规则引擎层级一（只改标签颜色，数字不变）
    const dfs = risk.dfs || 0;
    const dfsTag = document.getElementById('risk-dfs-tag');

    if (dfs >= 30) {
        dfsTag.textContent = 'Very High Risk';
        dfsTag.className = 'risk-tag veryhigh';
        dfsTag.style.display = 'inline-block';
    } else if (dfs >= 15) {
        dfsTag.textContent = 'High Risk';
        dfsTag.className = 'risk-tag high';
        dfsTag.style.display = 'inline-block';
    } else if (dfs >= 5) {
        dfsTag.textContent = 'Moderate Risk';
        dfsTag.className = 'risk-tag moderate';
        dfsTag.style.display = 'inline-block';
    } else {
        dfsTag.textContent = 'Low Risk';
        dfsTag.className = 'risk-tag normal';
        dfsTag.style.display = 'inline-block';
    }

    document.getElementById('risk-dominant').textContent = risk.dominant_risk_type || '---';
    document.getElementById('risk-interval').textContent = risk.recommended_interval || '---';
}

// ---------- Update AI Recommendation ----------
function updateAIRecommendation(ai) {
    const container = document.getElementById('ai-content');

    if (!ai) {
        container.innerHTML = '<p style="color:#999;font-size:13px;">暂无 AI 建议数据</p>';
        return;
    }

    // If LLM generated advice, display it as formatted text
    if (ai.has_llm_advice && ai.raw_advice) {
        // Convert markdown-ish text to HTML
        const html = ai.raw_advice
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/^### (.+)$/gm, '<h4 style="margin:12px 0 6px;color:#1B3A5C;">$1</h4>')
            .replace(/^## (.+)$/gm, '<h3 style="margin:14px 0 8px;color:#1B3A5C;">$1</h3>')
            .replace(/^# (.+)$/gm, '<h2 style="margin:16px 0 8px;color:#1B3A5C;">$1</h2>')
            .replace(/^- (.+)$/gm, '<li>$1</li>')
            .replace(/(<li>.*<\/li>\n?)+/g, '<ul style="margin:6px 0 6px 20px;font-size:13px;">$&</ul>')
            .replace(/\n\n/g, '<br><br>')
            .replace(/\n/g, '<br>');

        container.innerHTML = `
            <div class="ai-section" style="max-height:350px;overflow-y:auto;font-size:13px;line-height:1.7;color:#444;">
                ${html}
            </div>
            <div style="margin-top:12px;padding-top:8px;border-top:1px solid #eee;">
                <button class="btn btn-outline btn-sm" onclick="generateAdvice()" id="btn-generate">
                    🤖 重新生成 AI 建议
                </button>
                <span style="font-size:11px;color:#999;margin-left:8px;">由 Qwen3-8B + 规则引擎 6.24 生成</span>
            </div>`;
        return;
    }

    // Rule-based structured display
    let examsHtml = '';
    if (ai.examinations && ai.examinations.length) {
        examsHtml = '<ul class="ai-exam-list">' +
            ai.examinations.map(e => `<li>${e}</li>`).join('') +
            '</ul>';
    }

    let riskInfoHtml = '';
    if (ai.risk_level) {
        riskInfoHtml = `
            <div style="margin-left:30px;font-size:13px;color:#555;margin-bottom:8px;">
                <strong>Risk Level:</strong> ${ai.risk_level} &nbsp;|&nbsp;
                <strong>Dominant:</strong> ${ai.dominant_risk || '---'}
            </div>`;
    }

    let alertHtml = '';
    if (ai.health_alert_content) {
        alertHtml = `
            <div class="health-alert">
                <span class="alert-icon">⚠️</span>
                <span>${ai.health_alert_content}</span>
            </div>`;
    }

    container.innerHTML = `
        <div class="ai-section">
            <div class="ai-title">
                <span class="ai-num">1</span> Recommended Interval
            </div>
            <div class="ai-content">${ai.next_visit || '---'}</div>
            ${riskInfoHtml}
        </div>
        <div class="ai-section">
            <div class="ai-title">
                <span class="ai-num">2</span> Recommended Examinations
            </div>
            ${examsHtml || '<div class="ai-content">---</div>'}
        </div>
        <div class="ai-section">
            <div class="ai-title">
                <span class="ai-num">3</span> Health Alert
            </div>
            ${alertHtml || '<div class="ai-content" style="color:#999;">No alerts at this time</div>'}
        </div>
        <div style="margin-top:12px;padding-top:8px;border-top:1px solid #eee;">
            <button class="btn btn-outline btn-sm" onclick="generateAdvice()" id="btn-generate">
                🤖 生成 AI 建议
            </button>
            <span style="font-size:11px;color:#999;margin-left:8px;">调用 Qwen3-8B + 规则引擎 6.24</span>
        </div>`;
}

// ---------- Generate AI Advice ----------
async function generateAdvice() {
    const btn = document.getElementById('btn-generate');
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = '⏳ 生成中...';

    try {
        const res = await fetch(`/api/patients/${patientId}/visit/${currentVisitId}/generate-advice`, {
            method: 'POST',
        });
        const data = await res.json();
        // Reload current visit detail to get updated AI advice
        await loadVisitDetail(currentVisitId);
    } catch (e) {
        alert('AI 建议生成失败: ' + e.message);
        btn.disabled = false;
        btn.textContent = '🤖 生成 AI 建议';
    }
}

// ---------- Navigation ----------
function goBack() {
    window.location.href = '/dashboard';
}
