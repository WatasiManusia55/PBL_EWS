import requests

API_KEY = "AIzaSyBmgepsmVXP1ekfUl47RsllWl-BnjKkSno"
DB_URL = "https://ews3-858da-default-rtdb.asia-southeast1.firebasedatabase.app"

# Input dari terminal
nama = input("Masukkan nama: ")
email = input("Masukkan email: ")
password = input("Masukkan password: ")

# 🔹 LOGIN
def login(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
    data = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    return requests.post(url, json=data).json()

# 🔹 REGISTER
def register(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
    data = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    return requests.post(url, json=data).json()

# 1. Coba login dulu
auth = login(email, password)

# 2. Kalau gagal → register
if "error" in auth:
    print("User belum ada, daftar dulu...")
    auth = register(email, password)

    if "error" in auth:
        print("Gagal auth:", auth["error"]["message"])
        exit()

# Ambil UID & token
uid = auth["localId"]
id_token = auth["idToken"]

print("Auth berhasil. UID:", uid)

# 3. Push ke Firebase (sesuai rules baru)
db_url = f"{DB_URL}/node1/latest/user/{uid}.json?auth={id_token}"

data = {
    "nama": nama,
    "email": email
}

res = requests.put(db_url, json=data)

if res.status_code == 200:
    print("Data berhasil masuk ke Firebase")
else:
    print("Gagal:", res.text)