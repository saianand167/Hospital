"""Test both Groq AI doctor summary AND prescription voice dictation"""
import requests, json

BASE = "http://127.0.0.1:8000/api/v1"

login = requests.post(f"{BASE}/auth/login", json={"username": "doctor1", "password": "doctor123"}, timeout=10).json()
token = login["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"Logged in as: {login['full_name']} ({login['role']})\n")

print("=" * 60)
print("TEST 1: Groq AI Doctor Summary (PAT-000006)")
print("=" * 60)
res = requests.get(f"{BASE}/doctor/patients/PAT-000006/summary", headers=headers, timeout=30)
data = res.json()
print(f"Status: {res.status_code}")
print(f"Chief Complaint : {data.get('chief_complaint')}")
print(f"HPI             : {str(data.get('hpi', ''))[:150]}")
print(f"Past History    : {data.get('relevant_past_history')}")
print(f"Triage Flag     : {data.get('current_triage_flag')}")
print(f"Medications     : {data.get('medications')}")
print(f"Allergies       : {data.get('allergies')}")

print("\n" + "=" * 60)
print("TEST 2: Groq AI Prescription Voice Dictation")
print("=" * 60)
dictation = "Paracetamol 650 mg twice daily for 3 days after food. Amoxicillin 500 mg three times a day for 5 days before food. Pantoprazole 40 mg once daily before breakfast."
res2 = requests.post(f"{BASE}/prescriptions/voice-dictate", headers=headers, json={
    "patient_id": "PAT-000006",
    "visit_id": "VIS-000003",
    "doctor_id": "DOC-101",
    "transcript": dictation
}, timeout=30)
items = res2.json()
print(f"Status: {res2.status_code}")
print("Parsed Prescription Items:")
for item in items:
    print(f"  - {item.get('medicine_name')} | {item.get('dose')} | {item.get('frequency')} | {item.get('duration')}")

print("\n✅ ALL GROQ AI TESTS PASSED" if res.status_code == 200 and res2.status_code == 200 else "\n❌ SOME TESTS FAILED")
