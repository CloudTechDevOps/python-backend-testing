# Frontend–Backend Communication Using Nginx Reverse Proxy

## Architecture

```text
                Internet
                    │
                    ▼
        http://98.91.246.171
                    │
                    ▼
          Frontend EC2 (Nginx)
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
 Serves index.html        Proxies /users
                                 │
                                 ▼
                 Backend EC2 (Flask API)
                  http://172.31.42.151:5000
                                 │
                                 ▼
                            Amazon RDS
```

---

# Why use a Reverse Proxy?

The backend is running on a **private IP**:

```
172.31.42.151:5000
```

Private IPs are **not accessible** from the Internet.

Instead of exposing the backend directly, Nginx acts as a **Reverse Proxy**.

Benefits:

- Backend remains private.
- Only Nginx is exposed publicly.
- Easier SSL (HTTPS) configuration.
- Better security.
- Single public endpoint for frontend and backend.

---

# Frontend Configuration

Instead of calling the backend directly:

```javascript
const backendIP = "http://172.31.42.151:5000";
```

Use:

```javascript
const backendIP = "";
```

or

```javascript
const backendIP = "/api";
```

Then the API call becomes:

```javascript
fetch(`${backendIP}/users`)
```

which resolves to

```
GET /users
```

or

```
GET /api/users
```

depending on your configuration.

---

# Browser Request Flow

When a user opens:

```
http://98.91.246.171
```

the browser downloads:

```
index.html
```

Inside JavaScript:

```javascript
fetch("/users")
```

The browser automatically sends:

```
GET http://98.91.246.171/users
```

Notice:

It **does not** contact the backend directly.

---

# Nginx Configuration

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location /users {

        proxy_pass http://172.31.42.151:5000;

        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

# How Nginx Works

### Step 1

Browser requests:

```
GET /
```

Nginx returns:

```
index.html
```

---

### Step 2

JavaScript executes:

```javascript
fetch("/users")
```

Browser sends:

```
GET /users
```

---

### Step 3

Nginx matches:

```nginx
location /users
```

---

### Step 4

Instead of serving a file,

Nginx forwards the request to:

```
http://172.31.42.151:5000/users
```

---

### Step 5

Flask receives:

```python
@app.route("/users")
```

---

### Step 6

Flask queries Amazon RDS.

```
SELECT * FROM users;
```

---

### Step 7

Flask returns JSON.

Example:

```json
[
  {
    "id": 1,
    "name": "John",
    "email": "john@gmail.com"
  }
]
```

---

### Step 8

Nginx forwards the JSON response back to the browser.

---

# Complete Request Flow

```text
Browser
   │
   │ GET /
   ▼
Nginx
   │
   ▼
index.html
   │
   ▼
JavaScript

fetch("/users")
        │
        ▼
GET /users
        │
        ▼
Nginx
        │
        │ location /users
        ▼
Proxy Request
        │
        ▼
Flask
172.31.42.151:5000/users
        │
        ▼
Amazon RDS
        │
        ▼
JSON Response
        │
        ▼
Flask
        │
        ▼
Nginx
        │
        ▼
Browser
```

---

# Advantages

- Backend is not publicly accessible.
- No CORS issues because requests originate from the same domain.
- Improved security.
- Easier HTTPS configuration.
- Centralized routing through Nginx.
- Scalable architecture for production deployments.

---

# Summary

```
Browser
    │
    ▼
Frontend (Nginx)
    │
    ├── "/"      → index.html
    │
    └── "/users" → Flask Backend
                    │
                    ▼
                  Amazon RDS
```
```
Browser
   |
   | GET /users
   v
Nginx
   |
   | reads its nginx.conf
   | sees location /users
   | sees proxy_pass
   v
Backend :5000
   |
   | generates response
   v
Nginx
   |
   | sends RESPONSE
   v
Browser
```
**Key Point:** The browser never communicates directly with the private backend (`172.31.42.151:5000`). All API requests first go to the **Nginx server** on the frontend EC2, which securely proxies them to the backend Flask application.
