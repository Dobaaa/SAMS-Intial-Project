import React, { useEffect, useRef, useState } from "react";
import { AccessibilityInfo, Animated, Easing, Pressable, StyleProp, StyleSheet, Text, TextInput, TextInputProps, View, ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { C, F, R, statusColor } from "./theme";

export function useReduceMotion() {
  const [r, setR] = useState(false);
  useEffect(() => void AccessibilityInfo.isReduceMotionEnabled().then(setR), []);
  return r;
}

/** Tiny scale response so every tap visibly lands. */
export function Press({ onPress, style, children, disabled }: { onPress?: () => void; style?: StyleProp<ViewStyle>; children: React.ReactNode; disabled?: boolean }) {
  const v = useRef(new Animated.Value(1)).current;
  const to = (x: number) => Animated.spring(v, { toValue: x, useNativeDriver: true, speed: 50, bounciness: 0 }).start();
  return (
    <Pressable onPress={onPress} disabled={disabled} onPressIn={() => to(0.98)} onPressOut={() => to(1)}>
      <Animated.View style={[style, { transform: [{ scale: v }] }]}>{children}</Animated.View>
    </Pressable>
  );
}

/** List entrance: staggered rise, once per mount. */
export function Reveal({ index, children }: { index: number; children: React.ReactNode }) {
  const reduce = useReduceMotion();
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(v, { toValue: 1, duration: reduce ? 0 : 300, delay: reduce ? 0 : Math.min(index, 8) * 50, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start();
  }, [v, index, reduce]);
  return <Animated.View style={{ opacity: v, transform: [{ translateY: v.interpolate({ inputRange: [0, 1], outputRange: [16, 0] }) }] }}>{children}</Animated.View>;
}

export type Stage = "done" | "current" | "todo" | "returned";
const stageColor: Record<Stage, string> = { done: C.ok, current: C.hivis, todo: C.line, returned: C.bad };

/** The approval chain as four storeys: Accounts, PD, OM, GM. */
export function Scaffold({ stages, labels, large, animate }: { stages: Stage[]; labels?: string[]; large?: boolean; animate?: boolean }) {
  const reduce = useReduceMotion();
  const vals = useRef(stages.map(() => new Animated.Value(animate ? 0 : 1))).current;
  useEffect(() => {
    if (!animate || reduce) return vals.forEach((v) => v.setValue(1));
    Animated.stagger(110, vals.map((v) => Animated.timing(v, { toValue: 1, duration: 380, easing: Easing.out(Easing.back(1.4)), useNativeDriver: true }))).start();
  }, [animate, reduce, vals]);
  return (
    <View style={{ flexDirection: "row", gap: 4 }}>
      {stages.map((s, i) => (
        <View key={i} style={{ flex: 1 }}>
          <Animated.View
            style={{
              height: large ? 14 : 6,
              backgroundColor: stageColor[s],
              borderRadius: 2,
              opacity: vals[i],
              transform: [{ scaleY: vals[i].interpolate({ inputRange: [0, 1], outputRange: [0.2, 1] }) }],
            }}
          />
          {large && labels && <Text style={[s2.lbl, s === "current" && { color: C.hivis, fontFamily: F.bodyB }, s === "done" && { color: C.ok }, s === "returned" && { color: C.bad }]}>{labels[i]}</Text>}
        </View>
      ))}
    </View>
  );
}

export const Badge = ({ status, label, onDark }: { status: string; label: string; onDark?: boolean }) => (
  <View style={[s2.badge, { backgroundColor: onDark ? "#FFFFFF22" : statusColor(status) + "1A" }]}>
    <View style={[s2.dot, { backgroundColor: onDark ? "#fff" : statusColor(status) }]} />
    <Text style={[s2.badgeT, { color: onDark ? "#fff" : statusColor(status) }]}>{label}</Text>
  </View>
);

export function Skeleton({ h = 120 }: { h?: number }) {
  const v = useRef(new Animated.Value(0.45)).current;
  useEffect(() => {
    const a = Animated.loop(Animated.sequence([Animated.timing(v, { toValue: 1, duration: 700, useNativeDriver: true }), Animated.timing(v, { toValue: 0.45, duration: 700, useNativeDriver: true })]));
    a.start();
    return () => a.stop();
  }, [v]);
  return <Animated.View style={{ height: h, backgroundColor: C.line, borderRadius: R, opacity: v }} />;
}
export const SkeletonList = () => (
  <View style={{ padding: 12, gap: 10 }}>
    {[0, 1, 2, 3].map((i) => <Skeleton key={i} h={132} />)}
  </View>
);

export const Center = ({ children }: { children: React.ReactNode }) => <View style={s2.center}>{children}</View>;
export const Loading = () => <SkeletonList />;
export const Empty = ({ title, hint }: { title: string; hint?: string }) => (
  <Center>
    <Text style={s2.emptyT}>{title}</Text>
    {!!hint && <Text style={s2.emptyH}>{hint}</Text>}
  </Center>
);
export const ErrorView = ({ msg, retry }: { msg: string; retry: () => void }) => (
  <Center>
    <Text style={s2.emptyT}>{msg}</Text>
    <Text style={s2.emptyH}>Check your connection, then try again.</Text>
    <View style={{ marginTop: 16, alignSelf: "stretch" }}><Button title="Try again" onPress={retry} /></View>
  </Center>
);

export const Button = ({ title, onPress, disabled, tone = "steel" }: { title: string; onPress: () => void; disabled?: boolean; tone?: "steel" | "ghost" | "light" }) => (
  <Press onPress={onPress} disabled={disabled} style={[s2.btn, tone === "ghost" && s2.btnGhost, tone === "light" && { backgroundColor: "#fff" }, disabled && { opacity: 0.45 }]}>
    <Text style={[s2.btnT, tone !== "steel" && { color: C.steel }]}>{title}</Text>
  </Press>
);

export const Panel = ({ title, children }: { title?: string; children: React.ReactNode }) => (
  <View style={s2.panel}>
    {!!title && <Text style={s2.panelT}>{title}</Text>}
    {children}
  </View>
);

export const Field = (p: TextInputProps) => <TextInput placeholderTextColor={C.muted} {...p} style={[s2.field, p.style]} />;

/** Steel header used by every tab screen. */
export function ScreenHeader({ title, sub, children }: { title: string; sub?: string; children?: React.ReactNode }) {
  const top = useSafeAreaInsets().top;
  return (
    <View style={[s2.header, { paddingTop: top + 10 }]}>
      <Text style={s2.hTitle}>{title}</Text>
      {!!sub && <Text style={s2.hSub}>{sub}</Text>}
      {children}
    </View>
  );
}

export const fmtDate = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";

export function timeAgo(iso: string) {
  const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (m < 1) return "Just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

const s2 = StyleSheet.create({
  lbl: { fontFamily: F.bodyM, fontSize: 11, color: C.muted, marginTop: 6 },
  badge: { alignSelf: "flex-start", flexDirection: "row", alignItems: "center", gap: 6, borderRadius: 4, paddingHorizontal: 8, paddingVertical: 3 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  badgeT: { fontFamily: F.bodyB, fontSize: 12 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 32 },
  emptyT: { fontFamily: F.displayM, fontSize: 22, color: C.ink, textAlign: "center" },
  emptyH: { fontFamily: F.body, color: C.muted, marginTop: 4, textAlign: "center" },
  btn: { backgroundColor: C.steel, borderRadius: R, paddingVertical: 14, alignItems: "center" },
  btnGhost: { backgroundColor: "transparent", borderWidth: 1, borderColor: C.steel },
  btnT: { color: "#fff", fontFamily: F.bodyB, fontSize: 16 },
  panel: { backgroundColor: C.panel, borderRadius: R, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: C.line },
  panelT: { fontFamily: F.displayM, fontSize: 20, color: C.ink, marginBottom: 6 },
  field: { backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: R, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, fontFamily: F.body, color: C.ink },
  header: { backgroundColor: C.steel, paddingHorizontal: 16, paddingBottom: 14 },
  hTitle: { fontFamily: F.display, fontSize: 38, color: "#fff", letterSpacing: 0.3 },
  hSub: { fontFamily: F.body, color: C.onSteel, marginTop: -2, marginBottom: 6 },
});
