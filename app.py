from flask import Flask, request, jsonify, render_template
import pyodbc
import hashlib
import re
from datetime import datetime

app = Flask(__name__)

# ✅ Cloud SQL SQL Server connection config
DB_CONFIG = {
    "driver": "{ODBC Driver 18 for SQL Server}",
    "server": "34.60.155.124,1433",  # 👈 استخدم الـ Public IP مباشرة مع المنفذ
    "database": "auth_system",
    "user": "sqlserver",
    "password": "Cloud@2025"
}

def get_db_connection():
    try:
        conn_str = (
            f"DRIVER={DB_CONFIG['driver']};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['user']};"
            f"PWD={DB_CONFIG['password']};"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
        )
        conn = pyodbc.connect(conn_str, timeout=5)
        print("✅ Database connection successful!")
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

# ==========================
# 🧱 Database Initialization
# ==========================
def init_database():
    """Create the 'users' table if it doesn't exist."""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' AND xtype='U')
                CREATE TABLE users (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    first_name NVARCHAR(100) NOT NULL,
                    last_name NVARCHAR(100) NOT NULL,
                    email NVARCHAR(255) UNIQUE NOT NULL,
                    password_hash NVARCHAR(255) NOT NULL,
                    country NVARCHAR(100) NOT NULL,
                    phone NVARCHAR(20),
                    workplace NVARCHAR(255) NOT NULL,
                    specialty NVARCHAR(255) NOT NULL,
                    created_at DATETIME DEFAULT GETDATE(),
                    last_login DATETIME,
                    is_active BIT DEFAULT 1
                )
            """)
            conn.commit()
            print("✅ Database initialized successfully.")
        except Exception as e:
            print(f"⚠️ Database initialization error: {e}")
        finally:
            conn.close()


# ==========================
# 🔐 Utilities
# ==========================
def hash_password(password: str) -> str:
    """Return SHA-256 hash of a password."""
    return hashlib.sha256(password.encode()).hexdigest()


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# ==========================
# 🌐 Routes
# ==========================
@app.route('/')
def index():
    """Render main page."""
    return render_template('index.html')


# 🧍‍♂️ User Registration
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json(force=True)

        required_fields = ['firstName', 'lastName', 'email', 'password', 'confirmPassword', 'country', 'workplace', 'specialty']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return jsonify({'success': False, 'message': f'الحقول التالية مطلوبة: {", ".join(missing)}'}), 400

        if not validate_email(data['email']):
            return jsonify({'success': False, 'message': 'البريد الإلكتروني غير صالح'}), 400

        if data['password'] != data['confirmPassword']:
            return jsonify({'success': False, 'message': 'كلمتا المرور غير متطابقتين'}), 400

        if len(data['password']) < 6:
            return jsonify({'success': False, 'message': 'كلمة المرور يجب أن تكون 6 أحرف على الأقل'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'خطأ في الاتصال بقاعدة البيانات'}), 500

        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", data['email'])
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'البريد الإلكتروني مسجل مسبقاً'}), 400

        hashed_password = hash_password(data['password'])
        cursor.execute("""
            INSERT INTO users (first_name, last_name, email, password_hash, country, phone, workplace, specialty)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['firstName'], data['lastName'], data['email'],
            hashed_password, data['country'], data.get('phone', ''),
            data['workplace'], data['specialty']
        ))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'تم التسجيل بنجاح ✅',
            'redirect': 'https://smart-assistant.arabccd.org/'
        })
    except Exception as e:
        print(f"⚠️ Registration error: {e}")
        return jsonify({'success': False, 'message': 'حدث خطأ أثناء التسجيل'}), 500


# 🔑 User Login
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json(force=True)
        if not data.get('email') or not data.get('password'):
            return jsonify({'success': False, 'message': 'يرجى إدخال البريد الإلكتروني وكلمة المرور'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'خطأ في الاتصال بقاعدة البيانات'}), 500

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, first_name, last_name, email, password_hash, is_active 
            FROM users 
            WHERE email = ?
        """, data['email'])
        user = cursor.fetchone()

        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'البريد الإلكتروني أو كلمة المرور غير صحيحة'}), 401

        user_dict = {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'password_hash': user.password_hash,
            'is_active': user.is_active
        }

        if not user_dict['is_active']:
            conn.close()
            return jsonify({'success': False, 'message': 'الحساب غير مفعل'}), 401

        hashed_password = hash_password(data['password'])
        if user_dict['password_hash'] != hashed_password:
            conn.close()
            return jsonify({'success': False, 'message': 'البريد الإلكتروني أو كلمة المرور غير صحيحة'}), 401

        cursor.execute("UPDATE users SET last_login = GETDATE() WHERE id = ?", user_dict['id'])
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'تم تسجيل الدخول بنجاح ✅',
            'user': {
                'id': user_dict['id'],
                'firstName': user_dict['first_name'],
                'lastName': user_dict['last_name'],
                'email': user_dict['email']
            },
            'redirect': 'https://summary.arabccd.org/'
        })
    except Exception as e:
        print(f"⚠️ Login error: {e}")
        return jsonify({'success': False, 'message': 'حدث خطأ أثناء تسجيل الدخول'}), 500


# 📧 Check Email Availability
@app.route('/check-email', methods=['POST'])
def check_email():
    try:
        data = request.get_json(force=True)
        email = data.get('email', '')

        conn = get_db_connection()
        if not conn:
            return jsonify({'exists': False})

        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", email)
        exists = cursor.fetchone() is not None

        conn.close()
        return jsonify({'exists': exists})
    except Exception as e:
        print(f"⚠️ Check email error: {e}")
        return jsonify({'exists': False})


# ==========================
# 🚀 Run App
# ==========================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
