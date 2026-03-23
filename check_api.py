"""
check_api.py — Diagnóstico rápido de la API de Mercado Público

Uso:
    python check_api.py
    python check_api.py LIC-123456-001   # prueba una licitación concreta

Resultado:
    ✅ API OPERATIVA   → el enriquecimiento debería funcionar
    ❌ API CAÍDA       → no es culpa nuestra, esperemos a que vuelva
"""

import sys
import time
import requests
from dotenv import load_dotenv
import os

# ---------------------------------------------------------------------------
load_dotenv()
TICKET = os.getenv("LICIT_MERCADO_PUBLICO_TICKET", "")
BASE   = "https://api.mercadopublico.cl/servicios/v1/publico"
TIMEOUT = 15
# ---------------------------------------------------------------------------

def check(url, params, etiqueta):
    inicio = time.time()
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT,
                         headers={"User-Agent": "MP-check_api/1.0"})
        elapsed = time.time() - inicio
        return r.status_code, elapsed, None
    except requests.exceptions.Timeout:
        elapsed = time.time() - inicio
        return None, elapsed, f"SIN RESPUESTA tras {elapsed:.0f}s (timeout)"
    except requests.exceptions.ConnectionError as e:
        elapsed = time.time() - inicio
        return None, elapsed, f"ERROR DE CONEXIÓN: {e}"
    except Exception as e:
        elapsed = time.time() - inicio
        return None, elapsed, f"ERROR INESPERADO: {e}"


def main():
    codigo_licitacion = sys.argv[1] if len(sys.argv) > 1 else None

    print("=" * 60)
    print("  DIAGNÓSTICO API — Mercado Público")
    print("=" * 60)

    if not TICKET:
        print("\n⚠️  TICKET no encontrado en .env (LICIT_MERCADO_PUBLICO_TICKET)")
        print("   El ticket es obligatorio para consultas de detalle.\n")
    else:
        print(f"\n  Ticket : {TICKET[:8]}...{TICKET[-4:]}")

    # ── Test 1: sin ticket (consulta pública general) ────────────────────────
    print(f"\n[1/2] Consulta general (sin ticket) ...")
    url1 = f"{BASE}/licitaciones.json"
    params1 = {"estado": "publicada", "cantidad": "1"}
    code, t, err = check(url1, params1, "general")

    if err:
        print(f"      ❌  {err}")
        api_general_ok = False
    else:
        icon = "✅" if code == 200 else "⚠️ "
        print(f"      {icon}  HTTP {code}  ({t:.1f}s)")
        api_general_ok = (code == 200)

    # ── Test 2: con ticket ───────────────────────────────────────────────────
    print(f"\n[2/2] Consulta con ticket ...")
    if not TICKET:
        print("      ⏭️  Saltado — no hay ticket configurado")
        api_ticket_ok = False
    else:
        params2 = {"ticket": TICKET, "estado": "publicada", "cantidad": "1"}
        code2, t2, err2 = check(url1, params2, "ticket")

        if err2:
            print(f"      ❌  {err2}")
            api_ticket_ok = False
        else:
            icon = "✅" if code2 == 200 else "⚠️ "
            print(f"      {icon}  HTTP {code2}  ({t2:.1f}s)")
            api_ticket_ok = (code2 == 200)

    # ── Test 3 (opcional): licitación concreta ───────────────────────────────
    if codigo_licitacion and TICKET:
        print(f"\n[+]  Detalle licitación '{codigo_licitacion}' ...")
        url3 = f"{BASE}/licitaciones/{codigo_licitacion}.json"
        params3 = {"ticket": TICKET}
        code3, t3, err3 = check(url3, params3, "detalle")
        if err3:
            print(f"      ❌  {err3}")
        else:
            icon = "✅" if code3 == 200 else "⚠️ "
            print(f"      {icon}  HTTP {code3}  ({t3:.1f}s)")

    # ── Veredicto ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if api_ticket_ok:
        print("  ✅  API OPERATIVA  → el enriquecimiento DEBERÍA funcionar")
        print("      Si falla, es un problema de nuestro código o del ticket.")
    elif api_general_ok and not api_ticket_ok:
        print("  ⚠️   API DEGRADA   → responde sin ticket pero falla con ticket")
        if TICKET:
            print("      Verificar que el ticket no esté vencido o revocado.")
        else:
            print("      Configurar LICIT_MERCADO_PUBLICO_TICKET en .env")
    else:
        print("  ❌  API CAÍDA      → no responde en absoluto")
        print("      No es culpa nuestra. Esperar a que Mercado Público la restaure.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
