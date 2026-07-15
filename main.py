"""
ChatterBox - a real, working chat prototype built on Kivy + MQTT.

Two people install this APK, enter the same "room" name, and their
messages travel over the public test.mosquitto.org MQTT broker to
each other in real time. No backend to host, no account needed.

For a real product you'd swap test.mosquitto.org for your own broker
(it's a public sandbox - don't send anything private through it).
"""

import json
import time
import threading
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import StringProperty

import paho.mqtt.client as mqtt

BROKER_HOST = "test.mosquitto.org"
BROKER_PORT = 1883
TOPIC_PREFIX = "chatterbox/room/"
PRESENCE_SUFFIX = "/presence/"

KV = """
ScreenManager:
    LoginScreen:
    ChatScreen:

<LoginScreen>:
    name: "login"
    BoxLayout:
        orientation: "vertical"
        padding: dp(30)
        spacing: dp(16)
        canvas.before:
            Color:
                rgba: 0.09, 0.09, 0.12, 1
            Rectangle:
                pos: self.pos
                size: self.size

        Widget:
            size_hint_y: 0.3

        Label:
            text: "ChatterBox"
            font_size: "32sp"
            bold: True
            size_hint_y: None
            height: dp(60)

        Label:
            text: "enter a name and a room to join"
            color: 0.6, 0.6, 0.65, 1
            size_hint_y: None
            height: dp(24)

        Widget:
            size_hint_y: 0.1

        TextInput:
            id: username
            hint_text: "your name"
            multiline: False
            size_hint_y: None
            height: dp(48)
            padding: dp(12), dp(12)

        TextInput:
            id: room
            hint_text: "room name (both people use the same one)"
            multiline: False
            size_hint_y: None
            height: dp(48)
            padding: dp(12), dp(12)

        Label:
            id: status
            text: ""
            color: 0.9, 0.4, 0.4, 1
            size_hint_y: None
            height: dp(24)

        Button:
            text: "Join room"
            size_hint_y: None
            height: dp(52)
            background_color: 0.25, 0.55, 0.95, 1
            on_release: app.join_room(username.text, room.text)

        Widget:

<ChatScreen>:
    name: "chat"
    BoxLayout:
        orientation: "vertical"
        canvas.before:
            Color:
                rgba: 0.09, 0.09, 0.12, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            size_hint_y: None
            height: dp(48)
            padding: dp(12), 0
            canvas.before:
                Color:
                    rgba: 0.14, 0.14, 0.18, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Label:
                text: "room: " + app.room_name
                bold: True
            Button:
                text: "leave"
                size_hint_x: None
                width: dp(70)
                on_release: app.leave_room()

        BoxLayout:
            size_hint_y: None
            height: dp(28)
            padding: dp(12), 0
            canvas.before:
                Color:
                    rgba: 0.12, 0.12, 0.15, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Label:
                id: online_label
                text: "online: just you"
                font_size: "12sp"
                color: 0.4, 0.85, 0.5, 1
                halign: "left"
                valign: "middle"
                text_size: self.size

        ScrollView:
            id: scroll
            do_scroll_x: False
            BoxLayout:
                id: message_box
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: dp(10)
                spacing: dp(8)

        BoxLayout:
            size_hint_y: None
            height: dp(56)
            padding: dp(8)
            spacing: dp(8)
            TextInput:
                id: msg_input
                hint_text: "message"
                multiline: False
                on_text_validate: app.send_message(self.text); self.text = ""
            Button:
                text: "Send"
                size_hint_x: None
                width: dp(80)
                background_color: 0.25, 0.55, 0.95, 1
                on_release: app.send_message(msg_input.text); msg_input.text = ""
"""


class LoginScreen(Screen):
    pass


class ChatScreen(Screen):
    pass


