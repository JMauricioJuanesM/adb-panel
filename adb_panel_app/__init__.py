"""Panel de control ADB: apps, bloqueo de apps de Xiaomi, DNS privado, ADB por WiFi e instalación de APK/XAPK.

Capas:
  adb/         comandos al teléfono (sin interfaz).
  meta/        nombres e iconos de apps (Google Play, APK) y su caché.
  controller/  detección del teléfono y re-bloqueos automáticos.
  ui/          ventana principal (`panel.Panel`), una página por archivo en `ui/pages/` y el diálogo de desbloqueo.
"""
