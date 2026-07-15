# ChatterBox (Kivy) → APK build instructions

Real chat prototype. Two installs join the same "room" and message each
other live over the public `test.mosquitto.org` MQTT broker — no backend
to host.

## 1. Test it on your computer first (fastest way to check it works)
```bash
pip install kivy paho-mqtt
python main.py
```
Enter a name and room, hit "Join room" — you should see the chat screen.
Open a second terminal and run it again with a different name, same room,
to see messages go both ways.

## 2. Build the actual APK
Buildozer needs Linux, and WSL2 is broken on this machine, so this builds
on GitHub's servers instead via `.github/workflows/build-apk.yml`:

1. Push this folder to a GitHub repo (contents at repo root, not nested)
2. Actions tab → runs automatically on push to `main` (or **Run workflow**)
3. ~15-25 min on first run (downloads Android SDK/NDK/toolchain)
4. Open the finished run → **Artifacts** → download `chatterbox-apk`

## 3. Install it on your phone
Unzip the artifact, sideload the `.apk` (enable "install from unknown
sources" if prompted). Do this on two phones to actually test messaging.

## Files in this project
- `main.py` — the app (Kivy UI, MQTT chat, online presence)
- `buildozer.spec` — build config, same base settings as the World Clock
  build: `android.api = 33`, `android.minapi = 21`, `android.ndk = 25b`,
  `android.archs = arm64-v8a,armeabi-v7a`, `android.accept_sdk_license = True`
- `.github/workflows/build-apk.yml` — CI build, pinned to `ubuntu-22.04`
  (24.04 breaks buildozer's autotools/libffi step)

## Who's online
A status line under the room name shows who's currently in. Clean exits
publish "offline" immediately; crashes/force-closes are caught by MQTT's
last-will feature, so the broker marks them offline automatically.

## Known limitations (it's a prototype)
- No message history — close the app, it's gone
- No auth — anyone with the room name can join
- Public broker — no privacy guarantees, don't send anything sensitive

## Want to customize?
- Swap the broker for a private one (e.g. HiveMQ Cloud free tier)
- Add local SQLite message history
- Add a simple username/password gate

Just say the word and I'll wire it in.