class ChatterBoxApp(App):
    room_name = StringProperty("")
    username = StringProperty("")

    def build(self):
        self.client = None
        self.connected = False
        self.online_users = {}  # username -> last seen timestamp
        return Builder.load_string(KV)

    def join_room(self, username, room):
        username = username.strip()
        room = room.strip()
        login_screen = self.root.get_screen("login")

        if not username or not room:
            login_screen.ids.status.text = "enter both a name and a room"
            return

        self.username = username
        self.room_name = room
        login_screen.ids.status.text = "connecting..."

        threading.Thread(target=self._connect_mqtt, daemon=True).start()

    def _connect_mqtt(self):
        try:
            client = mqtt.Client()
            client.on_connect = self._on_connect
            client.on_message = self._on_message

            # last will: if we vanish without a clean disconnect (crash,
            # force-close, connection drop), the broker auto-publishes this
            # "offline" message on our behalf, retained so late joiners see it
            presence_topic = TOPIC_PREFIX + self.room_name + PRESENCE_SUFFIX + self.username
            will_payload = json.dumps({"user": self.username, "status": "offline"})
            client.will_set(presence_topic, payload=will_payload, qos=1, retain=True)

            client.connect(BROKER_HOST, BROKER_PORT, keepalive=30)
            self.client = client
            client.loop_start()
        except Exception as e:
            Clock.schedule_once(lambda dt: self._connect_failed(str(e)))

    def _connect_failed(self, error):
        login_screen = self.root.get_screen("login")
        login_screen.ids.status.text = f"connection failed: {error}"

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            topic = TOPIC_PREFIX + self.room_name
            presence_wildcard = TOPIC_PREFIX + self.room_name + PRESENCE_SUFFIX + "+"
            client.subscribe(topic)
            client.subscribe(presence_wildcard)

            my_presence_topic = TOPIC_PREFIX + self.room_name + PRESENCE_SUFFIX + self.username
            online_payload = json.dumps({"user": self.username, "status": "online"})
            client.publish(my_presence_topic, online_payload, qos=1, retain=True)

            self.connected = True
            Clock.schedule_once(lambda dt: self._enter_chat())
        else:
            Clock.schedule_once(
                lambda dt: self._connect_failed(f"broker returned code {rc}")
            )

    def _enter_chat(self):
        self.root.current = "chat"
        self._add_message("system", f"joined room '{self.room_name}'", system=True)

    def leave_room(self):
        if self.client:
            presence_topic = TOPIC_PREFIX + self.room_name + PRESENCE_SUFFIX + self.username
            offline_payload = json.dumps({"user": self.username, "status": "offline"})
            # clean, explicit goodbye (the last-will only fires on unclean drops)
            self.client.publish(presence_topic, offline_payload, qos=1, retain=True)
            time.sleep(0.2)  # give the publish a moment to leave before we disconnect
            self.client.loop_stop()
            self.client.disconnect()
            self.client = None
        self.connected = False
        self.online_users = {}
        chat_screen = self.root.get_screen("chat")
        chat_screen.ids.message_box.clear_widgets()
        chat_screen.ids.online_label.text = "online: just you"
        self.root.current = "login"

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return

        presence_prefix = TOPIC_PREFIX + self.room_name + PRESENCE_SUFFIX
        if msg.topic.startswith(presence_prefix):
            Clock.schedule_once(lambda dt: self._handle_presence(payload))
        else:
            Clock.schedule_once(
                lambda dt: self._add_message(payload.get("user", "?"), payload.get("text", ""))
            )

    def _handle_presence(self, payload):
        user = payload.get("user")
        status = payload.get("status")
        if not user:
            return

        was_online = user in self.online_users
        if status == "online":
            self.online_users[user] = time.time()
            if not was_online and user != self.username:
                self._add_message("system", f"{user} joined", system=True)
        else:
            self.online_users.pop(user, None)
            if was_online and user != self.username:
                self._add_message("system", f"{user} left", system=True)

        self._refresh_online_label()

    def _refresh_online_label(self):
        chat_screen = self.root.get_screen("chat")
        others = [u for u in self.online_users if u != self.username]
        if others:
            text = "online: you, " + ", ".join(sorted(others))
        else:
            text = "online: just you"
        chat_screen.ids.online_label.text = text

    def send_message(self, text):
        text = text.strip()
        if not text or not self.connected or not self.client:
            return
        payload = json.dumps({
            "user": self.username,
            "text": text,
            "ts": time.time(),
        })
        topic = TOPIC_PREFIX + self.room_name
        self.client.publish(topic, payload)
        # show our own message immediately too
        self._add_message(self.username, text, mine=True)

    def _add_message(self, user, text, mine=False, system=False):
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.metrics import dp

        chat_screen = self.root.get_screen("chat")
        box = chat_screen.ids.message_box

        row = BoxLayout(size_hint_y=None, padding=(dp(4), dp(2)))
        if system:
            lbl = Label(
                text=f"[i]{text}[/i]",
                markup=True,
                color=(0.5, 0.5, 0.55, 1),
                size_hint_y=None,
                font_size="12sp",
            )
        else:
            stamp = datetime.now().strftime("%H:%M")
            prefix = "you" if mine else user
            lbl = Label(
                text=f"[b]{prefix}[/b]  [size=10sp][color=888888]{stamp}[/color][/size]\n{text}",
                markup=True,
                color=(0.95, 0.95, 0.95, 1) if not mine else (0.6, 0.85, 1, 1),
                size_hint_y=None,
                halign="left",
                valign="top",
            )
        lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1] + dp(10)))
        row.bind(minimum_height=row.setter("height"))
        row.add_widget(lbl)
        box.add_widget(row)

        # auto-scroll to bottom
        Clock.schedule_once(lambda dt: setattr(chat_screen.ids.scroll, "scroll_y", 0), 0.05)


if __name__ == "__main__":
    ChatterBoxApp().run()
