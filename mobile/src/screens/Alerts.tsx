import { useQueryClient } from "@tanstack/react-query";
import React, { useState } from "react";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { cleanTitle } from "../Banner";
import { api, errMsg } from "../api";
import { useNotifications } from "../notifs";
import { C, F, R } from "../theme";
import { Empty, ErrorView, Press, Reveal, ScreenHeader, SkeletonList, timeAgo } from "../ui";

export default function Alerts({ navigation }: any) {
  const qc = useQueryClient();
  const q = useNotifications();
  const [pulling, setPulling] = useState(false);
  const pull = async () => {
    setPulling(true);
    await q.refetch();
    setPulling(false);
  };

  const open = async (n: { id: string; agreement_id: string | null; read: boolean }) => {
    if (!n.read) {
      await api.post(`/notifications/${n.id}/read`).catch(() => {});
      qc.invalidateQueries({ queryKey: ["notifications"] });
    }
    if (n.agreement_id) navigation.navigate("Detail", { id: n.agreement_id });
  };

  return (
    <View style={{ flex: 1, backgroundColor: C.concrete }}>
      <ScreenHeader title="Alerts" sub={q.data ? (q.data.unread ? `${q.data.unread} unread` : "You're all caught up") : " "} />
      {q.isLoading ? (
        <SkeletonList />
      ) : q.isError ? (
        <ErrorView msg={errMsg(q.error)} retry={() => q.refetch()} />
      ) : (
        <FlatList
          data={q.data?.items}
          keyExtractor={(n) => n.id}
          contentContainerStyle={{ padding: 12, gap: 10, flexGrow: 1 }}
          refreshControl={<RefreshControl refreshing={pulling} onRefresh={pull} tintColor={C.steel} />}
          ListEmptyComponent={<Empty title="No alerts yet" hint="You'll be notified here when an agreement needs you." />}
          renderItem={({ item: n, index }) => (
            <Reveal index={index}>
              <Press onPress={() => open(n)} style={s.card}>
                <View style={[s.bar, { backgroundColor: n.read ? "transparent" : C.hivis }]} />
                <View style={{ flex: 1, padding: 14 }}>
                  <View style={s.top}>
                    <Text style={[s.title, n.read && { fontFamily: F.displayM, color: C.muted }]} numberOfLines={2}>{cleanTitle(n.title)}</Text>
                    <Text style={s.time}>{timeAgo(n.created_at)}</Text>
                  </View>
                  <Text style={s.body} numberOfLines={2}>{n.body.replace(/\s+/g, " ")}</Text>
                </View>
              </Press>
            </Reveal>
          )}
        />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  card: { flexDirection: "row", backgroundColor: C.panel, borderRadius: R, borderWidth: 1, borderColor: C.line, overflow: "hidden" },
  bar: { width: 5 },
  top: { flexDirection: "row", justifyContent: "space-between", gap: 10 },
  title: { flex: 1, fontFamily: F.display, fontSize: 19, color: C.ink, lineHeight: 22 },
  time: { fontFamily: F.body, fontSize: 12, color: C.muted, marginTop: 3 },
  body: { fontFamily: F.body, color: C.muted, marginTop: 4 },
});
