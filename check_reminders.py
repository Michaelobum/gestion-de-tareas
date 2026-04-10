#!/usr/bin/env python3
"""
check_reminders.py
Revisa tareas.json, envía emails para recordatorios vencidos y marca reminderSent=True.
Requiere variables de entorno: EMAILJS_SERVICE_ID, EMAILJS_TEMPLATE_ID,
EMAILJS_PUBLIC_KEY, EMAILJS_PRIVATE_KEY, RECIPIENT_EMAIL
"""

import json
import os
import sys
import requests
from datetime import datetime, timezone, timedelta

TASKS_FILE = "tareas.json"

# ── Cargar tareas ──────────────────────────────────────────────────────────────
if not os.path.exists(TASKS_FILE):
    print(f"⚠️  {TASKS_FILE} no encontrado — nada que revisar.")
    sys.exit(0)

with open(TASKS_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

tasks   = data.get("tasks", [])
now_utc = datetime.now(timezone.utc)
changed = False

# ── Configuración EmailJS ──────────────────────────────────────────────────────
SERVICE_ID   = os.environ.get("EMAILJS_SERVICE_ID",  "")
TEMPLATE_ID  = os.environ.get("EMAILJS_TEMPLATE_ID", "")
PUBLIC_KEY   = os.environ.get("EMAILJS_PUBLIC_KEY",  "")
PRIVATE_KEY  = os.environ.get("EMAILJS_PRIVATE_KEY", "")
TO_EMAIL     = os.environ.get("RECIPIENT_EMAIL",      "")

if not all([SERVICE_ID, TEMPLATE_ID, PUBLIC_KEY, TO_EMAIL]):
    print("❌ Faltan variables de entorno de EmailJS. Configura los secrets del repo.")
    sys.exit(1)


def send_email(task: dict, label: str) -> bool:
    """Envía el recordatorio vía EmailJS REST API."""
    due_str = ""
    if task.get("dueDate"):
        try:
            due_dt  = datetime.fromisoformat(task["dueDate"].replace("Z", "+00:00"))
            due_str = due_dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            due_str = task["dueDate"]

    payload = {
        "service_id":   SERVICE_ID,
        "template_id":  TEMPLATE_ID,
        "user_id":      PUBLIC_KEY,
        "accessToken":  PRIVATE_KEY,
        "template_params": {
            "to_email":       TO_EMAIL,
            "task_title":     task.get("title", ""),
            "task_priority":  task.get("priority", ""),
            "task_due":       due_str,
            "task_status":    task.get("status", ""),
            "reminder_label": label,
        },
    }

    try:
        res = requests.post(
            "https://api.emailjs.com/api/v1.0/email/send",
            json=payload,
            timeout=15,
        )
        if res.status_code == 200:
            print(f"  ✅ Email enviado → {task['title']}")
            return True
        else:
            print(f"  ❌ Error EmailJS {res.status_code}: {res.text}")
            return False
    except requests.RequestException as e:
        print(f"  ❌ Excepción al enviar email: {e}")
        return False


# ── Revisar cada tarea ─────────────────────────────────────────────────────────
print(f"🔍 Revisando {len(tasks)} tarea(s) — {now_utc.strftime('%Y-%m-%d %H:%M UTC')}")

for task in tasks:
    if task.get("reminderSent"):
        continue
    if task.get("status") == "Terminada":
        continue
    if not task.get("dueDate"):
        continue

    reminder_minutes = task.get("reminderMinutes") or 0

    try:
        due_dt = datetime.fromisoformat(task["dueDate"].replace("Z", "+00:00"))
    except Exception:
        continue

    trigger_dt  = due_dt - timedelta(minutes=reminder_minutes)
    window_end  = trigger_dt + timedelta(minutes=35)  # ventana de 35 min (> cron interval)

    if now_utc >= trigger_dt and now_utc <= window_end:
        mins_left = int((due_dt - now_utc).total_seconds() / 60)
        if mins_left <= 0:
            label = "¡Tarea vencida!"
        elif mins_left < 60:
            label = f"Vence en {mins_left} min"
        else:
            label = f"Vence en {round(mins_left / 60, 1)} h"

        print(f"⏰ Recordatorio: \"{task['title']}\" — {label}")
        ok = send_email(task, label)
        if ok:
            task["reminderSent"] = True
            changed = True

# ── Guardar cambios ────────────────────────────────────────────────────────────
if changed:
    data["updatedAt"] = now_utc.isoformat()
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 {TASKS_FILE} actualizado con reminderSent=True")
else:
    print("ℹ️  Sin recordatorios pendientes.")
