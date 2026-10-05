# SAMS Mobile (read-only companion app)

Expo + TypeScript. See `../docs/mobile-app-plan.md` for scope, status and the push-notification design.

```bash
npm install
EXPO_PUBLIC_API_URL=https://<host>/api npx expo start        # default http://10.0.2.2:8000/api (Android emulator -> host)
```

- Expo Go works for everything except OS-level push (SDK 53+ removed it); alerts still arrive via the polling feed + in-app banner.
- Real push: EAS dev/production build + Firebase (`google-services.json`, APNs key) + `FIREBASE_CREDENTIALS_PATH` on the backend.
