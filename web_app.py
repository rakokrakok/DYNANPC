# -*- coding: utf-8 -*-
"""
NPC-DynaSurv — 集成 Web 后端
Flask + DynamicRiskPredictor + LLM (Qwen3-8B)
"""
import os, sys, json, logging
from datetime import datetime
from pathlib import Path

# Add qwen dir to path for llm imports
QWEN_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(QWEN_DIR))

from flask import Flask, send_from_directory, redirect, request, jsonify
from flask_login import LoginManager, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

# ===== Config =====
BASE_DIR = str(QWEN_DIR)
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'change-me-in-production')
DB_PATH = os.path.join(BASE_DIR, 'web_database.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

app = Flask(__name__, static_folder='web', static_url_path='')
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'serve_index'

# ===== Models =====
class Doctor(db.Model, object):
    __tablename__ = 'doctors'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(120), default='')
    hospital = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_active(self): return True
    @property
    def is_authenticated(self): return True
    @property
    def is_anonymous(self): return False
    def get_id(self): return str(self.id)

    def to_dict(self):
        return {
            'id': self.id, 'username': self.username, 'email': self.email,
            'full_name': self.full_name, 'department': self.department,
            'hospital': self.hospital,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PatientRecord(db.Model):
    __tablename__ = 'patient_records'
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    patient_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(120), default='[Anonymized]')
    sex = db.Column(db.String(10), default='')
    age = db.Column(db.Integer, nullable=True)
    t_stage = db.Column(db.String(10), default='')
    n_stage = db.Column(db.String(10), default='')
    m_stage = db.Column(db.String(10), default='')
    overall_stage = db.Column(db.String(20), default='')
    treatment = db.Column(db.String(200), default='')
    treatment_end = db.Column(db.String(50), default='')
    raw_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    visits = db.relationship('VisitRecord', backref='patient', lazy='dynamic',
                             cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id, 'doctor_id': self.doctor_id,
            'patient_id': self.patient_id, 'name': self.name,
            'sex': self.sex, 'age': self.age,
            't_stage': self.t_stage, 'n_stage': self.n_stage,
            'm_stage': self.m_stage, 'overall_stage': self.overall_stage,
            'treatment': self.treatment, 'treatment_end': self.treatment_end,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class VisitRecord(db.Model):
    __tablename__ = 'visit_records'
    id = db.Column(db.Integer, primary_key=True)
    patient_record_id = db.Column(db.Integer, db.ForeignKey('patient_records.id'), nullable=False)
    visit_number = db.Column(db.Integer, nullable=False)
    visit_date = db.Column(db.String(50), default='')
    months = db.Column(db.Float, default=0.0)
    dfs_risk = db.Column(db.Float, default=0.0)
    dmfs_risk = db.Column(db.Float, default=0.0)
    lrrfs_risk = db.Column(db.Float, default=0.0)
    os_risk = db.Column(db.Float, default=0.0)
    dominant_risk = db.Column(db.String(200), default='')
    recommended_interval = db.Column(db.String(100), default='')
    ai_advice = db.Column(db.Text, default='')

    def to_dict(self):
        return {
            'id': self.id, 'visit_number': self.visit_number,
            'visit_date': self.visit_date, 'months': self.months,
            'label': f'Visit {self.visit_number} — {self.visit_date} (Month {self.months})',
            'dfs_risk': self.dfs_risk, 'dmfs_risk': self.dmfs_risk,
            'lrrfs_risk': self.lrrfs_risk, 'os_risk': self.os_risk,
            'dominant_risk': self.dominant_risk,
            'recommended_interval': self.recommended_interval,
            'ai_advice': self.ai_advice,
        }


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Doctor, int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/api/'):
        return jsonify({'error': '请先登录'}), 401
    return redirect('/')


# ===== Import llm pipeline components =====
from llm import (
    load_patient_data, DynamicRiskPredictor, build_prompt, call_llm,
    RULES_DIGEST, EXCEL_FILE, load_config,
    LLM_PROVIDER, LLM_API_BASE, LLM_API_KEY, LLM_MODEL,
    LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_TIMEOUT,
)

# Load llm config
load_config()

# Re-import after load_config to get updated values
import llm as llm_module

# Cache the default patient
_default_patient_cache = None

def get_default_patient_data():
    """Get the default patient data (seed=42)."""
    global _default_patient_cache
    if _default_patient_cache is None:
        _default_patient_cache = load_patient_data(seed=42)
    return _default_patient_cache


def import_default_patient(doctor_id):
    """Import the default seed=42 patient into the database for a doctor."""
    data = get_default_patient_data()
    pid = data['patient_id'][:20]

    existing = PatientRecord.query.filter_by(patient_id=pid, doctor_id=doctor_id).first()
    if existing:
        return existing

    cur = data['current_visit']
    baseline = data.get('baseline') or {}

    sex_map = {1: 'Male', 2: 'Female'}

    patient = PatientRecord(
        doctor_id=doctor_id,
        patient_id=pid,
        name='[Anonymized]',
        sex=sex_map.get(baseline.get('sex', cur.get('sex', 1)), 'Male'),
        age=int(baseline.get('age', cur.get('age', 0)) or 0),
        t_stage=f"T{int(baseline.get('T_stage', cur.get('T_stage', 0)) or 0)}",
        n_stage=f"N{int(baseline.get('N_stage', cur.get('N_stage', 0)) or 0)}",
        m_stage=f"M{int(baseline.get('M_stage', cur.get('M_stage', 0)) or 0)}",
        overall_stage=str(int(baseline.get('clinical_stage', cur.get('clinical_stage', 0)) or 0)),
        treatment='CCRT' if baseline.get('concurrent_chemo') == 1 else 'RT',
        treatment_end=str(baseline.get('治疗结束时间', cur.get('治疗结束时间', '')))[:10],
        raw_json=json.dumps({
            'patient_id': data['patient_id'],
            'baseline_keys': list(baseline.keys()),
            'current_visit_id': cur.get('Visit_ID'),
        }, ensure_ascii=False, default=str),
    )
    db.session.add(patient)
    db.session.flush()

    # Import all visits with predictions
    predictor = DynamicRiskPredictor(seed=42)

    all_visits = data.get('prior_followups', []) + [data['current_visit']]

    for v in all_visits:
        # Get prediction for this visit
        temp_data = {**data, 'current_visit': v}
        preds = predictor.predict(temp_data)

        visit_date = str(v.get('Visit_Date.x', ''))[:10]
        months = round(float(v.get('Months_From_Tx_End', 0) or 0), 1)

        # Determine dominant risk
        dmfs = preds['DMFS_risk_12m']
        lrrfs = preds['LRRFS_risk_12m']
        if dmfs >= lrrfs:
            dominant = 'Distant metastasis' if dmfs > 0.05 else 'Distant metastasis (low risk)'
        else:
            dominant = 'Locoregional recurrence' if lrrfs > 0.05 else 'Locoregional recurrence (low risk)'

        # Determine risk level
        dfs = preds['DFS_risk_12m']
        if dfs >= 0.30:
            interval = '1 month'
        elif dfs >= 0.15:
            interval = '3 months'
        elif dfs >= 0.05:
            interval = '6 months'
        else:
            interval = '12 months'

        visit = VisitRecord(
            patient_record_id=patient.id,
            visit_number=int(v.get('Visit_ID', 0)),
            visit_date=visit_date,
            months=months,
            dfs_risk=round(dfs * 100, 1),
            dmfs_risk=round(dmfs * 100, 1),
            lrrfs_risk=round(lrrfs * 100, 1),
            os_risk=round(preds['OS_risk_12m'] * 100, 1),
            dominant_risk=dominant,
            recommended_interval=interval,
        )
        db.session.add(visit)

    db.session.commit()
    return patient


# ===== API Routes =====

# -- Auth --
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()

    if not username or len(username) < 3:
        return jsonify({'error': '用户名至少3个字符'}), 400
    if not email or '@' not in email:
        return jsonify({'error': '请输入有效邮箱'}), 400
    if not password or len(password) < 6:
        return jsonify({'error': '密码至少6个字符'}), 400
    if not full_name:
        return jsonify({'error': '请输入真实姓名'}), 400
    if Doctor.query.filter_by(username=username).first():
        return jsonify({'error': '用户名已存在'}), 409

    doctor = Doctor(
        username=username, email=email,
        password_hash=generate_password_hash(password),
        full_name=full_name,
        department=data.get('department', '').strip(),
        hospital=data.get('hospital', '').strip(),
    )
    db.session.add(doctor)
    db.session.commit()

    from flask_login import login_user
    login_user(doctor)
    return jsonify({'message': '注册成功', 'doctor': doctor.to_dict()}), 201


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    doctor = Doctor.query.filter_by(username=username).first()
    if not doctor or not check_password_hash(doctor.password_hash, password):
        return jsonify({'error': '用户名或密码错误'}), 401

    from flask_login import login_user
    login_user(doctor)
    return jsonify({'message': '登录成功', 'doctor': doctor.to_dict()}), 200


@app.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    from flask_login import logout_user
    logout_user()
    return jsonify({'message': '已退出'}), 200


@app.route('/api/me', methods=['GET'])
@login_required
def api_me():
    return jsonify({'doctor': current_user.to_dict()}), 200


# -- Patients --
@app.route('/api/patients', methods=['GET'])
@login_required
def api_patients():
    patients = PatientRecord.query.filter_by(doctor_id=current_user.id) \
        .order_by(PatientRecord.created_at.desc()).all()
    return jsonify({'patients': [p.to_dict() for p in patients]}), 200


@app.route('/api/patients/load-default', methods=['POST'])
@login_required
def api_load_default():
    """Load the default seed=42 patient into doctor's list."""
    try:
        patient = import_default_patient(current_user.id)
        return jsonify({
            'message': '默认患者加载成功',
            'patient': patient.to_dict(),
            'redirect': f'/ppt/{patient.id}',
        }), 201
    except Exception as e:
        return jsonify({'error': f'加载失败: {str(e)}'}), 500


@app.route('/api/patients/upload', methods=['POST'])
@login_required
def api_upload_excel():
    """Upload Excel and import patients."""
    if 'file' not in request.files:
        return jsonify({'error': '请选择文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '请选择文件'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ('xlsx', 'xls'):
        return jsonify({'error': '仅支持 .xlsx / .xls 格式'}), 400

    from werkzeug.utils import secure_filename
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        import pandas as pd
        df = pd.read_excel(filepath)

        if 'id' not in df.columns or 'Phase' not in df.columns:
            os.remove(filepath)
            return jsonify({'error': 'Excel 必须包含 id 和 Phase 列'}), 400

        # Find all unique patient IDs
        patient_ids = df['id'].dropna().unique()
        imported = []
        predictor = DynamicRiskPredictor(seed=42)

        for pid in patient_ids:
            pid_str = str(pid)[:20]
            existing = PatientRecord.query.filter_by(patient_id=pid_str, doctor_id=current_user.id).first()
            if existing:
                imported.append(existing.id)
                continue

            pdf = df[df['id'].astype(str) == str(pid)]
            baseline = pdf[pdf['Phase'] == 'Baseline']
            if baseline.empty:
                continue

            bl = baseline.iloc[0]
            sex_map = {1: 'Male', 2: 'Female'}

            patient = PatientRecord(
                doctor_id=current_user.id,
                patient_id=pid_str,
                name='[Anonymized]',
                sex=sex_map.get(int(bl.get('sex', 1) or 1), 'Male'),
                age=int(bl.get('age', 0) or 0),
                t_stage=f"T{int(bl.get('T_stage', 0) or 0)}",
                n_stage=f"N{int(bl.get('N_stage', 0) or 0)}",
                m_stage=f"M{int(bl.get('M_stage', 0) or 0)}",
                overall_stage=str(int(bl.get('clinical_stage', 0) or 0)),
                treatment='CCRT' if bl.get('concurrent_chemo') == 1 else 'RT',
                treatment_end=str(bl.get('治疗结束时间', ''))[:10],
                raw_json='{}',
            )
            db.session.add(patient)
            db.session.flush()

            # Import follow-up visits
            fu_df = pdf[pdf['Phase'] == 'Follow-up'].copy()
            if 'Visit_ID' in fu_df.columns:
                fu_df = fu_df.sort_values('Visit_ID')

            for _, row in fu_df.iterrows():
                visit_num = int(row.get('Visit_ID', 0) or 0)
                visit_date = str(row.get('Visit_Date.x', ''))[:10]
                months = float(row.get('Months_From_Tx_End', 0) or 0)

                # Get predictions for this visit
                temp_data = {'current_visit': row.to_dict(), 'prior_followups': []}
                try:
                    preds = predictor.predict(temp_data)
                except Exception:
                    preds = {'DFS_risk_12m': 0.02, 'DMFS_risk_12m': 0.02,
                             'LRRFS_risk_12m': 0.02, 'OS_risk_12m': 0.02}

                dmfs = preds['DMFS_risk_12m']
                lrrfs = preds['LRRFS_risk_12m']
                dominant = 'Distant metastasis' if dmfs >= lrrfs else 'Locoregional recurrence'
                dfs = preds['DFS_risk_12m']
                if dfs >= 0.30: interval = '1 month'
                elif dfs >= 0.15: interval = '3 months'
                elif dfs >= 0.05: interval = '6 months'
                else: interval = '12 months'

                visit = VisitRecord(
                    patient_record_id=patient.id,
                    visit_number=visit_num,
                    visit_date=visit_date,
                    months=round(months, 1),
                    dfs_risk=round(dfs * 100, 1),
                    dmfs_risk=round(dmfs * 100, 1),
                    lrrfs_risk=round(lrrfs * 100, 1),
                    os_risk=round(preds['OS_risk_12m'] * 100, 1),
                    dominant_risk=dominant,
                    recommended_interval=interval,
                )
                db.session.add(visit)

            db.session.commit()
            imported.append(patient.id)

        # 保留上传文件，不删除

        if not imported:
            return jsonify({'error': '未找到有效的患者数据'}), 400

        return jsonify({
            'message': f'成功导入 {len(imported)} 位患者',
            'patient_id': imported[0],
            'redirect': f'/ppt/{imported[0]}',
        }), 201

    except Exception as e:
        db.session.rollback()
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': f'导入失败: {str(e)}'}), 500


@app.route('/api/patients/<int:patient_id>/visits', methods=['GET'])
@login_required
def api_visits(patient_id):
    patient = PatientRecord.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
    if not patient:
        return jsonify({'error': '患者不存在'}), 404
    visits = VisitRecord.query.filter_by(patient_record_id=patient.id) \
        .order_by(VisitRecord.visit_number).all()
    return jsonify({'visits': [v.to_dict() for v in visits]}), 200


@app.route('/api/patients/<int:patient_id>/visit/<int:visit_id>', methods=['GET'])
@login_required
def api_visit_detail(patient_id, visit_id):
    patient = PatientRecord.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
    if not patient:
        return jsonify({'error': '患者不存在'}), 404

    visit = VisitRecord.query.filter_by(id=visit_id, patient_record_id=patient.id).first()
    if not visit:
        return jsonify({'error': '随访记录不存在'}), 404

    # Get all visits for trajectory
    all_visits = VisitRecord.query.filter_by(patient_record_id=patient.id) \
        .order_by(VisitRecord.visit_number).all()
    trajectory = [{
        'visit_number': v.visit_number, 'months': v.months,
        'visit_date': v.visit_date, 'dfs': v.dfs_risk,
        'dmfs': v.dmfs_risk, 'lrrfs': v.lrrfs_risk, 'os': v.os_risk,
    } for v in all_visits]

    return jsonify({
        'patient': patient.to_dict(),
        'visit': visit.to_dict(),
        'trajectory': trajectory,
        'risk_assessment': {
            'dfs': visit.dfs_risk, 'dmfs': visit.dmfs_risk,
            'lrrfs': visit.lrrfs_risk, 'os': visit.os_risk,
            'dominant_risk_type': visit.dominant_risk,
            'recommended_interval': visit.recommended_interval,
        },
        'ai_recommendation': parse_ai_advice(visit),
    }), 200


@app.route('/api/patients/<int:patient_id>/visit/<int:visit_id>/generate-advice', methods=['POST'])
@login_required
def api_generate_advice(patient_id, visit_id):
    """Call LLM (Qwen3-8B) to generate AI advice for this visit."""
    patient = PatientRecord.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
    if not patient:
        return jsonify({'error': '患者不存在'}), 404

    visit = VisitRecord.query.filter_by(id=visit_id, patient_record_id=patient.id).first()
    if not visit:
        return jsonify({'error': '随访记录不存在'}), 404

    llm_error = ''

    try:
        # 先尝试从原始 Excel 加载（seed=42 默认患者）
        try:
            data = load_patient_data(patient_id=None, visit_id=visit.visit_number, seed=42)
        except Exception:
            data = None

        # 如果 Excel 加载失败（比如新上传的患者），用数据库记录组装
        if data is None:
            all_visits = VisitRecord.query.filter_by(patient_record_id=patient.id) \
                .order_by(VisitRecord.visit_number).all()
            current = visit.to_dict()
            prior = [v.to_dict() for v in all_visits if v.id != visit.id]
            predictions = {
                'DFS_risk_12m': visit.dfs_risk / 100,
                'DMFS_risk_12m': visit.dmfs_risk / 100,
                'LRRFS_risk_12m': visit.lrrfs_risk / 100,
                'OS_risk_12m': visit.os_risk / 100,
                'DFS_risk_prev': prior[-1]['dfs_risk'] / 100 if prior else 0.02,
                'DFS_risk_delta': 0,
            }
            # 组装简化 system + user prompt
            system_prompt = llm_module.RULES_DIGEST + "\n请按规则引擎六板块输出中文随访建议。"
            user_prompt = f"""患者: {patient.sex}, {patient.age}岁, T{patient.t_stage}N{patient.n_stage}M{patient.m_stage} Stage {patient.overall_stage}
治疗: {patient.treatment}, 结束于 {patient.treatment_end}
本次随访: Visit {visit.visit_number}, {visit.visit_date}, 治疗后 {visit.months} 月
预测: DFS={visit.dfs_risk}% DMFS={visit.dmfs_risk}% LRRFS={visit.lrrfs_risk}% OS={visit.os_risk}%
主导风险: {visit.dominant_risk}, 建议间隔: {visit.recommended_interval}
既往随访: {len(prior)} 次
请生成结构化随访建议。"""
            prompt = {'system': system_prompt, 'user': user_prompt}
        else:
            predictor = DynamicRiskPredictor(seed=42)
            predictions = predictor.predict(data)
            prompt = build_prompt(data, predictions)

        # Call LLM with config from config.yaml
        advice = call_llm(
            prompt, attach_pdf=None,
            api_key=llm_module.LLM_API_KEY,
            api_base=llm_module.LLM_API_BASE,
            model=llm_module.LLM_MODEL,
            temperature=llm_module.LLM_TEMPERATURE,
            max_tokens=llm_module.LLM_MAX_TOKENS,
            timeout=llm_module.LLM_TIMEOUT,
        )

        # Check if LLM returned real advice or debug message
        if advice and not advice.startswith('[call_llm]'):
            visit.ai_advice = advice
            db.session.commit()
            return jsonify({
                'message': 'AI 建议生成成功 (Qwen3-8B)',
                'ai_recommendation': parse_ai_advice(visit),
            }), 200
        else:
            llm_error = 'LLM 返回调试信息，可能未正确配置 API Key 或模型'

    except Exception as e:
        llm_error = str(e)[:200]
        logging.getLogger('web_app').warning(f'LLM call failed: {e}')

    # Fallback: rule-based advice
    advice = generate_rule_based_advice(visit)
    visit.ai_advice = advice
    db.session.commit()
    return jsonify({
        'message': f'⚠️ LLM 不可用（{llm_error[:80]}），已使用规则引擎生成建议。如需 AI 建议，请先启动: python serve_qwen.py --port 8000',
        'ai_recommendation': parse_ai_advice(visit),
    }), 200


def parse_ai_advice(visit):
    """Parse AI advice into structured format for PPT display."""
    if visit.ai_advice:
        # Use real LLM output as-is
        return {
            'next_visit': f'Based on risk assessment, visit.visit_number={visit.visit_number}',
            'examinations': [],  # Let LLM text speak for itself
            'raw_advice': visit.ai_advice,
            'has_llm_advice': True,
        }

    # Rule-based fallback from RULES_DIGEST
    dfs = visit.dfs_risk
    dmfs = visit.dmfs_risk
    lrrfs = visit.lrrfs_risk

    # Risk level
    if dfs >= 30:
        risk_level, interval = 'Very High Risk', '1 month'
    elif dfs >= 15:
        risk_level, interval = 'High Risk', '3 months'
    elif dfs >= 5:
        risk_level, interval = 'Intermediate Risk', '6 months'
    else:
        risk_level, interval = 'Low Risk', '12 months'

    # Dominant risk
    if dmfs >= lrrfs and dmfs >= 10:
        dominant = 'Distant metastasis (high risk)'
        imaging = 'Chest+abdominal enhanced CT, consider ECT if ALP elevated'
    elif dmfs >= lrrfs:
        dominant = 'Distant metastasis (low risk)'
        imaging = 'Chest CT (plain) + abdominal ultrasound'
    elif lrrfs >= 10:
        dominant = 'Locoregional recurrence (high risk)'
        imaging = 'Nasopharyngeal + neck enhanced MRI, nasal endoscopy'
    else:
        dominant = 'Locoregional recurrence (low risk)'
        imaging = 'Routine follow-up imaging'

    examinations = [
        'EBV-DNA quantification',
        'Electronic nasopharyngoscopy',
        'Complete blood count (Hb, WBC, PLT, NLR, PLR)',
        'Liver/renal function & electrolytes (ALB, LDH, ALP, ALT, AST, Ca)',
        'Thyroid function (TSH, FT3, FT4)',
        'Physical examination (head/neck palpation, neurological, weight)',
        imaging,
    ]

    next_visit = f'Next visit in {interval}'

    health_alert = ''
    if dfs >= 15:
        health_alert = f'DFS conditional risk = {dfs}% (≥15%). Risk level: {risk_level}. Close monitoring recommended.'
    elif dfs >= 5:
        health_alert = f'DFS conditional risk = {dfs}% (5-15%). Regular follow-up per protocol.'

    return {
        'next_visit': next_visit,
        'examinations': examinations,
        'risk_level': risk_level,
        'dominant_risk': dominant,
        'health_alert_content': health_alert,
        'has_llm_advice': False,
    }


def generate_rule_based_advice(visit):
    """Generate structured advice using the rule engine (fallback when LLM unavailable)."""
    dfs = visit.dfs_risk
    dmfs = visit.dmfs_risk
    lrrfs = visit.lrrfs_risk

    advice_parts = [
        "# AI 风险评估摘要 (规则引擎)",
        "",
        f"## 风险分层",
        f"- DFS 12个月条件风险: {dfs}%",
        f"- DMFS 12个月条件风险: {dmfs}%",
        f"- LRRFS 12个月条件风险: {lrrfs}%",
        f"- OS 12个月条件风险: {visit.os_risk}%",
        "",
        f"## 主导风险方向",
        f"- {visit.dominant_risk}",
        "",
        f"## 建议随访间隔",
        f"- {visit.recommended_interval}",
        "",
        "## 推荐检查项目",
        "- EBV-DNA 定量检测",
        "- 电子鼻咽镜检查",
        "- 血常规 (Hb, WBC, PLT, NLR, PLR)",
        "- 肝肾功能及电解质",
        "- 甲状腺功能 (TSH, FT3, FT4)",
        "- 体格检查",
    ]

    if dmfs >= lrrfs:
        advice_parts.append("- 胸腹部影像学筛查 (CT/超声)")
    else:
        advice_parts.append("- 鼻咽+颈部增强 MRI")

    advice_parts.extend([
        "",
        "## 健康提醒",
        "- 按规则引擎六层级执行随访",
        "- 关注 EBV-DNA 变化趋势",
        "- 定期评估甲状腺功能",
        "",
        "> 此建议由规则引擎自动生成。如需 AI 建议，请启动 Qwen 模型服务后点击「生成 AI 建议」。",
    ])

    return '\n'.join(advice_parts)


# ===== Delete Patient =====
@app.route('/api/patients/<int:patient_id>', methods=['DELETE'])
@login_required
def api_delete_patient(patient_id):
    patient = PatientRecord.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
    if not patient:
        return jsonify({'error': '患者不存在'}), 404
    db.session.delete(patient)
    db.session.commit()
    return jsonify({'message': '患者已删除'}), 200


# ===== Page Routes =====
@app.route('/')
def serve_index():
    return send_from_directory('web', 'index.html')


@app.route('/dashboard')
def serve_dashboard():
    return send_from_directory('web', 'dashboard.html')


@app.route('/ppt/<int:patient_id>')
def serve_ppt(patient_id):
    return send_from_directory('web', 'ppt.html')


# ===== Main =====
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print('✓ Database tables created')
        print(f'✓ Server: http://localhost:5000')
    app.run(debug=True, host='0.0.0.0', port=5000)
