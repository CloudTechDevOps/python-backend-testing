from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import redis
import json

app = Flask(__name__)
CORS(app)

# =========================
# REDIS CONFIG
# =========================
redis_client = redis.Redis(
    host='test-qtzhay.serverless.use1.cache.amazonaws.com',
    port=6379,
    ssl=True,
    decode_responses=True,
    socket_timeout=5
)

CACHE_TTL = 90

# =========================
# RDS CONFIG (DEV ONLY)
# =========================

db_write_config = {
    'host': 'database-1.c2pu22iyqlnl.us-east-1.rds.amazonaws.com',
    'user': 'admin',
    'password': 'Cloud123',
    'database': 'dev'
}

db_read_config = {
    'host': 'reader.c2pu22iyqlnl.us-east-1.rds.amazonaws.com',
    'user': 'admin',
    'password': 'Cloud123',
    'database': 'dev'
}

# =========================
# CONNECTION HELPERS
# =========================

def get_write_connection():
    print("✍️ CONNECTING TO RDS WRITER")
    return mysql.connector.connect(**db_write_config)

def get_read_connection():
    print("👀 CONNECTING TO RDS READER")
    return mysql.connector.connect(**db_read_config)

def get_db_info(cursor):
    cursor.execute("SELECT @@hostname AS host, @@read_only AS read_only")
    return cursor.fetchone()

# =========================
# ROUTES
# =========================

@app.route('/')
def index():
    return "API running with Redis + RDS (Reader/Writer)"

# =========================
# READ APIs
# =========================

@app.route('/users', methods=['GET'])
def get_users():
    cache_key = "users:all"

    try:
        # 1️⃣ Redis check
        cached_data = redis_client.get(cache_key)
        if cached_data:
            print("⚡ REDIS CACHE HIT → /users")
            return jsonify({
                "data": json.loads(cached_data),
                "source": "REDIS_CACHE",
                "db_role": "READER"
            })

        print("❌ REDIS CACHE MISS → /users")

        # 2️⃣ RDS Reader
        conn = get_read_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        db_info = get_db_info(cursor)

        print(f"📖 READ FROM RDS READER → host={db_info['host']}")

        # 3️⃣ Cache result
        redis_client.setex(cache_key, CACHE_TTL, json.dumps(users))
        print("📦 DATA STORED IN REDIS CACHE")

        return jsonify({
            "data": users,
            "served_by": db_info["host"],
            "read_only": db_info["read_only"],
            "db_role": "READER",
            "source": "RDS_READER"
        })

    except Error as err:
        print("❌ ERROR:", err)
        return jsonify({'error': str(err)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    cache_key = f"user:{user_id}"

    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            print(f"⚡ REDIS CACHE HIT → /users/{user_id}")
            return jsonify({
                "data": json.loads(cached_data),
                "source": "REDIS_CACHE",
                "db_role": "READER"
            })

        print(f"❌ REDIS CACHE MISS → /users/{user_id}")

        conn = get_read_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            print("⚠️ USER NOT FOUND IN DB")
            return jsonify({'error': 'User not found'}), 404

        db_info = get_db_info(cursor)
        print(f"📖 READ FROM RDS READER → host={db_info['host']}")

        redis_client.setex(cache_key, CACHE_TTL, json.dumps(user))
        print("📦 USER STORED IN REDIS CACHE")

        return jsonify({
            "data": user,
            "served_by": db_info["host"],
            "read_only": db_info["read_only"],
            "db_role": "READER",
            "source": "RDS_READER"
        })

    except Error as err:
        print("❌ ERROR:", err)
        return jsonify({'error': str(err)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# =========================
# WRITE APIs
# =========================

@app.route('/users/add', methods=['POST'])
def add_user():
    try:
        print("✍️ WRITE REQUEST → /users/add")
        conn = get_write_connection()
        cursor = conn.cursor()

        data = request.json
        cursor.execute(
            "INSERT INTO users (name, email) VALUES (%s, %s)",
            (data['name'], data['email'])
        )
        conn.commit()

        print("✅ WRITE SUCCESSFUL ON RDS WRITER")

        # Cache invalidation
        redis_client.delete("users:all")
        print("🧹 CACHE INVALIDATED → users:all")

        return jsonify({'message': 'User added successfully'}), 201

    except Error as err:
        print("❌ WRITE ERROR:", err)
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/users/update/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        print(f"✍️ WRITE REQUEST → /users/update/{user_id}")
        conn = get_write_connection()
        cursor = conn.cursor()

        data = request.json
        cursor.execute(
            "UPDATE users SET name = %s, email = %s WHERE id = %s",
            (data['name'], data['email'], user_id)
        )
        conn.commit()

        print("✅ UPDATE SUCCESSFUL ON RDS WRITER")

        redis_client.delete("users:all")
        redis_client.delete(f"user:{user_id}")
        print("🧹 CACHE INVALIDATED → users:all, user:{user_id}")

        return jsonify({'message': 'User updated successfully'})

    except Error as err:
        print("❌ UPDATE ERROR:", err)
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/users/delete/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        print(f"✍️ WRITE REQUEST → /users/delete/{user_id}")
        conn = get_write_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()

        print("✅ DELETE SUCCESSFUL ON RDS WRITER")

        redis_client.delete("users:all")
        redis_client.delete(f"user:{user_id}")
        print("🧹 CACHE INVALIDATED → users:all, user:{user_id}")

        return jsonify({'message': 'User deleted successfully'})

    except Error as err:
        print("❌ DELETE ERROR:", err)
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# =========================
# ENTRY POINT
# =========================
if __name__ == '__main__':
    print("🚀 Starting Flask API with Redis + RDS")
    app.run(host='0.0.0.0', port=5000, debug=True)
