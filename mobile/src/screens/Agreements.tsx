import { keepPreviousData, useQuery } from "@tanstack/react-query";
import React, { useMemo, useState } from "react";
import { FlatList, LayoutAnimation, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { api, errMsg } from "../api";
import { useAuth } from "../auth";
import { C, F, R, statusColor } from "../theme";
import { Badge, Empty, ErrorView, Press, Reveal, Scaffold, ScreenHeader, SkeletonList, Stage } from "../ui";

export type Row = {
  id: string; reference_number: string; subcontractor_name: string | null; project_name: string | null; project_code: string | null;
  scope_of_works: string; current_status: string; status_label: string; pending_with: string; is_executed: boolean;
};

const STATUSES = [
  ["", "All"], ["under_internal_review", "Internal review"], ["under_bgcc_revision", "Needs revision"],
  ["draft_forwarded_to_subcontractor", "With subcontractor"], ["under_subcontractor_signature", "Signature"], ["completed", "Completed"],
] as const;
const ROLE_LABEL: Record<string, string> = { admin: "Admin", project_director: "Project Director", accounts: "Accounts", operation_manager: "Operation Manager", gm: "GM" };
const CHAIN = ["Accounts", "Project Director", "Operation Manager", "GM"];

/** Card footer wording: who holds it, without the parenthetical. */
const short = (p: string) =>
  p.includes("ready to forward") ? "Ready to send to subcontractor" : p.includes("revision requested") ? "Revision requested" : p.replace("Pending with ", "With ").replace(/\s*\(.*\)/, "");

/** Where an agreement sits in the Accounts → PD → OM → GM chain, from the archive row alone. */
export function stagesFor(r: Row): Stage[] {
  const s = r.current_status;
  if (s === "under_drafting") return ["todo", "todo", "todo", "todo"];
  if (s === "under_internal_review" || s === "under_bgcc_revision") {
    const i = CHAIN.findIndex((c) => r.pending_with.startsWith(`Pending with ${c}`));
    if (i >= 0) return CHAIN.map((_, k) => (k < i ? "done" : k === i ? "current" : "todo"));
    return r.pending_with.includes("ready to forward") ? ["done", "done", "done", "done"] : ["returned", "returned", "returned", "returned"];
  }
  return ["done", "done", "done", "done"];
}

export default function Agreements({ navigation }: any) {
  const { user } = useAuth();
  const [filter, setFilter] = useState(""); // one chip at a time: "" = All, "mine" = Needs me, else a status
  const mine = filter === "mine";
  const status = mine ? "" : filter;
  const [search, setSearch] = useState("");
  const [project, setProject] = useState("");
  const [sub, setSub] = useState("");
  const [more, setMore] = useState(false);
  const [pulling, setPulling] = useState(false); // spinner only for a user pull, not background polls

  const q = useQuery({
    queryKey: ["agreements", status, search, project, sub],
    refetchInterval: 30000,
    placeholderData: keepPreviousData, // keep the list on screen while a new filter loads
    queryFn: async () =>
      (await api.get<Row[]>("/archive/agreements", {
        params: { status: status || undefined, reference_number: search || undefined, project_name: project || undefined, subcontractor_name: sub || undefined },
      })).data,
  });

  const pull = async () => {
    setPulling(true);
    await q.refetch();
    setPulling(false);
  };

  const me = ROLE_LABEL[user?.role ?? ""];
  const isMine = (r: Row) => r.pending_with.startsWith(`Pending with ${me}`);
  const rows = useMemo(() => (q.data ?? []).filter((r) => !mine || isMine(r)), [q.data, mine, me]); // eslint-disable-line react-hooks/exhaustive-deps
  const mineCount = (q.data ?? []).filter(isMine).length;

  const pick = (fn: () => void) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    fn();
  };

  return (
    <View style={s.wrap}>
      <ScreenHeader title="Agreements" sub={q.data ? `${q.data.length} in the system` : " "}>
        <TextInput style={s.search} placeholder="Search by reference" placeholderTextColor={C.onSteel} value={search} onChangeText={setSearch} autoCapitalize="characters" />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingTop: 10 }}>
          <Press onPress={() => pick(() => setFilter("mine"))} style={[s.chip, mine ? s.chipMine : s.chipMineOff]}>
            <Text style={[s.chipT, { color: mine ? "#fff" : C.hivis }]}>Needs me{mineCount ? `  ${mineCount}` : ""}</Text>
          </Press>
          {STATUSES.map(([v, l]) => (
            <Press key={v} onPress={() => pick(() => setFilter(v))} style={[s.chip, filter === v && s.chipOn]}>
              <Text style={[s.chipT, filter === v && { color: C.steel }]}>{l}</Text>
            </Press>
          ))}
          <Press onPress={() => pick(() => setMore(!more))} style={s.chip}>
            <Text style={s.chipT}>{more ? "Fewer filters" : "More filters"}</Text>
          </Press>
        </ScrollView>
        {more && (
          <View style={{ gap: 8, marginTop: 10 }}>
            <TextInput style={s.search} placeholder="Project name" placeholderTextColor={C.onSteel} value={project} onChangeText={setProject} />
            <TextInput style={s.search} placeholder="Subcontractor name" placeholderTextColor={C.onSteel} value={sub} onChangeText={setSub} />
          </View>
        )}
      </ScreenHeader>

      {q.isLoading ? (
        <SkeletonList />
      ) : q.isError ? (
        <ErrorView msg={errMsg(q.error)} retry={() => q.refetch()} />
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(r) => r.id}
          contentContainerStyle={{ padding: 12, gap: 10, flexGrow: 1 }}
          refreshControl={<RefreshControl refreshing={pulling} onRefresh={pull} tintColor={C.steel} />}
          ListEmptyComponent={mine ? <Empty title="Nothing is waiting on you" hint="New agreements will appear here when it's your turn to review." /> : <Empty title="No agreements match" hint="Try a different search or clear the filters." />}
          renderItem={({ item: r, index }) => (
            <Reveal index={index}>
              <Press style={s.card} onPress={() => navigation.navigate("Detail", { id: r.id })}>
                <View style={[s.stripe, { backgroundColor: isMine(r) ? C.hivis : statusColor(r.current_status) }]} />
                <View style={{ flex: 1, padding: 14 }}>
                  <View style={s.top}>
                    <Text style={s.ref}>{r.reference_number}</Text>
                    {isMine(r) && <Text style={s.yours}>Your turn</Text>}
                  </View>
                  <Text style={s.project}>{r.project_name ?? "—"}</Text>
                  <Text style={s.muted} numberOfLines={1}>{r.subcontractor_name ?? "—"}</Text>
                  <View style={{ marginTop: 12 }}><Scaffold stages={stagesFor(r)} /></View>
                  <View style={s.foot}>
                    <Badge status={r.current_status} label={r.status_label} />
                    <Text style={s.pending} numberOfLines={1}>{short(r.pending_with)}</Text>
                  </View>
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
  wrap: { flex: 1, backgroundColor: C.concrete },
  search: { backgroundColor: C.slate, color: "#fff", borderRadius: R, paddingHorizontal: 14, paddingVertical: 10, fontFamily: F.body, fontSize: 15, marginTop: 4 },
  chip: { borderRadius: R, paddingHorizontal: 13, paddingVertical: 8, backgroundColor: C.slate },
  chipOn: { backgroundColor: "#fff" },
  chipMine: { backgroundColor: C.hivis },
  chipMineOff: { backgroundColor: C.slate, borderWidth: 1, borderColor: C.hivis },
  chipT: { color: C.onSteel, fontFamily: F.bodyB, fontSize: 13 },
  card: { flexDirection: "row", backgroundColor: C.panel, borderRadius: R, borderWidth: 1, borderColor: C.line, overflow: "hidden" },
  stripe: { width: 5 },
  top: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  ref: { fontFamily: F.display, fontSize: 24, color: C.ink, letterSpacing: 0.2 },
  yours: { fontFamily: F.bodyB, fontSize: 12, color: C.hivis },
  project: { fontFamily: F.bodyM, fontSize: 15, color: C.ink, marginTop: 2 },
  muted: { fontFamily: F.body, color: C.muted, marginTop: 1 },
  foot: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 12, gap: 8 },
  pending: { fontFamily: F.body, color: C.muted, fontSize: 12, flexShrink: 1 },
});
