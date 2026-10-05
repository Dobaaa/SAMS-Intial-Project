import React, { useEffect, useRef, useState } from "react";
import { Animated, Easing, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Notif, onNewNotification } from "./notifs";
import { C, F, R } from "./theme";

export const cleanTitle = (t: string) => t.replace(/^SAMS[:\s-]+/i, "");

/** In-app notification that drops in from the top and leaves by itself. */
export function Banner({ onOpen }: { onOpen: (agreementId: string) => void }) {
  const [n, setN] = useState<Notif | null>(null);
  const y = useRef(new Animated.Value(-160)).current;
  const top = useSafeAreaInsets().top;

  useEffect(() => onNewNotification(setN), []);
  useEffect(() => {
    if (!n) return;
    y.setValue(-160);
    Animated.spring(y, { toValue: 0, useNativeDriver: true, bounciness: 6, speed: 14 }).start();
    const t = setTimeout(() => Animated.timing(y, { toValue: -160, duration: 220, easing: Easing.in(Easing.cubic), useNativeDriver: true }).start(() => setN(null)), 5500);
    return () => clearTimeout(t);
  }, [n, y]);

  if (!n) return null;
  return (
    <Animated.View style={[s.wrap, { top: top + 8, transform: [{ translateY: y }] }]}>
      <Pressable
        onPress={() => {
          if (n.agreement_id) onOpen(n.agreement_id);
          setN(null);
        }}
        style={s.inner}
      >
        <View style={s.bar} />
        <View style={{ flex: 1, padding: 12 }}>
          <Text style={s.title} numberOfLines={1}>{cleanTitle(n.title)}</Text>
          <Text style={s.body} numberOfLines={2}>{n.body.replace(/\s+/g, " ")}</Text>
        </View>
      </Pressable>
    </Animated.View>
  );
}

const s = StyleSheet.create({
  wrap: { position: "absolute", left: 12, right: 12, elevation: 10, shadowColor: "#000", shadowOpacity: 0.25, shadowRadius: 10, shadowOffset: { width: 0, height: 4 } },
  inner: { flexDirection: "row", backgroundColor: C.steel, borderRadius: R, overflow: "hidden" },
  bar: { width: 5, backgroundColor: C.hivis },
  title: { color: "#fff", fontFamily: F.displayM, fontSize: 18 },
  body: { color: C.onSteel, fontFamily: F.body, marginTop: 2 },
});
