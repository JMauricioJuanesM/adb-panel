#!/usr/bin/env python3
"""Panel de control ADB: apps, bloqueo de apps de Xiaomi, DNS privado, ADB por WiFi
e instalación de APK/XAPK.

Filosofía: bloquear es fácil (un clic); desbloquear cuesta un poquito: pide un motivo,
espera unos segundos para pensarlo, contraseña, y de preferencia es temporal
(se vuelve a bloquear solo). Todo desbloqueo queda en el historial.

Modos internos:
  adb_panel.py --apk-meta SERIAL PAQUETE   nombre/icono leídos del APK en el teléfono
  adb_panel.py --file-meta RUTA            nombre/paquete/versión/icono de un .apk/.xapk/.apks/.apkm
El código vive en el paquete `adb_panel_app/`.
"""
import json
import sys


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--apk-meta":
        from adb_panel_app.meta.apkinfo import apk_meta
        try:
            result = apk_meta(sys.argv[2], sys.argv[3])
        except Exception:  # noqa: BLE001
            result = {"name": None, "src": "none"}
        print(json.dumps(result, ensure_ascii=False))
    elif len(sys.argv) == 3 and sys.argv[1] == "--file-meta":
        from adb_panel_app.meta.apkinfo import file_meta
        try:
            result = file_meta(sys.argv[2])
        except Exception:  # noqa: BLE001
            result = {}
        print(json.dumps(result, ensure_ascii=False))
    else:
        from adb_panel_app.ui.panel import Panel
        Panel().mainloop()


if __name__ == "__main__":
    main()
