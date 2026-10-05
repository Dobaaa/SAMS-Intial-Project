import Constants from "expo-constants";
import { Platform } from "react-native";
import { api } from "./api";

// Expo Go (SDK 53+) can't load expo-notifications at all; real/dev builds can.
// Lazy require so Expo Go still runs the app (in-app banner + polling feed cover the demo).
const N: typeof import("expo-notifications") | null = Constants.executionEnvironment === "storeClient" ? null : require("expo-notifications");

N?.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }),
});

let deviceToken: string | null = null;

/** Ask permission and register the native FCM/APNs token with the backend. */
export async function registerPush() {
  if (!N) return;
  if (Platform.OS === "android") {
    await N.setNotificationChannelAsync("default", { name: "SAMS", importance: N.AndroidImportance.HIGH });
  }
  const perm = await N.requestPermissionsAsync();
  if (!perm.granted) return;
  try {
    const t = await N.getDevicePushTokenAsync();
    deviceToken = String(t.data);
    await api.post("/devices", { token: deviceToken, platform: Platform.OS });
  } catch {
    // no FCM yet (Firebase not configured) — the polling feed still delivers alerts
  }
}

export async function unregisterPush() {
  if (deviceToken) await api.delete("/devices", { params: { token: deviceToken } });
  deviceToken = null;
}

/** System banner for a notification the polling feed just saw (dev/fallback path;
 *  with real FCM the OS already showed the push). */
export async function showLocal(n: { title: string; body: string; agreement_id: string | null }) {
  await N?.scheduleNotificationAsync({
    content: { title: n.title, body: n.body.slice(0, 200), data: { agreement_id: n.agreement_id } },
    trigger: null,
  });
}

/** Tap on a system notification -> callback with its agreement id. */
export function onNotificationTap(cb: (agreementId: string) => void) {
  const sub = N?.addNotificationResponseReceivedListener((r) => {
    const id = r.notification.request.content.data?.agreement_id as string | undefined;
    if (id) cb(id);
  });
  return () => sub?.remove();
}
