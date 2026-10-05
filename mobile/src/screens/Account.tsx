import Constants from "expo-constants";
import React from "react";
import { Alert, ScrollView, StyleSheet, Text, View } from "react-native";
import { API_URL } from "../api";
import { useAuth } from "../auth";
import { useNotifications } from "../notifs";
import { C, F } from "../theme";
import { Button, Panel, ScreenHeader } from "../ui";

const ROLES: Record<string, string> = { admin: "Admin", project_director: "Project Director", accounts: "Accounts", operation_manager: "Operation Manager", gm: "General Manager" };

const Row = ({ k, v }: { k: string; v: string }) => (
  <View style={s.row}>
    <Text style={s.k}>{k}</Text>
    <Text style={s.v} numberOfLines={2}>{v}</Text>
  </View>
);

export default function Account() {
  const { user, logout } = useAuth();
  const { data } = useNotifications();
  const initials = (user?.name ?? "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  const host = API_URL.replace(/^https?:\/\//, "").replace(/\/api$/, "");

  const confirmSignOut = () =>
    Alert.alert("Sign out?", "You'll stop receiving notifications on this phone.", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign out", style: "destructive", onPress: () => void logout() },
    ]);

  return (
    <View style={{ flex: 1, backgroundColor: C.concrete }}>
      <ScreenHeader title="Account">
        <View style={s.hero}>
          <View style={s.avatar}><Text style={s.initials}>{initials}</Text></View>
          <View style={{ flex: 1 }}>
            <Text style={s.name} numberOfLines={1}>{user?.name}</Text>
            <Text style={s.role}>{ROLES[user?.role ?? ""] ?? user?.role}</Text>
          </View>
        </View>
      </ScreenHeader>
      <ScrollView contentContainerStyle={{ padding: 12 }}>
        <Panel title="Profile">
          <Row k="Email" v={user?.email ?? "—"} />
          <Row k="Unread alerts" v={String(data?.unread ?? 0)} />
        </Panel>
        <Panel title="About this app">
          <Row k="Version" v={Constants.expoConfig?.version ?? "1.0.0"} />
          <Row k="Server" v={host} />
          <Text style={s.note}>This app is read-only. Editing, comments and approvals stay on the SAMS web app.</Text>
        </Panel>
        <Button title="Sign out" tone="ghost" onPress={confirmSignOut} />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  hero: { flexDirection: "row", alignItems: "center", gap: 14, marginTop: 8 },
  avatar: { width: 56, height: 56, borderRadius: 6, backgroundColor: C.slate, borderWidth: 1, borderColor: C.slateLine, alignItems: "center", justifyContent: "center" },
  initials: { fontFamily: F.display, fontSize: 26, color: "#fff" },
  name: { fontFamily: F.displayM, fontSize: 24, color: "#fff" },
  role: { fontFamily: F.bodyM, color: C.hivis },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 10, borderTopWidth: 1, borderColor: C.line, gap: 16 },
  k: { fontFamily: F.body, color: C.muted },
  v: { fontFamily: F.bodyM, color: C.ink, flexShrink: 1, textAlign: "right" },
  note: { fontFamily: F.body, color: C.muted, fontSize: 13, marginTop: 10 },
});
