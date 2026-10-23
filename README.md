# Panel ADB

Panel de escritorio (Tk) para controlar el teléfono por ADB: bloquear/desactivar apps, bloqueo
de apps de Xiaomi, DNS privado (filtro de sitios), ADB por WiFi e instalación de
.apk/.xapk/.apks/.apkm.

Filosofía: **bloquear es fácil, desbloquear cuesta**: pide un motivo, una espera para pensarlo,
contraseña, y de preferencia es temporal (se vuelve a bloquear solo). Todo queda en el historial.

## Uso

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install pyaxmlparser       # nombres/iconos leídos de los APK (Pillow viene del sistema)
.venv/bin/python adb_panel.py
```

## Datos personales

Nada personal vive en el repositorio:

- `~/.config/adb-panel/config.json`: estado, contraseña (hash), apps bloqueadas, historial.
- `~/.config/adb-panel/defaults.json`: tus valores por defecto personales (p. ej. tu servidor de
  NextDNS). Ver `defaults.example.json`.

## Estructura

```
adb_panel.py            punto de entrada (+ modos internos --apk-meta / --file-meta)
adb_panel_app/
  paths.py, theme.py    rutas y paleta
  config.py             valores por defecto, carga y guardado
  utils.py              notificaciones y formatos
  adb/                  comandos al teléfono: cliente, operaciones, instalador
  meta/                 nombres e iconos de apps (Google Play / APK) y su caché
  controller/           detección del teléfono y re-bloqueos automáticos
  ui/
    panel.py            ventana principal: combina las páginas y controladores (mixins)
    pages/              una página por archivo: inicio, apps, instalar, dns, ajustes
    gate.py             diálogo de desbloqueo lento
    styles.py           estilos ttk
```
