import json
import logging
import time

from flask import Flask, request, jsonify, g
from flask_cors import CORS
import mysql.connector
import boto3
from botocore.exceptions import ClientError

#########################################################
# Flask App
#########################################################

app = Flask(__name__)
CORS(app)

#########################################################
# Logging Configuration
#########################################################

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

#########################################################
# Request Logging
#########################################################

@app.before_request
def before_request():
    g.start_time = time.time()

    app.logger.info("=" * 80)
    app.logger.info(f"Method      : {request.method}")
    app.logger.info(f"URL         : {request.url}")
    app.logger.info(f"Client IP   : {request.remote_addr}")

    if request.is_json:
        app.logger.info(f"Request JSON: {request.get_json()}")
    elif request.form:
        app.logger.info(f"Request Form: {request.form.to_dict()}")


@app.after_request
def after_request(response):

    duration = time.time() - g.start_time

    app.logger.info(f"Status Code : {response.status_code}")
    app.logger.info(f"Response Time : {duration:.3f} seconds")
    app.logger.info("=" * 80)

    return response


@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.exception("Unhandled Exception:")
    return jsonify({"error": str(e)}), 500


#########################################################
# Secrets Manager
#########################################################

def get_secret():

    secret_name = "rds!db-0437b423-1517-4d45-8c21-d86763de1afd"
    region_name = "us-east-1"

    session = boto3.session.Session()

    client = session.client(
        service_name="secretsmanager",
        region_name=region_name
    )

    response = client.get_secret_value(
        SecretId=secret_name
    )

    secret_string = response.get("SecretString")

    if secret_string is None:
        secret_string = response["SecretBinary"].decode("utf-8")

    return json.loads(secret_string)


secret_data = get_secret()

#########################################################
# Database
#########################################################

db_config = {
    "host": "database-1.ce5q60wqojxk.us-east-1.rds.amazonaws.com",
    "user": secret_data["username"],
    "password": secret_data["password"],
    "database": "dev"
}


def get_db_connection():
    return mysql.connector.connect(**db_config)

#########################################################
# Routes
#########################################################

@app.route("/")
def home():
    return "Hello"


#########################################################
# Get All Users
#########################################################

@app.route("/users", methods=["GET"])
def get_users():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users")

    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(users)


#########################################################
# Get User By ID
#########################################################

@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (user_id,)
    )

    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user:
        return jsonify(user)

    return jsonify({
        "error": "User not found"
    }), 404


#########################################################
# Add User
#########################################################

@app.route("/users/add", methods=["POST"])
def add_user():

    data = request.get_json()

    name = data.get("name")
    email = data.get("email")

    if not name or not email:
        return jsonify({
            "error": "Name and Email are required"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            "INSERT INTO users(name,email) VALUES(%s,%s)",
            (name, email)
        )

        conn.commit()

        app.logger.info(f"Inserted User : {name}")

        return jsonify({
            "message": "User added successfully"
        }), 201

    except mysql.connector.Error as err:

        app.logger.error(err)

        return jsonify({
            "error": str(err)
        }), 500

    finally:

        cursor.close()
        conn.close()


#########################################################
# Update User
#########################################################

@app.route("/users/update/<int:user_id>", methods=["PUT"])
def update_user(user_id):

    data = request.get_json()

    name = data.get("name")
    email = data.get("email")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (user_id,)
    )

    if not cursor.fetchone():
        cursor.close()
        conn.close()

        return jsonify({
            "error": "User not found"
        }), 404

    try:

        cursor.execute(
            "UPDATE users SET name=%s,email=%s WHERE id=%s",
            (name, email, user_id)
        )

        conn.commit()

        app.logger.info(f"Updated User : {user_id}")

        return jsonify({
            "message": "User updated successfully"
        })

    except mysql.connector.Error as err:

        app.logger.error(err)

        return jsonify({
            "error": str(err)
        }), 500

    finally:

        cursor.close()
        conn.close()


#########################################################
# Delete User
#########################################################

@app.route("/users/delete/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id=%s",
        (user_id,)
    )

    if not cursor.fetchone():
        cursor.close()
        conn.close()

        return jsonify({
            "error": "User not found"
        }), 404

    try:

        cursor.execute(
            "DELETE FROM users WHERE id=%s",
            (user_id,)
        )

        conn.commit()

        app.logger.info(f"Deleted User : {user_id}")

        return jsonify({
            "message": "User deleted successfully"
        })

    except mysql.connector.Error as err:

        app.logger.error(err)

        return jsonify({
            "error": str(err)
        }), 500

    finally:

        cursor.close()
        conn.close()


#########################################################
# Start Server
#########################################################

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
