import os
import time
import json
import psycopg2
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="SA Clinic Appointment API")
Instrumentator().instrument(app).expose(app)

DB_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# Redis connection
cache = redis.from_url(REDIS_URL, decode_responses=True)

def get_conn():
    return psycopg2.connect(DB_URL)

def init_db():
    retries = 5
    while retries > 0:
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    id_number TEXT UNIQUE NOT NULL,
                    province TEXT NOT NULL,
                    phone TEXT,
                    registered_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id SERIAL PRIMARY KEY,
                    patient_id INTEGER REFERENCES patients(id),
                    clinic TEXT NOT NULL,
                    doctor TEXT NOT NULL,
                    appointment_date TEXT NOT NULL,
                    status TEXT DEFAULT 'scheduled',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            conn.commit()
            conn.close()
            print("Database initialised successfully")
            break
        except Exception as e:
            print(f"DB not ready, retrying in 5s... ({e})")
            retries -= 1
            time.sleep(5)

init_db()

# --- Models ---
class Patient(BaseModel):
    name: str
    id_number: str
    province: str
    phone: str

class Appointment(BaseModel):
    patient_id: int
    clinic: str
    doctor: str
    appointment_date: str

# --- Routes ---
@app.get("/")
def root():
    return {"service": "SA Clinic Appointment API", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": str(datetime.utcnow())}

@app.post("/patients")
def register_patient(patient: Patient):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO patients (name, id_number, province, phone)
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (patient.name, patient.id_number, patient.province, patient.phone))
        patient_id = cur.fetchone()[0]
        conn.commit()
        cache.delete("all_patients")
        return {"message": f"Patient registered", "patient_id": patient_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.get("/patients")
def list_patients():
    cached = cache.get("all_patients")
    if cached:
        print("Serving patients from Redis cache")
        return json.loads(cached)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM patients ORDER BY registered_at DESC")
    rows = cur.fetchall()
    conn.close()
    result = [{"id": r[0], "name": r[1], "id_number": r[2], "province": r[3], "phone": r[4], "registered_at": str(r[5])} for r in rows]
    cache.setex("all_patients", 60, json.dumps(result))
    return result

@app.post("/appointments")
def book_appointment(appt: Appointment):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO appointments (patient_id, clinic, doctor, appointment_date)
        VALUES (%s, %s, %s, %s) RETURNING id
    """, (appt.patient_id, appt.clinic, appt.doctor, appt.appointment_date))
    appt_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    cache.delete(f"appointments_{appt.patient_id}")
    return {"message": "Appointment booked", "appointment_id": appt_id}

@app.get("/appointments/{patient_id}")
def get_appointments(patient_id: int):
    cache_key = f"appointments_{patient_id}"
    cached = cache.get(cache_key)
    if cached:
        print(f"Serving appointments for patient {patient_id} from cache")
        return json.loads(cached)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, p.name, a.clinic, a.doctor, a.appointment_date, a.status, a.created_at
        FROM appointments a JOIN patients p ON a.patient_id = p.id
        WHERE a.patient_id = %s ORDER BY a.appointment_date
    """, (patient_id,))
    rows = cur.fetchall()
    conn.close()
    result = [{"id": r[0], "patient": r[1], "clinic": r[2], "doctor": r[3], "date": r[4], "status": r[5], "created_at": str(r[6])} for r in rows]
    cache.setex(cache_key, 60, json.dumps(result))
    return result

@app.get("/appointments")
def list_all_appointments():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, p.name, a.clinic, a.doctor, a.appointment_date, a.status
        FROM appointments a JOIN patients p ON a.patient_id = p.id
        ORDER BY a.appointment_date
    """)
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "patient": r[1], "clinic": r[2], "doctor": r[3], "date": r[4], "status": r[5]} for r in rows]

@app.put("/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE appointments SET status = 'cancelled'
        WHERE id = %s RETURNING patient_id
    """, (appointment_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Appointment not found")
    conn.commit()
    conn.close()
    cache.delete(f"appointments_{row[0]}")
    return {"message": f"Appointment {appointment_id} cancelled"}
