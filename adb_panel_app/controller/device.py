"""Detección del teléfono (cable/WiFi) y lo que pasa al conectarlo."""
import threading
import time

from ..adb import client
from ..adb.client import is_wifi, list_devices
from ..adb.device import enable_wifi_adb, get_applock, get_dns, phone_model, wifi_connect
from ..config import save_config


class DeviceController:
    def poll_device(self):
        if self.busy:  # p. ej. `adb tcpip` reinicia la conexión: no interpretar eso como desconexión
            self.after(1500, self.poll_device)
            return

        def work():
            devs = list_devices()
            ready = [s for s, st in devs if st == "device"]
            if not ready and self.cfg["wifi_auto"] and self.cfg.get("wifi_ip") \
                    and time.time() - self.last_wifi_try > 10:
                self.last_wifi_try = time.time()
                wifi_connect(self.cfg["wifi_ip"])
                devs = list_devices()
            return devs

        def done(devs):
            ready = [s for s, st in devs if st == "device"]
            usb = next((s for s in ready if not is_wifi(s)), None)
            wifi = next((s for s in ready if is_wifi(s)), None)
            was, was_usb = self.device, self.usb_serial
            self.device = usb or wifi
            self.usb_serial = usb
            self.wifi_connected = bool(wifi)
            client.set_serial(self.device)
            if not self.device:
                self.packages = {}
                self.state_cache.update(dns=None, applock=None)
                if any(st == "unauthorized" for _, st in devs):
                    self.set_status("Acepta la depuración USB en el teléfono.")
            if self.device and not was:
                self.on_connect(usb_new=bool(usb))
            elif usb and not was_usb:
                self.on_usb()
            else:
                self.process_relocks()
            if self.current_page == "inicio":
                self.render_home()
            else:
                self.render_connection()
            self.after(3000, self.poll_device)

        threading.Thread(target=lambda: self.after(0, done, work()), daemon=True).start()

    def on_connect(self, usb_new):
        apply = self.cfg["auto_apply_on_connect"]
        wifi = usb_new and self.cfg["wifi_auto"]
        usb = self.usb_serial
        due = [r for r in self.cfg["relocks"] if r["at"] <= time.time()]

        def work():
            msgs = []
            self.state_cache["model"] = phone_model()
            if wifi:
                ok, out, ip = enable_wifi_adb(usb)
                if ip:
                    self.cfg["wifi_ip"] = ip
                msgs.append(f"WiFi listo ({ip})" if ok else f"WiFi no: {out}")
            if due:
                self._relock_work(due)
            if apply:
                msgs.append(self._apply_blocks_work())
            return msgs

        def done(msgs):
            if due:
                self._relock_done(due)
            save_config(self.cfg)
            self.set_status(" · ".join(msgs) or "Teléfono conectado.")
            self.load_packages()
            self.after(200, self.refresh_states)

        self.run_bg(work, done, "Teléfono conectado: preparando…")

    def on_usb(self):
        # Ya estaba conectado por WiFi y ahora llegó el cable: refresca el modo WiFi si hace falta.
        if self.cfg["wifi_auto"]:
            usb = self.usb_serial
            self.run_bg(lambda: enable_wifi_adb(usb), lambda r: self.set_status(
                f"ADB por WiFi listo ({r[2]})." if r[0] else f"WiFi: {r[1]}"), "Revisando ADB por WiFi…")

    def refresh_states(self):
        if not self.device:
            return

        def done(res):
            self.state_cache["dns"], self.state_cache["applock"] = res
            self.show_dns(res[0])
            self.render_home()
            self.set_status("Estado leído.")

        self.run_bg(lambda: (get_dns(), get_applock()), done, "Leyendo estado…")
